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

"""Test pre_configure entry point."""

from itertools import product
import os
from pathlib import Path
from shlex import split
from subprocess import run
from types import SimpleNamespace

import pytest
from pytest import param

from cylc.rose.utilities import NotARoseSuiteException, load_rose_config


@pytest.mark.parametrize(
    'srcdir, expect',
    [
        param(
            '07_cli_override',
            'failed 1.1\n(add --verbose for more context)',
            id='template variable not set'
        ),
        param(
            '08_template_engine_conflict',
            (
                'A plugin set the templating engine to empy which does'
                ' not match #!jinja2 set in flow.cylc.'
            ),
            id='template engine conflict'
        )
    ]
)
async def test_validate_fail(srcdir, expect, cylc_validate_cli):
    srcdir = Path(__file__).parent / srcdir
    validate = await cylc_validate_cli(srcdir)
    assert validate.ret == 1
    if expect:
        assert expect == str(validate.exc)


@pytest.mark.parametrize(
    'srcdir, envvars, args',
    [
        ('00_jinja2_basic', None, None),
        ('01_empy', None, None),
        ('02_env', None, None),
        (
            '04_opts_set_from_env',
            {'ROSE_SUITE_OPT_CONF_KEYS': 'Gaelige'},
            None
        ),
        (
            '05_opts_set_from_rose_suite_conf',
            {'ROSE_SUITE_OPT_CONF_KEYS': ''},
            None
        ),
        ('06_jinja2_thorough', {'XYZ': 'xyz'}, None),
        (
            '07_cli_override', {'XYZ': ''},
            {'templatevars': ["CLI_VAR='Wobble'"]}
        ),
        ('09_template_vars_vanilla', {'XYZ': 'xyz'}, None),
    ],
)
async def test_validate(monkeypatch, srcdir, envvars, args, cylc_validate_cli):
    for key, value in (envvars or {}).items():
        monkeypatch.setenv(key, value)
    srcdir = Path(__file__).parent / srcdir
    validate = await cylc_validate_cli(str(srcdir), args)
    assert validate.ret == 0


@pytest.mark.parametrize(
    'srcdir, envvars',
    [
        ('00_jinja2_basic', None),
        ('01_empy', None),
        (
            '04_opts_set_from_env',
            {'ROSE_SUITE_OPT_CONF_KEYS': 'Gaelige'},
        ),
        (
            '05_opts_set_from_rose_suite_conf',
            {'ROSE_SUITE_OPT_CONF_KEYS': ''},
        ),
        ('06_jinja2_thorough', {'XYZ': 'xyz'}),
    ],
)
def test_process(srcdir, envvars):
    srcdir = Path(__file__).parent / srcdir
    result = run(
        ['cylc', 'view', '-p', str(srcdir)],
        capture_output=True,
        env={**os.environ, **(envvars or {})}
    ).stdout.decode()
    expect = (srcdir / 'processed.conf.control').read_text()
    assert expect == result


@pytest.mark.parametrize(
    'root_dir_config', [
        'root-dir="/the/only/path/ive/ever/known"\n',
        'root-dir{work}="some/other/path"/n'
    ]
)
def test_warn_if_root_dir_set(root_dir_config, tmp_path, caplog):
    """Test using unsupported root-dir config raises error."""
    (tmp_path / 'rose-suite.conf').write_text(root_dir_config)
    load_rose_config(tmp_path)
    msg = 'rose-suite.conf[root-dir]'
    assert msg in caplog.records[0].msg


@pytest.mark.parametrize(
    'compat_mode',
    [
        pytest.param(True, id='back-compat'),
        pytest.param(False, id='no-back-compat')
    ]
)
@pytest.mark.parametrize(
    'rose_config', [
        'empy:suite.rc',
        'jinja2:suite.rc',
        'empy:flow.cylc',
        'jinja2:flow.cylc',
        'JinjA2:flOw.cylC',
    ]
)
def test_warn_if_old_templating_set(
    compat_mode, rose_config, tmp_path, caplog, monkeypatch
):
    """Test using unsupported root-dir config raises error."""
    monkeypatch.setattr(
        'cylc.rose.utilities.cylc7_back_compat', compat_mode
    )
    (tmp_path / 'rose-suite.conf').write_text(f'[{rose_config}]')
    load_rose_config(tmp_path)
    msg = "Use [template variables]"
    if compat_mode:
        assert not caplog.records
    else:
        assert msg in caplog.records[0].message


@pytest.mark.parametrize(
    'opts',
    [
        SimpleNamespace(opt_conf_keys=['Foo']),
        SimpleNamespace(defines=['Wurble']),
        SimpleNamespace(rose_template_vars=['X=3'])
    ]
)
def test_fail_if_options_but_no_rose_suite_conf(opts, tmp_path):
    """Tests for rose only options being used in a Cylc
    workflow which is not a rose-suite.conf
    """
    with pytest.raises(
        NotARoseSuiteException,
        match='^Cylc-Rose CLI'
    ):
        load_rose_config(tmp_path, opts)


def generate_params():
    """Generates a list of parameters to test assorted Cylc CLI commands
    which require rose-cylc parsing.
    """
    cmds = {
        'list': 'cylc list',
        'graph': 'cylc graph --reference',
        'config': 'cylc config',
        'view': 'cylc view -j'
    }
    cases = {
        'No Opts': ['', {}, b'mynd'],
        'use -O': ['-O Gaelige', {}, b'gabh'],
        'use -D': ['-D opts=""', {}, b'allow'],
        'use ROSE_SUITE_OPT_CONF_KEYS': [
            '', {'ROSE_SUITE_OPT_CONF_KEYS': 'Gaelige'}, b'gabh'
        ]
    }
    for test in product(cmds.items(), cases.items()):
        ((cmd_n, cmd), (case, [cli_opts, env_opts, result])) = test
        if case == 'graph':
            result = b'edge \"{}.1\"'.format(result)
        if case == 'config':
            result = b'[[{}]]'.format(result)
        out = pytest.param(
            cli_opts, env_opts, cmd, result, id=f'[{cmd_n}] {case}'
        )
        yield out


@pytest.mark.parametrize(
    'option, envvars, cmd, expect',
    generate_params()
)
def test_cylc_script(monkeypatch, option, envvars, cmd, expect):
    """Cylc scripts can parse folders without installing."""
    for name, value in envvars.items():
        monkeypatch.setenv(name, value)
    srcpath = Path(__file__).parent / (
        '05_opts_set_from_rose_suite_conf')
    output = run(split(f'{cmd} {srcpath} {option}'), capture_output=True)
    assert expect in output.stdout
