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
"""

import pytest
from pytest import param
from types import SimpleNamespace

from cylc.rose.stem import (
    ProjectNotFoundException,
    RoseStemVersionException,
    RoseSuiteConfNotFoundException,
    StemRunner, SUITE_RC_PREFIX,
    get_source_opt_from_args
)

from metomi.rose.reporter import Reporter
from metomi.rose.popen import RosePopener
from metomi.rose.fs_util import FileSystemUtil


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

    result = get_source_opt_from_args(opts, args).source

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
        opts = SimpleNamespace(**{'verbosity': 1, 'quietness': 1})
        for k, v in options.items():
            setattr(opts, k, v)
        stemrunner = StemRunner(opts, **kwargs)
        return stemrunner
    return _inner


@pytest.mark.parametrize(
    'attribute, object_, kwargs', [
        param('reporter', Reporter, {}, id='reporter default'),
        param('reporter', str, {'reporter': 'foo'}, id='reporter set'),
        param('popen', RosePopener, {}, id='popen default'),
        param('popen', str, {'popen': 'foo'}, id='popen set'),
        param('fs_util', FileSystemUtil, {}, id='fs_util default'),
        param('fs_util', str, {'fs_util': 'foo'}, id='fs_util set')
    ]
)
def test_StemRunner_init(get_StemRunner, attribute, object_, kwargs):
    """It handles __init__ with different kwargs."""
    stemrunner = get_StemRunner(kwargs)
    item = getattr(stemrunner, attribute)
    if isinstance(object_, str):
        assert item == kwargs[attribute]
    else:
        assert isinstance(item, object_)


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
    assert f'{SUITE_RC_PREFIX}FOO="bar"' in stemrunner.opts.defines
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
                'some waffle which ought to be ignored',
                ''
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
def test__generate_name(get_StemRunner, monkeypatch, tmp_path, source, expect):
    """It generates a name if StemRunner._ascertain_project fails.

    (This happens if the workflow source is not controlled with FCM)
    """
    monkeypatch.chdir(tmp_path)

    # Case: we've set source:
    source = (tmp_path / source / expect) if expect == 'some_dir' else None
    # Case: we've not set source:
    expect = tmp_path.name if expect == 'cwd' else expect

    stemrunner = get_StemRunner({}, {'source': source})
    assert stemrunner._generate_name() == expect


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
        import cylc
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
        with pytest.raises(RoseSuiteConfNotFoundException):
            stemrunner = get_StemRunner({}, {'stem_sources': stem_sources})
            assert stemrunner._this_suite() == str(stem_suite_subdir)


def test__check_suite_version_fails_if_no_stem_source(
    get_StemRunner, tmp_path
):
    """It fails if path of first stem source is not a file"""
    stemrunner = get_StemRunner(
        {}, {'stem_sources': str(tmp_path), 'source': None})
    stem_suite_subdir = tmp_path / 'rose-stem'
    stem_suite_subdir.mkdir()
    with pytest.raises(RoseSuiteConfNotFoundException, match='^\nCannot'):
        stemrunner._check_suite_version(str(tmp_path))


def test__check_suite_version_incompatible(get_StemRunner, tmp_path):
    """It fails if path of first stem source is not a file"""
    (tmp_path / 'rose-suite.conf').write_text('')
    stemrunner = get_StemRunner(
        {}, {'stem_sources': [], 'source': str(tmp_path)})
    with pytest.raises(
        RoseStemVersionException, match='ROSE_VERSION'
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
