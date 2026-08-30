import os
import unittest

from conversation_audit.brief import pointers, render_brief
from conversation_audit.metrics import analyze

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples",
                      "standup_dictation.txt")


class BriefTests(unittest.TestCase):
    def _messy(self):
        with open(SAMPLE, encoding="utf-8") as fh:
            return analyze(fh.read(), source=SAMPLE)

    def test_three_pointers_by_default(self):
        points = pointers(self._messy())
        self.assertEqual(len(points), 3)
        joined = "\n".join(points)
        self.assertIn("fillers per 100 words", joined)
        self.assertIn("broken thoughts", joined)

    def test_higher_limit_yields_more(self):
        a = self._messy()
        self.assertGreater(len(pointers(a, 10)), len(pointers(a, 3)))

    def test_every_pointer_has_a_recommendation(self):
        for p in pointers(self._messy(), 10):
            self.assertIn("->", p)

    def test_buried_lead_pointer(self):
        joined = "\n".join(pointers(self._messy(), 10))
        self.assertIn("ask landed", joined)

    def test_crisp_text_has_no_pointers(self):
        a = analyze(
            "I want a decision on the launch date by noon. The staging link "
            "works and testing passed. The vendor needs one more pass on the "
            "pricing table. Can you ping them today?"
        )
        self.assertEqual(pointers(a), [])
        self.assertIn("crisp", render_brief(a))

    def test_render_shape(self):
        out = render_brief(self._messy())
        lines = out.splitlines()
        self.assertIn("Clarity", lines[0])
        self.assertIn("standup_dictation.txt", lines[0])
        self.assertTrue(lines[1].startswith("1. "))
        self.assertTrue(lines[-1].startswith("Drill: "))

    def test_render_respects_speaker_suffix(self):
        a = analyze("Um, um, um, we should, uh, basically ship it, right? "
                    * 6, source="/long/path/meeting.txt [Jordan Lee]")
        self.assertTrue(render_brief(a).startswith("meeting.txt [Jordan Lee]"))


if __name__ == "__main__":
    unittest.main()
