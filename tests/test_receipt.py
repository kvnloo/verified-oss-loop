#!/usr/bin/env python3
"""Revision-bound receipt contract, including the onboarded CLI copy."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else ROOT / 'scripts/check-receipt.py'
spec = importlib.util.spec_from_file_location('receipt', SCRIPT)
receipt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receipt)
BASE = 'a' * 40
HEAD = 'b' * 40


def body(base=BASE, head=HEAD):
    return f'''issue: 14
base_revision: {base}
head_revision: {head}
tests:
  red: python3 tests/test_receipt.py (expected failure)
  green: python3 tests/test_receipt.py (passed)
'''


class ReceiptContract(unittest.TestCase):
    def assertRejected(self, text, head=HEAD, reason=None):
        errors = receipt.check(text, head)
        self.assertTrue(errors, 'receipt must fail closed')
        if reason:
            self.assertIn(reason, '\n'.join(errors))

    def test_complete_exact_head(self):
        self.assertEqual(receipt.check(body(), HEAD), [])

    def test_completeness_without_expected_head(self):
        self.assertEqual(receipt.check(body()), [])

    def test_case_and_outer_whitespace_are_normalized(self):
        self.assertEqual(receipt.check(body(BASE.upper(), HEAD.upper()), f' {HEAD} '), [])

    def test_short_receipt_head_is_not_exact(self):
        for length in (1, 7, 39):
            with self.subTest(length=length):
                self.assertRejected(body(head=HEAD[:length]))

    def test_short_expected_head_cannot_weaken_binding(self):
        for length in (1, 7, 39):
            with self.subTest(length=length):
                self.assertRejected(body(), HEAD[:length], 'expected head')

    def test_empty_expected_head_is_not_omitted(self):
        for expected in ('', ' ', '\n'):
            with self.subTest(expected=expected):
                self.assertRejected(body(), expected, 'expected head')

    def test_base_must_also_identify_full_revision(self):
        self.assertRejected(body(base=BASE[:7]), reason='base_revision')

    def test_shared_prefix_different_revision(self):
        self.assertRejected(body(head=HEAD[:39] + 'c'), reason='does not match')

    def test_invalid_hash_characters_and_lengths(self):
        for value in ('z' * 40, HEAD + '0', HEAD + 'suffix', 'null'):
            with self.subTest(value=value):
                self.assertRejected(body(head=value))
                self.assertRejected(body(), value)

    def test_standalone_completeness_rejects_short_revisions(self):
        self.assertRejected(body(head=HEAD[:7]), None)
        self.assertRejected(body(base=BASE[:7]), None)

    def test_duplicate_revision_keys_do_not_use_last_value(self):
        self.assertRejected(body(head='c' * 40) + f'head_revision: {HEAD}\n', reason='duplicate')

    def test_identical_duplicate_revision_is_still_ambiguous(self):
        self.assertRejected(body() + f'head_revision: {HEAD}\n', reason='duplicate')

    def test_duplicate_tests_mapping_is_rejected(self):
        self.assertRejected(body() + 'tests:\n  red: other\n  green: other\n', reason='duplicate')

    def test_duplicate_test_evidence_is_rejected(self):
        self.assertRejected(body() + '  green: replacement\n', reason='duplicate')

    def test_two_receipts_do_not_pick_most_convenient_one(self):
        for second in (body(), body(head='c' * 40), 'issue: 99\n'):
            with self.subTest(second=second):
                text = f'```yaml\n{body()}```\n```yaml\n{second}```'
                self.assertRejected(text, reason='multiple evidence')

    def test_unrelated_yaml_is_not_a_second_receipt(self):
        text = f'```yaml\noptions:\n  value: x\n```\n```yaml\n{body()}```'
        self.assertEqual(receipt.check(text, HEAD), [])

    def test_missing_receipt_is_rejected(self):
        self.assertRejected('No evidence yet', reason='no evidence')

    def test_cli_exit_code_and_diagnostic(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--head', HEAD],
                                input=body(head=HEAD[:7]), text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('head_revision', result.stdout)
        self.assertNotIn('Traceback', result.stderr)

    def test_cli_duplicate_does_not_raise_traceback(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--head', HEAD],
                                input=body() + f'head_revision: {HEAD}\n', text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('duplicate', result.stdout)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
