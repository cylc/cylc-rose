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
"""
Tests for cylc.rose.stem
========================

Structure
---------

#. ``setup_stem_repo`` is a module scoped fixture which creates a Rose Stem
   repository which is used for all the tests.
#. ``rose_stem_run_template`` is a class scoped fixture, which runs a rose
   stem command. Most of the tests are encapsulated in classes to allow
   this expensive fixture to be run only once per class. Most of the tests
   check that the ``rose stem`` has returned 0, and then check that variables
   have been written to a job file.
#. For each test class there is a fixture encapsulating the test to be run.

.. code::

    ┌───────┬──────────┬───────────┬───────────┬───────────────┐
    │       │          │           │           │Test rose stem │
    │       │ test     │ rose stem │ Class     │returned 0     │
    │set-up │ specific │ runner    │ container ├───────────────┤
    │repo   │ fixture  │ fixture   │           │Test for output│
    │fixture│ (set up  │           │ Only run  │strings "foo"  │
    │       │ rose stem│ (run      │ class     ├───────────────┤
    │       │ command) │ rose stem)│ fixture   │Test for output│
    │       │          │           │ once      │strings "bar"  │
    │       ├──────────┼─ ── ── ── ├───────────┼───────────────┤
    │       │          │           │           │               │
    │       │          │           │           ├───────────────┤
    │       │          │           │           │               │
    │       │          │           │           ├───────────────┤
    │       │          │           │           │               │

Debugging
---------
Because of the tasks being run in subprocesses debugging can be a little
tricky. As a result there is a commented ``breakpoint`` in
``rose_stem_run_template`` indicating a location where it might be useful
to investigate failing tests.


"""
import os
import pytest
import shutil
import subprocess

from pathlib import Path
from shlex import split
from uuid import uuid4

from cylc.flow.pathutil import get_workflow_run_dir
from cylc.flow.hostuserutil import get_host

HOST = get_host().split('.')[0]


class SubprocessesError(Exception):
    ...


# Check that FCM is present on system, skipping checks elsewise:
try:
    subprocess.run(['fcm', '--version'])
except FileNotFoundError:
    pytest.skip("\"FCM\" not installed", allow_module_level=True)


@pytest.fixture(scope='module')
def monkeymodule():
    """Make monkeypatching available in a module scope.
    """
    from _pytest.monkeypatch import MonkeyPatch
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.fixture(scope='module')
def setup_stem_repo(tmp_path_factory, monkeymodule, request):
    """Setup a Rose Stem Repository for the tests.

    creates the following repo structure:

    .. code::

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
    basetemp = tmp_path_factory.getbasetemp()
    baseinstall = basetemp / 'baseinstall'
    rose_stem_dir = baseinstall / 'trunk/rose-stem'
    repo = basetemp / 'rose-test-battery-stemtest-repo'
    confdir = basetemp / 'conf'
    workingcopy = basetemp / f'cylc-rose-stem-test-{str(uuid4())[:8]}'
    for dir_ in [baseinstall, repo, rose_stem_dir, confdir, workingcopy]:
        dir_.mkdir(parents=True)

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
    yield {
        'basetemp': basetemp,
        'workingcopy': workingcopy,
        'suitename': suitename,
        'suite_install_dir': suite_install_dir
    }
    if not request.session.testsfailed:
        shutil.rmtree(suite_install_dir)


@pytest.fixture(scope='class')
def rose_stem_run_template(setup_stem_repo, pytestconfig):
    """Runs rose-stem and Cylc Play.

    Uses an inner function to allow inheriting fixtures to run different
    cylc-run commands.

    n.b. Subprocesses are run with capture_output so that running
    ``pytest --pdb`` allows one to inspect the stderr and stdout
    if a test fails.

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

    def _inner_fn(rose_stem_cmd, verbosity=verbosity):
        # Run rose-stem
        run_stem = subprocess.run(
            split(rose_stem_cmd), capture_output=True,
            cwd=setup_stem_repo['workingcopy']
        )

        # To assist with debugging fail horribly if the subproc'd rose-stem
        # command returns non-zero:
        if run_stem.returncode != 0:
            if verbosity > 1:
                # If -v print error details
                print('\n\t'.join(
                    [x.decode() for x in run_stem.stderr.split(b'\n')]
                ))
            if verbosity > 2:
                # If -vv print replication instructions.
                msg = (
                    'To reproduce failure outside test environment:'
                    f'\n\tcd {setup_stem_repo["workingcopy"]}'
                    f'\n\texport FCM_CONF_PATH={os.environ["FCM_CONF_PATH"]}'
                    f'\n\t{rose_stem_cmd}'
                )
                print(msg)
                # If you want to debug add a breakpoint here:
            msg = (
                f'rose-stem command:\n {rose_stem_cmd} failed with'
                f':\n{run_stem.stderr.decode()}'
            )
            raise SubprocessesError(msg)
        outputpath = (
            Path(setup_stem_repo['suite_install_dir']) /
            'runN/opt/rose-suite-cylc-install.conf'
        )
        output = outputpath.read_text()

        return {
            'run_stem': run_stem,
            'jobout_content': output,
            **setup_stem_repo
        }
    yield _inner_fn


@pytest.fixture(scope='class')
def rose_stem_run_basic(rose_stem_run_template, setup_stem_repo):
    rose_stem_cmd = (
        "rose stem --group=earl_grey --task=milk,sugar --group=spoon,cup,milk "
        f"--source={setup_stem_repo['workingcopy']} "
        "--source=\"fcm:foo.x_tr\"@head "
        f"--workflow-name {setup_stem_repo['suitename']}"
    )
    yield rose_stem_run_template(rose_stem_cmd)


class TestBasic():
    @pytest.mark.parametrize(
        'expected',
        [
            "run_ok",
            "RUN_NAMES=['earl_grey', 'milk', 'sugar', 'spoon', 'cup', 'milk']",
            "SOURCE_FOO=\"{workingcopy} fcm:foo.x_tr@head\"",
            "HOST_SOURCE_FOO=\"{hostname}:{workingcopy} fcm:foo.x_tr@head\"",
            "SOURCE_FOO_BASE=\"{workingcopy}\"\n",
            "SOURCE_FOO_BASE=\"{hostname}:{workingcopy}\"\n",
            "SOURCE_FOO_REV=\"\"\n",
            "SOURCE_FOO_MIRROR=\"fcm:foo.xm/trunk@1\"\n",
        ]
    )
    def test_basic(self, rose_stem_run_basic, expected):
        """Check that assorted variables have been exported.
        """
        if expected == 'run_ok':
            assert rose_stem_run_basic['run_stem'].returncode == 0
        else:
            expected = expected.format(
                workingcopy=rose_stem_run_basic['workingcopy'],
                hostname=HOST
            )
            assert expected in rose_stem_run_basic['jobout_content']


@pytest.fixture(scope='class')
def project_override(
    rose_stem_run_template, setup_stem_repo
):
    rose_stem_cmd = (
        "rose stem --group=earl_grey --task=milk,sugar --group=spoon,cup,milk "
        f"--source=bar={setup_stem_repo['workingcopy']} "
        "--source=fcm:foo.x_tr@head "
        f"--workflow-name {setup_stem_repo['suitename']}"
    )
    yield rose_stem_run_template(rose_stem_cmd)


class TestProjectOverride():
    @pytest.mark.parametrize(
        'expected',
        [
            "run_ok",
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
        ]
    )
    def test_project_override(self, project_override, expected):
        """Check that assorted variables have been exported.
        """
        if expected == 'run_ok':
            assert project_override['run_stem'].returncode == 0
        else:
            expected = expected.format(
                workingcopy=project_override['workingcopy'],
                hostname=HOST
            )
            assert expected in project_override['jobout_content']


@pytest.fixture(scope='class')
def suite_redirection(
    rose_stem_run_template, setup_stem_repo
):
    rose_stem_cmd = (
        f"rose stem {setup_stem_repo['workingcopy']}/rose-stem "
        "--group=lapsang "
        "--source=\"fcm:foo.x_tr\"@head "
        f"--workflow-name {setup_stem_repo['suitename']}"
    )
    yield rose_stem_run_template(rose_stem_cmd)


class TestSuiteRedirection:
    @pytest.mark.parametrize(
        'expected',
        [
            "run_ok",
            "RUN_NAMES=[\'lapsang\']",
            "SOURCE_FOO=\"fcm:foo.x_tr@head\"",
            "SOURCE_FOO_BASE=\"fcm:foo.x_tr\"",
            "SOURCE_FOO_REV=\"@1\"",
        ]
    )
    def test_suite_redirection(self, suite_redirection, expected):
        """Check that assorted variables have been exported.
        """
        if expected == 'run_ok':
            assert suite_redirection['run_stem'].returncode == 0
        else:
            expected = expected.format(
                workingcopy=suite_redirection['workingcopy'],
                hostname=HOST
            )
            assert expected in suite_redirection['jobout_content']


@pytest.fixture(scope='class')
def subdirectory(
    rose_stem_run_template, setup_stem_repo
):
    rose_stem_cmd = (
        "rose stem --group=assam "
        f"--source={setup_stem_repo['workingcopy']}/rose-stem "
        f"--workflow-name {setup_stem_repo['suitename']}"
    )
    yield rose_stem_run_template(rose_stem_cmd)


class TestSubdirectory:
    @pytest.mark.parametrize(
        'expected',
        [
            "run_ok",
            "RUN_NAMES=[\'assam\']",
            "SOURCE_FOO=\"{workingcopy}\"",
            "HOST_SOURCE_FOO=\"{hostname}:{workingcopy}\"",
            "SOURCE_FOO_BASE=\"{workingcopy}\"",
            "HOST_SOURCE_FOO_BASE=\"{hostname}:{workingcopy}\"",
            "SOURCE_FOO_REV=\"\"",
            "SOURCE_FOO_MIRROR=\"fcm:foo.xm/trunk@1\"",
        ]
    )
    def test_subdirectory(self, subdirectory, expected):
        """Check that assorted variables have been exported.
        """
        if expected == 'run_ok':
            assert subdirectory['run_stem'].returncode == 0
        else:
            expected = expected.format(
                workingcopy=subdirectory['workingcopy'],
                hostname=HOST
            )
            assert expected in subdirectory['jobout_content']


@pytest.fixture(scope='class')
def relative_path(
    rose_stem_run_template, setup_stem_repo
):
    rose_stem_cmd = (
        f"rose stem rose-stem --group=ceylon "
        f"--workflow-name {setup_stem_repo['suitename']}"
    )
    yield rose_stem_run_template(rose_stem_cmd)


class TestRelativePath:
    """Check relative path with src is working.
    """
    @pytest.mark.parametrize(
        'expected',
        [
            "run_ok",
            "RUN_NAMES=[\'ceylon\']",
            "SOURCE_FOO=\"{workingcopy}\"",
            "HOST_SOURCE_FOO=\"{hostname}:{workingcopy}\"",
            "SOURCE_FOO_BASE=\"{workingcopy}\"",
            "HOST_SOURCE_FOO_BASE=\"{hostname}:{workingcopy}\"",
            "SOURCE_FOO_REV=\"\"",
        ]
    )
    def test_relative_path(self, relative_path, expected):
        """Check that assorted variables have been exported.
        """
        if expected == 'run_ok':
            assert relative_path['run_stem'].returncode == 0
        else:
            expected = expected.format(
                workingcopy=relative_path['workingcopy'],
                hostname=HOST
            )
            assert expected in relative_path['jobout_content']


@pytest.fixture(scope='class')
def with_config(
    rose_stem_run_template, setup_stem_repo, monkeymodule
):
    """test for successful execution with site/user configuration
    """
    rose_stem_cmd = (
        "rose stem --group=earl_grey --task=milk,sugar --group=spoon,cup,milk "
        f"--source={setup_stem_repo['workingcopy']} "
        "--source=fcm:foo.x_tr@head "
        f"--workflow-name {setup_stem_repo['suitename']}"
    )
    (setup_stem_repo['basetemp'] / 'rose.conf').write_text(
        '[rose-stem]\n'
        'automatic-options=MILK=true\n'
    )
    monkeymodule.setenv(
        'ROSE_CONF_PATH', str(setup_stem_repo['basetemp'])
    )
    yield rose_stem_run_template(rose_stem_cmd)
    monkeymodule.delenv('ROSE_CONF_PATH')


class TestWithConfig:
    @pytest.mark.parametrize(
        'expected',
        [
            "run_ok",
            (
                "RUN_NAMES=[\'earl_grey\', \'milk\', \'sugar\', "
                "\'spoon\', \'cup\', \'milk\']"
            ),
            "SOURCE_FOO=\"{workingcopy} fcm:foo.x_tr@head\"",
            "HOST_SOURCE_FOO=\"{hostname}:{workingcopy} fcm:foo.x_tr@head\"",
            "SOURCE_FOO_BASE=\"{workingcopy}\"",
            "HOST_SOURCE_FOO_BASE=\"{hostname}:{workingcopy}\"",
            "SOURCE_FOO_REV=\"\"",
            "MILK=\"true\"",
        ]
    )
    def test_with_config(self, with_config, expected):
        """test for successful execution with site/user configuration
        """
        if expected == 'run_ok':
            assert with_config['run_stem'].returncode == 0
        else:
            expected = expected.format(
                workingcopy=with_config['workingcopy'],
                hostname=HOST
            )
            assert expected in with_config['jobout_content']


@pytest.fixture(scope='class')
def with_config2(
    rose_stem_run_template, setup_stem_repo, monkeymodule
):
    """test for successful execution with site/user configuration
    """
    rose_stem_cmd = (
        "rose stem --group=assam "
        f"--source={setup_stem_repo['workingcopy']}/rose-stem "
        f"--workflow-name {setup_stem_repo['suitename']}"
    )
    (setup_stem_repo['basetemp'] / 'rose.conf').write_text(
        '[rose-stem]\n'
        'automatic-options=MILK=true TEA=darjeeling\n'
    )
    monkeymodule.setenv(
        'ROSE_CONF_PATH', str(setup_stem_repo['basetemp'])
    )
    yield rose_stem_run_template(rose_stem_cmd)
    monkeymodule.delenv('ROSE_CONF_PATH')


class TestWithConfig2:
    @pytest.mark.parametrize(
        'expected',
        [
            "run_ok",
            "MILK=\"true\"\n",
            "TEA=\"darjeeling\"\n"
        ]
    )
    def test_with_config2(self, with_config2, expected):
        """test for successful execution with site/user configuration
        """
        if expected == 'run_ok':
            assert with_config2['run_stem'].returncode == 0
        else:
            expected = expected.format(
                workingcopy=with_config2['workingcopy'],
                hostname=HOST
            )
            assert expected in with_config2['jobout_content']


@pytest.fixture(scope='class')
def incompatible_versions(setup_stem_repo):
    # Copy suite into working copy.
    test_src_dir = Path(__file__).parent / '12_rose_stem'
    src = str(test_src_dir / 'rose-suite2.conf')
    dest = str(
        setup_stem_repo['workingcopy'] / 'rose-stem/rose-suite.conf'
    )
    shutil.copy2(src, dest)
    rose_stem_cmd = (
        "rose stem --group=earl_grey "
        "--task=milk,sugar"
        " --group=spoon,cup,milk "
        f"--source={setup_stem_repo['workingcopy']} "
        "--source=fcm:foo.x_tr@head "
        f"--workflow-name {setup_stem_repo['suitename']}"
    )

    run_stem = subprocess.run(
        split(rose_stem_cmd), capture_output=True,
        cwd=setup_stem_repo['workingcopy']
    )
    yield run_stem
    test_src_dir = Path(__file__).parent / '12_rose_stem'
    src = str(test_src_dir / 'rose-suite.conf')
    dest = str(
        setup_stem_repo['workingcopy'] / 'rose-stem/rose-suite.conf'
    )
    shutil.copy2(src, dest)


class TestIncompatibleVersions:
    def test_incompatible_versions(self, incompatible_versions):
        """test for successful execution with site/user configuration
        """

        assert incompatible_versions.returncode == 1
        assert (b'Running rose-stem version 1 but suite is at version 0'
                in incompatible_versions.stderr
                )


@pytest.fixture(scope='class')
def project_not_in_keywords(setup_stem_repo, monkeymodule):
    # Copy suite into working copy.
    monkeymodule.delenv('FCM_CONF_PATH')
    rose_stem_cmd = (
        "rose stem --group=earl_grey "
        "--task=milk,sugar"
        " --group=spoon,cup,milk "
        f"--source={setup_stem_repo['workingcopy']} "
        "--source=fcm:foo.x_tr@head "
        f"--workflow-name {setup_stem_repo['suitename']}"
    )

    run_stem = subprocess.run(
        split(rose_stem_cmd), capture_output=True,
        cwd=setup_stem_repo['workingcopy']
    )
    yield run_stem


class TestProjectNotInKeywords:
    def test_project_not_in_keywords(self, project_not_in_keywords):
        """test for successful execution with site/user configuration
        """
        assert project_not_in_keywords.returncode == 1
        assert (b'Cannot ascertain project for source tree' in
                project_not_in_keywords.stderr
                )
