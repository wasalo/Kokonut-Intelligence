"""Tests for the owner-approved F001 activity-type mapping policy."""

import unittest

from scripts.baserow_reconciliation_dry_run import (
    DryRunError,
    map_f001_activity_selection,
)


class F001ActivityTypeMappingTests(unittest.TestCase):
    def test_new_option_uses_exact_label_and_preserves_selection_order(self):
        primary, preserved = map_f001_activity_selection(
            [7102, 7101],
            {"7102": "  Synthetic label  ", "7101": "Secondary label"},
            approved_targets={},
        )

        self.assertEqual(primary, "  Synthetic label  ")
        self.assertEqual(
            preserved,
            [
                {"option_id": 7102, "label": "  Synthetic label  "},
                {"option_id": 7101, "label": "Secondary label"},
            ],
        )

    def test_existing_approved_target_remains_authoritative(self):
        primary, preserved = map_f001_activity_selection(
            [7101, 7102],
            {"7101": "Source label", "7102": "Other source label"},
            approved_targets={"7101": "irrigation"},
        )

        self.assertEqual(primary, "irrigation")
        self.assertEqual(preserved[0]["label"], "Source label")

    def test_unknown_selected_option_is_rejected(self):
        with self.assertRaisesRegex(DryRunError, "unknown activity option"):
            map_f001_activity_selection([9999], {"7101": "Known"}, approved_targets={})

    def test_malformed_and_empty_option_values_are_rejected(self):
        with self.assertRaisesRegex(DryRunError, "malformed activity selection"):
            map_f001_activity_selection([True], {}, approved_targets={})
        with self.assertRaisesRegex(DryRunError, "empty activity selection"):
            map_f001_activity_selection([], {}, approved_targets={})

    def test_invalid_canonical_label_is_rejected(self):
        with self.assertRaisesRegex(DryRunError, "invalid activity type label"):
            map_f001_activity_selection(
                [7101], {"7101": "x" * 101}, approved_targets={}
            )


if __name__ == "__main__":
    unittest.main()
