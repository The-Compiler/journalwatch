import re
from datetime import datetime, timezone

import pytest

import journalwatch


def test_read_patterns():
    lines = [
        '# This is a comment',
        '_SYSTEMD_UNIT = foo',
        'bar',
        '',
        '_SYSTEMD_UNIT = /baz/',
        'fish',
    ]
    expected = {
        ('_SYSTEMD_UNIT', 'foo'): [re.compile('bar')],
        ('_SYSTEMD_UNIT', re.compile('baz')): [re.compile('fish')],
    }
    assert journalwatch.read_patterns(lines) == expected


@pytest.mark.parametrize('entry, expected', [
    ({'_SYSTEMD_UNIT': 'foo'},
     'U foo : EMPTY!'),

    ({
        '_SYSTEMD_UNIT': 'foo',
        'PRIORITY': 'prio',
        '__REALTIME_TIMESTAMP': datetime.fromtimestamp(0, tz=timezone.utc),
        '_PID': 1337,
        'MESSAGE': "Hello World"
    }, 'U Thu Jan  1 00:00:00 1970 prio foo [1337]: Hello World'),

    ({'SYSLOG_IDENTIFIER': 'sys', 'MESSAGE': "Hello World"},
     'S sys: Hello World'),
])
def test_format_entry(entry, expected):
    assert journalwatch.format_entry(entry) == expected


@pytest.mark.parametrize('patterns, entry, filtered', [
    # No patterns
    ({}, {'MESSAGE': 'foo'}, False),
    # No message
    (
        {('_SYSLOG_IDENTIFIER', 'foo'): [re.compile('bar')]},
        {'_SYSLOG_IDENTIFIER': 'foo'},
        False
    ),
    # No matching pattern
    (
        {('_SYSLOG_IDENTIFIER', 'bar'): [re.compile('bar')]},
        {'_SYSLOG_IDENTIFIER': 'foo', 'MESSAGE': 'unmatched'},
        False
    ),
    # Matching pattern
    (
        {('_SYSLOG_IDENTIFIER', 'bar'): [re.compile('msg')]},
        {'_SYSLOG_IDENTIFIER': 'bar', 'MESSAGE': 'msg'},
        True
    ),
    # Regex as identifier
    (
        {('_SYSLOG_IDENTIFIER', re.compile('bar')): [re.compile('msg')]},
        {'_SYSLOG_IDENTIFIER': 'bar', 'MESSAGE': 'msg'},
        True
    ),
    # Matching priority (#7)
    (
        {('PRIORITY', '1'): [re.compile('msg')]},
        {'PRIORITY': 1, 'MESSAGE': 'msg'},
        True
    ),
    (
        {('PRIORITY', re.compile('1')): [re.compile('msg')]},
        {'PRIORITY': 1, 'MESSAGE': 'msg'},
        True
    ),
    # Binary message (#5)
    (
        {('_SYSLOG_IDENTIFIER', 'bar'): [re.compile('msg')]},
        {'_SYSLOG_IDENTIFIER': 'bar', 'MESSAGE': b'\xde\xad\xbe\xef'},
        False
    ),
])
def test_filter_message(patterns, entry, filtered):
    assert journalwatch.filter_message(patterns, entry) == filtered


def test_new_config_files(monkeypatch, tmpdir):
    config_home = tmpdir / 'config'
    data_home = tmpdir / 'data'
    config_dir = config_home / 'journalwatch'
    data_dir = data_home / 'journalwatch'
    config_file = config_dir / 'config'
    pattern_file = config_dir / 'patterns'

    monkeypatch.setattr(journalwatch, 'parse_args', lambda: None)
    monkeypatch.setattr(journalwatch, 'XDG_DATA_HOME', str(data_home))
    monkeypatch.setattr(journalwatch, 'DATA_DIR', str(data_dir))
    monkeypatch.setattr(journalwatch, 'XDG_CONFIG_HOME', str(config_home))
    monkeypatch.setattr(journalwatch, 'CONFIG_DIR', str(config_dir))
    monkeypatch.setattr(journalwatch, 'CONFIG_FILE', str(config_file))
    monkeypatch.setattr(journalwatch, 'PATTERN_FILE', str(pattern_file))

    journalwatch.parse_config_files()
    assert pattern_file.read() == journalwatch.DEFAULT_PATTERNS
