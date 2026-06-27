use serde::Serialize;

#[derive(Serialize)]
pub(super) struct SelectOption {
    code: &'static str,
    label: &'static str,
}

#[derive(Serialize)]
pub(super) struct KeyboardResponse {
    keyboard_layout: &'static str,
    keyboard_layout_hint: &'static str,
    keyboard_layout_label: &'static str,
    keyboard_layouts: &'static [SelectOption],
    keyboard_os: &'static str,
    keyboard_os_label: &'static str,
    keyboard_oses: &'static [SelectOption],
    keyboard_target_label: &'static str,
    message: &'static str,
    notice: &'static str,
}

static KEYBOARD_LAYOUTS: &[SelectOption] = &[SelectOption {
    code: "US",
    label: "English (US)",
}];

static KEYBOARD_OSES: &[SelectOption] = &[
    SelectOption {
        code: "WIN",
        label: "Windows",
    },
    SelectOption {
        code: "MAC",
        label: "macOS",
    },
    SelectOption {
        code: "LINUX",
        label: "Linux",
    },
];

pub(super) fn current_target() -> KeyboardResponse {
    KeyboardResponse {
        keyboard_layout: "US",
        keyboard_layout_hint: "Used for typed text and remembered on the device.",
        keyboard_layout_label: "English (US)",
        keyboard_layouts: KEYBOARD_LAYOUTS,
        keyboard_os: "WIN",
        keyboard_os_label: "Windows",
        keyboard_oses: KEYBOARD_OSES,
        keyboard_target_label: "Windows - English (US)",
        message: "Keyboard service layer not wired.",
        notice: "quiet",
    }
}
