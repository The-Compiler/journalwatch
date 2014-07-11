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


import sys
from pprint import pprint
from systemd import journal
from datetime import datetime,timedelta
import re
import smtplib
from email.mime.text import MIMEText


def read_config():
    filters = {}
    is_header = True
    cur_filters = []
    header = None

    with open('filters') as f:
        for line in f:
            if line.startswith('#'):
                pass
            elif not line.strip():
                is_header = True
                if header is not None and cur_filters:
                    filters[header] = cur_filters
                cur_filters = []
                header = None
            else:
                if is_header:
                    k, v = line.split('=')
                    v = v.strip()
                    if v.startswith('/') and v.endswith('/'):
                        v = re.compile(v[1:-1])
                    header = (k.strip(), v)
                    is_header = False
                else:
                    cur_filters.append(re.compile(line.rstrip('\n')))
    return filters


def format_entry(entry):
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

def is_intresting(entry):
    if 'MESSAGE' not in entry:
        return True
    for (k, v), filters in config.items():
        if k not in entry:
            continue
        if hasattr(v, 'match'):
            if not v.match(entry[k]):
                continue
        else:
            if entry[k] != v:
                continue
        for filt in filters:
            if filt.match(entry['MESSAGE']):
                return False
    return True

config = read_config()

# Open the journal for reading, set log level and go back one day and 10 minutes
j = journal.Reader()
j.log_level(journal.LOG_INFO)
yesterday = datetime.now() - timedelta(days=1, minutes=10)
j.seek_realtime(yesterday)

output = []

# Filter and store output
for entry in j:
    if is_intresting(entry):
        output.append(format_entry(entry))

# Send the content in a mail to root
if '--mail' in sys.argv:
    mail = MIMEText('\n'.join(mailContent))
    mail['Subject'] = '[example.com] Logs from ' + datetime.ctime(yesterday) + ' to ' + datetime.ctime(datetime.now())
    mail['From'] = 'journald@example.com'
    mail['To'] = 'root@example.com'
    server = smtplib.SMTP('localhost')
    server.send_message(mail)
    server.quit()
else:
    print('\n'.join(output))
