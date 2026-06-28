#![no_std]

#[cfg(test)]
extern crate std;

pub mod ducky;

#[cfg(test)]
#[path = "utils/json_buffer.rs"]
pub(crate) mod json_buffer;

#[cfg(test)]
mod utils {}
