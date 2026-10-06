"""Tests for QC's verdict parsing and vaccine extraction.

QC holds the final sign-off, so a parser that mistakes "NOT APPROVED" for
approval is a correctness bug, not a cosmetic one.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lc.roles.qa import QAResult
from lc.roles.qc import QualityControl
from lc.roles.pm import Ticket


def make_ticket():
    return Ticket(
        title="t",
        task="t",
        stack="python",
        missing_items=[],
        acceptance_criteria=["works"],
        definition_of_done="done",
        suggested_files=["calc.py"],
    )


def qa(success=True):
    return QAResult(
        success=success,
        command="pytest",
        output="out",
        exit_code=0 if success else 1,
        attempt=1,
        error_summary="" if success else "boom",
    )


class TestVerdictParsing(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        # Point QC at a workspace this test owns. Passing the global
        # tempfile.gettempdir() here hands QC the entire %TEMP% as its
        # sandbox -- and, because other tests aim their escape targets at the
        # shared temp root, makes this test's behaviour depend on leftovers
        # from unrelated runs.
        ws = Path(self.temp_dir.name) / "workspace"
        ws.mkdir()
        self.qc = QualityControl(
            llm=None,
            memory=mock.MagicMock(),
            console=mock.MagicMock(),
            workspace=str(ws),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def verdict(self, text):
        return self.qc._parse_verdict(text)

    def test_plain_approved(self):
        self.assertTrue(self.verdict("[VERDICT]\nAPPROVED"))

    def test_plain_rejected(self):
        self.assertFalse(self.verdict("[VERDICT]\nREJECTED"))

    def test_not_approved_prose_is_not_approval(self):
        # The regression: the old substring check read this as approved.
        self.assertFalse(self.verdict(
            "This is NOT APPROVED, the diff is bloated.\n[VERDICT]\nREJECTED"
        ))

    def test_verdict_block_wins_over_later_prose(self):
        # APPROVED in the verdict, REJECTED mentioned in prose later.
        self.assertTrue(self.verdict(
            "[VERDICT]\nAPPROVED\n[FEEDBACK]\nGood. (Not rejected.)\n"
        ))

    def test_rejected_in_verdict_block_wins(self):
        self.assertFalse(self.verdict(
            "[VERDICT]\nREJECTED -- this is not APPROVED quality\n[FEEDBACK]\nrefactor"
        ))

    def test_verdict_line_with_trailing_punctuation(self):
        self.assertTrue(self.verdict("**APPROVED.**"))
        self.assertFalse(self.verdict("REJECTED."))

    def test_bare_lines_without_section(self):
        self.assertTrue(self.verdict("APPROVED\nAll good."))
        self.assertFalse(self.verdict("REJECTED\nNeeds work."))

    def test_ambiguous_falls_back_conservatively(self):
        # Both words present with no clear section -> reject, never sign off.
        self.assertFalse(self.verdict("It could be APPROVED but might be REJECTED."))


class TestReviewSprint(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory = mock.MagicMock()
        self.memory.record_vaccine.return_value = 7
        self.qc = QualityControl(
            llm=None,
            memory=self.memory,
            console=mock.MagicMock(),
            workspace=self.temp_dir.name,
        )
        self.ticket = make_ticket()
        self.dev_files = [{"file": "calc.py", "diff_lines": 10}]

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_review(self, review_text, *, qa_success=True, past_failures=()):
        self.qc.generate = mock.MagicMock(return_value=review_text)
        return self.qc.review_sprint(
            ticket=self.ticket,
            dev_files=self.dev_files,
            qa_result=qa(qa_success),
            past_failures=list(past_failures),
        )

    def test_approved_review_passes(self):
        report = self.run_review("[VERDICT]\nAPPROVED\n[DIFF_SCORE]\nExcellent\n[FEEDBACK]\nClean.")
        self.assertTrue(report.approved)
        self.assertEqual(report.diff_score, "Excellent")

    def test_failed_qa_always_rejects(self):
        # Even an APPROVED verdict cannot override a failed test run.
        report = self.run_review("[VERDICT]\nAPPROVED", qa_success=False)
        self.assertFalse(report.approved)

    def test_not_approved_prose_rejected(self):
        report = self.run_review(
            "[VERDICT]\nREJECTED\n[FEEDBACK]\nThis is NOT APPROVED yet."
        )
        self.assertFalse(report.approved)

    def test_vaccine_created_after_a_fixed_failure(self):
        report = self.run_review(
            "[VERDICT]\nAPPROVED",
            past_failures=[qa(success=False)],
        )
        self.assertTrue(report.vaccine_created)
        self.assertEqual(self.memory.record_vaccine.call_count, 1)

    def test_no_vaccine_when_first_attempt_passed(self):
        report = self.run_review("[VERDICT]\nAPPROVED", past_failures=[])
        self.assertIsNone(report.vaccine_created)
        self.memory.record_vaccine.assert_not_called()

    def test_vaccine_parser_reads_sections(self):
        self.qc.generate = mock.MagicMock(side_effect=[
            "[VERDICT]\nAPPROVED",  # the review
            "[SYMPTOM]\nNameError: x is not defined\n\n[ROOT_CAUSE]\nTypo\n\n"
            "[PREVENTION_RULE]\nRun the file before claiming done",
        ])
        report = self.qc.review_sprint(
            ticket=self.ticket,
            dev_files=self.dev_files,
            qa_result=qa(True),
            past_failures=[qa(False)],
        )
        kwargs = self.memory.record_vaccine.call_args.kwargs
        self.assertEqual(kwargs["symptom"], "NameError: x is not defined")
        self.assertEqual(kwargs["root_cause"], "Typo")
        self.assertEqual(kwargs["prevention_rule"], "Run the file before claiming done")
        self.assertEqual(kwargs["stack"], "python")


if __name__ == "__main__":
    unittest.main()