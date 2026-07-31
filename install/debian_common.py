"""Shared Debian installer settings and preflight checks.

The constants in this module are also the authoritative source for a future
Debian package.  ``DEBIAN_PACKAGE_DEPENDS`` maps directly to the package's
``Depends`` field; the additional entries in ``APT_PACKAGES`` are needed by
the current /usr/local installer integration.
"""

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess


DEBIAN_PACKAGE_DEPENDS = (
    "python3",
    "python3-urwid",
    "python3-xdg",
    "openssh-client",
    "util-linux",
    "git",
)
INSTALLER_INTEGRATION_PACKAGES = (
    "cron",
    "bash-completion",
    "sudo",
)
APT_PACKAGES = DEBIAN_PACKAGE_DEPENDS + INSTALLER_INTEGRATION_PACKAGES

PYTHON_MODULE_PACKAGES = {
    "urwid": "python3-urwid",
    "xdg": "python3-xdg",
}


@dataclass(frozen=True)
class InstallPaths:
    library: Path
    state: Path
    repository: Path
    hosts: Path
    bin_dir: Path
    launcher: Path
    pull_wrapper: Path
    whitelist: Path
    completion: Path


SYSTEM_PATHS = InstallPaths(
    library=Path("/usr/local/lib/lssh"),
    state=Path("/var/local/lssh"),
    repository=Path("/var/local/lssh/host_repo"),
    hosts=Path("/var/local/lssh/hosts"),
    bin_dir=Path("/usr/local/bin"),
    launcher=Path("/usr/local/bin/lssh"),
    pull_wrapper=Path("/var/local/lssh/pull.sh"),
    whitelist=Path("/etc/lssh/remotecommand-whitelist.csv"),
    completion=Path("/etc/bash_completion.d/lssh_completion"),
)


def user_paths(home=None):
    home = Path.home() if home is None else Path(home)
    state = home / ".lssh"
    bin_dir = state / "bin"
    return InstallPaths(
        library=state / "lib" / "lssh",
        state=state,
        repository=state / "host_repo",
        hosts=state / "hosts",
        bin_dir=bin_dir,
        launcher=bin_dir / "lssh",
        pull_wrapper=bin_dir / "pull.sh",
        whitelist=state / "remotecommand-whitelist.csv",
        completion=home / ".bashrc",
    )


def missing_apt_packages(packages=APT_PACKAGES):
    """Return Debian packages which are not installed according to dpkg."""
    if shutil.which("dpkg-query") is None:
        raise RuntimeError("dpkg-query was not found; this installer requires Debian")

    missing = []
    for package in packages:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", package],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or result.stdout.strip() != "install ok installed":
            missing.append(package)
    return missing


def missing_python_modules():
    return [
        package
        for module, package in PYTHON_MODULE_PACKAGES.items()
        if importlib.util.find_spec(module) is None
    ]


def verify_dependencies():
    """Return the sorted union of missing APT packages and Python modules."""
    return sorted(set(missing_apt_packages()) | set(missing_python_modules()))


def install_dependencies(use_sudo=False):
    command = ["apt-get", "install", "-y", *APT_PACKAGES]
    if use_sudo:
        command.insert(0, "sudo")
    subprocess.run(command, check=True)


def validate_python_sources(source):
    """Compile all Python sources in memory before installed files are touched."""
    source = Path(source)
    for filename in sorted(source.rglob("*.py")):
        compile(filename.read_bytes(), str(filename), "exec")


def replace_python_package(source, destination):
    source = Path(source)
    destination = Path(destination)
    os.makedirs(destination, exist_ok=True)
    source_files = {path.name for path in source.iterdir() if path.suffix == ".py"}
    destination_files = {
        path.name for path in destination.iterdir() if path.suffix == ".py"
    }
    for filename in source_files:
        shutil.copy2(source / filename, destination / filename)
    for filename in destination_files - source_files:
        os.remove(destination / filename)
