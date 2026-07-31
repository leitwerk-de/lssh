import errno
import fcntl
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import termios
import time
import unittest


TERMINALS = (
    "xterm",
    "xterm-256color",
    "screen",
    "screen-256color",
    "tmux-256color",
)
REPOSITORY_ROOT = Path(__file__).parents[1]


@unittest.skipUnless(os.name == "posix", "requires POSIX pseudo terminals")
class TuiPseudoTerminalTests(unittest.TestCase):
    def run_dialog(self, terminal, mode):
        master, slave = os.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
        original_settings = termios.tcgetattr(slave)

        code = """
import os
import sys
from lssh import tui_dialog

if sys.argv[1] == "flat":
    result = tui_dialog.flat_option_dialog(["alpha", "beta"], "Hosts")
else:
    result = tui_dialog.hierarchical_option_dialog(
        [("customer", ["host"])], {}, "Customers", "Hosts"
    )
print("RESULT=" + repr(result))
print("TERM_AFTER=" + os.environ.get("TERM", ""))
print("TERMINAL_CANARY")
"""
        environment = os.environ.copy()
        environment["TERM"] = terminal
        environment["PYTHONPATH"] = str(REPOSITORY_ROOT)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"

        def child_setup():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

        process = subprocess.Popen(
            [sys.executable, "-c", code, mode],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=environment,
            close_fds=True,
            preexec_fn=child_setup,
        )
        os.close(slave)
        output = bytearray()
        sent_cancel = False
        deadline = time.monotonic() + 8
        try:
            while time.monotonic() < deadline:
                readable, _, _ = select.select([master], [], [], 0.1)
                if readable:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError as error:
                        if error.errno == errno.EIO:
                            break
                        raise
                    if not chunk:
                        break
                    output.extend(chunk)
                    if not sent_cancel:
                        os.write(master, b"q")
                        sent_cancel = True
                if process.poll() is not None:
                    break
            process.wait(timeout=2)
            restored_settings = termios.tcgetattr(master)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)

        decoded = output.decode("utf-8", errors="replace")
        self.assertEqual(process.returncode, 0, decoded)
        self.assertIn("RESULT=None", decoded)
        self.assertIn("TERM_AFTER=" + terminal, decoded)
        self.assertIn("TERMINAL_CANARY", decoded)
        self.assertNotIn("Traceback", decoded)
        self.assertEqual(restored_settings, original_settings)

    def test_flat_and_hierarchical_abort_restore_each_terminal(self):
        for terminal in TERMINALS:
            for mode in ("flat", "hierarchical"):
                with self.subTest(terminal=terminal, mode=mode):
                    self.run_dialog(terminal, mode)


if __name__ == "__main__":
    unittest.main()
