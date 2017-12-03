#!/bin/bash
set -e
set -x

# Prepare the environment
pip3 install --user systemd pytest

# Run the tests
cd /build
exec "$PYTHON" ~/.local/bin/pytest
