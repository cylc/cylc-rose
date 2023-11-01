# THIS FILE IS PART OF THE ROSE-CYLC PLUGIN FOR THE CYLC WORKFLOW ENGINE.
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

from types import SimpleNamespace

from cylc.flow.hostuserutil import get_host
from metomi.isodatetime.datetimeoper import DateTimeOperator
from metomi.rose.config import ConfigLoader
from metomi.rose.config_tree import ConfigTree
import pytest

from cylc.rose.entry_points import (
    copy_config_file,
    post_install,
    record_cylc_install_options,
)
from cylc.rose.fileinstall import rose_fileinstall
from cylc.rose.utilities import (
    ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING,
    MultipleTemplatingEnginesError,
)

HOST = get_host()


def assert_rose_conf_full_equal(left, right, no_ignore=True):
    for keys_1, node_1 in left.walk(no_ignore=no_ignore):
        node_2 = right.get(keys_1, no_ignore=no_ignore)
        assert not (  # noqa: E721
            type(node_1) != type(node_2) or
            (
                not isinstance(node_1.value, dict) and
                node_1.value != node_2.value
            ) or
            node_1.comments != node_2.comments
        )

    for keys_2, _node_2 in right.walk(no_ignore=no_ignore):
        assert left.get(keys_2, no_ignore=no_ignore) is not None


def test_no_rose_suite_conf_in_devdir(tmp_path):
    result = post_install(tmp_path, tmp_path, SimpleNamespace())
    assert result is False


def test_rose_fileinstall_uses_rose_template_vars(tmp_path):
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
        rose_template_vars=[],
        clear_rose_install_opts=False
    )

    # Run both record_cylc_install options and fileinstall.
    record_cylc_install_options(srcdir, destdir, opts)
    rose_fileinstall(destdir, opts)
    assert ((destdir / 'installedme').read_text() ==
            'Galileo No! We will not let you go.'
            )


@pytest.mark.parametrize(
    (
        'opts, files, env_inserts,'
    ),
    [
        # Basic clean install example.
        (
            # opts:
            SimpleNamespace(
                opt_conf_keys='',
                defines=['[env]FOO=1'],
                rose_template_vars=['X=Y'],
                clear_rose_install_opts=False
            ),
            # {file: content}
            {
                'test/rose-suite.conf': 'opts=foo',
                'test/opt/rose-suite-cylc-install.conf': '',
                'test/opt/rose-suite-foo.conf': '',
                'ref/opt/rose-suite-cylc-install.conf': (
                    'opts=\n[env]\nFOO=1'
                    f'\n[template variables]\nX=Y\n'
                    f'#{ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING}\n'
                    f'ROSE_ORIG_HOST={HOST}\n'
                    f'\n[env]\n'
                    f'#{ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING}\n'
                    f'ROSE_ORIG_HOST={HOST}\n'
                ),
                'ref/rose-suite.conf': '!opts=foo (cylc-install)',
                'ref/opt/rose-suite-foo.conf': '',
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
                opt_conf_keys='baz',
                defines=['[env]BAR=2'],
                clear_rose_install_opts=False
            ),
            # {file: content}
            {
                'test/rose-suite.conf': 'opts=foo',
                'test/opt/rose-suite-foo.conf': '',
                'test/opt/rose-suite-bar.conf': '',
                'test/opt/rose-suite-baz.conf': '',
                'test/opt/rose-suite-cylc-install.conf': (
                    '!opts=bar\n[env]\nBAR=1\nROSE_ORIG_HOST=abc123\n'
                    '\n[template variables]\nROSE_ORIG_HOST=abc123\n'
                ),
                'ref/opt/rose-suite-cylc-install.conf':
                    f'!opts=bar baz\n[env]\nBAR=2\n'
                    f'#{ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING}\n'
                    f'ROSE_ORIG_HOST={HOST}\n'
                    f'\n[template variables]\n'
                    f'#{ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING}\n'
                    f'ROSE_ORIG_HOST={HOST}\n',
                'ref/rose-suite.conf': '!opts=foo bar baz (cylc-install)',
                'ref/opt/rose-suite-foo.conf': '',
                'ref/opt/rose-suite-bar.conf': '',
                'ref/opt/rose-suite-baz.conf': '',
                'ref/rose-suite.conf': '!opts=foo bar baz (cylc-install)'
            },
            # ENVIRONMENT VARS
            {},
        ),
        # Third cylc install example.
        (
            # opts:
            SimpleNamespace(
                opt_conf_keys='c',
                clear_rose_install_opts=False
            ),
            # {file: content}
            {
                'test/rose-suite.conf': 'opts=a',
                'test/opt/rose-suite-cylc-install.conf': '',
                'test/opt/rose-suite-a.conf': '',
                'test/opt/rose-suite-b.conf': '',
                'test/opt/rose-suite-c.conf': '',
                'ref/opt/rose-suite-cylc-install.conf': (
                    f'!opts=b c\n\n[env]\n'
                    f'#{ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING}\n'
                    f'ROSE_ORIG_HOST={HOST}\n'
                    f'\n[template variables]\n'
                    f'#{ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING}\n'
                    f'ROSE_ORIG_HOST={HOST}\n'
                ),
                'ref/rose-suite.conf': '!opts=a b c (cylc-install)',
                'ref/opt/rose-suite-a.conf': '',
                'ref/opt/rose-suite-b.conf': '',
                'ref/opt/rose-suite-c.conf': '',
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
                rose_template_vars=['a="b"'],
                clear_rose_install_opts=False
            ),
            # {file: content}
            {
                'test/rose-suite.conf': 'opts=\n[jinja2:suite.rc]\ny="base"',
                'test/opt/rose-suite-foo.conf': '[jinja2:suite.rc]\ny="f"\n',
                'test/opt/rose-suite-bar.conf': '[jinja2:suite.rc]\ny="b"\n',
                'ref/opt/rose-suite-cylc-install.conf': (
                    f'!opts=foo bar\n[env]\na=b\n'
                    f'#{ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING}\n'
                    f'ROSE_ORIG_HOST={HOST}\n'
                    f'[jinja2:suite.rc]\na="b"\n'
                    f'#{ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING}\n'
                    f'ROSE_ORIG_HOST={HOST}\n'
                ),
                'ref/rose-suite.conf': (
                    '!opts=foo bar (cylc-install)\n[jinja2:suite.rc]\ny="base"'
                ),
                'ref/opt/rose-suite-foo.conf': '[jinja2:suite.rc]\ny="f"\n',
                'ref/opt/rose-suite-bar.conf': '[jinja2:suite.rc]\ny="b"\n',
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
    record_cylc_install_options(testdir, testdir, opts=opts)
    rose_fileinstall(testdir, opts)
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
    rundir = (tmp_path / 'rundir')
    for dir_ in [srcdir, rundir]:
        dir_.mkdir()
    (srcdir / 'rose-suite.conf').touch()  # sidestep test for conf existance
    (rundir / 'nicest_work_of.nature').touch()
    (rundir / 'rose-suite.conf').write_text(
        "[file:Gnu]\nsrc=nicest_work_of.nature\n"
    )
    (rundir / 'cylc.flow').touch()
    rose_fileinstall(rundir, SimpleNamespace())

    assert (rundir / '.rose-config_processors-file.db').is_file()


@pytest.mark.parametrize(
    (
        'opts, files, expect'
    ),
    [
        pytest.param(
            # opts:
            SimpleNamespace(
                opt_conf_keys='', defines=['[jinja2:suite.rc]FOO=1'],
                define_suites=[], clear_rose_install_opts=False
            ),
            # {file: content}
            {
                'test/rose-suite.conf':
                    f'\n[empy:suite.rc]\nFOO=7\nROSE_ORIG_HOST={HOST}\n'
            },
            (
                r"((jinja2:suite\.rc)|(empy:suite.rc)); "
                r"((jinja2:suite\.rc)|(empy:suite.rc))"
            ),
            id='CLI contains different templating'
        ),
    ]
)
def test_template_section_conflict(
    monkeypatch, tmp_path, opts, files, expect
):
    """Cylc install fails if multiple template sections set:"""
    testdir = tmp_path / 'test'
    # Set up existing files, should these exist:
    for fname, content in files.items():
        path = tmp_path / fname
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    with pytest.raises(MultipleTemplatingEnginesError) as exc_info:
        # Run the entry point top-level function:
        record_cylc_install_options(testdir, testdir, opts)
    assert exc_info.match(expect)


def test_rose_fileinstall_exception(tmp_path, monkeypatch):
    """It throws an exception if you try to install files to a non existent
    destination.

    (And returns to the directory you started at)
    """
    def fakenode(_, __):
        tree = ConfigTree()
        tree.node.value = {'file': ''}
        return tree

    monkeypatch.setattr(
        'cylc.rose.utilities.rose_config_tree_loader',
        fakenode,
    )
    monkeypatch.setattr(
        'cylc.rose.fileinstall.rose_config_exists',
        lambda x: True,
    )
    with pytest.raises(FileNotFoundError):
        rose_fileinstall('/oiruhgaqhnaigujhj', SimpleNamespace())


def test_cylc_no_rose(tmp_path):
    """A Cylc workflow that contains no ``rose-suite.conf`` installs OK.
    """
    from cylc.rose.entry_points import post_install
    assert post_install(tmp_path, tmp_path, SimpleNamespace()) is False


def test_copy_config_file_fails(tmp_path):
    """It fails if source not a rose suite."""
    copy_config_file(tmp_path, tmp_path)
