# Selected Cylc-Rose Changes

## __cylc-rose-1.0.3 (<span actions:bind='release-date'></span>)__

### Fixes

[139](https://github.com/cylc/cylc-rose/pull/139) - Make `rose stem` command
work correctly with changes made to `cylc install` in
[cylc-flow PR #4823](https://github.com/cylc/cylc-flow/pull/4823)

[130](https://github.com/cylc/cylc-rose/pull/130) - Fix bug preventing
``cylc reinstall`` using Rose fileinstall.

[132](https://github.com/cylc/cylc-rose/pull/132) - Fix bug preventing
Cylc commands (other than `install`) from accessing the content of
`--rose-template-variable`.

[133](https://github.com/cylc/cylc-rose/pull/133) - Fix bug allowing setting
multiple template variable sections.

## __cylc-rose-1.0.2 (<span actions:bind='release-date'>Released 2022-03-24</span>)__

### Fixes

[118](https://github.com/cylc/cylc-rose/pull/118) - Fail if
a workflow is not a Rose Suite but user provides Rose CLI options.

## cylc-rose-1.0.1 (Released 2022-02-17)

First official release of Cylc-Rose.

Implements interfaces to allow the use of Rose suite configurations with
Cylc 8.

> **Note:**
> The `1.0.1` was preceeded by the `1.0.0` release which had incorrect metadata.
