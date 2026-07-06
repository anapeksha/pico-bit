use crate::ducky::errors::DuckyError;
use crate::ducky::types::{KeySequence, modifiers};
use defmt::Format;

/// Stateless helpers for translating DuckyScript key tokens into HID reports.
pub struct DuckyKeyboard;

struct KeyMapping {
    modifier: u8,
    keycode: u8,
}

/// Supported host keyboard layouts for typed `STRING` content.
///
/// The firmware maps ASCII characters to physical HID key positions for the
/// selected host layout. This does not change the USB HID descriptor; it changes
/// the report generated for each character.
#[derive(Clone, Copy, Debug, Eq, Format, PartialEq)]
#[repr(u8)]
pub enum KeyboardLayout {
    Us = 0,
    Uk = 1,
    De = 2,
    Fr = 3,
}

/// Supported host operating-system targets for DuckyScript key aliases.
///
/// Layout controls printable character mapping, while OS controls how semantic
/// modifier aliases such as `COMMAND`, `WINDOWS`, and `OPTION` are interpreted.
#[derive(Clone, Copy, Debug, Eq, Format, PartialEq)]
#[repr(u8)]
pub enum KeyboardOs {
    Windows = 0,
    MacOs = 1,
    Linux = 2,
}

impl DuckyKeyboard {
    fn lookup_char(c: char, layout: KeyboardLayout) -> Option<KeyMapping> {
        if !c.is_ascii() {
            return None;
        }

        let ascii = c as u8;

        match layout {
            KeyboardLayout::Us => Self::lookup_us_char(ascii),
            KeyboardLayout::Uk => Self::lookup_uk_char(ascii),
            KeyboardLayout::De => Self::lookup_de_char(ascii),
            KeyboardLayout::Fr => Self::lookup_fr_char(ascii),
        }
    }

    fn lookup_us_char(ascii: u8) -> Option<KeyMapping> {
        match ascii {
            // Lowercase alphanumeric mappings
            b'a'..=b'z' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x04 + (ascii - b'a'),
            }),
            // Uppercase alphanumeric mappings (Requires Left Shift)
            b'A'..=b'Z' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x04 + (ascii - b'A'),
            }),

            // Numeric Row mappings
            b'1'..=b'9' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x1E + (ascii - b'1'),
            }),
            b'0' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x27,
            }),

            // Basic whitespace and structural control character overrides
            b' ' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x2C, // Spacebar
            }),
            b'\n' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x28, // Return/Enter
            }),
            b'\t' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x2B, // Tab
            }),

            // Common shifting symbol targets (Shift + Key)
            b'!' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x1E,
            }),
            b'@' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x1F,
            }),
            b'#' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x20,
            }),
            b'$' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x21,
            }),
            b'%' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x22,
            }),
            b'^' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x23,
            }),
            b'&' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x24,
            }),
            b'*' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x25,
            }),
            b'(' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x26,
            }),
            b')' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x27,
            }),

            // Non-shifting basic symbol targets
            b'-' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x2D,
            }),
            b'=' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x2E,
            }),
            b'[' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x2F,
            }),
            b']' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x30,
            }),
            b'\\' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x31,
            }),
            b';' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x33,
            }),
            b'\'' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x34,
            }),
            b'`' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x35,
            }),
            b',' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x36,
            }),
            b'.' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x37,
            }),
            b'/' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x38,
            }),

            // Shifting variant symbol pairs
            b'_' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x2D,
            }),
            b'+' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x2E,
            }),
            b'{' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x2F,
            }),
            b'}' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x30,
            }),
            b'|' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x31,
            }),
            b':' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x33,
            }),
            b'"' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x34,
            }),
            b'~' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x35,
            }),
            b'<' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x36,
            }),
            b'>' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x37,
            }),
            b'?' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x38,
            }),

            _ => None,
        }
    }

    fn lookup_uk_char(ascii: u8) -> Option<KeyMapping> {
        match ascii {
            b'"' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x1F,
            }),
            b'@' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x34,
            }),
            b'#' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x32,
            }),
            b'~' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x32,
            }),
            b'\\' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x64,
            }),
            b'|' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x64,
            }),
            _ => Self::lookup_us_char(ascii),
        }
    }

    fn lookup_de_char(ascii: u8) -> Option<KeyMapping> {
        match ascii {
            b'y' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x1D,
            }),
            b'Y' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x1D,
            }),
            b'z' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x1C,
            }),
            b'Z' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x1C,
            }),
            b'"' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x1F,
            }),
            b'&' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x23,
            }),
            b'/' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x24,
            }),
            b'(' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x25,
            }),
            b')' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x26,
            }),
            b'=' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x27,
            }),
            b'?' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x2D,
            }),
            b'\\' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x2D,
            }),
            b'@' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x14,
            }),
            b'{' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x24,
            }),
            b'[' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x25,
            }),
            b']' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x26,
            }),
            b'}' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x27,
            }),
            b';' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x36,
            }),
            b':' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x37,
            }),
            b'-' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x38,
            }),
            b'_' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x38,
            }),
            b'+' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x30,
            }),
            b'*' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x30,
            }),
            b'#' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x32,
            }),
            b'\'' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x32,
            }),
            _ => Self::lookup_us_char(ascii),
        }
    }

    fn lookup_fr_char(ascii: u8) -> Option<KeyMapping> {
        match ascii {
            b'a' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x14,
            }),
            b'A' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x14,
            }),
            b'q' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x04,
            }),
            b'Q' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x04,
            }),
            b'w' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x1D,
            }),
            b'W' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x1D,
            }),
            b'z' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x1A,
            }),
            b'Z' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x1A,
            }),
            b'm' => Some(KeyMapping {
                modifier: modifiers::NONE,
                keycode: 0x33,
            }),
            b'M' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x33,
            }),
            b'1' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x1E,
            }),
            b'2' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x1F,
            }),
            b'3' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x20,
            }),
            b'4' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x21,
            }),
            b'5' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x22,
            }),
            b'6' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x23,
            }),
            b'7' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x24,
            }),
            b'8' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x25,
            }),
            b'9' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x26,
            }),
            b'0' => Some(KeyMapping {
                modifier: modifiers::LEFT_SHIFT,
                keycode: 0x27,
            }),
            b'@' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x27,
            }),
            b'#' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x20,
            }),
            b'[' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x22,
            }),
            b'|' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x23,
            }),
            b'`' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x24,
            }),
            b'\\' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x25,
            }),
            b'^' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x26,
            }),
            b']' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x2D,
            }),
            b'}' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x2E,
            }),
            b'{' => Some(KeyMapping {
                modifier: modifiers::RIGHT_ALT,
                keycode: 0x21,
            }),
            _ => Self::lookup_us_char(ascii),
        }
    }

    /// Parses a DuckyScript key chord for a specific host operating system.
    ///
    /// The HID usage IDs are the same across operating systems, but common
    /// script aliases are not. This keeps `COMMAND`/`OPTION` natural on macOS
    /// while preserving `WINDOWS`/`GUI` behavior for Windows and Linux targets.
    pub fn parse_token_sequence_for_os(
        line: &str,
        os: KeyboardOs,
    ) -> Result<KeySequence, DuckyError> {
        let mut sequence = KeySequence::default();
        let mut key_idx = 0;

        for token in line.split_whitespace() {
            if let Some(modifier) = modifier_for_token(token, os) {
                sequence.report.modifier |= modifier;
            } else {
                // Check for action/structural keys
                let code = match token {
                    "ENTER" => 0x28,
                    "ESCAPE" | "ESC" => 0x29,
                    "BACKSPACE" => 0x2A,
                    "TAB" => 0x2B,
                    "SPACE" => 0x2C,
                    "DEL" | "DELETE" => 0x4C,
                    "PRINTSCREEN" => 0x46,
                    "SCROLLLOCK" => 0x47,
                    "PAUSE" => 0x48,
                    "INSERT" => 0x49,
                    "HOME" => 0x4A,
                    "PAGEUP" => 0x4B,
                    "END" => 0x4D,
                    "PAGEDOWN" => 0x4E,
                    "RIGHT" | "RIGHTARROW" => 0x4F,
                    "LEFT" | "LEFTARROW" => 0x50,
                    "DOWN" | "DOWNARROW" => 0x51,
                    "UP" | "UPARROW" => 0x52,
                    _ => return Err(DuckyError::InvalidKey),
                };

                // USB HID limits simultaneous non-modifier report inputs to 6 keys (6KRO)
                if key_idx >= 6 {
                    return Err(DuckyError::TooManyKeys);
                }
                sequence.report.keycodes[key_idx] = code;
                key_idx += 1;
            }
        }

        // Catch empty lines or unmappable structures falling into sequence parsing
        if sequence.report.modifier == modifiers::NONE && key_idx == 0 {
            return Err(DuckyError::UnknownCommand);
        }

        Ok(sequence)
    }

    /// Converts a printable character into a HID report using the selected layout.
    pub(crate) fn character_to_sequence_for_layout(
        c: char,
        layout: KeyboardLayout,
    ) -> Result<KeySequence, DuckyError> {
        let mapping = Self::lookup_char(c, layout).ok_or(DuckyError::InvalidKey)?;

        let mut sequence = KeySequence::default();
        sequence.report.modifier = mapping.modifier;
        sequence.report.keycodes[0] = mapping.keycode;

        Ok(sequence)
    }
}

fn modifier_for_token(token: &str, os: KeyboardOs) -> Option<u8> {
    match token {
        "CTRL" | "CONTROL" => Some(modifiers::LEFT_CTRL),
        "RCTRL" | "RIGHTCTRL" | "RIGHT_CONTROL" => Some(modifiers::RIGHT_CTRL),
        "SHIFT" => Some(modifiers::LEFT_SHIFT),
        "RSHIFT" | "RIGHTSHIFT" | "RIGHT_SHIFT" => Some(modifiers::RIGHT_SHIFT),
        "ALT" => Some(modifiers::LEFT_ALT),
        "RALT" | "RIGHTALT" | "RIGHT_ALT" | "ALTGR" => Some(modifiers::RIGHT_ALT),
        "GUI" | "META" => Some(modifiers::LEFT_GUI),
        "RGUI" | "RIGHTGUI" | "RIGHT_GUI" => Some(modifiers::RIGHT_GUI),
        "WINDOWS" | "WIN" => match os {
            KeyboardOs::MacOs => None,
            KeyboardOs::Windows | KeyboardOs::Linux => Some(modifiers::LEFT_GUI),
        },
        "COMMAND" | "CMD" => match os {
            KeyboardOs::MacOs => Some(modifiers::LEFT_GUI),
            KeyboardOs::Windows | KeyboardOs::Linux => None,
        },
        "OPTION" => match os {
            KeyboardOs::MacOs => Some(modifiers::LEFT_ALT),
            KeyboardOs::Windows | KeyboardOs::Linux => None,
        },
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::{DuckyKeyboard, KeyboardLayout, KeyboardOs};
    use crate::ducky::errors::DuckyError;
    use crate::ducky::types::modifiers;

    #[test]
    fn maps_lowercase_uppercase_and_symbols_to_hid_reports() {
        let lower =
            DuckyKeyboard::character_to_sequence_for_layout('a', KeyboardLayout::Us).unwrap();
        assert_eq!(lower.report.modifier, modifiers::NONE);
        assert_eq!(lower.report.keycodes[0], 0x04);

        let upper =
            DuckyKeyboard::character_to_sequence_for_layout('A', KeyboardLayout::Us).unwrap();
        assert_eq!(upper.report.modifier, modifiers::LEFT_SHIFT);
        assert_eq!(upper.report.keycodes[0], 0x04);

        let bang =
            DuckyKeyboard::character_to_sequence_for_layout('!', KeyboardLayout::Us).unwrap();
        assert_eq!(bang.report.modifier, modifiers::LEFT_SHIFT);
        assert_eq!(bang.report.keycodes[0], 0x1E);
    }

    #[test]
    fn rejects_non_ascii_characters() {
        assert_eq!(
            DuckyKeyboard::character_to_sequence_for_layout('é', KeyboardLayout::Us).unwrap_err(),
            DuckyError::InvalidKey
        );
    }

    #[test]
    fn maps_uk_specific_symbols() {
        let at = DuckyKeyboard::character_to_sequence_for_layout('@', KeyboardLayout::Uk).unwrap();
        assert_eq!(at.report.modifier, modifiers::LEFT_SHIFT);
        assert_eq!(at.report.keycodes[0], 0x34);

        let quote =
            DuckyKeyboard::character_to_sequence_for_layout('"', KeyboardLayout::Uk).unwrap();
        assert_eq!(quote.report.modifier, modifiers::LEFT_SHIFT);
        assert_eq!(quote.report.keycodes[0], 0x1F);
    }

    #[test]
    fn maps_german_qwertz_and_altgr_symbols() {
        let z = DuckyKeyboard::character_to_sequence_for_layout('z', KeyboardLayout::De).unwrap();
        assert_eq!(z.report.modifier, modifiers::NONE);
        assert_eq!(z.report.keycodes[0], 0x1C);

        let at = DuckyKeyboard::character_to_sequence_for_layout('@', KeyboardLayout::De).unwrap();
        assert_eq!(at.report.modifier, modifiers::RIGHT_ALT);
        assert_eq!(at.report.keycodes[0], 0x14);
    }

    #[test]
    fn maps_french_azerty_letters_and_digits() {
        let a = DuckyKeyboard::character_to_sequence_for_layout('a', KeyboardLayout::Fr).unwrap();
        assert_eq!(a.report.modifier, modifiers::NONE);
        assert_eq!(a.report.keycodes[0], 0x14);

        let one = DuckyKeyboard::character_to_sequence_for_layout('1', KeyboardLayout::Fr).unwrap();
        assert_eq!(one.report.modifier, modifiers::LEFT_SHIFT);
        assert_eq!(one.report.keycodes[0], 0x1E);
    }

    #[test]
    fn parses_modifier_and_key_sequences() {
        let sequence =
            DuckyKeyboard::parse_token_sequence_for_os("CTRL ALT DELETE", KeyboardOs::Windows)
                .unwrap();

        assert_eq!(
            sequence.report.modifier,
            modifiers::LEFT_CTRL | modifiers::LEFT_ALT
        );
        assert_eq!(sequence.report.keycodes[0], 0x4C);
    }

    #[test]
    fn parses_right_side_modifier_aliases() {
        let sequence = DuckyKeyboard::parse_token_sequence_for_os(
            "RIGHTCTRL RIGHTSHIFT RIGHTALT RIGHTGUI ENTER",
            KeyboardOs::Windows,
        )
        .unwrap();

        assert_eq!(
            sequence.report.modifier,
            modifiers::RIGHT_CTRL
                | modifiers::RIGHT_SHIFT
                | modifiers::RIGHT_ALT
                | modifiers::RIGHT_GUI
        );
        assert_eq!(sequence.report.keycodes[0], 0x28);
    }

    #[test]
    fn parses_os_specific_modifier_aliases() {
        let mac =
            DuckyKeyboard::parse_token_sequence_for_os("COMMAND SPACE", KeyboardOs::MacOs).unwrap();
        assert_eq!(mac.report.modifier, modifiers::LEFT_GUI);
        assert_eq!(mac.report.keycodes[0], 0x2C);

        assert_eq!(
            DuckyKeyboard::parse_token_sequence_for_os("COMMAND SPACE", KeyboardOs::Windows)
                .unwrap_err(),
            DuckyError::InvalidKey
        );

        let windows =
            DuckyKeyboard::parse_token_sequence_for_os("WINDOWS SPACE", KeyboardOs::Windows)
                .unwrap();
        assert_eq!(windows.report.modifier, modifiers::LEFT_GUI);
        assert_eq!(windows.report.keycodes[0], 0x2C);

        assert_eq!(
            DuckyKeyboard::parse_token_sequence_for_os("WINDOWS SPACE", KeyboardOs::MacOs)
                .unwrap_err(),
            DuckyError::InvalidKey
        );
    }

    #[test]
    fn rejects_empty_unknown_and_too_many_key_sequences() {
        assert_eq!(
            DuckyKeyboard::parse_token_sequence_for_os("", KeyboardOs::Windows).unwrap_err(),
            DuckyError::UnknownCommand
        );
        assert_eq!(
            DuckyKeyboard::parse_token_sequence_for_os("NOPE", KeyboardOs::Windows).unwrap_err(),
            DuckyError::InvalidKey
        );
        assert_eq!(
            DuckyKeyboard::parse_token_sequence_for_os("A B C D E F G", KeyboardOs::Windows)
                .unwrap_err(),
            DuckyError::InvalidKey
        );
        assert_eq!(
            DuckyKeyboard::parse_token_sequence_for_os(
                "ENTER ESC TAB SPACE HOME END DELETE",
                KeyboardOs::Windows
            )
            .unwrap_err(),
            DuckyError::TooManyKeys
        );
    }
}
