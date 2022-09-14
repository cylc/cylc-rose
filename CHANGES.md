# Selected Cylc-Rose Changes

<!-- The topmost release date is automatically updated by GitHub Actions. When
creating a new release entry be sure to copy & paste the span tag with the
`actions:bind` attribute, which is used by a regex to find the text to be
updated. Only the first match gets replaced, so it's fine to leave the old
ones in. -->
## __cylc-rose-1.1.1 (<span actions:bind='release-date'>Released 2022-09-14</span>)__

### Fixes

[#171](https://github.com/cylc/cylc-rose/pull/171) - Fix bug where Cylc Rose
passed `rose-suite.conf` items commented with `!` or `!!` to Cylc regardless.


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

[#172](https://github.com/cylc/cylc-rose/pull/172) - Allow getting a workflow
name when source is not an SVN repo.

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
