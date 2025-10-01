# Selected Cylc-Rose Changes

<!--
NOTE: Do not add entries here, use towncrier fragments instead:
$ towncrier create <PR-number>.<break|feat|fix>.md --content "Short description"
-->

<!-- towncrier release notes start -->

## 1.7.0 (Released 2025-10-01)

### ⚠️ Breaking changes

[#384](https://github.com/cylc/cylc-rose/pull/384) - Minimum supported Python version is now 3.12.

## 1.6.1 (Released 2025-09-19)

### 🔧 Fixes

[#386](https://github.com/cylc/cylc-rose/pull/386) - Ensure `rose_prune` skips platforms that cannot be found.

## 1.6.0 (Released 2025-07-24)

Updated for cylc-flow 8.5.0 and metomi-rose 2.5.0.

## 1.5.1 (Released 2025-04-07)

[#361](https://github.com/cylc/cylc-rose/pull/361) -
Rose stem now uses long hostnames for the `HOST_SOURCE...` variables to match
`ROSE_ORIG_HOST`.

## 1.5.0 (Released 2025-01-09)

[#353](https://github.com/cylc/cylc-rose/pull/353) - Remove Empy support.
Cylc has dropped empy support at Cylc 8.4.0.

## 1.4.2 (Released 2024-11-07)

[#345](https://github.com/cylc/cylc-rose/pull/345) - Fix an issue
where `cylc vr` could report erroneous validation failures.

## 1.4.1 (Released 2024-07-23)

No significant change - Updated to use feature added at Cylc 8.3.3.
See [#336](https://github.com/cylc/cylc-rose/pull/336)

## 1.4.0 (Released 2024-06-18)

### Features

[#269](https://github.com/cylc/cylc-rose/pull/269) - Allow environment variables
set in ``rose-suite.conf`` to be used when parsing ``global.cylc``.

### Fixes

[#319](https://github.com/cylc/cylc-rose/pull/319) - Prevent Cylc Rose
from modifying Cylc's compatibility mode.


## 1.3.4 (Released 2024-05-02)

[#312](https://github.com/cylc/cylc-rose/pull/312) - Fixed an issue that could cause the cylc-rose CLI options (`-S`, `-D`, `-O`) to be applied incorrectly.


## 1.3.3 (Released 2024-04-05)

### Fixes

[#302](https://github.com/cylc/cylc-rose/pull/302) -
Fix issues which could cause "fcm_make" and "rose_prune" tasks intermittently
fail with the message
"Workflow database is incompatible with Cylc x.y.z, or is corrupted".


## 1.3.2 (Released 2024-01-18)

[#284](https://github.com/cylc/cylc-rose/pull/284) - Allow use of Metomi-Rose 2.2.*.


## 1.3.1 (Released 2023-10-24)

### Fixes

[#250](https://github.com/cylc/cylc-rose/pull/250) - Prevent project
name being manually set to an empty string.

[#225](https://github.com/cylc/cylc-rose/pull/225) - Prevent totally invalid
CLI --defines with no = sign.

[#248](https://github.com/cylc/cylc-rose/pull/248) - Make sure that
rose stem sets variables in `[jinja2:suite.rc]` not `[jinja2]`.

## 1.3.0 (Released 2023-07-21)

### Fixes

[#229](https://github.com/cylc/cylc-rose/pull/229) -
Fix bug which stops rose-stem suites using the new `[template variables]` section
in their `rose-suite.conf` files.

[#231](https://github.com/cylc/cylc-rose/pull/231) - Show warning about
`root-dir` config setting in compatibility mode.

## 1.2.0 (Released 2023-01-16)

### Fixes

[#192](https://github.com/cylc/cylc-rose/pull/192) -
Fix bug where Cylc Rose would prevent change to template language on reinstall.

[#180](https://github.com/cylc/cylc-rose/pull/180) -
Rose stem gets stem suite's basename to use as workflow name when not otherwise
set.

## 1.1.1 (Released 2022-09-14)

### Fixes

[#171](https://github.com/cylc/cylc-rose/pull/171) - Fix bug where Cylc Rose
passed `rose-suite.conf` items commented with `!` or `!!` to Cylc regardless.

[#172](https://github.com/cylc/cylc-rose/pull/172) - Allow getting a workflow
name when source is not an SVN repo.

## 1.1.0 (Released 2022-07-28)

### Fixes

[#140](https://github.com/cylc/cylc-rose/pull/140) -
Support integers with leading zeros (e.g `001`) to back support Rose
configurations for use with cylc-flow>=8.0rc4 which uses Jinja2 v3 which
no longer supports this.

[#155](https://github.com/cylc/cylc-rose/pull/155) -
Use the public rather than private database for platform lookups. This resolves
a database locking issue with the `rose_prune` built-in app.

## 1.0.3 (Released 2022-05-20)

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

## 1.0.2 (Released 2022-03-24)

### Fixes

[118](https://github.com/cylc/cylc-rose/pull/118) - Fail if
a workflow is not a Rose Suite but user provides Rose CLI options.

## 1.0.1 (Released 2022-02-17)

First official release of Cylc-Rose.

Implements interfaces to allow the use of Rose suite configurations with
Cylc 8.

> **Note:**
> The `1.0.1` was preceeded by the `1.0.0` release which had incorrect metadata.
