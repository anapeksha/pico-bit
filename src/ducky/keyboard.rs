// src/ducky/keyboard.rs

use crate::ducky::errors::DuckyError;
use crate::ducky::types::{KeySequence, modifiers};

pub struct DuckyKeyboard;

struct KeyMapping {
    modifier: u8,
    keycode: u8,
}

impl DuckyKeyboard {
    fn lookup_char(c: char) -> Option<KeyMapping> {
        if !c.is_ascii() {
            return None;
        }

        let ascii = c as u8;

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

    pub fn parse_token_sequence(line: &str) -> Result<KeySequence, DuckyError> {
        let mut sequence = KeySequence::default();
        let mut key_idx = 0;

        for token in line.split_whitespace() {
            if matches!(
                token,
                "CTRL" | "CONTROL" | "SHIFT" | "ALT" | "GUI" | "WINDOWS"
            ) {
                sequence.report.modifier |= match token {
                    "CTRL" | "CONTROL" => modifiers::LEFT_CTRL,
                    "SHIFT" => modifiers::LEFT_SHIFT,
                    "ALT" => modifiers::LEFT_ALT,
                    "GUI" | "WINDOWS" => modifiers::LEFT_GUI,
                    _ => modifiers::NONE,
                };
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

    pub fn character_to_sequence(c: char) -> Result<KeySequence, DuckyError> {
        let mapping = Self::lookup_char(c).ok_or(DuckyError::InvalidKey)?;

        let mut sequence = KeySequence::default();
        sequence.report.modifier = mapping.modifier;
        sequence.report.keycodes[0] = mapping.keycode;

        Ok(sequence)
    }
}
