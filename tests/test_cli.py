import contextlib
import io
import json
import os
import tempfile
import unittest

from conversation_audit import cli

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples",
                      "standup_dictation.txt")


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["CONVERSATION_AUDIT_HOME"] = self._tmp.name

    def tearDown(self):
        os.environ.pop("CONVERSATION_AUDIT_HOME", None)
        self._tmp.cleanup()

    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(argv)
        return code, out.getvalue()

    def test_json_output(self):
        code, out = self._run([SAMPLE, "--json", "--no-store"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertGreater(data["words"], 100)
        self.assertIn("overall", data["scores"])
        self.assertGreaterEqual(data["filler_total"], 10)

    def test_report_output(self):
        code, out = self._run([SAMPLE, "--no-store", "--no-color"])
        self.assertEqual(code, 0)
        self.assertIn("CONVERSATION AUDIT", out)
        self.assertIn("FLUENCY", out)
        self.assertIn("Biggest lever", out)

    def test_speaker_filter(self):
        meeting = os.path.join(os.path.dirname(SAMPLE), "meeting_labeled.txt")
        code, out = self._run(
            [meeting, "--speaker", "jordan", "--json", "--no-store"]
        )
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("Jordan Lee", data["source"])

    def test_speaker_flag_on_plain_dictation_audits_all(self):
        # a solo dictation has no labels; --speaker must not empty it
        code, out = self._run([SAMPLE, "--speaker", "zarmeen", "--json",
                               "--no-store"])
        self.assertEqual(code, 0)
        self.assertGreater(json.loads(out)["words"], 100)

    def test_unknown_speaker_errors(self):
        meeting = os.path.join(os.path.dirname(SAMPLE), "meeting_labeled.txt")
        code, _ = self._run([meeting, "--speaker", "nobody", "--no-store"])
        self.assertEqual(code, 2)

    def test_history_and_trends(self):
        code, _ = self._run([SAMPLE, "--no-color"])
        self.assertEqual(code, 0)
        code, out = self._run(["trends"])
        self.assertEqual(code, 0)
        self.assertIn("clarity", out)
        self.assertIn("standup_dictation.txt", out)

    def test_trends_empty(self):
        code, out = self._run(["trends"])
        self.assertEqual(code, 0)
        self.assertIn("no audits recorded yet", out)

    def test_missing_file(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, _ = self._run(["does-not-exist.txt", "--no-store"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
