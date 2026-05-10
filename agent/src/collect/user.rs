use serde_json::{Value, json};

pub fn home_dir() -> String {
    std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .unwrap_or_default()
}

pub fn collect() -> Value {
    let username = std::env::var("USER")
        .or_else(|_| std::env::var("USERNAME"))
        .unwrap_or_default();
    let home = home_dir();
    let path = std::env::var("PATH").unwrap_or_default();
    json!({
        "username": username,
        "home_dir": home,
        "path": path,
        "is_elevated": is_elevated(),
    })
}

#[cfg(target_os = "windows")]
fn is_elevated() -> bool {
    use std::process::Command;
    Command::new("net")
        .args(["session"])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

#[cfg(not(target_os = "windows"))]
fn is_elevated() -> bool {
    unsafe { libc::geteuid() == 0 }
}
