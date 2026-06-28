export type NoticeTone = 'quiet' | 'success' | 'error' | 'warning';

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

export type RunHistoryItem = {
  ok?: boolean;
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
  kind: string;
  name: string;
  path?: string;
  size: number;
  url?: string;
};

export type ArmoryListResponse = {
  files: ArmoryFile[];
  has_binary: boolean;
};

export type ArmoryMutationResponse = {
  filename: string;
  has_binary: boolean;
  message: string;
  notice: NoticeTone;
};

export type KeyboardTargetRequest = {
  layout?: string;
  os?: string;
};

export type KeyboardTargetResponse = {
  keyboard_layout: string;
  keyboard_os: string;
  message: string;
  notice: NoticeTone;
};

export type PayloadReadResponse = {
  code: string;
};

export type RunsResponse = {
  run_history: RunHistoryItem[];
  seeded: boolean;
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
  error_line?: number | null;
  message: string;
  success: boolean;
  validation?: ValidationState;
};

export type BootstrapState = {
  ap_password?: string;
  ap_ssid?: string;
  host_hid_active?: boolean;
  keyboard_layout?: string;
  keyboard_os?: string;
  ncm_active?: boolean;
  ncm_url?: string;
  seeded?: boolean;
};

export type HydratedBootstrapState = BootstrapState & {
  files?: LittleFsFile[];
  payload?: string;
  payload_file?: string;
  run_history?: RunHistoryItem[];
};

export type RequestFailure = Error & {
  data?: Record<string, unknown>;
  status?: number;
};
