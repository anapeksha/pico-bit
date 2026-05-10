use serde_json::{Value, json};
use sysinfo::{Process, System};

pub fn collect(sys: &System) -> Value {
    json!({
        "hostname": System::host_name().unwrap_or_default(),
        "os_name": System::name().unwrap_or_default(),
        "os_version": System::os_version().unwrap_or_default(),
        "kernel": System::kernel_version().unwrap_or_default(),
        "arch": std::env::consts::ARCH,
        "uptime_secs": System::uptime(),
        "total_mem_mb": sys.total_memory() / (1024 * 1024),
        "used_mem_mb": sys.used_memory() / (1024 * 1024),
    })
}

pub fn collect_processes(sys: &System) -> Value {
    let mut procs: Vec<Value> = sys
        .processes()
        .values()
        .map(|p: &Process| {
            json!({
                "name": p.name().to_string_lossy(),
                "pid": p.pid().as_u32(),
                "mem_mb": p.memory() / (1024 * 1024),
            })
        })
        .collect();
    procs.sort_by(|a, b| {
        b["mem_mb"]
            .as_u64()
            .unwrap_or(0)
            .cmp(&a["mem_mb"].as_u64().unwrap_or(0))
    });
    Value::Array(procs)
}
