FROM ubuntu:artful

RUN apt -qq update && apt install -y python3.6 python3-systemd python3-pytest

RUN useradd ci
USER ci
