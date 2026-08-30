import unittest

from conversation_audit.metrics import analyze


def total(counter_dict, key):
    return sum(counter_dict[key].values())


class FluencyTests(unittest.TestCase):
    def test_hesitations(self):
        a = analyze("Um, so, uh, this is, um, hard to say. Mm-hmm, exactly.")
        self.assertEqual(total(a.fluency, "hesitations"), 4)

    def test_crutch_words(self):
        a = analyze("Basically it works. Basically, it is actually quite fine.")
        counts = a.fluency["crutch words"]
        self.assertEqual(counts["basically"], 2)
        self.assertEqual(counts["actually"], 1)

    def test_tag_questions(self):
        a = analyze("It works, right? We ship today, okay? Fine, you know?")
        self.assertEqual(total(a.fluency, "tag questions"), 3)

    def test_you_know_without_question_is_phrase_filler(self):
        a = analyze("It works, you know, most of the time.")
        self.assertEqual(total(a.fluency, "phrase fillers"), 1)
        self.assertEqual(total(a.fluency, "tag questions"), 0)

    def test_like_filler_needs_comma(self):
        a = analyze("It's, like, hard. He looks like his dad.")
        self.assertEqual(total(a.fluency, "filler 'like'"), 1)

    def test_verb_like_not_double_counted(self):
        a = analyze("I feel like, honestly, we should wait for the vendor.")
        self.assertEqual(total(a.fluency, "filler 'like'"), 0)
        self.assertEqual(a.fluency["hedges"]["i feel like"], 1)

    def test_hedges(self):
        a = analyze("I think we should wait. I feel like maybe it's fine.")
        self.assertEqual(total(a.fluency, "hedges"), 3)

    def test_just_is_counted_but_unscored(self):
        clean = analyze("We ship the release on Friday at noon for everyone.")
        justy = analyze("We just ship the just release just on Friday for everyone.")
        self.assertEqual(justy.just_count, 3)
        self.assertEqual(justy.filler_total, clean.filler_total)


class CoherenceTests(unittest.TestCase):
    def test_stutters(self):
        a = analyze("I, I switched the, the microphone over there.")
        self.assertEqual(a.repairs["stutters"], 2)

    def test_phrase_restart(self):
        a = analyze("I want to have, I want to improve my speaking.")
        self.assertEqual(a.repairs["phrase restarts"], 1)

    def test_ellipsis_false_start(self):
        a = analyze("It basically... we didn't plan this through at all.")
        self.assertEqual(a.repairs["false starts"], 1)

    def test_dash_cutoff_false_start(self):
        a = analyze("Let me just— I'm just needing coffee right now.")
        self.assertEqual(a.repairs["false starts"], 1)

    def test_self_correction(self):
        a = analyze("Oh, it's eloquence. That is the right word for it.")
        self.assertEqual(a.repairs["self-corrections"], 1)

    def test_clean_text_has_no_repairs(self):
        a = analyze("We tested the release. Every check passed. We ship at noon.")
        self.assertEqual(a.repair_total, 0)


class ConcisionTests(unittest.TestCase):
    def test_long_sentence_is_run_on(self):
        words = " ".join(f"word{i}" for i in range(40))
        a = analyze(words + ".")
        self.assertEqual(a.run_ons, 1)

    def test_conjunction_chain_is_run_on(self):
        a = analyze(
            "We built the page and we tested the flow and we fixed the fonts "
            "so we can ship the launch tomorrow morning."
        )
        self.assertEqual(a.run_ons, 1)

    def test_short_clear_sentence_is_not_run_on(self):
        a = analyze("We built the page. We tested the flow. We ship tomorrow.")
        self.assertEqual(a.run_ons, 0)

    def test_fragments(self):
        a = analyze("Yeah. Okay, cool. This sentence here has plenty of words in it.")
        self.assertEqual(a.fragments, 2)


class StructureTests(unittest.TestCase):
    FILLER = (
        "The dashboard shows numbers for last month and the newsletter draft "
        "needs review before Thursday. The vendor sent two mockups and the "
        "team liked the second one better. The office move is on track. "
    )

    def test_bluf_detected(self):
        a = analyze("I need a decision on the launch date. " + self.FILLER * 2)
        self.assertTrue(a.structure["bluf"])
        self.assertFalse(a.structure["buried_lead"])

    def test_buried_lead_detected(self):
        a = analyze(self.FILLER * 3 + " So my ask is a decision on the date.")
        self.assertTrue(a.structure["buried_lead"])
        self.assertFalse(a.structure["bluf"])

    def test_short_text_not_judged(self):
        a = analyze("Ship it tomorrow, please.")
        self.assertFalse(a.structure["judged"])
        self.assertIsNone(a.scores["structure"])


class ScoreTests(unittest.TestCase):
    def test_messy_scores_below_clean(self):
        clean = analyze(
            "I want to lock the launch date by Friday. The staging link works. "
            "The pricing table still breaks on mobile, so the vendor needs one "
            "more pass. Can you ping them today for a timeline?"
        )
        messy = analyze(
            "Okay so, um, basically the staging thing is, like, fine, right? "
            "And the pricing table is, um, kind of broken and the fonts are "
            "off and the CTA is old and, uh, I feel like maybe... what I was, "
            "what I was trying to say is the vendor needs, um, another pass, "
            "you know?"
        )
        self.assertGreater(clean.scores["overall"], messy.scores["overall"])
        self.assertGreater(clean.scores["fluency"], messy.scores["fluency"])

    def test_scores_bounded(self):
        a = analyze("Um, uh, um, uh, um, uh, um, uh, basically, right?")
        for key, value in a.scores.items():
            if value is not None:
                self.assertGreaterEqual(value, 0, key)
                self.assertLessEqual(value, 100, key)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            analyze("...")


if __name__ == "__main__":
    unittest.main()
