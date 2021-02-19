# THIS FILE IS PART OF THE ROSE-CYLC PLUGIN FOR THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Functional tests for top-level function record_cylc_install_options and
rose_fileinstall

Check functions which would be called by
``cylc install -D [fileinstall:myfile]example`` will lead to the correct file
installation.
"""
import pytest

from types import SimpleNamespace

from metomi.isodatetime.datetimeoper import DateTimeOperator

from cylc.rose.entry_points import (
    record_cylc_install_options, rose_fileinstall
)
from metomi.rose.config import ConfigLoader


def assert_rose_conf_full_equal(left, right, no_ignore=True):
    for keys_1, node_1 in left.walk(no_ignore=no_ignore):
        node_2 = right.get(keys_1, no_ignore=no_ignore)
        assert not (
            type(node_1) != type(node_2) or
            (
                not isinstance(node_1.value, dict) and
                node_1.value != node_2.value
            ) or
            node_1.comments != node_2.comments
        )

    for keys_2, node_2 in right.walk(no_ignore=no_ignore):
        assert left.get(keys_2, no_ignore=no_ignore) is not None


def test_no_rose_suite_conf_in_devdir(tmp_path):
    result = record_cylc_install_options(dir_=tmp_path)
    assert result is False


def test_rose_fileinstall_no_config_in_folder():
    # It returns false if no rose-suite.conf
    assert rose_fileinstall('/dev/null') is False


def test_rose_fileinstall_uses_suite_defines(tmp_path):
    # Setup source and destination dirs, including the file ``installme``:
    srcdir = tmp_path / 'source'
    destdir = tmp_path / 'dest'
    [dir_.mkdir() for dir_ in [srcdir, destdir]]
    (destdir / 'rose-suite.conf').touch()
    (srcdir / 'rose-suite.conf').touch()
    (srcdir / 'installme').write_text('Galileo No! We will not let you go.')

    # Create an SimpleNamespace pretending to be the options:
    opts = SimpleNamespace(
        opt_conf_keys='',
        defines=[f'[file:installedme]source={str(srcdir)}/installme'],
        define_suites=[]
    )

    # Run both record_cylc_install options and fileinstall.
    record_cylc_install_options(opts=opts, dest_root=destdir)
    rose_fileinstall(str(srcdir), opts, str(destdir))
    assert (destdir / 'installedme').read_text() == \
        'Galileo No! We will not let you go.'


@pytest.mark.parametrize(
    (
        'opts, files, env_inserts,'
    ),
    [
        # Basic clean install example.
        (
            # opts:
            SimpleNamespace(
                opt_conf_keys='', defines=['[env]FOO=1'], define_suites=['X=Y']
            ),
            # {file: content}
            {
                'test/rose-suite.conf': 'opts=foo',
                'test/opt/rose-suite-cylc-install.conf': '',
                'test/opt/rose-suite-foo.conf': '',
                'ref/opt/rose-suite-cylc-install.conf': (
                    'opts=\n[env]\nFOO=1'
                    '\n[jinja2:suite.rc]\nX=Y\n'
                ),
                'ref/rose-suite.conf': '!opts=foo (cylc-install)',
                'ref/opt/rose-suite-foo.conf': '',
                'ref/log/conf/18151210T0000Z-rose-suite.conf': (
                    '!opts=\n\n[env]\nFOO=1\n\n[jinja2:suite.rc]\nX=Y\n'
                ),
                'ref/rose-suite.conf': '!opts=foo (cylc-install)'
            },
            # ENVIRONMENT VARS
            {},
        ),
        # First cylc reinstall example - should be wrong once
        # cylc reinstall --clear-rose-install-opts implemented?
        (
            # opts:
            SimpleNamespace(
                opt_conf_keys='baz', defines=['[env]BAR=2']
            ),
            # {file: content}
            {
                'test/rose-suite.conf': 'opts=foo',
                'test/opt/rose-suite-foo.conf': '',
                'test/opt/rose-suite-bar.conf': '',
                'test/opt/rose-suite-baz.conf': '',
                'test/opt/rose-suite-cylc-install.conf':
                    '!opts=bar\n[env]\nBAR=1',
                'ref/opt/rose-suite-cylc-install.conf':
                    '!opts=bar baz\n[env]\nBAR=2',
                'ref/rose-suite.conf': '!opts=foo bar baz (cylc-install)',
                'ref/opt/rose-suite-foo.conf': '',
                'ref/opt/rose-suite-bar.conf': '',
                'ref/opt/rose-suite-baz.conf': '',
                'ref/log/conf/18151210T0000Z-rose-suite.conf': (
                    '!opts=bar baz\n\n[env]\nBAR=2\n'
                ),
                'ref/rose-suite.conf': '!opts=foo bar baz (cylc-install)'
            },
            # ENVIRONMENT VARS
            {},
        ),
        # Third cylc install example.
        (
            # opts:
            SimpleNamespace(
                opt_conf_keys='c'
            ),
            # {file: content}
            {
                'test/rose-suite.conf': 'opts=a',
                'test/opt/rose-suite-cylc-install.conf': '',
                'test/opt/rose-suite-a.conf': '',
                'test/opt/rose-suite-b.conf': '',
                'test/opt/rose-suite-c.conf': '',
                'ref/opt/rose-suite-cylc-install.conf': '!opts=b c\n',
                'ref/rose-suite.conf': '!opts=a b c (cylc-install)',
                'ref/opt/rose-suite-a.conf': '',
                'ref/opt/rose-suite-b.conf': '',
                'ref/opt/rose-suite-c.conf': '',
                'ref/log/conf/18151210T0000Z-rose-suite.conf': (
                    '!opts=b c\n\n'
                )
            },
            # ENVIRONMENT VARS
            {'ROSE_SUITE_OPT_CONF_KEYS': 'b'},
        ),
        # Oliver's review e.g.
        (
            # opts:
            SimpleNamespace(
                opt_conf_keys='bar',
                defines=['[env]a=b'],
                define_suites=['a="b"']
            ),
            # {file: content}
            {
                'test/rose-suite.conf': 'opts=\n[jinja2:suite.rc]\ny="base"',
                'test/opt/rose-suite-foo.conf': '[jinja2:suite.rc]\ny="f"\n',
                'test/opt/rose-suite-bar.conf': '[jinja2:suite.rc]\ny="b"\n',
                'ref/opt/rose-suite-cylc-install.conf': (
                    '!opts=foo bar\n[env]\na=b\n[jinja2:suite.rc]\na="b"'
                ),
                'ref/rose-suite.conf': (
                    '!opts=foo bar (cylc-install)\n[jinja2:suite.rc]\ny="base"'
                ),
                'ref/opt/rose-suite-foo.conf': '[jinja2:suite.rc]\ny="f"\n',
                'ref/opt/rose-suite-bar.conf': '[jinja2:suite.rc]\ny="b"\n',
                'ref/log/conf/18151210T0000Z-rose-suite.conf': (
                    '!opts=foo bar\n\n[env]\na=b'
                    '\n\n[jinja2:suite.rc]\na="b"\ny="b"\n'
                )
            },
            # ENVIRONMENT VARS
            {'ROSE_SUITE_OPT_CONF_KEYS': 'foo'},
        ),
    ]
)
def test_functional_record_cylc_install_options(
    monkeypatch, tmp_path, opts, files, env_inserts
):
    """It works the way the proposal says it should.

    TODO: Once the the dump of the final rose-suite.conf is done then this
    should be expanded to test that too.
    """
    # Pin down the results of the function used to provide a timestamp.
    def fake(*arg, **kwargs):
        return '18151210T0000Z'
    monkeypatch.setattr(
        DateTimeOperator, 'process_time_point_str', fake
    )

    testdir = tmp_path / 'test'
    refdir = tmp_path / 'ref'
    # Set up existing files, should these exist:
    for fname, content in files.items():
        path = tmp_path / fname
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    # Set any environment variables we require:
    for envvar, val in env_inserts.items():
        monkeypatch.setenv(envvar, val)
    loader = ConfigLoader()

    # Run the entry point top-level function:
    rose_suite_cylc_install_node, rose_suite_opts_node = \
        record_cylc_install_options(
            dest_root=testdir, opts=opts, dir_=testdir
        )
    rose_fileinstall(
        dest_root=testdir, opts=opts, dir_=testdir
    )
    ritems = sorted([i.relative_to(refdir) for i in refdir.rglob('*')])
    titems = sorted([i.relative_to(testdir) for i in testdir.rglob('*')])
    assert titems == ritems
    for counter, item in enumerate(titems):
        output = testdir / item
        reference = refdir / ritems[counter]
        if output.is_file():
            assert_rose_conf_full_equal(
                loader.load(str(output)),
                loader.load(str(reference)),
                no_ignore=False
            )


def test_functional_rose_database_dumped_correctly(tmp_path):
    srcdir = (tmp_path / 'srcdir')
    destdir = (tmp_path / 'destdir')
    for dir_ in [srcdir, destdir]:
        dir_.mkdir()
    (srcdir / 'rose-suite.conf').touch()  # sidestep test for conf existance
    (destdir / 'nicest_work_of.nature').touch()
    (destdir / 'rose-suite.conf').write_text(
        "[file:Gnu]\nsrc=nicest_work_of.nature\n"
    )
    (destdir / 'cylc.flow').touch()
    rose_fileinstall(dir_=srcdir, dest_root=destdir)

    assert (destdir / '.rose-config_processors-file.db').is_file()


def test_functional_rose_database_dumped_errors(tmp_path):
    srcdir = (tmp_path / 'srcdir')
    srcdir.mkdir()
    (srcdir / 'nicest_work_of.nature').touch()
    (srcdir / 'rose-suite.conf').write_text(
        "[file:Gnu]\nsrc=nicest_work_of.nature\n"
    )
    (srcdir / 'cylc.flow').touch()
    assert rose_fileinstall(dir_='/this/path/goes/nowhere') is False


def test_rose_fileinstall_exception(tmp_path, monkeypatch):
    def broken():
        raise FileNotFoundError('Any Old Error')
    import os
    monkeypatch.setattr(os, 'getcwd', broken)
    (tmp_path / 'rose-suite.conf').touch()
    with pytest.raises(FileNotFoundError):
        rose_fileinstall(dir_=tmp_path, dest_root=tmp_path)
