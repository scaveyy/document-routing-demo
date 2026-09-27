import dataclasses
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routing import Message, Rule, RoutingError, load_batch, plan_batch  # noqa: E402


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.messages, self.rules = load_batch()

    def test_sample_batch_has_ready_review_and_skip(self):
        decisions, ledger = plan_batch(self.messages, self.rules)
        self.assertEqual([item.status for item in decisions], ["ready", "review", "skipped"])
        self.assertEqual(decisions[0].destination, "finance/MSG-001-sample-invoice.pdf")
        self.assertEqual(decisions[1].reason, "no_rule")
        self.assertEqual(set(ledger), {"MSG-001"})

    def test_same_message_is_skipped_on_replay(self):
        _, ledger = plan_batch(self.messages[:1], self.rules)
        decisions, new_ledger = plan_batch(self.messages[:1], self.rules, ledger)
        self.assertEqual(decisions[0].status, "skipped")
        self.assertEqual(new_ledger, ledger)

    def test_changed_content_with_same_id_requires_review(self):
        _, ledger = plan_batch(self.messages[:1], self.rules)
        changed = dataclasses.replace(self.messages[0], content="Different invented content")
        decisions, new_ledger = plan_batch([changed], self.rules, ledger)
        self.assertEqual(decisions[0].reason, "id_content_conflict")
        self.assertEqual(new_ledger, ledger)

    def test_ambiguous_rules_require_review(self):
        rules = [*self.rules, Rule("invoice", "archive")]
        decisions, ledger = plan_batch(self.messages[:1], rules)
        self.assertEqual(decisions[0].reason, "ambiguous_rules")
        self.assertEqual(ledger, {})

    def test_unsafe_filename_requires_review(self):
        bad = dataclasses.replace(self.messages[0], attachment_name="../private.pdf")
        decisions, ledger = plan_batch([bad], self.rules)
        self.assertEqual(decisions[0].reason, "invalid_message")
        self.assertEqual(ledger, {})

    def test_wrong_extension_requires_review(self):
        bad = dataclasses.replace(self.messages[0], attachment_name="script.exe")
        decisions, ledger = plan_batch([bad], self.rules)
        self.assertEqual(decisions[0].reason, "invalid_message")
        self.assertEqual(ledger, {})

    def test_destination_path_in_rule_is_rejected(self):
        with self.assertRaisesRegex(RoutingError, "invalid routing rule"):
            plan_batch(self.messages, [Rule("invoice", "../private")])

    def test_invalid_ledger_is_rejected(self):
        with self.assertRaisesRegex(RoutingError, "invalid ledger"):
            plan_batch(self.messages, self.rules, {"MSG-001": "not-a-digest"})
        with self.assertRaisesRegex(RoutingError, "invalid ledger"):
            plan_batch(self.messages, self.rules, [("MSG-001", "a" * 64)])

    def test_existing_ledger_is_not_mutated(self):
        old = {"MSG-999": "a" * 64}
        _, new = plan_batch(self.messages[:1], self.rules, old)
        self.assertEqual(old, {"MSG-999": "a" * 64})
        self.assertIn("MSG-001", new)

    def test_malformed_batch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "batch.json"
            path.write_text(json.dumps({"messages": [{"message_id": "MSG-001"}], "rules": []}))
            with self.assertRaisesRegex(RoutingError, "invalid message"):
                load_batch(path)

    def test_planning_never_creates_a_file(self):
        with tempfile.TemporaryDirectory() as directory:
            before = list(Path(directory).iterdir())
            plan_batch(self.messages, self.rules)
            self.assertEqual(list(Path(directory).iterdir()), before)


if __name__ == "__main__":
    unittest.main()
