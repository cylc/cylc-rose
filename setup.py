#!/usr/bin/env python3
# THIS FILE IS PART OF THE ROSE-CYLC PLUGIN FOR THE CYLC SUITE ENGINE.
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

from setuptools import setup, find_namespace_packages

# load __version__ number from the source
exec(open('cylc/rose/__init__.py', 'r').read())


with open("README.md", "r") as fh:
    long_description = fh.read()


INSTALL_REQUIRES = [
    'metomi-rose>=2.0b1',
    'cylc-flow>=8.0b0',
]
EXTRAS_REQUIRE = {
}
TESTS_REQUIRE = [
    'coverage>=5.0.0',
    'flake8',
    'pytest',
    'pytest_cov',
]
EXTRAS_REQUIRE['all'] = list(
    {
        y
        for x in EXTRAS_REQUIRE.values()
        for y in x
    }
) + TESTS_REQUIRE

setup(
    name='cylc-rose',
    version=__version__,   # noqa
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    tests_require=TESTS_REQUIRE,
    package_data={'cylc.rose': ['py.typed']},
    packages=find_namespace_packages(include=["cylc.*"]),
)
