import io
import os.path
import re
from setuptools import setup


def read(*names, **kwargs):
    with io.open(
        os.path.join(os.path.dirname(__file__), *names),
        encoding=kwargs.get("encoding", "utf8")
    ) as fp:
        return fp.read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name='journalwatch',
    description="A tool to get notified on error messages in the systemd "
                "journal",
    url='http://git.the-compiler.org/journalwatch/',
    author="Florian Bruhin",
    author_email='me@the-compiler.org',
    version=find_version('journalwatch.py'),
    py_modules=['journalwatch'],
    entry_points={
        'console_scripts': [
            'journalwatch=journalwatch:main',
        ],
    },
    license='GPL',
    long_description=read('README.rst'),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v3 or later '
            '(GPLv3+)',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Topic :: System',
        'Topic :: System :: Boot :: Init',
        'Topic :: System :: Logging',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ],
    keywords='systemd journal journald logwatch logcheck',
)
