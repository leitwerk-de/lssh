import unittest
from unittest import mock

import urwid

from lssh import tui_dialog


SIZE = (100, 20)


class FlatDialogTests(unittest.TestCase):
    def test_enter_returns_original_index(self):
        dialog = tui_dialog._FlatDialog(["first", "second", "third"], "Hosts")
        dialog.keypress(SIZE, "down")
        with self.assertRaises(urwid.ExitMainLoop):
            dialog.keypress(SIZE, "enter")
        self.assertEqual(dialog.result, 1)

    def test_cancel_keys_return_none(self):
        for key in ("q", "esc", "ctrl c"):
            with self.subTest(key=key):
                dialog = tui_dialog._FlatDialog(["host"], "Hosts")
                with self.assertRaises(urwid.ExitMainLoop):
                    dialog.keypress(SIZE, key)
                self.assertIsNone(dialog.result)

    def test_empty_list_returns_none_without_opening_terminal(self):
        with mock.patch.object(tui_dialog, "_run") as run:
            self.assertIsNone(tui_dialog.flat_option_dialog([], "Hosts"))
        run.assert_not_called()

    def test_non_interactive_terminal_returns_none(self):
        with (
            mock.patch.object(tui_dialog, "_interactive_terminal", return_value=False),
            mock.patch.object(tui_dialog, "_run") as run,
        ):
            self.assertIsNone(tui_dialog.flat_option_dialog(["host"], "Hosts"))
        run.assert_not_called()


class HierarchicalDialogTests(unittest.TestCase):
    OPTIONS = [
        ("z-customer", ["z-host"]),
        ("a-customer", ["a-host-1", "a-host-2"]),
    ]
    DISPLAYNAMES = {
        "z-customer": "Zulu",
        "a-customer": "Alpha",
    }

    def make_dialog(self):
        return tui_dialog._HierarchicalDialog(
            self.OPTIONS, self.DISPLAYNAMES, "Customers", "Hosts"
        )

    def test_sorted_customer_maps_back_to_original_indices(self):
        dialog = self.make_dialog()
        self.assertEqual(dialog._sorted_options[0][0], 1)
        dialog.keypress(SIZE, "enter")
        dialog.keypress(SIZE, "down")
        with self.assertRaises(urwid.ExitMainLoop):
            dialog.keypress(SIZE, "enter")
        self.assertEqual(dialog.result, (1, 1))

    def test_missing_display_name_uses_internal_name(self):
        dialog = tui_dialog._HierarchicalDialog(
            [("Zulu", ["z"]), ("Alpha", ["a"])],
            {},
            "Customers",
            "Hosts",
        )
        self.assertEqual(dialog._sorted_options[0][1][0], "Alpha")

    def test_all_navigation_keys_switch_to_host_column(self):
        for key in ("enter", "right", "tab"):
            with self.subTest(key=key):
                dialog = self.make_dialog()
                dialog.keypress(SIZE, key)
                self.assertEqual(dialog.columns.focus_position, 1)

    def test_left_and_backspace_return_to_customer_column(self):
        for key in ("left", "backspace"):
            with self.subTest(key=key):
                dialog = self.make_dialog()
                dialog.keypress(SIZE, "right")
                dialog.keypress(SIZE, key)
                self.assertEqual(dialog.columns.focus_position, 0)

    def test_moving_customer_updates_host_list(self):
        dialog = self.make_dialog()
        self.assertEqual(len(dialog.right_walker), 2)
        dialog.keypress(SIZE, "down")
        self.assertEqual(len(dialog.right_walker), 1)
        row = dialog.right_walker[0].original_widget
        self.assertEqual(row.text, "z-host")

    def test_cancel_keys_work_in_both_columns(self):
        for right_column in (False, True):
            for key in ("q", "esc", "ctrl c"):
                with self.subTest(right_column=right_column, key=key):
                    dialog = self.make_dialog()
                    if right_column:
                        dialog.keypress(SIZE, "right")
                    with self.assertRaises(urwid.ExitMainLoop):
                        dialog.keypress(SIZE, key)
                    self.assertIsNone(dialog.result)

    def test_unicode_long_lists_and_single_host_render(self):
        options = [("kunde-ä", ["höst-唯一"])] + [
            ("kunde-%03d" % index, ["host-%03d" % index])
            for index in range(120)
        ]
        dialog = tui_dialog._HierarchicalDialog(options, {}, "Kunden", "Hosts")
        canvas = dialog.render((120, 12), focus=True)
        self.assertEqual(canvas.cols(), 120)
        self.assertEqual(len(dialog.left_walker), 121)

    def test_customer_with_one_host_can_be_selected(self):
        dialog = tui_dialog._HierarchicalDialog(
            [("customer", ["only-host"])], {}, "Customers", "Hosts"
        )
        dialog.keypress(SIZE, "right")
        with self.assertRaises(urwid.ExitMainLoop):
            dialog.keypress(SIZE, "enter")
        self.assertEqual(dialog.result, (0, 0))

    def test_empty_hierarchy_returns_none_without_opening_terminal(self):
        with mock.patch.object(tui_dialog, "_run") as run:
            result = tui_dialog.hierarchical_option_dialog([], {}, "A", "B")
        self.assertIsNone(result)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
