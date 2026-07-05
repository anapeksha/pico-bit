pub mod controller;
mod service;

pub(crate) use service::{
    host_hid_active, ncm_active, ncm_url, seeded_this_boot, set_host_hid_active, set_ncm_active,
};
