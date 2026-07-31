#! /usr/bin/env python3

"""Terminal dialogs used by lssh.

The public functions in this module intentionally keep their established return
values.  The small widget classes are separate so that keyboard behaviour can
be tested without opening a real terminal.
"""

import sys

import urwid


_PALETTE = [
    ("menu", "light gray", "black"),
    ("menu_focus", "black", "light gray"),
    ("footer", "dark gray", "black"),
]
_CANCEL_KEYS = {"q", "esc", "ctrl c"}


class _MenuText(urwid.Text):
    """A selectable text row without the decorations of an urwid.Button."""

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


def _list_box(labels):
    rows = [urwid.AttrMap(_MenuText(str(label)), "menu", "menu_focus") for label in labels]
    walker = urwid.SimpleFocusListWalker(rows)
    return walker, urwid.ListBox(walker)


def _focus_position(walker):
    return walker.focus if walker else None


class _FlatDialog(urwid.WidgetWrap):
    def __init__(self, options, heading):
        self.result = None
        self.walker, list_box = _list_box(options)
        body = urwid.LineBox(list_box, title=str(heading))
        footer = urwid.AttrMap(
            urwid.Text("Enter: auswählen   q/Esc/Ctrl-C: abbrechen"),
            "footer",
        )
        super().__init__(urwid.Frame(body, footer=footer))

    def keypress(self, size, key):
        if key in _CANCEL_KEYS:
            raise urwid.ExitMainLoop()
        if key == "enter":
            self.result = _focus_position(self.walker)
            if self.result is not None:
                raise urwid.ExitMainLoop()
            return None
        return super().keypress(size, key)


class _HierarchicalDialog(urwid.WidgetWrap):
    def __init__(self, options, displaynames, heading_left, heading_right):
        self.result = None
        self._displaynames = displaynames or {}
        self._sorted_options = list(enumerate(options))
        self._sorted_options.sort(key=self._option_sort_key)

        left_labels = [self._display_name(entry[1][0]) for entry in self._sorted_options]
        self.left_walker, left_box = _list_box(left_labels)
        self.right_walker, right_box = _list_box([])

        left = urwid.LineBox(left_box, title=str(heading_left))
        right = urwid.LineBox(right_box, title=str(heading_right))
        self.columns = urwid.Columns(
            [("weight", 1, left), ("weight", 2, right)],
            dividechars=1,
            focus_column=0,
        )
        footer = urwid.AttrMap(
            urwid.Text(
                "Enter/→/Tab: Hosts   ←/Backspace: Kunden   "
                "q/Esc/Ctrl-C: abbrechen"
            ),
            "footer",
        )
        self._selected_left = 0
        self._show_hosts(0)
        super().__init__(urwid.Frame(self.columns, footer=footer))

    def _display_name(self, name):
        return self._displaynames.get(name, name)

    def _option_sort_key(self, option):
        _original_index, (heading, _hosts) = option
        display = str(self._display_name(heading))
        return display.lower(), display, str(heading)

    def _show_hosts(self, sorted_index):
        if sorted_index is None or not self._sorted_options:
            self.right_walker.clear()
            return
        self._selected_left = sorted_index
        hosts = self._sorted_options[sorted_index][1][1]
        self.right_walker[:] = [
            urwid.AttrMap(_MenuText(str(host)), "menu", "menu_focus")
            for host in hosts
        ]
        if self.right_walker:
            self.right_walker.set_focus(0)

    def _navigate_right(self):
        left_index = _focus_position(self.left_walker)
        if left_index is None:
            return
        self._show_hosts(left_index)
        self.columns.focus_position = 1

    def _navigate_left(self):
        self.columns.focus_position = 0

    def _select_host(self):
        right_index = _focus_position(self.right_walker)
        if right_index is None:
            return
        original_left_index = self._sorted_options[self._selected_left][0]
        self.result = original_left_index, right_index
        raise urwid.ExitMainLoop()

    def keypress(self, size, key):
        if key in _CANCEL_KEYS:
            raise urwid.ExitMainLoop()

        if self.columns.focus_position == 0:
            if key in {"enter", "right", "tab"}:
                self._navigate_right()
                return None
            result = super().keypress(size, key)
            left_index = _focus_position(self.left_walker)
            if left_index is not None and left_index != self._selected_left:
                self._show_hosts(left_index)
            return result

        if key in {"left", "backspace"}:
            self._navigate_left()
            return None
        if key == "enter":
            self._select_host()
            return None
        return super().keypress(size, key)


def _interactive_terminal():
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, OSError):
        return False


def _run(dialog):
    loop = urwid.MainLoop(dialog, palette=_PALETTE, handle_mouse=False)
    try:
        loop.run()
    except KeyboardInterrupt:
        return None
    return dialog.result


def flat_option_dialog(options, heading) -> int | None:
    """Let the user choose an item and return its original index."""
    if not options or not _interactive_terminal():
        return None
    return _run(_FlatDialog(options, heading))


def hierarchical_option_dialog(
    options, displaynames, heading_left, heading_right
) -> tuple[int, int] | None:
    """Return ``(customer_index, host_index)`` or ``None`` on cancellation."""
    if not options or not _interactive_terminal():
        return None
    return _run(
        _HierarchicalDialog(options, displaynames, heading_left, heading_right)
    )
