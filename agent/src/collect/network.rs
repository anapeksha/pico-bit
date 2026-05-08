use serde_json::{json, Value};
use sysinfo::Networks;

pub fn collect() -> Value {
    let networks = Networks::new_with_refreshed_list();
    let ifaces: Vec<Value> = networks
        .iter()
        .map(|(name, _data)| json!({ "name": name }))
        .collect();
    Value::Array(ifaces)
}
