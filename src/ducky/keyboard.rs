// src/ducky/keyboard.rs

use crate::ducky::errors::DuckyError;
use crate::ducky::types::{KeySequence, modifiers};

pub struct DuckyKeyboard;

struct KeyMapping {
    modifier: u8,
    keycode: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum KeyboardLayout {
    Us = 0,
    Uk = 1,
    De = 2,
    Fr = 3,
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

#[cfg(test)]
mod tests {
    use super::{DuckyKeyboard, KeyboardLayout};
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
        let sequence = DuckyKeyboard::parse_token_sequence("CTRL ALT DELETE").unwrap();

        assert_eq!(
            sequence.report.modifier,
            modifiers::LEFT_CTRL | modifiers::LEFT_ALT
        );
        assert_eq!(sequence.report.keycodes[0], 0x4C);
    }

    #[test]
    fn rejects_empty_unknown_and_too_many_key_sequences() {
        assert_eq!(
            DuckyKeyboard::parse_token_sequence("").unwrap_err(),
            DuckyError::UnknownCommand
        );
        assert_eq!(
            DuckyKeyboard::parse_token_sequence("NOPE").unwrap_err(),
            DuckyError::InvalidKey
        );
        assert_eq!(
            DuckyKeyboard::parse_token_sequence("A B C D E F G").unwrap_err(),
            DuckyError::InvalidKey
        );
        assert_eq!(
            DuckyKeyboard::parse_token_sequence("ENTER ESC TAB SPACE HOME END DELETE").unwrap_err(),
            DuckyError::TooManyKeys
        );
    }
}
