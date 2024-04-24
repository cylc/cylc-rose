# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (C) 2012-2020 British Crown (Met Office) & Contributors.
#
# This file is part of Rose, a framework for meteorological suites.
#
# Rose is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Rose is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Rose. If not, see <http://www.gnu.org/licenses/>.
# -----------------------------------------------------------------------------

"""Tests for cylc.rose.stem"""

import os
from pathlib import Path
from shlex import split
import shutil
import subprocess
from io import StringIO
from uuid import uuid4
from typing import Dict

from metomi.rose.config import ConfigLoader
from metomi.rose.host_select import HostSelector
from cylc.flow.pathutil import get_workflow_run_dir
from metomi.rose.resource import ResourceLocator
import pytest

from cylc.rose.stem import (
    RoseStemVersionException,
    get_rose_stem_opts,
    rose_stem,
)


# We want to test Rose-Stem's insertion of the hostname,
# not Rose's method of getting the hostname, so it doesn't
# Matter that we are using the same host selector here as
# in the module under test:
HOST = HostSelector().get_local_host()


# Check that FCM is present on system, skipping checks elsewise:
try:
    subprocess.run(['fcm', '--version'])
except FileNotFoundError:
    pytest.skip("\"FCM\" not installed", allow_module_level=True)


@pytest.fixture()
def mock_global_cfg(monkeymodule):
    """Mock the rose ResourceLocator.default

    Args (To _inner):
        target: The module to patch.
        conf: A fake rose global config as a string.
    """
    def _inner(target, conf):
        """Get the ResourceLocator.default and patch its get_conf method
        """
        obj = ResourceLocator.default()
        monkeymodule.setattr(
            obj, 'get_conf', lambda: ConfigLoader().load(StringIO(conf))
        )

        monkeymodule.setattr(target, lambda *_, **__: obj)

    yield _inner


@pytest.fixture()
def setup_stem_repo(tmp_path_factory, monkeymodule, request):
    """Setup a Rose Stem Repository for the tests.

    creates the following repo structure::

       |-- baseinstall
       |   `-- trunk
       |       `-- rose-stem
       |-- conf
       |   `-- keyword.cfg
       |-- cylc-rose-stem-test-1df3e028
       |   `-- rose-stem
       |       |-- flow.cylc
       |       `-- rose-suite.conf
       `-- rose-test-battery-stemtest-repo
           `-- foo
               <truncated>

    Yields:
        dictionary:
            workingcopy:
                Path to the location of the working copy.
            suite_install_dir:
                The path to the installed suite/workflow. Handy for cleaning
                up after tests.

    """
    # Set up required folders:
    testname = request.function.__name__
    basetemp = tmp_path_factory.getbasetemp() / testname
    baseinstall = basetemp / 'baseinstall'
    rose_stem_dir = baseinstall / 'trunk/rose-stem'
    repo = basetemp / 'rose-test-battery-stemtest-repo'
    confdir = basetemp / 'conf'
    workingcopy = basetemp / f'cylc-rose-stem-test-{str(uuid4())[:8]}'
    for dir_ in [baseinstall, repo, rose_stem_dir, confdir, workingcopy]:
        dir_.mkdir(parents=True, exist_ok=True)

    # Turn repo into an svn repo:
    subprocess.run(['svnadmin', 'create', f'{repo}/foo'])
    url = f'file://{repo}/foo'

    old = Path().cwd()
    os.chdir(baseinstall)
    subprocess.run(['svn', 'import', '-q', '-m', '""', f'{url}'])
    os.chdir(old)

    # Set Keywords for repository.
    (basetemp / 'conf/keyword.cfg').write_text(
        f"location{{primary}}[foo.x]={url}"
    )
    monkeymodule.setenv('FCM_CONF_PATH', str(confdir))
    # Check out a working copy of the repo:
    suitename = workingcopy.parts[-1]
    subprocess.run(split(f'fcm checkout -q fcm:foo.x_tr {workingcopy}'))
    # Copy suite into working copy.
    test_src_dir = Path(__file__).parent / '12_rose_stem'
    for file in ['rose-suite.conf', 'flow.cylc']:
        src = str(test_src_dir / file)
        dest = str(workingcopy / 'rose-stem')
        shutil.copy2(src, dest)
    suite_install_dir = get_workflow_run_dir(suitename)

    monkeymodule.setattr(
        'cylc.flow.pathutil.make_symlink_dir',
        lambda *_, **__: {}
    )

    yield {
        'workingcopy': workingcopy,
        'suite_install_dir': suite_install_dir
    }
    # Only clean up if all went well.
    if (
        not request.session.testsfailed
        and Path(suite_install_dir).exists()
    ):
        shutil.rmtree(suite_install_dir)
        ResourceLocator.default(reset=True)


@pytest.fixture()
def rose_stem_runner(setup_stem_repo, monkeymodule):
    """Runs rose-stem."""

    async def _inner_fn(rose_stem_opts, cwd=None):
        # make it look like we're running the "rose stem" CLI
        monkeymodule.setattr('sys.argv', ['stem'])

        # cd into the working copy (unless overridden)
        monkeymodule.chdir(cwd or setup_stem_repo['workingcopy'])

        # merge the opts in with the defaults
        parser, opts = get_rose_stem_opts()
        for key, val in rose_stem_opts.items():
            setattr(opts, key, val)

        # run rose stem
        await rose_stem(parser, opts)

        # return a dictionary of template variables found in the
        # cylc-install optional configuration
        opt_conf = ConfigLoader().load(
            str(
                Path(
                    setup_stem_repo['suite_install_dir'],
                    'runN/opt/rose-suite-cylc-install.conf',
                )
            )
        )
        return {
            key: node.value  # noqa B035 (false positive)
            for [_, key], node in opt_conf.get(('template variables',)).walk()
        }

    yield _inner_fn


def check_template_variables(
    expected: Dict[str, str], got: Dict[str, str]
) -> None:
    """Check template variable dictionaries.

    Check the template vars in "expected" are present and match those in "got".

    Raises:
        AssertionError

    """
    for key in expected:
        assert key in got, f'template var {key} missing from config'
        assert (
            expected[key] == got[key]
        ), f'template var {key}={got[key]}, expected {expected[key]}'


async def test_hello_world(rose_stem_runner, setup_stem_repo):
    """It should run a hello-world example without erroring."""
    rose_stem_opts = {
        'stem_groups': [],
        'stem_sources': [
            str(setup_stem_repo['workingcopy']), "fcm:foo.x_tr@head"
        ],
    }
    await rose_stem_runner(rose_stem_opts)


async def test_template_variables(rose_stem_runner, setup_stem_repo):
    """It should set various template variables.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L56-L78
    """
    rose_stem_opts = {
        'stem_groups': ['earl_grey', 'milk,sugar', 'spoon,cup,milk'],
        'stem_sources': [
            str(setup_stem_repo['workingcopy']), "fcm:foo.x_tr@head"
        ],
    }
    template_vars = await rose_stem_runner(rose_stem_opts)

    workingcopy = setup_stem_repo["workingcopy"]
    check_template_variables(
        {
            "RUN_NAMES":
                "['earl_grey', 'milk', 'sugar', 'spoon', 'cup', 'milk']",
            "SOURCE_FOO": f'"{workingcopy} fcm:foo.x_tr@head"',
            "HOST_SOURCE_FOO": f'"{HOST}:{workingcopy} fcm:foo.x_tr@head"',
            "SOURCE_FOO_BASE": f'"{workingcopy}"',
            "HOST_SOURCE_FOO_BASE": f'"{HOST}:{workingcopy}"',
            "SOURCE_FOO_REV": '""',
            "SOURCE_FOO_MIRROR": '"fcm:foo.xm/trunk@1"',
        },
        template_vars,
    )


async def test_manual_project_override(rose_stem_runner, setup_stem_repo):
    """It should accept named project sources.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L80-L112
    """
    rose_stem_opts = {
        "stem_groups": ["earl_grey", "milk,sugar", "spoon,cup,milk"],
        "stem_sources": [
            # specify a named source called "bar"
            f'bar={setup_stem_repo["workingcopy"]}',
            "fcm:foo.x_tr@head",
        ],
    }
    template_vars = await rose_stem_runner(rose_stem_opts)

    workingcopy = setup_stem_repo['workingcopy']
    check_template_variables(
        {
            "RUN_NAMES":
                "['earl_grey', 'milk', 'sugar', " "'spoon', 'cup', 'milk']",
            "SOURCE_FOO": '"fcm:foo.x_tr@head"',
            "HOST_SOURCE_FOO": '"fcm:foo.x_tr@head"',
            "SOURCE_BAR": f'"{workingcopy}"',
            "HOST_SOURCE_BAR": f'"{HOST}:{workingcopy}"',
            "SOURCE_FOO_BASE": '"fcm:foo.x_tr"',
            "HOST_SOURCE_FOO_BASE": '"fcm:foo.x_tr"',
            "SOURCE_BAR_BASE": f'"{workingcopy}"',
            "HOST_SOURCE_BAR_BASE": f'"{HOST}:{workingcopy}"',
            "SOURCE_FOO_REV": '"@1"',
            "SOURCE_BAR_REV": '""',
            "SOURCE_FOO_MIRROR": '"fcm:foo.xm/trunk@1"',
        },
        template_vars,
    )


async def test_config_dir_absolute(rose_stem_runner, setup_stem_repo):
    """It should allow you to specify the config directory as an absolute path.

    This is an alternative approach to running the "rose stem" command
    in the directory itelf.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L114-L128
    """
    rose_stem_opts = {
        'workflow_conf_dir': f'{setup_stem_repo["workingcopy"]}/rose-stem',
        'stem_groups': ['lapsang'],
        'stem_sources': ["fcm:foo.x_tr@head"],
        # specify the workflow name to standardise the installed ID
        'workflow_name': setup_stem_repo['workingcopy'].parts[-1],
    }
    template_vars = await rose_stem_runner(
        rose_stem_opts,
        # don't CD into the project directory first
        cwd=Path.cwd(),
    )
    check_template_variables(
        {
            "RUN_NAMES": "['lapsang']",
            "SOURCE_FOO": '"fcm:foo.x_tr@head"',
            "SOURCE_FOO_BASE": '"fcm:foo.x_tr"',
            "SOURCE_FOO_REV": '"@1"',
        },
        template_vars,
    )


async def test_config_dir_relative(rose_stem_runner, setup_stem_repo):
    """It should allow you to specify the config directory as a relative path.

    This is an alternative approach to running the "rose stem" command
    in the directory itelf.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L152-L171
    """
    rose_stem_opts = {
        'workflow_conf_dir': './rose-stem',
        'stem_groups': ['ceylon'],
    }
    template_vars = await rose_stem_runner(rose_stem_opts)
    workingcopy = setup_stem_repo["workingcopy"]
    check_template_variables(
        {
            "RUN_NAMES": "['ceylon']",
            "SOURCE_FOO": f'"{workingcopy}"',
            "HOST_SOURCE_FOO": f'"{HOST}:{workingcopy}"',
            "SOURCE_FOO_BASE": f'"{workingcopy}"',
            "HOST_SOURCE_FOO_BASE": f'"{HOST}:{workingcopy}"',
            "SOURCE_FOO_REV": '""',
        },
        template_vars,
    )


async def test_source_in_a_subdirectory(rose_stem_runner, setup_stem_repo):
    """It should accept a source in a subdirectory.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L130-L150
    """
    rose_stem_opts = {
        'stem_groups': ['assam'],
        # stem source in a sub directory
        'stem_sources': [f'{setup_stem_repo["workingcopy"]}/rose-stem'],
    }
    template_vars = await rose_stem_runner(rose_stem_opts)
    workingcopy = setup_stem_repo["workingcopy"]
    check_template_variables(
        {
            "RUN_NAMES": "['assam']",
            "SOURCE_FOO": f'"{workingcopy}"',
            "HOST_SOURCE_FOO": f'"{HOST}:{workingcopy}"',
            "SOURCE_FOO_BASE": f'"{workingcopy}"',
            "HOST_SOURCE_FOO_BASE": f'"{HOST}:{workingcopy}"',
            "SOURCE_FOO_REV": '""',
            "SOURCE_FOO_MIRROR": '"fcm:foo.xm/trunk@1"',
        },
        template_vars,
    )


async def test_automatic_options(rose_stem_runner, setup_stem_repo, mock_global_cfg):
    """It should use automatic options from the site/user configuration.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L182-L204
    """
    rose_stem_opts = {
        'stem_groups': ['earl_grey', 'milk,sugar', 'spoon,cup,milk'],
        'stem_sources': [
            f'{setup_stem_repo["workingcopy"]}', 'fcm:foo.x_tr@head'],
    }
    mock_global_cfg(
        'cylc.rose.stem.ResourceLocator.default',
        # automatic options defined in the site/user config
        '[rose-stem]\nautomatic-options = MILK=true',
    )
    template_vars = await rose_stem_runner(rose_stem_opts)
    workingcopy = setup_stem_repo["workingcopy"]
    check_template_variables(
        {
            "RUN_NAMES": "['earl_grey', 'milk', 'sugar', 'spoon', 'cup', 'milk']",
            "SOURCE_FOO": f'"{workingcopy} fcm:foo.x_tr@head"',
            "HOST_SOURCE_FOO": f'"{HOST}:{workingcopy} fcm:foo.x_tr@head"',
            "SOURCE_FOO_BASE": f'"{workingcopy}"',
            "HOST_SOURCE_FOO_BASE": f'"{HOST}:{workingcopy}"',
            "SOURCE_FOO_REV": '""',
            "MILK": '"true"',
        },
        template_vars,
    )


async def test_automatic_options_multi(
    rose_stem_runner, setup_stem_repo, mock_global_cfg
):
    """It should use MULTIPLE automatic options from the site/user conf.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L206-L221
    """
    rose_stem_opts = {
        'stem_groups': ['assam'],
        'stem_sources': [
            f'{setup_stem_repo["workingcopy"]}'],
    }
    mock_global_cfg(
        'cylc.rose.stem.ResourceLocator.default',
        # *multiple* automatic options defined in the site/user config
        '[rose-stem]\nautomatic-options = MILK=true TEA=darjeeling',
    )
    template_vars = await rose_stem_runner(rose_stem_opts)
    check_template_variables(
        {
            "MILK": '"true"',
            "TEA": '"darjeeling"',
        },
        template_vars,
    )


async def test_incompatible_rose_stem_versions(setup_stem_repo, monkeymodule):
    """It should fail if trying to install an incompatible rose-stem config.

    Rose Stem configurations must specify a Rose Stem version, it should fail
    if the versions don't match.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L223-L232
    """
    # Copy suite into working copy.
    test_src_dir = Path(__file__).parent / '12_rose_stem'
    src = str(test_src_dir / 'rose-suite2.conf')
    dest = str(
        setup_stem_repo['workingcopy'] / 'rose-stem/rose-suite.conf'
    )
    shutil.copy2(src, dest)

    rose_stem_opts = {
        'stem_groups': ['earl_grey', 'milk,sugar', 'spoon,cup,milk'],
        'stem_sources': [
            str(setup_stem_repo['workingcopy']),
            "fcm:foo.x_tr@head",
        ],
        'verbosity': 2,
    }

    monkeymodule.setattr('sys.argv', ['stem'])
    monkeymodule.chdir(setup_stem_repo['workingcopy'])
    parser, opts = get_rose_stem_opts()
    [setattr(opts, key, val) for key, val in rose_stem_opts.items()]

    with pytest.raises(
        RoseStemVersionException, match='1 but suite is at version 0'
    ):
        await rose_stem(parser, opts)


async def test_project_not_in_keywords(setup_stem_repo, monkeymodule, capsys):
    """It fails if it cannot extract project name from FCM keywords."""
    # Copy suite into working copy.
    monkeymodule.delenv('FCM_CONF_PATH')
    rose_stem_opts = {
        'stem_groups': ['earl_grey', 'milk,sugar', 'spoon,cup,milk'],
        'stem_sources': [
            str(setup_stem_repo['workingcopy']),
            "fcm:foo.x_tr@head",
        ],
    }

    monkeymodule.setattr('sys.argv', ['stem'])
    monkeymodule.chdir(setup_stem_repo['workingcopy'])
    parser, opts = get_rose_stem_opts()
    [setattr(opts, key, val) for key, val in rose_stem_opts.items()]

    await rose_stem(parser, opts)
    assert 'ProjectNotFoundException' in capsys.readouterr().err


async def test_picks_template_section(setup_stem_repo, monkeymodule, capsys):
    """test error message when project not in keywords

    Note, it can cope with template variables section being either
    ``template variables`` or ``jinja2:suite.rc``.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L234-L245
    """
    monkeymodule.setattr('sys.argv', ['stem'])
    monkeymodule.chdir(setup_stem_repo['workingcopy'])
    (setup_stem_repo['workingcopy'] / 'rose-stem/rose-suite.conf').write_text(
        'ROSE_STEM_VERSION=1\n'
        '[template_variables]\n'
    )
    parser, opts = get_rose_stem_opts()
    await rose_stem(parser, opts)
    _, err = capsys.readouterr()
    assert "[jinja2:suite.rc]' is deprecated" not in err
