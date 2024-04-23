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
from types import SimpleNamespace
from uuid import uuid4

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
            basetemp:
                The location of the base temporary file, which allows tests
                to modify any part of the rose-stem suite.
            workingcopy:
                Path to the location of the working copy.
            suitename:
                The name of the suite, which will be name of the suite/workflow
                installed in ``~/cylc-run``.
            suite_install_directory:
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
        'basetemp': basetemp,
        'workingcopy': workingcopy,
        'suitename': suitename,
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
def rose_stem_run_template(setup_stem_repo, pytestconfig, monkeymodule):
    """Runs rose-stem.

    Uses an inner function to allow inheriting fixtures to run different
    cylc-run commands.

    Args:
        setup_stem_repo (function):
            Pytest fixture function setting up the structure of a rose-stem
            suite

    Yields:
        function which can be give a rose-stem command. This function returns:
            dict:
                'run_stem': subprocess.CompletedProcess
                    The results of running rose-stem.
                'jobout_content': str
                    Content of test job output file.
                ``**setup_stem_repo``:
                    Unpack all yields from setup_stem_repo.
    """
    verbosity = pytestconfig.getoption('verbose')

    async def _inner_fn(rose_stem_opts, verbosity=verbosity):
        monkeymodule.setattr('sys.argv', ['stem'])
        monkeymodule.chdir(setup_stem_repo['workingcopy'])
        parser, opts = get_rose_stem_opts()
        [setattr(opts, key, val) for key, val in rose_stem_opts.items()]

        run_stem = SimpleNamespace()
        run_stem.stdout = ''
        try:
            await rose_stem(parser, opts)
            run_stem.returncode = 0
            run_stem.stderr = ''
        except Exception as exc:
            run_stem.returncode = 1
            run_stem.stderr = exc

        return {
            'run_stem': run_stem,
            'jobout_content': (
                Path(setup_stem_repo['suite_install_dir']) /
                'runN/opt/rose-suite-cylc-install.conf'
            ).read_text(),
            **setup_stem_repo
        }

    yield _inner_fn


async def test_rose_stem_run_really_basic(
    rose_stem_run_template,
    setup_stem_repo,
):
    rose_stem_opts = {
        'stem_groups': [],
        'stem_sources': [
            str(setup_stem_repo['workingcopy']), "fcm:foo.x_tr@head"
        ],
    }
    plugin_result = await rose_stem_run_template(rose_stem_opts)
    assert plugin_result['run_stem'].returncode == 0


async def test_rose_stem_run_basic(
    rose_stem_run_template,
    setup_stem_repo,
):
    rose_stem_opts = {
        'stem_groups': ['earl_grey', 'milk,sugar', 'spoon,cup,milk'],
        'stem_sources': [
            str(setup_stem_repo['workingcopy']), "fcm:foo.x_tr@head"
        ],
        'workflow_name': setup_stem_repo['suitename']
    }
    plugin_result = await rose_stem_run_template(rose_stem_opts)

    assert plugin_result['run_stem'].returncode == 0

    for line in [
        "RUN_NAMES=['earl_grey', 'milk', 'sugar', 'spoon', 'cup', 'milk']",
        "SOURCE_FOO=\"{workingcopy} fcm:foo.x_tr@head\"",
        "HOST_SOURCE_FOO=\"{hostname}:{workingcopy} fcm:foo.x_tr@head\"",
        "SOURCE_FOO_BASE=\"{workingcopy}\"\n",
        "SOURCE_FOO_BASE=\"{hostname}:{workingcopy}\"\n",
        "SOURCE_FOO_REV=\"\"\n",
        "SOURCE_FOO_MIRROR=\"fcm:foo.xm/trunk@1\"\n",
    ]:
        line = line.format(
            workingcopy=plugin_result['workingcopy'],
            hostname=HOST
        )
        assert line in plugin_result['jobout_content']


async def test_project_override(rose_stem_run_template, setup_stem_repo):
    rose_stem_opts = {
        'stem_groups': ['earl_grey', 'milk,sugar', 'spoon,cup,milk'],
        'stem_sources': [
            f'bar={str(setup_stem_repo["workingcopy"])}', "fcm:foo.x_tr@head"
        ],
        'workflow_name': setup_stem_repo['suitename']
    }
    plugin_result = await rose_stem_run_template(rose_stem_opts)
    assert plugin_result['run_stem'].returncode == 0
    for line in [
        (
            "RUN_NAMES=[\'earl_grey\', \'milk\', \'sugar\', "
            "\'spoon\', \'cup\', \'milk\']"
        ),
        "SOURCE_FOO=\"fcm:foo.x_tr@head\"",
        "HOST_SOURCE_FOO=\"fcm:foo.x_tr@head\"",
        "SOURCE_BAR=\"{workingcopy}\"",
        "HOST_SOURCE_BAR=\"{hostname}:{workingcopy}\"",
        "SOURCE_FOO_BASE=\"fcm:foo.x_tr\"",
        "HOST_SOURCE_FOO_BASE=\"fcm:foo.x_tr\"",
        "SOURCE_BAR_BASE=\"{workingcopy}\"",
        "HOST_SOURCE_BAR_BASE=\"{hostname}:{workingcopy}\"",
        "SOURCE_FOO_REV=\"@1\"",
        "SOURCE_BAR_REV=\"\"",
        "SOURCE_FOO_MIRROR=\"fcm:foo.xm/trunk@1\"",
    ]:
        line = line.format(
            workingcopy=plugin_result['workingcopy'],
            hostname=HOST
        )
        assert line in plugin_result['jobout_content']


async def test_suite_redirection(rose_stem_run_template, setup_stem_repo):
    """Check that assorted variables have been exported."""
    rose_stem_opts = {
        'workflow_conf_dir': f'{setup_stem_repo["workingcopy"]}/rose-stem',
        'stem_groups': ['lapsang'],
        'stem_sources': ["fcm:foo.x_tr@head"],
        'workflow_name': setup_stem_repo['suitename']
    }
    plugin_result = await rose_stem_run_template(rose_stem_opts)
    assert plugin_result['run_stem'].returncode == 0
    for line in [
        "RUN_NAMES=[\'lapsang\']",
        "SOURCE_FOO=\"fcm:foo.x_tr@head\"",
        "SOURCE_FOO_BASE=\"fcm:foo.x_tr\"",
        "SOURCE_FOO_REV=\"@1\"",
    ]:
        line = line.format(
            workingcopy=plugin_result['workingcopy'],
            hostname=HOST
        )
        assert line in plugin_result['jobout_content']


async def test_subdirectory(rose_stem_run_template, setup_stem_repo):
    """Check that assorted variables have been exported."""
    rose_stem_opts = {
        'stem_groups': ['assam'],
        'stem_sources': [f'{setup_stem_repo["workingcopy"]}/rose-stem'],
        'workflow_name': setup_stem_repo['suitename']
    }
    plugin_result = await rose_stem_run_template(rose_stem_opts)
    assert plugin_result['run_stem'].returncode == 0
    for line in [
        "RUN_NAMES=[\'assam\']",
        "SOURCE_FOO=\"{workingcopy}\"",
        "HOST_SOURCE_FOO=\"{hostname}:{workingcopy}\"",
        "SOURCE_FOO_BASE=\"{workingcopy}\"",
        "HOST_SOURCE_FOO_BASE=\"{hostname}:{workingcopy}\"",
        "SOURCE_FOO_REV=\"\"",
        "SOURCE_FOO_MIRROR=\"fcm:foo.xm/trunk@1\"",
    ]:
        line = line.format(
            workingcopy=plugin_result['workingcopy'],
            hostname=HOST
        )
        assert line in plugin_result['jobout_content']


async def test_relative_path(rose_stem_run_template, setup_stem_repo):
    """Check that assorted variables have been exported."""
    rose_stem_opts = {
        'workflow_conf_dir': './rose-stem',
        'stem_groups': ['ceylon'],
        'workflow_name': setup_stem_repo['suitename']
    }
    plugin_result = await rose_stem_run_template(rose_stem_opts)
    assert plugin_result['run_stem'].returncode == 0
    for line in [
        "RUN_NAMES=[\'ceylon\']",
        "SOURCE_FOO=\"{workingcopy}\"",
        "HOST_SOURCE_FOO=\"{hostname}:{workingcopy}\"",
        "SOURCE_FOO_BASE=\"{workingcopy}\"",
        "HOST_SOURCE_FOO_BASE=\"{hostname}:{workingcopy}\"",
        "SOURCE_FOO_REV=\"\"",
    ]:
        line = line.format(
            workingcopy=plugin_result['workingcopy'],
            hostname=HOST
        )
        assert line in plugin_result['jobout_content']


async def test_with_config(
    rose_stem_run_template, setup_stem_repo, mock_global_cfg
):
    """Test for successful execution with site/user configuration."""
    rose_stem_opts = {
        'stem_groups': ['earl_grey', 'milk,sugar', 'spoon,cup,milk'],
        'stem_sources': [
            f'{setup_stem_repo["workingcopy"]}', 'fcm:foo.x_tr@head'],
        'workflow_name': setup_stem_repo['suitename']
    }
    mock_global_cfg(
        'cylc.rose.stem.ResourceLocator.default',
        '[rose-stem]\nautomatic-options = MILK=true',
    )
    plugin_result = await rose_stem_run_template(rose_stem_opts)
    assert plugin_result['run_stem'].returncode == 0
    for line in [
        "RUN_NAMES=['earl_grey', 'milk', 'sugar', 'spoon', 'cup', 'milk']",
        'SOURCE_FOO="{workingcopy} fcm:foo.x_tr@head"',
        'HOST_SOURCE_FOO="{hostname}:{workingcopy} fcm:foo.x_tr@head"',
        'SOURCE_FOO_BASE="{workingcopy}"',
        'HOST_SOURCE_FOO_BASE="{hostname}:{workingcopy}"',
        'SOURCE_FOO_REV=""',
        'MILK="true"',
    ]:
        line = line.format(
            **plugin_result,
            hostname=HOST
        )
        assert line in plugin_result['jobout_content']


async def test_with_config2(
    rose_stem_run_template, setup_stem_repo, mock_global_cfg
):
    """Test for successful execution with site/user configuration."""
    rose_stem_opts = {
        'stem_groups': ['assam'],
        'stem_sources': [
            f'{setup_stem_repo["workingcopy"]}'],
        'workflow_name': setup_stem_repo['suitename']
    }
    mock_global_cfg(
        'cylc.rose.stem.ResourceLocator.default',
        '[rose-stem]\nautomatic-options = MILK=true TEA=darjeeling',
    )
    plugin_result = await rose_stem_run_template(rose_stem_opts)
    assert plugin_result['run_stem'].returncode == 0
    for line in [
        'MILK="true"',
        'TEA="darjeeling"',
    ]:
        line = line.format(
            **plugin_result,
            hostname=HOST
        )
        assert line in plugin_result['jobout_content']


async def test_incompatible_versions(setup_stem_repo, monkeymodule):
    """It fails if trying to install an incompatible version.
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
        'workflow_name': str(setup_stem_repo['suitename']),
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
    """It fails if it cannot extract project name from FCM keywords.
    """
    # Copy suite into working copy.
    monkeymodule.delenv('FCM_CONF_PATH')
    rose_stem_opts = {
        'stem_groups': ['earl_grey', 'milk,sugar', 'spoon,cup,milk'],
        'stem_sources': [
            str(setup_stem_repo['workingcopy']),
            "fcm:foo.x_tr@head",
        ],
        'workflow_name': str(setup_stem_repo['suitename'])
    }

    monkeymodule.setattr('sys.argv', ['stem'])
    monkeymodule.chdir(setup_stem_repo['workingcopy'])
    parser, opts = get_rose_stem_opts()
    [setattr(opts, key, val) for key, val in rose_stem_opts.items()]

    await rose_stem(parser, opts)

    assert 'ProjectNotFoundException' in capsys.readouterr().err


async def test_picks_template_section(setup_stem_repo, monkeymodule, capsys):
    """It can cope with template variables section being either
    ``template variables`` or ``jinja2:suite.rc``.
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
