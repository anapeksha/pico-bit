# Upstream provenance

This directory contains `cyw43` 0.7.0 with the SoftAP WPA3 changes from
[embassy-rs/embassy#6529](https://github.com/embassy-rs/embassy/pull/6529),
merged as commit `5763f62d945576afcb0442bfec433e853809cf5f`.

The local patch keeps the released 0.7.0 dependency graph while the upstream
change awaits a crates.io release. Remove this override after upgrading to a
published `cyw43` version containing that merge.
