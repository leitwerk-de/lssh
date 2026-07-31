# Debian packaging preparation

The current installers intentionally retain the existing `/usr/local` rollout.
They share their package lists and destination paths through
`install/debian_common.py`, so package checks and installations cannot drift
between the system-wide and user installers.

## Current APT dependencies

Both installers check the following packages before replacing installed Python
source files:

```text
python3 python3-urwid python3-xdg openssh-client util-linux git cron bash-completion sudo
```

The `-i` option installs this exact list through `apt-get`. A non-root user
installer invokes `sudo apt-get` when sudo is available; otherwise it prints an
administrator command and stops before changing lssh files.

## Future binary package

The runtime mapping for an eventual binary package is defined as
`DEBIAN_PACKAGE_DEPENDS` and translates to:

```text
Depends: python3, python3-urwid, python3-xdg, openssh-client, util-linux, git
```

The current installer additionally needs `cron`, `bash-completion` and `sudo`
because it writes the cron entry, shell completion integration and privilege
rule itself. A future package should express those integrations through normal
Debian maintainer scripts and package relationships.

## Current system-wide paths

```text
/usr/local/lib/lssh                 Python package
/usr/local/bin/lssh                 command
/var/local/lssh/host_repo           managed host repository
/var/local/lssh/hosts               validated host configuration
/var/local/lssh/pull.sh             update wrapper
/etc/lssh/remotecommand-whitelist.csv
/etc/bash_completion.d/lssh_completion
```

Reinstallation replaces only Python files in `/usr/local/lib/lssh` and the
generated integration files. It does not delete or recreate an existing host
repository, validated host directory, whitelist or recordings.
