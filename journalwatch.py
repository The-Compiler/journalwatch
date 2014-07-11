#!/usr/bin/env python3


# Copyright 2014 Florian Bruhin (The Compiler) <me@the-compiler.org>
#
# journalwatch is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# journalwatch is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with journalwatch.  If not, see <http://www.gnu.org/licenses/>.


import os
import os.path
import re
import sys
import socket
import subprocess
from systemd import journal
from datetime import datetime, timedelta
from email.mime.text import MIMEText


HOME = os.path.expanduser("~")
XDG_DATA_HOME = os.environ.get("XDG_DATA_HOME",
                               os.path.join(HOME, ".local", "share"))
XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME",
                                 os.path.join(HOME, ".config"))
PATTERN_FILE = os.path.join(XDG_CONFIG_HOME, 'journalwatch', 'patterns')
CONFIG_FILE = os.path.join(XDG_CONFIG_HOME, 'journalwatch', 'config')


def read_patterns(iterable):
    """Read the patterns file.

    Args:
        iterable: An iterable (e.g. a file object) to read the patterns from.

    Return:
        A dict with a mapping of (key, value) tuples to a list of filter regex
        objects. Value can be a string or a regex object.
    """
    # The output dict
    filters = {}
    # Whether the next line is a header (key = value)
    is_header = True
    # The filters for the current block
    cur_filters = []
    # The current header
    header = None
    for line in iterable:
        if line.startswith('#'):
            # Ignore comments
            pass
        elif not line.strip():
            # An empty line starts a new block and saves the accumulated
            # filters.
            is_header = True
            if header is not None and cur_filters:
                filters[header] = cur_filters
            cur_filters = []
            header = None
        elif is_header:
            # We got a non-empty line after an empty one so this is a header.
            k, v = line.split('=')
            v = v.strip()
            if v.startswith('/') and v.endswith('/'):
                v = re.compile(v[1:-1])
            header = (k.strip(), v)
            is_header = False
        else:
            # We got a non-empty line anywhere else, so this is a filter.
            cur_filters.append(re.compile(line.rstrip('\n')))
    # Also add the last block to the filters
    if header is not None and cur_filters:
        filters[header] = cur_filters
    return filters


def format_entry(entry):
    """Format a systemd log entry to a string.

    Args:
        entry: A systemd.journal.Reader entry.
    """
    words = []
    if '_SYSTEMD_UNIT' in entry:
        words.append('U')
    else:
        words.append('S')
    if '__REALTIME_TIMESTAMP' in entry:
        words.append(datetime.ctime(entry['__REALTIME_TIMESTAMP']))
    if 'PRIORITY' in entry:
        words.append(entry['PRIORITY'])
    if '_SYSTEMD_UNIT' in entry:
        words.append(entry['_SYSTEMD_UNIT'])
    name = ''
    if 'SYSLOG_IDENTIFIER' in entry:
        name += entry['SYSLOG_IDENTIFIER']
    if '_PID' in entry:
        name += '[{}]'.format(entry['_PID'])
    name += ':'
    words.append(name)
    words.append(entry.get('MESSAGE', 'EMPTY!'))
    return ' '.join(map(str, words))


def filter_message(patterns, entry):
    """Check if a message is filtered by any filter.

    Args:
        patterns: The patterns to apply, as returned by read_patterns().
        entry: A systemd.journal.Reader entry.
    """
    if 'MESSAGE' not in entry:
        return False
    for (k, v), filters in patterns.items():
        if k not in entry:
            # If the message doesn't have this key, we ignore it.
            continue
        # Now check if the message key matches the key we're currently looking
        # at
        if hasattr(v, 'match'):
            if not v.match(entry[k]):
                continue
        else:
            if entry[k] != v:
                continue
        # If we arrive here, the keys matched so we need to check these
        # filters.
        for filt in filters:
            if filt.match(entry['MESSAGE']):
                return True
    # No filters on no key/value blocks matched.
    return False


def main():
    """Main entry point. Filter the log and output it or send a mail."""
    output = []
    with open(PATTERN_FILE) as f:
        patterns = read_patterns(f)

    j = journal.Reader()
    j.log_level(journal.LOG_INFO)
    yesterday = datetime.now() - timedelta(days=1, minutes=10)
    j.seek_realtime(yesterday)
    for entry in j:
        if not filter_message(patterns, entry):
            output.append(format_entry(entry))
    if '--mail' in sys.argv:
        mail = MIMEText('\n'.join(output))
        mail['Subject'] = '[{}] - {} journal messages ({} - {})'.format(
            socket.gethostname(),
            len(output),
            datetime.ctime(yesterday),
            datetime.ctime(datetime.now()))
        mail['From'] = 'journalwatch@the-compiler.org'
        mail['To'] = 'journalwatch@the-compiler.org'
        p = subprocess.Popen(["sendmail", "-toi"], stdin=subprocess.PIPE)
        p.communicate(mail.as_bytes())
        #server = smtplib.SMTP('localhost')
        #server.send_message(mail)
        #server.quit()
    else:
        print('\n'.join(output))


if __name__ == '__main__':
    sys.exit(main())
