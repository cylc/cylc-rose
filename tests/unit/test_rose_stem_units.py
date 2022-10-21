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

import os
import pytest
from types import SimpleNamespace

from cylc.rose.stem import get_source_opt_from_args, StemRunner


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


class Test_generate_name:
    """Try 3 paths in StemRunner._generate_name.

    Contains a setup function for each path.
    """
    EXPECT = 'bar'
    MSG = 'Suite is named bar'

    @staticmethod
    def name_from_fcm(monkeypatch):
        """It gets the name from _ascertain_project.
        """
        class MonkeyStemRunner(StemRunner):
            def _ascertain_project(self, x):
                return ['foo', '/foo/bar']
        return MonkeyStemRunner(SimpleNamespace, reporter=print)

    @staticmethod
    def source_set(monkeypatch):
        """It gets the name from the source opt.

        equivalent of using:
            rose stem /foo/bar/rose-stem
        """
        opts = SimpleNamespace()
        opts.workflow_conf_dir = '/foo/bar'
        stemrunner = StemRunner(opts, reporter=print)
        return stemrunner

    @staticmethod
    def source_unset(monkeypatch):
        """It gets the name from the file path.

        equivalent of using:
            rose stem
        """
        opts = SimpleNamespace()
        opts.workflow_conf_dir = ''
        monkeypatch.setattr(os, "getcwd", lambda: "/foo/bar/rose-stem")
        stemrunner = StemRunner(opts, reporter=print)
        return stemrunner

    @pytest.mark.parametrize(
        'setup', [
            'source_set', 'source_unset', 'name_from_fcm'])
    def test__generate_name(self, capsys, monkeypatch, setup):
        """Tests StemRunner._generate_name for fake stemrunner
        returned by each test case method.
        """
        result = getattr(self, setup)(monkeypatch)._generate_name()
        assert result == self.EXPECT
        assert self.MSG in capsys.readouterr().out
