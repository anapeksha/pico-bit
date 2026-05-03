const notice = document.getElementById('notice');
const payloadField = document.getElementById('payload');
const saveButton = document.getElementById('save');
const runButton = document.getElementById('run');
const refreshButton = document.getElementById('refresh');
const unsafeToggle = document.getElementById('unsafe-toggle');
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
const payloadLibrary = document.getElementById('payload-library');
const saveAsInput = document.getElementById('save-as-name');
const saveAsBtn = document.getElementById('save-as-btn');

const uiState = {
  charWidth: 8,
  lineHeight: 22,
  modeDescription: '',
  padLeft: 16,
  padTop: 14,
  changingTarget: false,
  keyboardOses: [],
  keyboardLayouts: [],
  libraryWorking: false,
  running: false,
  saving: false,
  togglingUnsafe: false,
  validating: false,
  validation: null,
  validationRequest: 0,
  validationTimer: 0,
  lastValidatedPayload: null,
};

const HL_UNSAFE = new Set([
  'ATTACKMODE',
  'EXFIL',
  'HIDE_PAYLOAD',
  'RESTORE_PAYLOAD',
  'SAVE_ATTACKMODE',
  'RESTORE_ATTACKMODE',
  'SAVE_HOST_KEYBOARD_LOCK_STATE',
  'RESTORE_HOST_KEYBOARD_LOCK_STATE',
  'WAIT_FOR_CAPS_CHANGE',
  'WAIT_FOR_CAPS_OFF',
  'WAIT_FOR_CAPS_ON',
  'WAIT_FOR_NUM_CHANGE',
  'WAIT_FOR_NUM_OFF',
  'WAIT_FOR_NUM_ON',
  'WAIT_FOR_SCROLL_CHANGE',
  'WAIT_FOR_SCROLL_OFF',
  'WAIT_FOR_SCROLL_ON',
]);
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
  'DELAY',
  'DEFAULTDELAY',
  'DEFAULT_DELAY',
  'DEFAULTCHARDELAY',
  'DEFAULT_CHAR_DELAY',
  'DEFAULTCHARJITTER',
  'DISABLE_BUTTON',
  'ENABLE_BUTTON',
  'INJECT_MOD',
  'INJECT_VAR',
  'RD_KBD',
  'RELEASE',
  'RESET',
  'STOP_PAYLOAD',
  'RESTART_PAYLOAD',
  'VERSION',
  'WAIT_FOR_BUTTON_PRESS',
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
  if (HL_UNSAFE.has(tu)) cls = 'hl-unsafe';
  else if (HL_FLOW.has(tu)) cls = 'hl-flow';
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
    node.textContent = value;
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
  if (unsafeToggle) {
    unsafeToggle.disabled = uiState.togglingUnsafe;
  }
  if (keyboardOsSelect) {
    keyboardOsSelect.disabled = uiState.changingTarget;
  }
  if (keyboardLayoutSelect) {
    keyboardLayoutSelect.disabled = uiState.changingTarget;
  }
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
      `${sourceLabel} run #${entry.sequence}\n${entry.mode_label || ''}\n${entry.message || ''}`.trim();

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

  if (response.status === 401) {
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

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

function applyMode(state) {
  uiState.modeDescription = state.mode_description || '';
  setBoundText('mode_label', (state.mode_label || '').split(' ')[0]);
  if (unsafeToggle) {
    unsafeToggle.checked = !!state.allow_unsafe;
  }
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
  loadLibrary();
  setBoundText('ap_ssid', state.ap_ssid);
  setBoundText('ap_password', state.ap_password || 'Open network');
  applyMode(state);
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

async function toggleUnsafe(unsafeOn) {
  uiState.togglingUnsafe = true;
  updateControls();
  try {
    const result = await requestJson('/api/safe-mode', {
      method: 'POST',
      body: JSON.stringify({ enabled: !unsafeOn, payload: payloadField.value }),
    });
    applyMode(result);
    if (result.validation) {
      uiState.validating = false;
      renderValidation(result.validation);
    }
    setNotice(result.message, result.notice || 'success');
  } catch (error) {
    if (unsafeToggle) {
      unsafeToggle.checked = !unsafeOn;
    }
    if (error.data?.validation) {
      renderValidation(error.data.validation);
    }
    setNotice(error.message, 'error');
  } finally {
    uiState.togglingUnsafe = false;
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

if (unsafeToggle) {
  unsafeToggle.addEventListener('change', () => {
    toggleUnsafe(unsafeToggle.checked);
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

function updateLibraryControls() {
  if (saveAsBtn) saveAsBtn.disabled = uiState.libraryWorking;
  if (saveAsInput) saveAsInput.disabled = uiState.libraryWorking;
}

function renderLibrary(payloads = []) {
  if (!payloadLibrary) return;
  payloadLibrary.textContent = '';
  if (!payloads.length) {
    const p = document.createElement('p');
    p.className = 'library__empty';
    p.textContent = 'No saved payloads.';
    payloadLibrary.appendChild(p);
    return;
  }
  payloads.forEach(({ name }) => {
    const item = document.createElement('article');
    item.className = 'library__item';

    const nameEl = document.createElement('span');
    nameEl.className = 'library__name';
    nameEl.textContent = name;
    nameEl.title = `${name}.dd`;

    const actions = document.createElement('div');
    actions.className = 'library__actions';

    const loadBtn = document.createElement('button');
    loadBtn.className = 'btn btn--ghost btn--sm';
    loadBtn.type = 'button';
    loadBtn.textContent = 'Load';
    loadBtn.addEventListener('click', () => loadNamedPayload(name));

    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn--danger-ghost btn--sm';
    delBtn.type = 'button';
    delBtn.textContent = 'Delete';
    delBtn.setAttribute('aria-label', `Delete ${name}`);
    delBtn.addEventListener('click', () => deleteNamedPayload(name));

    actions.appendChild(loadBtn);
    actions.appendChild(delBtn);
    item.appendChild(nameEl);
    item.appendChild(actions);
    payloadLibrary.appendChild(item);
  });
}

async function loadLibrary() {
  try {
    const result = await requestJson('/api/payloads');
    renderLibrary(result.payloads || []);
  } catch (_) {}
}

async function loadNamedPayload(name) {
  if (uiState.libraryWorking) return;
  uiState.libraryWorking = true;
  try {
    const result = await requestJson(
      `/api/payloads/${encodeURIComponent(name)}`,
    );
    if (payloadField) {
      payloadField.value = result.payload || '';
      handlePayloadInput();
    }
    setNotice(`Loaded ${name}.dd`, 'success');
  } catch (error) {
    setNotice(error.message, 'error');
  } finally {
    uiState.libraryWorking = false;
  }
}

async function deleteNamedPayload(name) {
  if (uiState.libraryWorking) return;
  uiState.libraryWorking = true;
  try {
    await requestJson(`/api/payloads/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    });
    setNotice(`Deleted ${name}.dd`, 'success');
    loadLibrary();
  } catch (error) {
    setNotice(error.message, 'error');
  } finally {
    uiState.libraryWorking = false;
  }
}

async function saveAsPayload() {
  if (uiState.libraryWorking || !saveAsInput) return;
  const name = saveAsInput.value.trim();
  if (!name) {
    setNotice('Enter a name first.', 'error');
    return;
  }
  uiState.libraryWorking = true;
  updateLibraryControls();
  try {
    await requestJson('/api/payloads', {
      method: 'POST',
      body: JSON.stringify({ name, payload: payloadField?.value || '' }),
    });
    saveAsInput.value = '';
    setNotice(`Saved as ${name}.dd`, 'success');
    loadLibrary();
  } catch (error) {
    setNotice(error.message, 'error');
  } finally {
    uiState.libraryWorking = false;
    updateLibraryControls();
  }
}

if (saveAsBtn) {
  saveAsBtn.addEventListener('click', saveAsPayload);
}

if (saveAsInput) {
  saveAsInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') saveAsPayload();
  });
}

loadBootstrap().catch((error) => setNotice(error.message, 'error'));
