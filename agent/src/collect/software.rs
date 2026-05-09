use serde_json::Value;

#[cfg(any(target_os = "macos", target_os = "linux"))]
use serde_json::json;

#[cfg(target_os = "windows")]
pub fn collect() -> Value {
    use std::process::Command;
    let output = Command::new("powershell")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-c",
            "Get-Package | Select-Object -Property Name,Version | ConvertTo-Json -Compress",
        ])
        .output();
    let Ok(output) = output else {
        return Value::Array(vec![]);
    };
    let text = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(text.trim()).unwrap_or(Value::Array(vec![]))
}

#[cfg(target_os = "macos")]
pub fn collect() -> Value {
    use std::process::Command;
    let output = Command::new("ls").args(["-1", "/Applications"]).output();
    let apps: Vec<Value> = output
        .ok()
        .map(|o| {
            String::from_utf8_lossy(&o.stdout)
                .lines()
                .filter(|l| l.ends_with(".app"))
                .map(|l| json!({ "name": l.trim_end_matches(".app"), "version": "" }))
                .collect()
        })
        .unwrap_or_default();
    Value::Array(apps)
}

#[cfg(target_os = "linux")]
pub fn collect() -> Value {
    use std::process::Command;
    // try dpkg first, fall back to rpm, then pacman
    let output = Command::new("dpkg")
        .args(["-l"])
        .output()
        .or_else(|_| Command::new("rpm").args(["-qa", "--queryformat", "%{NAME} %{VERSION}\n"]).output())
        .or_else(|_| Command::new("pacman").args(["-Q"]).output());
    let Ok(output) = output else {
        return Value::Array(vec![]);
    };
    let text = String::from_utf8_lossy(&output.stdout);
    // dpkg output starts lines with "ii"; rpm/pacman output is "name version"
    let pkgs: Vec<Value> = text
        .lines()
        .filter(|l| !l.starts_with('+') && !l.starts_with('|') && !l.starts_with("Desired"))
        .filter_map(|l| {
            let parts: Vec<&str> = l.split_whitespace().collect();
            if parts.len() < 2 {
                return None;
            }
            let (name, version) = if parts[0] == "ii" {
                (parts.get(1)?, parts.get(2)?)
            } else {
                (parts.first()?, parts.get(1)?)
            };
            Some(json!({ "name": name, "version": version }))
        })
        .collect();
    Value::Array(pkgs)
}
