//! Host-testable library surface for firmware-agnostic Pico Bit modules.
//!
//! The firmware binary lives in `main.rs`. This library keeps parser, keyboard,
//! and utility tests available to host-side CI without pulling in the embedded
//! runtime.

#![no_std]

#[cfg(test)]
extern crate std;

/// DuckyScript parser, keyboard mapper, and bounded executor.
pub mod ducky;
