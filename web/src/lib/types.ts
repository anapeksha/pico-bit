export type NoticeTone = 'quiet' | 'success' | 'error' | 'warning';
export type TargetOs = 'windows' | 'linux' | 'macos';

export type SelectOption = {
  code: string;
  label: string;
};

export type Diagnostic = {
  code?: string;
  column: number;
  end_column?: number;
  hint?: string;
  line: number;
  message: string;
  severity: 'error' | 'warning';
};

export type ValidationState = {
  badge_label: string;
  badge_tone: NoticeTone | 'warn';
  blocking: boolean;
  can_run: boolean;
  can_save: boolean;
  diagnostics: Diagnostic[];
  error_count?: number;
  line_count?: number;
  notice: NoticeTone;
  parsed_commands?: unknown[];
  summary: string;
  warning_count?: number;
};

export type UsbAgentState = {
  active?: boolean;
  available?: boolean;
  can_mount?: boolean;
  can_unmount?: boolean;
  filename?: string;
  has_binary?: boolean;
  message?: string;
  mounted?: boolean;
  state?: string;
  volume_label?: string;
  volume_note?: string;
};

export type RunHistoryItem = {
  message?: string;
  notice?: NoticeTone | string;
  preview?: string;
  sequence?: number;
  source?: string;
};

export type KeyboardState = {
  hint: string;
  layout: string;
  layoutLabel: string;
  layouts: SelectOption[];
  os: string;
  osLabel: string;
  oses: SelectOption[];
  targetLabel: string;
};

export type BootstrapState = {
  ap_password?: string;
  ap_ssid?: string;
  auth_enabled?: boolean;
  has_binary?: boolean;
  keyboard_layout?: string;
  keyboard_layout_hint?: string;
  keyboard_layout_label?: string;
  keyboard_layouts?: SelectOption[];
  keyboard_os?: string;
  keyboard_os_label?: string;
  keyboard_oses?: SelectOption[];
  keyboard_ready?: boolean;
  keyboard_target_label?: string;
  message?: string;
  notice?: NoticeTone;
  payload?: string;
  run_history?: RunHistoryItem[];
  seeded?: boolean;
  usb_agent?: UsbAgentState;
  validation?: ValidationState;
};

export type LootRecord = Record<string, any>;

export type RequestFailure = Error & {
  data?: Record<string, any>;
  status?: number;
};
