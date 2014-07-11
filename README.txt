journalwatch is a tool which can find error messages in the systemd journal.

It is similiar to tools like logwatch/logcheck except it's much more KISS and
only works with the systemd journal. It works by defining patterns to match all
log lines which are not interesting, and then prints all log lines not matching
those patterns (or sends them by mail).

When you start it the first time, it'll write the default pattern and config to
$XDG_CONFIG_HOME/.config/journalwatch ($XDG_CONFIG_HOME is your home if unset).
Details on how to configure journalwatch are available in these files.



journalwatch is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

journalwatch is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with journalwatch.  If not, see <http://www.gnu.org/licenses/>.
