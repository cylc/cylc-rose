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
from uuid import uuid4
from typing import Dict

from metomi.rose.host_select import HostSelector

import pytest

from cylc.rose.stem import RoseStemVersionException

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


@pytest.fixture(scope='module')
def rose_stem_project(tmp_path_factory, monkeymodule, request):
    """A Rose Stem project's root directory.

    The project has the following structure::

       <rose_stem_project>/
       |-- baseinstall/
       |   `-- trunk/
       |       `-- rose-stem
       |-- conf/
       |   `-- keyword.cfg
       |-- cylc-rose-stem-test-project-1df3e028/
       |   `-- rose-stem/
       |       |-- flow.cylc
       |       `-- rose-suite.conf
       `-- rose-test-battery-stemtest-repo/
           `-- foo/
               `- <truncated>

    """
    # Set up required folders:
    basetemp = tmp_path_factory.getbasetemp() / request.module.__name__
    baseinstall = basetemp / 'baseinstall'
    rose_stem_dir = baseinstall / 'trunk/rose-stem'
    repo = basetemp / 'rose-test-battery-stemtest-repo'
    confdir = basetemp / 'conf'
    workingcopy = basetemp / f'cylc-rose-stem-test-project-{str(uuid4())[:8]}'
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
    subprocess.run(split(f'fcm checkout -q fcm:foo.x_tr {workingcopy}'))
    # Copy suite into working copy.
    test_src_dir = Path(__file__).parent / '12_rose_stem'
    for file in ['rose-suite.conf', 'flow.cylc']:
        src = str(test_src_dir / file)
        dest = str(workingcopy / 'rose-stem')
        shutil.copy2(src, dest)

    monkeymodule.setattr(
        'cylc.flow.pathutil.make_symlink_dir',
        lambda *_, **__: {}
    )

    return workingcopy


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


async def test_hello_world(rose_stem, rose_stem_project):
    """It should run a hello-world example without erroring."""
    await rose_stem(
        rose_stem_project,
        stem_groups=[],
        stem_sources=[str(rose_stem_project), "fcm:foo.x_tr@head"],
    )


async def test_template_variables(rose_stem, rose_stem_project):
    """It should set various template variables.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L56-L78
    """
    template_vars = await rose_stem(
        rose_stem_project,
        stem_groups=['earl_grey', 'milk,sugar', 'spoon,cup,milk'],
        stem_sources=[str(rose_stem_project), "fcm:foo.x_tr@head"],
    )

    check_template_variables(
        {
            "RUN_NAMES":
                "['earl_grey', 'milk', 'sugar', 'spoon', 'cup', 'milk']",
            "SOURCE_FOO":
                f'"{rose_stem_project} fcm:foo.x_tr@head"',
            "HOST_SOURCE_FOO":
                f'"{HOST}:{rose_stem_project} '
                'fcm:foo.x_tr@head"',
            "SOURCE_FOO_BASE":
                f'"{rose_stem_project}"',
            "HOST_SOURCE_FOO_BASE":
                f'"{HOST}:{rose_stem_project}"',
            "SOURCE_FOO_REV":
                '""',
            "SOURCE_FOO_MIRROR":
                '"fcm:foo.xm/trunk@1"',
        },
        template_vars,
    )


async def test_manual_project_override(rose_stem, rose_stem_project):
    """It should accept named project sources.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L80-L112
    """
    template_vars = await rose_stem(
        rose_stem_project,
        stem_groups=["earl_grey", "milk,sugar", "spoon,cup,milk"],
        stem_sources=[
            # specify a named source called "bar"
            f'bar={rose_stem_project}',
            "fcm:foo.x_tr@head",
        ],
    )

    check_template_variables(
        {
            "RUN_NAMES":
                "['earl_grey', 'milk', 'sugar', " "'spoon', 'cup', 'milk']",
            "SOURCE_FOO": '"fcm:foo.x_tr@head"',
            "HOST_SOURCE_FOO": '"fcm:foo.x_tr@head"',
            "SOURCE_BAR": f'"{rose_stem_project}"',
            "HOST_SOURCE_BAR": f'"{HOST}:{rose_stem_project}"',
            "SOURCE_FOO_BASE": '"fcm:foo.x_tr"',
            "HOST_SOURCE_FOO_BASE": '"fcm:foo.x_tr"',
            "SOURCE_BAR_BASE": f'"{rose_stem_project}"',
            "HOST_SOURCE_BAR_BASE": f'"{HOST}:{rose_stem_project}"',
            "SOURCE_FOO_REV": '"@1"',
            "SOURCE_BAR_REV": '""',
            "SOURCE_FOO_MIRROR": '"fcm:foo.xm/trunk@1"',
        },
        template_vars,
    )


async def test_config_dir_absolute(rose_stem, rose_stem_project):
    """It should allow you to specify the config directory as an absolute path.

    This is an alternative approach to running the "rose stem" command
    in the directory itelf.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L114-L128
    """
    template_vars = await rose_stem(
        rose_stem_project,
        workflow_conf_dir=f'{rose_stem_project}/rose-stem',
        stem_groups=['lapsang'],
        stem_sources=["fcm:foo.x_tr@head"],
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


async def test_config_dir_relative(rose_stem, rose_stem_project):
    """It should allow you to specify the config directory as a relative path.

    This is an alternative approach to running the "rose stem" command
    in the directory itelf.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L152-L171
    """
    template_vars = await rose_stem(
        rose_stem_project,
        workflow_conf_dir='./rose-stem',
        stem_groups=['ceylon'],
    )
    check_template_variables(
        {
            "RUN_NAMES": "['ceylon']",
            "SOURCE_FOO": f'"{rose_stem_project}"',
            "HOST_SOURCE_FOO": f'"{HOST}:{rose_stem_project}"',
            "SOURCE_FOO_BASE": f'"{rose_stem_project}"',
            "HOST_SOURCE_FOO_BASE": f'"{HOST}:{rose_stem_project}"',
            "SOURCE_FOO_REV": '""',
        },
        template_vars,
    )


async def test_source_in_a_subdirectory(rose_stem, rose_stem_project):
    """It should accept a source in a subdirectory.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L130-L150
    """
    template_vars = await rose_stem(
        rose_stem_project,
        stem_groups=['assam'],
        # stem source in a sub directory
        stem_sources=[f'{rose_stem_project / "rose-stem"}'],
    )
    check_template_variables(
        {
            "RUN_NAMES": "['assam']",
            "SOURCE_FOO": f'"{rose_stem_project}"',
            "HOST_SOURCE_FOO": f'"{HOST}:{rose_stem_project}"',
            "SOURCE_FOO_BASE": f'"{rose_stem_project}"',
            "HOST_SOURCE_FOO_BASE": f'"{HOST}:{rose_stem_project}"',
            "SOURCE_FOO_REV": '""',
            "SOURCE_FOO_MIRROR": '"fcm:foo.xm/trunk@1"',
        },
        template_vars,
    )


async def test_automatic_options(
    rose_stem,
    rose_stem_project,
    mock_global_cfg,
):
    """It should use automatic options from the site/user configuration.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L182-L204
    """
    mock_global_cfg(
        'cylc.rose.stem.ResourceLocator.default',
        # automatic options defined in the site/user config
        '[rose-stem]\nautomatic-options = MILK=true',
    )
    template_vars = await rose_stem(
        rose_stem_project,
        stem_groups=['earl_grey', 'milk,sugar', 'spoon,cup,milk'],
        stem_sources=[f'{rose_stem_project}', 'fcm:foo.x_tr@head'],
    )
    check_template_variables(
        {
            "RUN_NAMES":
                "['earl_grey', 'milk', 'sugar', 'spoon', 'cup', 'milk']",
            "SOURCE_FOO":
                f'"{rose_stem_project} fcm:foo.x_tr@head"',
            "HOST_SOURCE_FOO":
                f'"{HOST}:{rose_stem_project} fcm:foo.x_tr@head"',
            "SOURCE_FOO_BASE":
                f'"{rose_stem_project}"',
            "HOST_SOURCE_FOO_BASE":
                f'"{HOST}:{rose_stem_project}"',
            "SOURCE_FOO_REV":
                '""',
            "MILK":
                '"true"',
        },
        template_vars,
    )


async def test_automatic_options_multi(
    rose_stem, rose_stem_project, mock_global_cfg
):
    """It should use MULTIPLE automatic options from the site/user conf.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L206-L221
    """
    mock_global_cfg(
        'cylc.rose.stem.ResourceLocator.default',
        # *multiple* automatic options defined in the site/user config
        '[rose-stem]\nautomatic-options = MILK=true TEA=darjeeling',
    )
    template_vars = await rose_stem(
        rose_stem_project,
        stem_groups=['assam'],
        stem_sources=[f'{rose_stem_project}'],
    )
    check_template_variables(
        {
            "MILK": '"true"',
            "TEA": '"darjeeling"',
        },
        template_vars,
    )


async def test_incompatible_rose_stem_versions(rose_stem_project, rose_stem):
    """It should fail if trying to install an incompatible rose-stem config.

    Rose Stem configurations must specify a Rose Stem version, it should fail
    if the versions don't match.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L223-L232
    """
    # Copy suite into working copy.
    test_src_dir = Path(__file__).parent / '12_rose_stem'
    src = str(test_src_dir / 'rose-suite2.conf')
    dest = str(
        rose_stem_project / 'rose-stem/rose-suite.conf'
    )
    shutil.copy2(src, dest)

    with pytest.raises(
        RoseStemVersionException, match='1 but suite is at version 0'
    ):
        await rose_stem(
            rose_stem_project,
            stem_groups=['earl_grey', 'milk,sugar', 'spoon,cup,milk'],
            stem_sources=[str(rose_stem_project), "fcm:foo.x_tr@head"],
            verbosity=2,
        )


async def test_project_not_in_keywords(
    rose_stem_project,
    rose_stem,
    monkeypatch,
    capsys,
):
    """It fails if it cannot extract project name from FCM keywords."""
    # Copy suite into working copy.
    monkeypatch.delenv('FCM_CONF_PATH')
    await rose_stem(
        rose_stem_project,
        stem_groups=['earl_grey', 'milk,sugar', 'spoon,cup,milk'],
        stem_sources=[str(rose_stem_project), "fcm:foo.x_tr@head"],
    )
    assert 'ProjectNotFoundException' in capsys.readouterr().err


async def test_picks_template_section(rose_stem_project, rose_stem, capsys):
    """test error message when project not in keywords

    Note, it can cope with template variables section being either
    ``template variables`` or ``jinja2:suite.rc``.

    https://github.com/metomi/rose/blob/2c8956a9464bd277c8eb24d38af4803cba4c1243/t/rose-stem/00-run-basic.t#L234-L245
    """
    (rose_stem_project / 'rose-stem/rose-suite.conf').write_text(
        'ROSE_STEM_VERSION=1\n'
        '[template_variables]\n'
    )
    await rose_stem(rose_stem_project)
    _, err = capsys.readouterr()
    assert "[jinja2:suite.rc]' is deprecated" not in err
