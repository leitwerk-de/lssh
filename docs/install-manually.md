# Installing lssh manually

## Dependencies

- **Python 3, Urwid and PyXDG**
  On Debian 13 install these as `python3`, `python3-urwid` and `python3-xdg`.
  Use distribution packages for a shared installation so every user runs the
  same administrator-maintained code.

- **git**
  If you want to share your host configuration using git, you will need git installed locally. But another vcs will also work.

- **OpenSSH client and util-linux**
  The SSH connection, recording and replay features use `ssh`, `script` and
  `scriptreplay`. On Debian these are provided by `openssh-client` and
  `util-linux`.

- (optional) **sudo**
  If you install lssh systemwide, you may need sudo to run config updates as a normal user.

For a full Debian installation, install all runtime and integration packages:

```bash
apt-get install python3 python3-urwid python3-xdg git openssh-client util-linux cron bash-completion sudo
```

No user-specific Python environment is needed.

## Installing

Before you start to install, you need to specify a few paths on your file system.
Placeholders are used in the rest of this guide that you need to replace with your actual chosen path.

- A bin directory where the lssh python script can be stored, called `$BIN`
- A place where the lssh directory with the main python code can be stored, called `$LIB`
- A local directory for the repository clone containing host entries, called `$HOST_REPO_CLONE`
- A local directory for the validated host entries, called `$HOSTS_VALIDATED`

## Installing python code

Copy the lssh directory from this repository to the `$LIB` directory.

For understanding: The python files must be located under `$LIB/lssh/*.py`

```bash
cp -r lssh $LIB/
```

## Clone the host configuration repository

Clone the repository that contains your ssh configuration files, to the location `$HOST_REPO_CLONE`, for example using git:

```bash
git clone _your-clone-url_ $HOST_REPO_CLONE
```

## Create a folder for validated host entries

Create an empty folder at `$HOSTS_VALIDATED`:

```bash
mkdir $HOSTS_VALIDATED
```

## Create the lssh executable file

Use the following template to create the executable script `$BIN/lssh` and customize it.

```python
#! /usr/bin/env python3

import sys

repo_clone = "<host repo clone>"
validated = "<hosts validated>"

def update_hosts():
    # Called when a user executes `lssh --update-hosts`
    import subprocess
    subprocess.run(["git", "pull"], cwd=repo_clone, check=True)
    subprocess.run(["lssh", "--load-from", repo_clone], check=True)

sys.path.append("<lib>")

from lssh import main
main.main(validated, update_hosts)
```

Replace `<hosts validated>` with your `$HOSTS_VALIDATED`, `<host repo clone>` with your `$HOST_REPO_CLONE` and `<lib>` with your `$LIB` in the template

Make the file executable:

```bash
chmod +x $BIN/lssh
```

## Include the ssh configuration files

In your ssh client configuration file (for example `/etc/ssh/ssh_config` or `~/.ssh/config`) add an include-entry using the following template:

```
Host *
Include <hosts validated>/*.txt
```

Replace `<hosts validated>` with your `$HOSTS_VALIDATED`.

Replace `example.com` with the actual alias hostname of your proxy in both lines.

## Automatically update host entries

Crontabs can be edited with the command `crontab -l`  
Use the following template for an entry in your crontab:

```
42 * * * * <bin>/lssh --update-hosts
```

Replace `<bin>` with your `$BIN` directory. An absolute path to lssh is often needed because cronjobs run with a minimalistic `$PATH` environment variable.

The given example runs the host-update command every hour on minute 42 (0:42, 1:42, 2:42, ..., 23:42)

## Setup bash completion

Put the following instruction into a bash startup file for example `~/.bashrc`

```bash
complete -o filenames -C 'lssh __complete__' lssh
```

# Optional settings

## General first proxy

You may specify a global proxy machine in the lssh executable. This proxy will always be used as a first connection step to the target machine.

To activate the proxy, replace the line `main.main(...)` at the end of the lssh executable file with the following template:

```python
options = {
    "general_proxy": "example.com",
}
main.main(hosts_dir, update_hosts, attributes=options)
```

Replace `example.com` with your actual proxy host you want to use.
