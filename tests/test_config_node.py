# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Tests the plugin with Rose suite configurations via the Python API."""

import pytest

from metomi.rose.config import (
    ConfigNode,
)
from metomi.rose.config_processor import ConfigProcessError

from cylc.rose.rose import (
    get_rose_vars_from_config_node,
)


def test_blank():
    """It should provide only standard vars for a blank config."""
    ret = {}
    node = ConfigNode()
    get_rose_vars_from_config_node(ret, node, {})
    assert set(ret.keys()) == {'env'}
    assert set(ret['env'].keys()) == {
        'ROSE_ORIG_HOST',
        'ROSE_SITE',
        'ROSE_VERSION',
    }


def test_invalid_templatevar():
    """It should wrap eval errors as something more informative."""
    ret = {}
    node = ConfigNode()
    node.set(['jinja2:suite.rc', 'X'], 'Y')
    with pytest.raises(ConfigProcessError):
        get_rose_vars_from_config_node(ret, node, {})
