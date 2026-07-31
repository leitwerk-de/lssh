#!/bin/bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get -qq update
apt-get -qq install -y \
    python3 python3-urwid python3-xdg git openssh-client util-linux \
    cron bash-completion sudo

if dpkg-query -W python3-pip >/dev/null 2>&1; then
    echo "Unexpected user-package installer dependency present" >&2
    exit 1
fi

cp -a /workspace /tmp/lssh
cd /tmp/lssh
export PYTHONPATH=/tmp/lssh
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1

python3 --version | grep -E '^Python 3\.13\.'
python3 -m compileall -q -f lssh install tests
python3 -m unittest discover -s tests -v

mkdir -p /tmp/runtime-hosts /tmp/valid-config
cat >/tmp/valid-config/customer.txt <<'EOF'
Host demo
    HostName example.invalid
    User admin
EOF

python3 -c 'from lssh import main; main.main("/tmp/runtime-hosts", lambda: None)' --help >/tmp/lssh-help
grep -q -- '--validate' /tmp/lssh-help
python3 -c 'from lssh import main; main.main("/tmp/runtime-hosts", lambda: None)' --version | grep -q 'lssh version'
python3 -c 'from lssh import main; main.main("/tmp/runtime-hosts", lambda: None)' --validate /tmp/valid-config

git init /tmp/host-source
git -C /tmp/host-source config user.email integration@example.invalid
git -C /tmp/host-source config user.name Integration
cp /tmp/valid-config/customer.txt /tmp/host-source/customer.txt
git -C /tmp/host-source add customer.txt
git -C /tmp/host-source commit -m initial

./install/debian-systemwide-install file:///tmp/host-source
/usr/local/bin/lssh --help >/tmp/installed-lssh-help
grep -q -- '--validate' /tmp/installed-lssh-help
/usr/local/bin/lssh --version | grep -q 'lssh version'
/usr/local/bin/lssh --validate /tmp/valid-config
host_hash=$(sha256sum /var/local/lssh/hosts/customer.txt | cut -d' ' -f1)
repo_head=$(git -C /var/local/lssh/host_repo rev-parse HEAD)
mkdir -p /var/local/lssh/recordings
printf 'preserve\n' >/var/local/lssh/recordings/installer-test
printf 'obsolete = True\n' >/usr/local/lib/lssh/obsolete.py

./install/debian-systemwide-install file:///tmp/host-source
./install/debian-systemwide-install -i file:///tmp/host-source
test ! -e /usr/local/lib/lssh/obsolete.py
test "$(sha256sum /var/local/lssh/hosts/customer.txt | cut -d' ' -f1)" = "$host_hash"
test "$(git -C /var/local/lssh/host_repo rev-parse HEAD)" = "$repo_head"
grep -q preserve /var/local/lssh/recordings/installer-test

useradd --create-home jump1
useradd --create-home jump2
cp -a /tmp/host-source /home/jump1/host-source
chown -R jump1:jump1 /home/jump1/host-source
runuser -u jump1 -- env HOME=/home/jump1 PYTHONNOUSERSITE=1 \
    /tmp/lssh/install/debian-user-install file:///home/jump1/host-source
runuser -u jump1 -- env HOME=/home/jump1 PYTHONNOUSERSITE=1 \
    /tmp/lssh/install/debian-user-install file:///home/jump1/host-source
test ! -d /home/jump1/.local/lib/python3.13/site-packages

runuser -u jump1 -- env HOME=/home/jump1 PYTHONPATH=/tmp/lssh \
    PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
    python3 -m unittest discover -s /tmp/lssh/tests -p test_tui_pty.py \
    >/tmp/jump1.output 2>&1 &
pid1=$!
runuser -u jump2 -- env HOME=/home/jump2 PYTHONPATH=/tmp/lssh \
    PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
    python3 -m unittest discover -s /tmp/lssh/tests -p test_tui_pty.py \
    >/tmp/jump2.output 2>&1 &
pid2=$!
wait "$pid1"
wait "$pid2"
grep -q '^OK$' /tmp/jump1.output
grep -q '^OK$' /tmp/jump2.output

echo "Debian Trixie integration checks passed"
