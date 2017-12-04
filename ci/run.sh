#!/bin/bash
set -e
set -x

# Prepare the environment
apt -qq update
apt install -y "$PYTHON" python3-pip libsystemd-dev
pip3 install --user systemd pytest

# Run the tests
cd /build
exec "$PYTHON" ~/.local/bin/pytest
