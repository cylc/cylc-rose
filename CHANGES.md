# Selected Cylc-Rose Changes

<!-- The topmost release date is automatically updated by GitHub Actions. When
creating a new release entry be sure to copy & paste the span tag with the
`actions:bind` attribute, which is used by a regex to find the text to be
updated. Only the first match gets replaced, so it's fine to leave the old
ones in. -->

## __cylc-rose-1.4.0 (<span actions:bind='release-date'>Released 2024-07-23</span>)__

### Features

[#269](https://github.com/cylc/cylc-rose/pull/269) - Allow environment variables
set in ``rose-suite.conf`` to be used when parsing ``global.cylc``.

### Fixes

[#319](https://github.com/cylc/cylc-rose/pull/319) - Prevent Cylc Rose
from modifying Cylc's compatibility mode.


## __cylc-rose-1.3.4 (<span actions:bind='release-date'>Released 2024-05-02</span>)__

[#312](https://github.com/cylc/cylc-rose/pull/312) - Fixed an issue that could cause the cylc-rose CLI options (`-S`, `-D`, `-O`) to be applied incorrectly.


## __cylc-rose-1.3.3 (<span actions:bind='release-date'>Released 2024-04-05</span>)__

### Fixes

[#302](https://github.com/cylc/cylc-rose/pull/302) -
Fix issues which could cause "fcm_make" and "rose_prune" tasks intermittently
fail with the message
"Workflow database is incompatible with Cylc x.y.z, or is corrupted".


## __cylc-rose-1.3.2 (<span actions:bind='release-date'>Released 2024-01-18</span>)__

[#284](https://github.com/cylc/cylc-rose/pull/284) - Allow use of Metomi-Rose 2.2.*.


## __cylc-rose-1.3.1 (<span actions:bind='release-date'>Released 2023-10-24</span>)__

### Fixes

[#250](https://github.com/cylc/cylc-rose/pull/250) - Prevent project
name being manually set to an empty string.

[#225](https://github.com/cylc/cylc-rose/pull/225) - Prevent totally invalid
CLI --defines with no = sign.

[#248](https://github.com/cylc/cylc-rose/pull/248) - Make sure that
rose stem sets variables in `[jinja2:suite.rc]` not `[jinja2]`.

## __cylc-rose-1.3.0 (<span actions:bind='release-date'>Released 2023-07-21</span>)__

### Fixes

[#229](https://github.com/cylc/cylc-rose/pull/229) -
Fix bug which stops rose-stem suites using the new `[template variables]` section
in their `rose-suite.conf` files.

[#231](https://github.com/cylc/cylc-rose/pull/231) - Show warning about
`root-dir` config setting in compatibility mode.

## __cylc-rose-1.2.0 (<span actions:bind='release-date'>Released 2023-01-16</span>)__

### Fixes

[#192](https://github.com/cylc/cylc-rose/pull/192) -
Fix bug where Cylc Rose would prevent change to template language on reinstall.

[#180](https://github.com/cylc/cylc-rose/pull/180) -
Rose stem gets stem suite's basename to use as workflow name when not otherwise
set.

## __cylc-rose-1.1.1 (<span actions:bind='release-date'>Released 2022-09-14</span>)__

### Fixes

[#171](https://github.com/cylc/cylc-rose/pull/171) - Fix bug where Cylc Rose
passed `rose-suite.conf` items commented with `!` or `!!` to Cylc regardless.

[#172](https://github.com/cylc/cylc-rose/pull/172) - Allow getting a workflow
name when source is not an SVN repo.

## __cylc-rose-1.1.0 (<span actions:bind='release-date'>Released 2022-07-28</span>)__

### Fixes

[#140](https://github.com/cylc/cylc-rose/pull/140) -
Support integers with leading zeros (e.g `001`) to back support Rose
configurations for use with cylc-flow>=8.0rc4 which uses Jinja2 v3 which
no longer supports this.

[#155](https://github.com/cylc/cylc-rose/pull/155) -
Use the public rather than private database for platform lookups. This resolves
a database locking issue with the `rose_prune` built-in app.

## __cylc-rose-1.0.3 (<span actions:bind='release-date'>Released 2022-05-20</span>)__

### Fixes

[#139](https://github.com/cylc/cylc-rose/pull/139) - Make `rose stem` command
work correctly with changes made to `cylc install` in
[cylc-flow PR #4823](https://github.com/cylc/cylc-flow/pull/4823)

[#130](https://github.com/cylc/cylc-rose/pull/130) - Fix bug preventing
``cylc reinstall`` using Rose fileinstall.

[#132](https://github.com/cylc/cylc-rose/pull/132) - Fix bug preventing
Cylc commands (other than `install`) from accessing the content of
`--rose-template-variable`.

[#133](https://github.com/cylc/cylc-rose/pull/133) - Fix bug allowing setting
multiple template variable sections.

## __cylc-rose-1.0.2 (<span actions:bind='release-date'>Released 2022-03-24</span>)__

### Fixes

[118](https://github.com/cylc/cylc-rose/pull/118) - Fail if
a workflow is not a Rose Suite but user provides Rose CLI options.

## __cylc-rose-1.0.1 (Released 2022-02-17)__

First official release of Cylc-Rose.

Implements interfaces to allow the use of Rose suite configurations with
Cylc 8.

> **Note:**
> The `1.0.1` was preceeded by the `1.0.0` release which had incorrect metadata.
