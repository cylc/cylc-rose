# THIS FILE IS PART OF THE ROSE-CYLC PLUGIN FOR THE CYLC WORKFLOW ENGINE.
# Copyright (C) Earth Sciences New Zealand & British Crown (Met Office)
# & Contributors.
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

"""Unit tests for utilities."""

import os
from pathlib import Path
from textwrap import dedent

import pytest

from cylc.rose.entry_points import copy_config_file
from cylc.rose.utilities import SubshellError, _cli_template

from cylc.flow.pathutil import get_workflow_run_dir


def test_basic(tmp_path):
    # Create files
    for fname, content in (
        ('src/rose-suite.conf', '[env]\nFOO=2'),
        ('dest/rose-suite.conf', '[env]\nFOO=1'),
    ):
        fname = Path(tmp_path / fname)
        fname.parent.mkdir(parents=True, exist_ok=True)
        fname.write_text(content)

    # Test
    assert copy_config_file(tmp_path / 'src', tmp_path / 'dest')
    assert Path(tmp_path / 'src/rose-suite.conf').read_text() == (
        Path(tmp_path / 'dest/rose-suite.conf').read_text()
    )


async def test_global_config_environment_validate(
    monkeypatch, tmp_path, cylc_validate_cli
):
    """It should reload the global config after exporting env variables.

    See: https://github.com/cylc/cylc-rose/issues/237
    """
    # Setup global config:
    global_conf = """#!jinja2
        {% from "cylc.flow" import LOG %}
        {% set cylc_symlinks = environ.get('CYLC_SYMLINKS', None) %}
        {% do LOG.critical(cylc_symlinks) %}
    """
    conf_path = tmp_path / 'conf'
    conf_path.mkdir()
    monkeypatch.setenv('CYLC_CONF_PATH', str(conf_path))

    # Setup workflow config:
    (conf_path / 'global.cylc').write_text(global_conf)
    (tmp_path / 'rose-suite.conf').write_text(
        '[env]\nCYLC_SYMLINKS="Foo"\n')
    (tmp_path / 'flow.cylc').write_text("""
        [scheduling]
            initial cycle point = now
            [[graph]]
                R1 = x
        [runtime]
            [[x]]
    """)

    # Validate the config:
    output = await cylc_validate_cli(tmp_path)

    # CYLC_SYMLINKS == None the first time the global.cylc
    # is loaded and "Foo" the second time.
    assert output.logging.split('\n')[-1] == '"Foo"'


async def test_global_config_environment_validate2(
    caplog, monkeypatch, tmp_path, cylc_install_cli
):
    """It should reload the global config after exporting env variables.

    See: https://github.com/cylc/cylc-rose/issues/237
    """
    # Setup global config:
    global_conf = dedent(f'''
        #!jinja2
        [install]
            [[symlink dirs]]
                [[[localhost]]]
        {{% set cylc_symlinks = environ.get(\'CYLC_SYMLINKS\', None) %}}
        {{% if cylc_symlinks == "foo" %}}
                    log = {str(tmp_path)}/foo
        {{% else %}}
                    log = {str(tmp_path)}/bar
        {{% endif %}}
    ''').strip()
    glbl_conf_path = tmp_path / 'conf'
    glbl_conf_path.mkdir()
    (glbl_conf_path / 'global.cylc').write_text(global_conf)
    monkeypatch.setenv('CYLC_CONF_PATH', str(glbl_conf_path))

    # Setup workflow config:
    (tmp_path / 'rose-suite.conf').write_text(
        '[env]\nCYLC_SYMLINKS=foo\n')
    (tmp_path / 'flow.cylc').write_text("""
        [scheduling]
            initial cycle point = now
            [[graph]]
                R1 = x
        [runtime]
            [[x]]
    """)

    # Install the config:
    _, id_ = await cylc_install_cli(tmp_path)

    # Assert symlink created back to test_path/foo:
    run_dir = get_workflow_run_dir(id_)
    expected_msg = (
        f'Symlink created: {run_dir}/log -> '
        f'{tmp_path}/foo/cylc-run/{id_}/log'
    )
    assert expected_msg in caplog.messages


def test_cli_template(capsys):
    """It should process substring templates."""
    # strings supported
    assert _cli_template('') == ''
    assert _cli_template('a-b-c') == 'a-b-c'

    # $(subshells) - supported
    assert _cli_template('a-$(echo b)-c') == 'a-b-c'
    assert _cli_template('$(echo a)-$(echo b)-$(echo c)') == 'a-b-c'

    # `subshells` - not supported
    assert _cli_template('a-`echo b`-c') == 'a-`echo b`-c'

    # subshell nesting is not supported
    assert _cli_template('a-$(echo $(echo b))-c') == 'a-$(echo b)-c'

    # environment variables are not supported
    assert _cli_template('$USER') == '$USER'

    # except in subshells
    assert _cli_template('$(echo $USER)') == os.environ['USER']

    # non-zero return code produces errors
    assert _cli_template('$(true)') == ''
    with pytest.raises(SubshellError, match=r'.*\$\(false\).*'):
        _cli_template('$(false)')

    # stderr from subshells goes to stderr - stdout is captured
    capsys.readouterr()
    assert _cli_template('$(echo out)$(echo err >&2)') == 'out'
    assert capsys.readouterr() == ('', 'err')

    # edge cases and implementation details
    assert _cli_template(' a ') == ' a '
    assert _cli_template('$(echo " a ")') == 'a'
    assert _cli_template('$(false; true)') == ''
    with pytest.raises(SubshellError):
        _cli_template('$(true; false)')
    assert _cli_template('$(false; true)') == ''
    assert _cli_template('$(echo a | sed "s/a/b/")') == 'b'
