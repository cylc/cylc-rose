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

"""Unit tests for utilities."""

from pathlib import Path

from cylc.rose.entry_points import copy_config_file


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


def test_CYLC_SYMLINKS_validate(monkeypatch, tmp_path, cylc_validate_cli):
    """We reload the global config after exporting env variables."""
    # Setup global config:
    global_conf = """#!jinja2
        {% from "cylc.flow" import LOG %}
        {% set cylc_symlinks = environ.get('CYLC_SYMLINKS', None) %}
        {% do LOG.critical(cylc_symlinks) %}
    """
    conf_path = tmp_path / 'conf'
    conf_path.mkdir()
    monkeypatch.setenv('CYLC_CONF_PATH', conf_path)

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
    output = cylc_validate_cli(tmp_path)
    assert output.ret == 0

    # CYLC_SYMLINKS == None the first time the global.cylc
    # is loaded and "Foo" the second time.
    assert output.logging == 'None\n"Foo"'


def test_CYLC_SYMLINKS_install(monkeypatch, tmp_path, cylc_install_cli):
    """We reload the global config after exporting env variables."""
    # Setup global config:
    global_conf = (
        '#!jinja2\n'
        '[install]\n'
        '    [[symlink dirs]]\n'
        '        [[[localhost]]]\n'
        '{% set cylc_symlinks = environ.get(\'CYLC_SYMLINKS\', None) %}\n'
        '{% if cylc_symlinks == "foo" %}\n'
        f'log = {str(tmp_path)}/foo\n'
        '{% else %}\n'
        f'log = {str(tmp_path)}/bar\n'
        '{% endif %}\n'
    )
    glbl_conf_path = tmp_path / 'conf'
    glbl_conf_path.mkdir()
    (glbl_conf_path / 'global.cylc').write_text(global_conf)
    monkeypatch.setenv('CYLC_CONF_PATH', glbl_conf_path)

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
    output = cylc_install_cli(tmp_path)
    import sys
    for i in output.logging.split('\n'):
        print(i, file=sys.stderr)
    assert output.ret == 0

    # Assert symlink created back to test_path/foo:
    expected_msg = (
        f'Symlink created: {output.run_dir}/log -> '
        f'{tmp_path}/foo/cylc-run/{output.id}/log'
    )
    assert expected_msg in output.logging.split('\n')[0]
