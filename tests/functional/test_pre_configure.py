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
import re

from itertools import product
from pathlib import Path
from pytest import param
from shlex import split
from subprocess import run
from types import SimpleNamespace

from cylc.rose.entry_points import get_rose_vars, NotARoseSuiteException


def envar_exporter(dict_):
    for key, val in dict_.items():
        os.environ[key] = val


@pytest.mark.parametrize(
    'srcdir, expect',
    [
        param(
            '07_cli_override',
            b'CLI_VAR=="Wobble", "failed 1.1"',
            id='template variable not set'
        ),
        param(
            '08_template_engine_conflict',
            b'TemplateVarLanguageClash: .*empy.*#!jinja2.*',
            id='template engine conflict'
        )
    ]
)
def test_validate_fail(srcdir, expect):
    srcdir = Path(__file__).parent / srcdir
    sub = run(
        ['cylc', 'validate', str(srcdir)], capture_output=True
    )
    assert sub.returncode != 0
    if expect:
        assert re.findall(expect, sub.stderr)


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
        ('07_cli_override', {'XYZ': ''}, ["--set=CLI_VAR='Wobble'"]),
        ('09_template_vars_vanilla', {'XYZ': 'xyz'}, None),
    ],
)
def test_validate(tmp_path, srcdir, envvars, args):
    if envvars is not None:
        envvars = os.environ.update(envvars)
    srcdir = Path(__file__).parent / srcdir
    script = ['cylc', 'validate', str(srcdir)]
    if args:
        script = script + args
    assert (
        run(script, env=envvars)
    ).returncode == 0


@pytest.mark.parametrize(
    'srcdir, envvars, args',
    [
        ('00_jinja2_basic', None, None),
        ('01_empy', None, None),
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
    ],
)
def test_process(tmp_path, srcdir, envvars, args):
    if envvars is not None:
        envvars = os.environ.update(envvars)
    srcdir = Path(__file__).parent / srcdir
    result = run(
        ['cylc', 'view', '-p', '--stdout', str(srcdir)],
        capture_output=True,
        env=envvars
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
    get_rose_vars(srcdir=tmp_path)
    assert caplog.records[0].msg == (
        'You have set "root-dir", which is not supported at Cylc 8. Use '
        '`[install] symlink dirs` in global.cylc instead.'
    )


@pytest.mark.parametrize(
    'rose_config', [
        '[empy:suite.rc]',
        '[jinja2:suite.rc]'
    ]
)
def test_warn_if_old_templating_set(rose_config, tmp_path, caplog):
    """Test using unsupported root-dir config raises error."""
    (tmp_path / 'rose-suite.conf').write_text(rose_config)
    get_rose_vars(srcdir=tmp_path)
    msg = "is deprecated. Use [template variables]"
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
        get_rose_vars(tmp_path, opts)


def generate_params():
    """Generates a list of parameters to test assorted Cylc CLI commands
    which require rose-cylc parsing.
    """
    cmds = {
        'list': 'cylc list',
        'graph': 'cylc graph --reference',
        'config': 'cylc config'
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
