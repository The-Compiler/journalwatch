from distutils.core import setup


with open('README.txt') as f:
    description = f.read()


setup(
    name='journalwatch',
    description="A tool to get notified on error messages in the systemd "
                "journal",
    url='http://git.the-compiler.org/journalwatch/',
    author="Florian Bruhin",
    author_email='me@the-compiler.org',
    version='0.1.1',
    py_modules=['journalwatch'],
    scripts=['journalwatch'],
    license='GPL',
    long_description=description,
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
