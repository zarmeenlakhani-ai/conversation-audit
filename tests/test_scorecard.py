import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from conversation_audit import cli, scorecard, scorepage

# A crisp, structured speaker and a messy, hedging one, each well past the
# 250-word scoring floor.
CRISP = [
    "Two things. First, the launch date moves to Friday. Second, the vendor needs"
    " one more pass on pricing. The ask is simple: I need you to confirm the budget by Tuesday.",
    "Thank you for pulling this together. Great work on the numbers.",
    "Next steps: I'll send the revised plan by Wednesday, and we will review it on Thursday.",
    "For example, if the vendor slips, we launch with the old pricing. That's fair to both sides.",
    "Three options. Option A is a delay. Option B is a smaller launch. Option C is a partner"
    " launch. My recommendation is option B.",
] * 4

MESSY = [
    "Um, so I think, I think we, we should maybe, like, look at the, the thing, right?",
    "No, no, no, no, that's not what I was saying. Sorry, sorry, I think, um, basically,"
    " it's, it's kind of, you know, like a bit of a problem, right? And then we, and then we"
    " kind of have to see, and it's, like, maybe hopefully going to work, I guess, right?",
    "Sorry. Let me know if you want me to help on anything. Give me a little time, I'll think"
    " about it, I'm not sure, I don't know, maybe we can talk about it later.",
    "Uh, so, um, actually, like, the the the dashboard, right? I feel like it's, it's probably"
    " fine, I think, but, um, I guess, like, it could be, you know, a little bit better, right?",
] * 5


class ScoreTests(unittest.TestCase):
    def test_levels_and_interpolation(self):
        self.assertEqual(scorecard.level(1.0), "Distracting")
        self.assertEqual(scorecard.level(2.5), "Solid")
        self.assertEqual(scorecard.level(4.6), "Brilliant")
        anchors = [(0.0, 1.0), (2.0, 3.0)]
        self.assertAlmostEqual(scorecard.interpolate(1.0, anchors), 2.0)
        self.assertEqual(scorecard.interpolate(-5, anchors), 1.0)
        self.assertEqual(scorecard.interpolate(99, anchors), 3.0)

    def test_crisp_beats_messy_everywhere_it_matters(self):
        crisp = scorecard.build(CRISP, "crisp")
        messy = scorecard.build(MESSY, "messy")
        for key in ("structure", "points", "composure", "fluency", "hedging", "confidence",
                    "tone", "impact"):
            self.assertGreater(crisp.dimension(key).score, messy.dimension(key).score, key)
        self.assertGreaterEqual(crisp.overall, 4.0)
        self.assertLessEqual(messy.overall, 2.5)

    def test_hedging_and_confidence_count_their_own_rows(self):
        card = scorecard.build(MESSY, "messy")
        h = card.dimension("hedging").detail
        self.assertGreater(h["i_think"] + h["maybe"] + h["other_hedges"], 0)
        c = card.dimension("confidence").detail
        self.assertGreater(c["right_tags"] + c["other_tags"], 0)
        self.assertGreater(c["apologies"], 0)
        self.assertGreater(c["deferrals"], 0)

    def test_points_counts_numbered_delivery(self):
        d = scorecard.build(CRISP, "crisp").dimension("points").detail
        self.assertGreaterEqual(d["announced"] + d["ordinals"] + d["options"], 4 * 6)

    def test_each_phrase_is_counted_once(self):
        cases = {
            "I'm sorry, sorry, sorry. While we're here.": {"apologies": 1},
            "No, no, no, no, that's not what I was saying.": {"no_bursts": 1, "sharp": 1},
            "Okay, let me know if you want me to help on anything.": {"open_offers": 1},
            "I need you to push AWS by Friday.": {"asks": 1, "dates": 1},
            "Next steps for you guys is that you will check.": {"closers": 1},
            "Wait, wait, wait, let me take a screenshot.": {"stutters": 1},
        }
        for text, expected in cases.items():
            counts = {k: v for k, v in scorecard.tally(text).items() if v}
            self.assertEqual(counts, expected, text)

    def test_rows_never_share_words(self):
        spans = sorted((s, e) for _, s, e in scorecard.claims("\n".join(MESSY + CRISP)))
        self.assertGreater(len(spans), 20)
        for (_, end), (start, _) in zip(spans, spans[1:]):
            self.assertLessEqual(end, start)

    def test_listening_turns_are_set_aside(self):
        card = scorecard.build(CRISP + ["Mm-hmm.", "Yeah, okay.", "Perfect."], "x")
        self.assertEqual(card.listening_turns, 3)
        self.assertEqual(card.words, scorecard.build(CRISP, "x").words)

    def test_short_rooms_are_not_scored(self):
        card = scorecard.build(["We ship on Friday. I'll confirm by noon."], "tiny")
        self.assertIsNone(card.overall)
        self.assertIn("Too little speech", scorecard.render(card))

    def test_tone_labels(self):
        self.assertEqual(scorecard.tone_label(6.0, 0.5), "Warm and steady")
        self.assertEqual(scorecard.tone_label(6.0, 3.0), "Warm, sharp in disagreement")
        self.assertEqual(scorecard.tone_label(1.0, 0.0), "Neutral, businesslike")
        self.assertEqual(scorecard.tone_label(1.0, 3.0), "Cool, sharp in disagreement")

    def test_name_misheard_as_profanity_is_not_edge(self):
        # transcribers can turn a colleague's name into an expletive; it must not read as tone
        card = scorecard.build(["I'll confirm with fucker tomorrow and send the plan."] * 40, "x")
        self.assertEqual(card.dimension("tone").detail["sharp"], 0)

    def test_render_lists_every_dimension(self):
        out = scorecard.render(scorecard.build(CRISP, "crisp"))
        for _, name, question in scorecard.DIMENSIONS:
            self.assertIn(name, out)
            self.assertIn(question, out)


class PageTests(unittest.TestCase):
    def test_page_has_questions_scoreboard_rooms_and_moves(self):
        spec = scorepage.week_spec(
            [("Crisp room", "Mon", CRISP), ("Messy room", "Tue", MESSY)],
            title="Week 1 Speaker Scorecard", eyebrow="Speaker scorecard · Week 1",
            week_label="W1",
            notes={"verdict": "Solid week.",
                   "evidence": {"composure": {"quote": "No, no, no, no.", "room": "Messy room · Tue"}}},
        )
        page = scorepage.render(spec)
        self.assertTrue(page.startswith("<title>Week 1 Speaker Scorecard</title>"))
        for text in ("Am I messy?", "Am I structured?", "Am I using bullet points?",
                     "How is my tone?", "How confident do I sound?", "Room by room",
                     "Three moves for next week", "No, no, no, no.", "Brilliant looks like"):
            self.assertIn(text, page)
        self.assertEqual(len(spec["moves"]), 3)

    def test_thresholds_invert_the_anchors(self):
        for key in scorecard.ANCHORS:
            for target in (1.5, 2.5, 3.5, 4.5):
                value = scorepage.threshold_for(key, target)
                self.assertAlmostEqual(
                    scorecard.interpolate(value, scorecard.ANCHORS[key]), target, places=6)


class CliTests(unittest.TestCase):
    def test_scorecard_command_writes_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "meeting.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(CRISP))
            out_html = os.path.join(tmp, "card.html")
            buf = StringIO()
            with redirect_stdout(buf):
                code = cli.main(["scorecard", path, "--html", out_html, "--label", "W1"])
            self.assertEqual(code, 0)
            self.assertIn("SPEAKER SCORECARD", buf.getvalue())
            with open(out_html, encoding="utf-8") as fh:
                self.assertIn("The scoreboard", fh.read())

    def test_scorecard_command_rejects_unknown_speaker(self):
        meeting = os.path.join(os.path.dirname(__file__), "..", "samples",
                               "meeting_labeled.txt")
        err = StringIO()
        with redirect_stdout(StringIO()), redirect_stderr(err):
            code = cli.main(["scorecard", meeting, "--speaker", "Nobody"])
        self.assertEqual(code, 2)
        self.assertIn("no utterances match speaker 'Nobody'", err.getvalue())

    def test_analyze_json_includes_scorecard(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "meeting.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(CRISP))
            buf = StringIO()
            with redirect_stdout(buf):
                cli.main(["analyze", path, "--scorecard", "--json", "--no-store"])
            data = json.loads(buf.getvalue())
            self.assertIn("scorecard", data)
            self.assertEqual(len(data["scorecard"]["dimensions"]), len(scorecard.DIMENSIONS))


if __name__ == "__main__":
    unittest.main()
