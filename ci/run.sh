#!/bin/bash
set -e
set -x

# Prepare the environment
pip3 install --user systemd pytest

# Run the tests
exec "$PYTHON" -m pytest /build/test_journalwatch.py
