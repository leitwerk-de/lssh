import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).parents[1] / "install" / "debian_common.py"
SPEC = importlib.util.spec_from_file_location("debian_common", MODULE_PATH)
debian_common = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = debian_common
SPEC.loader.exec_module(debian_common)


class DebianCommonTests(unittest.TestCase):
    def test_package_lists_are_centralized_and_complete(self):
        expected = {
            "python3",
            "python3-urwid",
            "python3-xdg",
            "git",
            "openssh-client",
            "util-linux",
            "cron",
            "bash-completion",
            "sudo",
        }
        self.assertEqual(set(debian_common.APT_PACKAGES), expected)

    def test_missing_package_checks_dpkg_return_code(self):
        installed = mock.Mock(returncode=0, stdout="install ok installed")
        missing = mock.Mock(returncode=1, stdout="")
        with (
            mock.patch.object(debian_common.shutil, "which", return_value="/bin/dpkg-query"),
            mock.patch.object(
                debian_common.subprocess,
                "run",
                side_effect=[installed, missing],
            ),
        ):
            result = debian_common.missing_apt_packages(("present", "absent"))
        self.assertEqual(result, ["absent"])

    def test_source_validation_does_not_write_bytecode(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "valid.py").write_text("answer = 42\n")
            debian_common.validate_python_sources(source)
            self.assertFalse((source / "__pycache__").exists())

    def test_source_validation_raises_before_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            destination = Path(directory) / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "broken.py").write_text("if True print('broken')\n")
            (destination / "keep.py").write_text("keep = True\n")
            with self.assertRaises(SyntaxError):
                debian_common.validate_python_sources(source)
            self.assertTrue((destination / "keep.py").exists())

    def test_replacement_keeps_non_python_data(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            destination = Path(directory) / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "current.py").write_text("current = True\n")
            (destination / "obsolete.py").write_text("obsolete = True\n")
            (destination / "recording.data").write_text("preserve")
            debian_common.replace_python_package(source, destination)
            self.assertTrue((destination / "current.py").exists())
            self.assertFalse((destination / "obsolete.py").exists())
            self.assertEqual(
                (destination / "recording.data").read_text(), "preserve"
            )


if __name__ == "__main__":
    unittest.main()
