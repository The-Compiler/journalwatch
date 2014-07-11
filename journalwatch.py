#!/usr/bin/python3
# vim: set ft=python fileencoding=utf-8:

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

"""Filter error messages from systemd journal.

Copyright 2014 Florian Bruhin (The Compiler) <me@the-compiler.org>

For bugs, feature requests or contributions, mail <me@the-compiler.org>.
The newest version is available at http://g.cmpl.cc/journalwatch

journalwatch is free software, and you are welcome to redistribute it
under the conditions of the GNU GPLv3 or later.

You should have received a copy of the GNU General Public License
along with journalwatch.  If not, see <http://www.gnu.org/licenses/>.

journalwatch comes with ABSOLUTELY NO WARRANTY.
"""


import os
import os.path
import time
import re
import sys
import socket
import shlex
import subprocess
import configparser
import argparse
from systemd import journal
from datetime import datetime, timedelta
from email.mime.text import MIMEText


HOME = os.path.expanduser("~")
XDG_DATA_HOME = os.environ.get("XDG_DATA_HOME",
                               os.path.join(HOME, ".local", "share"))
XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME",
                                 os.path.join(HOME, ".config"))
CONFIG_DIR = os.path.join(XDG_CONFIG_HOME, 'journalwatch')
DATA_DIR = os.path.join(XDG_DATA_HOME, 'journalwatch')
TIME_FILE = os.path.join(DATA_DIR, 'time')
PATTERN_FILE = os.path.join(CONFIG_DIR, 'patterns')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config')

config = None


DEFAULT_PATTERNS = r"""
# In this file, patterns for journalwatch are defined to blacklist all journal
# messages which are not errors.
#
# Lines starting with '#' are comments. Inline-comments are not permitted.
#
# The patterns are separated into blocks delimited by empty lines. Each block
# matches on a log entry field, and the patterns in that block then are matched
# against all messages with a matching log entry field.
#
# The syntax of a block looks like this:
#
# <field> = <value>
# <pattern>
# [<pattern>]
# [...]
#
# If <value> starts and ends with a slash, it is interpreted as a regular
# expression, if not, it's an exact match. Patterns are always regular
# expressions.
#
# Below are some useful examples. If you have a small set of users, you might
# want to adjust things like "user \w" to something like "user (root|foo|bar)".
#
# The regular expressions are extended Python regular expressions, for details
# see:
#
# https://docs.python.org/3.4/library/re.html#regular-expression-syntax
# https://docs.python.org/3.4/howto/regex.html
# http://doc.pyschools.com/html/regex.html
#
# The journal fields are explained in systemd.journal-fields(7).

_SYSTEMD_UNIT = systemd-logind.service
New session [a-z]?\d+ of user \w+\.
Removed session [a-z]?\d+\.

SYSLOG_IDENTIFIER = /(CROND|crond)/
pam_unix\(crond:session\): session (opened|closed) for user \w+
\(\w+\) CMD .*

SYSLOG_IDENTIFIER = systemd
(Stopped|Stopping|Starting|Started) .*
(Created slice|Removed slice) user-\d*\.slice\.
Received SIGRTMIN\+24 from PID .*
(Reached target|Stopped target) .*
Startup finished in \d*ms\.
""".lstrip()

DEFAULT_CONFIG = """
# vim: ft=dosini
#
# This is the config for journalwatch. All options are defined in the [DEFAULT]
# section.
#
# You can add any commandline argument to the config, without the '--'.
# See  journalwatch --help for all arguments and their description.

[DEFAULT]
# mail_to = foobar@example.com
""".lstrip()


class JournalWatchError(Exception):

    """Exception raised on fatal errors."""

    pass


def parse_args():
    """Parse the commandline arguments and config.

    Based on http://stackoverflow.com/a/5826167

    Return:
        An argparse namespace.
    """
    defaults = {
        'action': 'print',
        'since': 'new',
        'mail_from': 'journalwatch@{}'.format(socket.getfqdn()),
        'mail_binary': 'sendmail',
        'mail_args': '-toi',
        'mail_subject': '[{hostname}] {count} journal messages ({start} - '
                        '{end})',
    }
    conf_parser = argparse.ArgumentParser(
        add_help=False,
    )
    _, remaining_argv = conf_parser.parse_known_args()
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    defaults.update(cfg['DEFAULT'])

    parser = argparse.ArgumentParser(
        parents=[conf_parser],
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.set_defaults(**defaults)
    parser.add_argument('action', nargs='?', choices=['print', 'mail'],
                        help="What to do with the filtered output "
                        "(print/mail).", metavar='ACTION')
    parser.add_argument('--since', nargs='?',
                        help="Timespan to process. Possible values:\n"
                        "all: Process the whole journal.\n"
                        "new: Process everything new since the last "
                        "invocation.\n"
                        "<n>: Process everything in the past <n> seconds.\n")
    parser.add_argument('--mail_from', nargs='?',
                        help="Sender of the mail.")
    parser.add_argument('--mail_to', nargs='?',
                        help="Recipient of the mail.")
    parser.add_argument('--mail_binary', nargs='?',
                        help="Binary to call to send mails")
    parser.add_argument('--mail_args', nargs='?',
                        help="Arguments to pass to the mail binary")
    parser.add_argument('--mail_subject', nargs='?',
                        help="Subject for the mail. The following strings are "
                        "replaced: \n"
                        "{hostname}: The hostname of this machine.\n"
                        "{count}: How many new messages were found.\n"
                        "{start}: The timestamp when journalwatch began"
                        "searching.\n"
                        "{end}: The current time when sending the message.")
    ns = parser.parse_args(remaining_argv)
    return ns


def read_patterns(iterable):
    """Read the patterns file.

    Args:
        iterable: An iterable (e.g. a file object) to read the patterns from.

    Return:
        A dict with a mapping of (key, value) tuples to a list of filter regex
        objects. Value can be a string or a regex object.
    """
    # The output dict
    patterns = {}
    # Whether the next line is a header (key = value)
    is_header = True
    # The patterns for the current block
    cur_patterns = []
    # The current header
    header = None
    for line in iterable:
        if line.startswith('#'):
            # Ignore comments
            pass
        elif not line.strip():
            # An empty line starts a new block and saves the accumulated
            # patterns.
            is_header = True
            if header is not None and cur_patterns:
                patterns[header] = cur_patterns
            cur_patterns = []
            header = None
        elif is_header:
            # We got a non-empty line after an empty one so this is a header.
            try:
                k, v = line.split('=')
            except ValueError:
                raise JournalWatchError(
                    "Got config line '{}' without header!".format(line))
            v = v.strip()
            if v.startswith('/') and v.endswith('/'):
                v = re.compile(v[1:-1])
            header = (k.strip(), v)
            is_header = False
        else:
            # We got a non-empty line anywhere else, so this is a filter.
            cur_patterns.append(re.compile(line.rstrip('\n')))
    # Also add the last block to the patterns
    if header is not None and cur_patterns:
        patterns[header] = cur_patterns
    return patterns


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
    for (k, v), patterns in patterns.items():
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
        # patterns.
        for filt in patterns:
            if filt.match(entry['MESSAGE']):
                return True
    # No patterns on no key/value blocks matched.
    return False


def parse_config_files():
    """Parse the config and pattern files.

    Return:
        A (config, patterns) tuple.
    """
    cfg = parse_args()
    if not os.path.exists(CONFIG_DIR):
        os.mkdir(CONFIG_DIR)
    if not os.path.exists(DATA_DIR):
        os.mkdir(DATA_DIR)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            f.write(DEFAULT_CONFIG)
    if not os.path.exists(PATTERN_FILE):
        with open(PATTERN_FILE, 'w') as f:
            f.write(DEFAULT_PATTERNS)
        patterns = read_patterns(DEFAULT_PATTERNS.splitlines())
    else:
        with open(PATTERN_FILE) as f:
            patterns = read_patterns(f)
    if not patterns:
        raise JournalWatchError("No patterns defined in {}!".format(
            PATTERN_FILE))
    return cfg, patterns


def get_journal(since=None):
    """Open the journal and get a journal reader.

    Args:
        since: A datetime object where to start reading.
               If None, the whole journal is read.
    """
    j = journal.Reader()
    j.log_level(journal.LOG_INFO)
    if since is not None:
        j.seek_realtime(since)
    else:
        j.seek_head()  # pylint: disable=no-member
    return j


def send_mail(output, since=None):
    """Send the log text via mail to the user.

    Args:
        output: A list of log lines.
        since: A datetime object when the collection started.
    """
    if since is None:
        start = 'beginning of time'
    else:
        start = datetime.ctime(since)
    text = '\n'.join(output)
    mail = MIMEText(text)
    mail['Subject'] = config.mail_subject.format(
        hostname=socket.gethostname(),
        count=len(output),
        start=start,
        end=datetime.ctime(datetime.now()))
    mail['From'] = config.mail_from
    try:
        mail['To'] = config.mail_to
    except AttributeError:
        raise JournalWatchError("Can't send mail without mail_to set. "
                                "Please set it either as argument or in "
                                "{}.".format(CONFIG_FILE))
    argv = [config.mail_binary]
    argv += shlex.split(config.mail_args)
    p = subprocess.Popen(argv, stdin=subprocess.PIPE)
    p.communicate(mail.as_bytes())


def parse_since():
    """Get the timespan to use."""
    if config.since == 'all':
        return None
    elif config.since == 'new':
        if not os.path.exists(TIME_FILE):
            return None
        with open(TIME_FILE) as f:
            since = datetime.fromtimestamp(float(f.read()))
            # Add an extra minute just to be sure.
            since -= timedelta(minutes=1)
            return since
    else:
        try:
            seconds = int(config.since)
        except ValueError:
            raise JournalWatchError("Can't parse {} seconds.".format(
                config.since))
        return datetime.now() - timedelta(seconds=seconds)


def write_time_file():
    """Write the execution time to a file."""
    with open(TIME_FILE, 'w') as f:
        f.write(str(time.time()))


def main():
    """Main entry point. Filter the log and output it or send a mail."""
    global config
    output = []
    config, patterns = parse_config_files()
    since = parse_since()
    write_time_file()
    j = get_journal(since)
    for entry in j:
        if not filter_message(patterns, entry):
            output.append(format_entry(entry))
    if not output:
        return
    if config.action == 'mail':
        send_mail(output, since)
    else:
        print('\n'.join(output))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except JournalWatchError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
