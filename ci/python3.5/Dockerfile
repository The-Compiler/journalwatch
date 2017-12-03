FROM ubuntu:xenial

RUN apt -qq update && apt install -y python3.5 python3-systemd python3-pytest

RUN useradd ci
USER ci
