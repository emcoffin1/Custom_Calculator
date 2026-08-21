import unittest
from features import HistoryEntry, add_history, is_favorite, normalize_state, normalized_precision, search_items, toggle_favorite


class FeatureTests(unittest.TestCase):
    def test_history_is_newest_first_deduplicated_and_bounded(self):
        state = {}
        add_history(state, HistoryEntry("math", "1+1", "2", {"expression": "1+1"}), limit=2)
        add_history(state, HistoryEntry("math", "1+1", "2", {"expression": "1+1"}), limit=2)
        self.assertEqual(len(state["history"]), 1)
        add_history(state, HistoryEntry("math", "2+2", "4", {"expression": "2+2"}), limit=2)
        add_history(state, HistoryEntry("math", "3+3", "6", {"expression": "3+3"}), limit=2)
        self.assertEqual([item["result"] for item in state["history"]], ["6", "4"])

    def test_favorite_toggle(self):
        state = {}
        self.assertTrue(toggle_favorite(state, "Electrical|Ohm's law"))
        self.assertTrue(is_favorite(state, "Electrical|Ohm's law"))
        self.assertFalse(toggle_favorite(state, "Electrical|Ohm's law"))

    def test_search_ranks_favorite_and_prefix(self):
        items = [
            {"key": "b", "label": "Voltage divider", "detail": "Electrical"},
            {"key": "a", "label": "DC voltage", "detail": "Electrical"},
        ]
        self.assertEqual(search_items(items, "voltage", {"b"})[0]["key"], "b")

    def test_precision_is_bounded(self):
        self.assertEqual(normalized_precision(1), 3)
        self.assertEqual(normalized_precision(99), 10)
        self.assertEqual(normalized_precision("bad"), 6)

    def test_malformed_nested_state_is_repaired(self):
        state=normalize_state({"history":{},"favorites":"bad","variables":[],"engineering_values":{"ok":{},"bad":[]}})
        self.assertEqual(state["history"],[]);self.assertEqual(state["favorites"],[])
        self.assertEqual(state["variables"],{});self.assertEqual(state["engineering_values"],{"ok":{}})


if __name__ == "__main__": unittest.main()
