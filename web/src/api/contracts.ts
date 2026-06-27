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

export type NcmLinkState = {
  address?: string;
  active?: boolean;
  available?: boolean;
  filename?: string;
  gateway?: string;
  has_binary?: boolean;
  interface?: string;
  message?: string;
  root_url?: string;
  state?: string;
  transport?: string;
};

export type HostHidState = {
  active?: boolean;
  available?: boolean;
  message?: string;
  state?: string;
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

export type LittleFsFile = {
  kind: string;
  name: string;
  path: string;
  size: number;
};

export type ArmoryFile = {
  kind?: string;
  name: string;
  path?: string;
  size: number;
  url: string;
};

export type ArmoryListResponse = {
  files: ArmoryFile[];
  has_binary: boolean;
  max_upload_bytes?: number;
  message: string;
  notice: NoticeTone;
};

export type ArmoryMutationResponse = {
  filename: string;
  has_binary: boolean;
  max_upload_bytes?: number;
  message: string;
  notice: NoticeTone;
};

export type KeyboardTargetRequest = {
  layout?: string;
  os?: string;
};

export type PayloadReadResponse = {
  code: string;
};

export type PayloadWriteRequest = {
  code: string;
};

export type PayloadMutationResponse = {
  error_line: number | null;
  message: string | null;
  notice?: NoticeTone;
  success: boolean;
  validation?: ValidationState;
};

export type PayloadRunResponse = {
  message: string;
  success: boolean;
};

export type BootstrapState = {
  ap_password?: string;
  ap_ssid?: string;
  files?: LittleFsFile[];
  has_binary?: boolean;
  host_hid?: HostHidState;
  keyboard_layout?: string;
  keyboard_layout_hint?: string;
  keyboard_layout_label?: string;
  keyboard_layouts?: SelectOption[];
  keyboard_os?: string;
  keyboard_os_label?: string;
  keyboard_oses?: SelectOption[];
  keyboard_target_label?: string;
  max_upload_bytes?: number;
  message?: string;
  notice?: NoticeTone;
  payload?: string;
  payload_file?: string;
  run_history?: RunHistoryItem[];
  seeded?: boolean;
  ncm_link?: NcmLinkState;
};

export type RequestFailure = Error & {
  data?: Record<string, unknown>;
  status?: number;
};
