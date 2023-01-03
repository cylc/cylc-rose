# Cylc-Rose Plugin

[![PyPI](https://img.shields.io/pypi/v/cylc-rose)](https://pypi.org/project/cylc-rose/)
[![tests](https://github.com/cylc/cylc-rose/actions/workflows/tests.yml/badge.svg)](https://github.com/cylc/cylc-rose/actions/workflows/tests.yml)
[![Codecov](https://img.shields.io/codecov/c/github/cylc/cylc-rose)](https://app.codecov.io/gh/cylc/cylc-rose)

A [Cylc](https://github.com/cylc/cylc-flow) plugin providing support for the
[Rose](https://github.com/metomi/rose) `rose-suite.conf` file.

For use with Cylc 8 and Rose 2.

### Installation

Install from PyPi:

```
pip install cylc-rose
```

Or Conda:

```
conda install cylc-rose
```

No further configuration is required, Cylc will load this plugin automatically.

### Overview

In the past Rose provided a wrapper to Cylc providing additional capabilities
including workflow installation.

As of Cylc 8 and Rose 2 some of this functionality has been re-built directly
in Cylc, the rest has been migrated into this Plugin.

The last versions of Cylc and Rose which use the wrapper are:

* Cylc 7
* Rose 2019

For all later versions please install this plugin into your Cylc/Rose
environment for Rose integration.

### What This Plugin Does

This plugin provides support for the `rose-suite.conf` file, namely:

* Jinja2/EmPy template variables.
* Scheduler environment variables.
* File installation.
* Optional configurations.

### What This Plugin Does Not Do

* Support the `root-dir*` configurations, these have been deprecated by
  the new Cylc `symlink dirs` functionality.
* Graphical configuration editors.

### Contributing

[![Contributors](https://img.shields.io/github/contributors/cylc/cylc-rose.svg?color=9cf)](https://github.com/cylc/cylc-rose/graphs/contributors)
[![Commit activity](https://img.shields.io/github/commit-activity/m/cylc/cylc-rose.svg?color=yellowgreen)](https://github.com/cylc/cylc-rose/commits/master)
[![Last commit](https://img.shields.io/github/last-commit/cylc/cylc-rose.svg?color=ff69b4)](https://github.com/cylc/cylc-rose/commits/master)

* Read the [contributing](CONTRIBUTING.md) page.
* Development setup instructions are in the
  [developer docs](https://cylc.github.io/cylc-admin/#cylc-8-developer-docs).
* Involved change proposals can be found in the
  [admin pages](https://cylc.github.io/cylc-admin/#change-proposals).
* Touch base in the
  [developers chat](https://matrix.to/#/#cylc-general:matrix.org).

> **Note:** If also developing Cylc and or Rose you may wish to install
  cylc-rose in the same environment before installing cylc-rose.

```
pip install -e cylc-rose[all]
```

### Copyright and Terms of Use

[![License](https://img.shields.io/github/license/cylc/cylc-flow.svg?color=lightgrey)](https://github.com/cylc/cylc-flow/blob/master/COPYING)

Copyright (C) 2008-<span actions:bind='current-year'>2023</span> NIWA &
British Crown (Met Office) & Contributors.

Cylc-rose is free software: you can redistribute it and/or modify it under the terms
of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

Cylc-rose is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
Cylc-rose.  If not, see [GNU licenses](http://www.gnu.org/licenses/).
