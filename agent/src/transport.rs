use serde_json::Value;

const LOOT_URL: &str = "http://192.168.4.1/api/loot";

pub fn post_loot(payload: &Value) {
    let _ = ureq::post(LOOT_URL)
        .set("Content-Type", "application/json")
        .send_string(&payload.to_string());
}
