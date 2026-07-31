#!/bin/sh
set -eu

repository=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

docker run --rm \
    --volume "$repository:/workspace:ro" \
    debian:trixie-slim \
    /bin/bash /workspace/tests/trixie-container.sh
