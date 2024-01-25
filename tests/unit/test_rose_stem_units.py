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

"""Unit tests for Rose Stem."""

from types import SimpleNamespace
from typing import Any, Tuple

from metomi.rose.config_tree import ConfigTree
from metomi.rose.fs_util import FileSystemUtil
from metomi.rose.popen import RosePopener
from metomi.rose.reporter import Reporter
import pytest
from pytest import param

import cylc.rose
from cylc.rose.stem import (
    ProjectNotFoundException,
    RoseStemVersionException,
    RoseSuiteConfNotFoundException,
    StemRunner,
    get_rose_stem_opts,
    get_source_opt_from_args,
)

Fixture = Any


class MockPopen:
    def __init__(self, mocked_return):
        self.mocked_return = mocked_return

    def run(self, *args):
        return self.mocked_return


@pytest.mark.parametrize(
    'args, expect',
    [
        pytest.param(
            [],
            None,
            id='no-path'
        ),
        pytest.param(
            ['/foo'],
            '/foo',
            id='absolute-path'
        ),
        pytest.param(
            ['foo'],
            '{tmp_path}/foo',
            id='relative-path'
        ),
    ]
)
def test_get_source_opt_from_args(tmp_path, monkeypatch, args, expect):
    """It converts Rose 2 CLI features to options usable by Rose Stem
    """
    monkeypatch.chdir(tmp_path)
    opts = SimpleNamespace()

    result = get_source_opt_from_args(opts, args).workflow_conf_dir

    if expect is None:
        assert result == expect
    else:
        assert result == expect.format(tmp_path=str(tmp_path))


@pytest.fixture
def get_StemRunner():
    def _inner(kwargs, options=None):
        if options is None:
            options = {}
        """Create a StemRunner objects with some options set."""
        opts = SimpleNamespace(verbosity=1, quietness=1, **options)
        stemrunner = StemRunner(opts, **kwargs)
        return stemrunner
    return _inner


def test_StemRunner_init_kwargs_set(get_StemRunner):
    """It handles __init__ with different kwargs."""
    stemrunner = get_StemRunner({
        'reporter': 'foo', 'popen': 'foo', 'fs_util': 'foo'
    })
    assert isinstance(stemrunner.reporter, str)
    assert isinstance(stemrunner.popen, str)
    assert isinstance(stemrunner.popen, str)


def test_StemRunner_init_defaults(get_StemRunner):
    """It handles __init__ with different kwargs."""
    stemrunner = get_StemRunner({})
    assert isinstance(stemrunner.reporter, Reporter)
    assert isinstance(stemrunner.popen, RosePopener)
    assert isinstance(stemrunner.fs_util, FileSystemUtil)


@pytest.mark.parametrize(
    'exisiting_defines',
    [
        param([], id='no existing defines'),
        param(['opts=(cylc-install)'], id='existing defines')
    ]
)
def test__add_define_option(get_StemRunner, capsys, exisiting_defines):
    """It adds to defines, rather than replacing any."""
    stemrunner = get_StemRunner(
        {'reporter': print}, {'defines': exisiting_defines})
    assert stemrunner._add_define_option('FOO', '"bar"') is None
    assert '[template variables]FOO="bar"' in stemrunner.opts.defines
    assert 'Variable FOO set to "bar"' in capsys.readouterr().out


@pytest.mark.parametrize(
    'mocked_return',
    [
        param((1, 'foo', 'SomeError'), id='it fails if fcm-loc-layout fails'),
        param(
            (
                0,
                'url: file:///worthwhile/foo/bar/baz/trunk@1\n'
                'project: \n'
                'key_with_no_value_ignored:\n'
                'some waffle which ought to be ignored\n',
                None
            ),
            id='Good fcm output'
        )

    ]
)
def test__get_fcm_loc_layout_info(get_StemRunner, capsys, mocked_return):
    """It parses information from fcm loc layout"""

    stemrunner = get_StemRunner({'popen': MockPopen(mocked_return)})

    if mocked_return[0] == 0:
        expect = {
            'url': 'file:///worthwhile/foo/bar/baz/trunk@1',
            'project': ''
        }
        assert expect == stemrunner._get_fcm_loc_layout_info('foo')
    else:
        with pytest.raises(ProjectNotFoundException) as exc:
            stemrunner._get_fcm_loc_layout_info('foo')
        assert mocked_return[2] in str(exc.value)


@pytest.mark.parametrize(
    'source_dict, mockreturn, expect',
    [
        param(
            {
                'root': 'svn://subversive',
                'project': 'waltheof',
                'url': 'Irrelevent, it\'s mocked away, but required.'
            },
            (
                0,
                (
                    "location{primary}[mortimer] = "
                    "svn://subversive/rogermortimer\n"
                    "location{primary}[fenwick] = "
                    "svn://subversive/johnfenwick\n"
                    "location{primary}[waltheof] = "
                    "svn://subversive/waltheof\n"
                ),
            ),
            'waltheof',
            id='all paths true'
        ),
        param(
            {
                'root': 'svn://subversive',
                'project': 'waltheof',
                'url': 'Irrelevent, it\'s mocked away, but required.'
            },
            (0, "location{primary} = svn://subversive/waltheof\n"),
            None,
            id='no kp result'
        )
    ]
)
def test__get_project_from_url(
    get_StemRunner, source_dict, mockreturn, expect
):
    stemrunner = get_StemRunner({'popen': MockPopen(mockreturn)})
    project = stemrunner._get_project_from_url(source_dict)
    assert project == expect


@pytest.mark.parametrize(
    'source, expect',
    (
        (None, 'cwd'),
        ('foo/bar', 'some_dir'),
    )
)
def test__generate_name(
    get_StemRunner, monkeypatch, tmp_path, source, expect, caplog, capsys
):
    """It generates a name if StemRunner._ascertain_project fails.

    (This happens if the workflow source is not controlled with FCM)
    """
    monkeypatch.chdir(tmp_path)

    # Case: we've set source:
    source = (tmp_path / source / expect) if expect == 'some_dir' else None
    # Case: we've not set source:
    expect = tmp_path.name if expect == 'cwd' else expect

    stemrunner = get_StemRunner({}, {'workflow_conf_dir': source})
    stemrunner.reporter.contexts['stdout'].verbosity = 5
    assert stemrunner._generate_name() == expect
    assert 'Suite is named' in capsys.readouterr().out


@pytest.mark.parametrize(
    'stem_sources, expect',
    (
        ('given', True),
        ('given', False),
        ('infer', True),
        ('infer', False),
    )
)
def test__this_suite(
    get_StemRunner, monkeypatch, tmp_path, stem_sources, expect
):
    """It returns a sensible suite-dir."""
    stem_suite_subdir = tmp_path / 'rose-stem'
    stem_suite_subdir.mkdir()

    if stem_sources == 'infer':
        stem_sources = []
        monkeypatch.setattr(
            cylc.rose.stem.StemRunner,
            '_ascertain_project',
            lambda x, y: [0, str(tmp_path)]
        )
    else:
        stem_sources = [tmp_path]

    if expect:
        (stem_suite_subdir / 'rose-suite.conf').write_text(
            'ROSE_STEM_VERSION=1')
        stemrunner = get_StemRunner({}, {'stem_sources': stem_sources})
        assert stemrunner._this_suite() == str(stem_suite_subdir)
    else:
        stemrunner = get_StemRunner({}, {'stem_sources': stem_sources})
        with pytest.raises(RoseSuiteConfNotFoundException):
            stemrunner._this_suite()


def test__this_suite_raises_if_no_dir(get_StemRunner):
    """It raises an exception if there is no suitefile"""
    stemrunner = get_StemRunner({}, {'stem_sources': ['/foo']})
    with pytest.raises(RoseSuiteConfNotFoundException):
        stemrunner._this_suite()


def test__check_suite_version_fails_if_no_stem_source(
    get_StemRunner, tmp_path
):
    """It fails if path of first stem source is not a file"""
    stemrunner = get_StemRunner(
        {}, {'stem_sources': str(tmp_path), 'workflow_conf_dir': None})
    stem_suite_subdir = tmp_path / 'rose-stem'
    stem_suite_subdir.mkdir()
    with pytest.raises(RoseSuiteConfNotFoundException, match='^\nCannot'):
        stemrunner._check_suite_version(str(tmp_path))


def test__check_suite_version_incompatible(get_StemRunner, tmp_path):
    """It fails if path of first stem source is not a file"""
    (tmp_path / 'rose-suite.conf').write_text('')
    stemrunner = get_StemRunner(
        {}, {'stem_sources': [], 'workflow_conf_dir': str(tmp_path)})
    with pytest.raises(
        RoseStemVersionException, match='ROSE_STEM_VERSION'
    ):
        stemrunner._check_suite_version(str(tmp_path / 'rose-suite.conf'))


def test__deduce_mirror():
    source_dict = {
        'root': 'svn://lab/spaniel.xm',
        'project': 'myproject.xm',
        'url': 'svn://lab/spaniel.xm/myproject/trunk@123',
        'sub_tree': 'foo'
    }
    project = 'someproject'
    StemRunner._deduce_mirror(source_dict, project)


def test_RoseSuiteConfNotFoundException_repr():
    """It handles dirctory not existing _at all_"""
    result = RoseSuiteConfNotFoundException('/foo').__repr__()
    expect = 'Suite directory /foo is not a valid directory'
    assert expect in result


def test__ascertain_project(get_StemRunner, monkeypatch):
    """It doesn't handle sub_tree if not available."""
    monkeypatch.setattr(
        cylc.rose.stem.StemRunner,
        '_get_project_from_url', lambda _, __: 'foo'
    )
    monkeypatch.setattr(
        cylc.rose.stem.StemRunner,
        '_deduce_mirror', lambda _, __, ___: 'foo'
    )
    stemrunner = get_StemRunner({'popen': MockPopen((
        0,
        (
            'root: https://foo.com/\n'
            'url: https://foo.com/helloworld\n'
            'project: helloworld\n'
        ),
        'stderr'
    ))})
    result = stemrunner._ascertain_project('')
    assert result == ('foo', '', '', '', 'foo')


def test_process_multiple_auto_opts(
    monkeypatch: Fixture, get_StemRunner: Fixture
) -> None:
    """Read a list of options from site config.

    - Correctly splits list.
    - Adds valid key=value pairs to stemrunner.options.
    - Rejects malformed items.
    """
    stemrunner = get_StemRunner({}, options={'defines': []})
    monkeypatch.setattr(
        cylc.rose.stem.StemRunner, '_read_auto_opts',
        lambda _: 'foo=bar baz=qux=quiz'
    )
    stemrunner._parse_auto_opts()
    assert 'foo="bar"' in stemrunner.opts.defines[0]


def test_process_no_auto_opts(
    monkeypatch: Fixture, get_StemRunner: Fixture
) -> None:
    """Read an empty list of options from site config.
    """
    stemrunner = get_StemRunner({}, options={'defines': []})
    monkeypatch.setattr(
        cylc.rose.stem.StemRunner, '_read_auto_opts',
        lambda _: ''
    )
    stemrunner._parse_auto_opts()
    assert stemrunner.opts.defines == []


@pytest.mark.parametrize(
    'item, expect, stdout',
    (
        (
            # Normally formed project=url
            'foo=bar',
            ('foo', 'bar'),
            "Forcing project for 'bar' to be 'foo'",
        ),
        (
            # Malformed project=url
            '=foo',
            ('', 'foo'),
            None,
        ),
    )
)
def test_ascertain_project_if_name_supplied(
    get_StemRunner: Fixture,
    capsys: pytest.CaptureFixture,
    item: str,
    expect: Tuple[str],
    stdout: str,
) -> None:
    """Method gives sensible results for different CLI input.

    Written because `-s=foo` leads to "item" including a leading = sign.
    This led to project name being set to '', and skipping the FCM
    calling logic, which the user might expect.
    """
    stemrunner = get_StemRunner({})
    if stdout:
        results = stemrunner._ascertain_project(item)
        assert results[:2] == expect
        assert stdout in capsys.readouterr().out
    else:
        with pytest.raises(
            ProjectNotFoundException, match='is not a working copy'
        ):
            stemrunner._ascertain_project(item)


@pytest.mark.parametrize(
    'language, expect',
    (
        ('empy', '[empy:suite.rc]'),
        ('jinja2', '[jinja2:suite.rc]'),
        ('template variables', '[template variables]'),
    )
)
def test_process_template_engine_set_correctly(monkeypatch, language, expect):
    """Defines are correctly assigned a [<template language>:suite.rc]
    section.

    https://github.com/cylc/cylc-rose/issues/246
    """
    monkeypatch.setattr(
        'cylc.rose.stem.load_rose_config',
        lambda _: ConfigTree()
    )
    monkeypatch.setattr(
        'cylc.rose.stem.process_config',
        lambda _: {'templating_detected': language, 'env': {}}
    )
    monkeypatch.setattr(
        'sys.argv',
        ['foo', 'bar']
    )

    # We are not interested in these checks, just in the defines
    # created by the process method.
    stemrunner = StemRunner(get_rose_stem_opts()[1])
    stemrunner._ascertain_project = lambda _: ['', '', '', '', '']
    stemrunner._this_suite = lambda: '.'
    stemrunner._check_suite_version = lambda _: '1'
    stemrunner.process()

    for define in stemrunner.opts.defines:
        assert define.startswith(expect)
