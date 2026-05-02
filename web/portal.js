const notice = document.getElementById('notice');
const payloadField = document.getElementById('payload');
const saveButton = document.getElementById('save');
const runButton = document.getElementById('run');
const refreshButton = document.getElementById('refresh');
const unsafeToggle = document.getElementById('unsafe-toggle');
const librarySelect = document.getElementById('library-select');
const runHistory = document.getElementById('run-history');
const editorGutter = document.getElementById('editor-gutter');
const editorMarkers = document.getElementById('editor-markers');
const validationDiagnostics = document.getElementById('validation-diagnostics');
const validationUnsafe = document.getElementById('validation-unsafe');
const validationCommands = document.getElementById('validation-commands');
const validationBadge = document.querySelector('[data-bind="validation_badge"]');

const uiState = {
  charWidth: 8,
  libraryCount: 0,
  lineHeight: 22,
  modeDescription: '',
  padLeft: 16,
  padTop: 14,
  running: false,
  saving: false,
  togglingUnsafe: false,
  validating: false,
  validation: null,
  validationRequest: 0,
  validationTimer: 0,
  loadingLibrary: false,
};

function setNotice(message, tone = 'quiet') {
  if (!notice) {
    return;
  }
  if (!message) {
    notice.className = 'notice notice--hidden';
    notice.textContent = '';
    return;
  }
  notice.className = `notice notice--${tone}`;
  notice.textContent = message;
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

function payloadLibraryCount(groups = []) {
  return groups.reduce((count, group) => count + (group.items || []).length, 0);
}

function libraryHint(groups, allowUnsafe) {
  const count = payloadLibraryCount(groups);
  if (!count) {
    return 'No baked payload templates are available in this build.';
  }
  if (allowUnsafe) {
    return `${count} baked payload templates available. Unsafe-mode templates are included.`;
  }
  return `${count} baked payload templates available in safe mode.`;
}

function updateControls() {
  const validation = uiState.validation;
  if (saveButton) {
    saveButton.disabled =
      uiState.validating || uiState.saving || !validation || !validation.can_save;
  }
  if (runButton) {
    runButton.disabled =
      uiState.validating || uiState.running || !validation || !validation.can_run;
  }
  if (librarySelect) {
    librarySelect.disabled = uiState.loadingLibrary || uiState.libraryCount === 0;
  }
  if (unsafeToggle) {
    unsafeToggle.disabled = uiState.togglingUnsafe;
  }
}

function itemTitle(item) {
  return [item.message, item.hint].filter(Boolean).join('\n');
}

function renderPayloadLibrary(groups = []) {
  if (!librarySelect) {
    return;
  }

  const selected = librarySelect.value;
  const validIds = new Set();
  uiState.libraryCount = payloadLibraryCount(groups);

  librarySelect.textContent = '';

  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = uiState.libraryCount
    ? 'Load a baked payload template…'
    : 'No baked payload templates available';
  librarySelect.appendChild(placeholder);

  groups.forEach((group) => {
    const optgroup = document.createElement('optgroup');
    optgroup.label = group.label;

    (group.items || []).forEach((item) => {
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = item.safe ? item.label : `${item.label} (unsafe)`;
      optgroup.appendChild(option);
      validIds.add(item.id);
    });

    if (optgroup.childNodes.length) {
      librarySelect.appendChild(optgroup);
    }
  });

  librarySelect.value = validIds.has(selected) ? selected : '';
  updateControls();
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

    const top = document.createElement('div');
    top.className = 'history__top';

    const title = document.createElement('div');
    title.className = 'history__title';
    title.textContent = `#${entry.sequence} · ${
      entry.source === 'boot' ? 'Boot payload' : 'Portal run'
    }`;

    const badge = document.createElement('span');
    badge.className = `badge ${
      entry.notice === 'success' ? 'badge--success' : 'badge--error'
    }`;
    badge.textContent = entry.notice === 'success' ? 'OK' : 'Error';

    top.appendChild(title);
    top.appendChild(badge);

    const preview = document.createElement('p');
    preview.className = 'history__preview';
    preview.textContent = entry.preview || 'Empty payload';

    const meta = document.createElement('p');
    meta.className = 'history__meta';
    meta.textContent = entry.mode_label || 'Runtime mode';

    const message = document.createElement('p');
    message.className = 'history__message';
    message.textContent = entry.message || '';

    item.appendChild(top);
    item.appendChild(preview);
    item.appendChild(meta);
    item.appendChild(message);
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
    const error = new Error(data.message || `Request failed with ${response.status}`);
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

function applyLibraryState(state) {
  const groups = state.payload_library_groups || [];
  renderPayloadLibrary(groups);
  setBoundText('library_hint', libraryHint(groups, !!state.allow_unsafe));
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
    const current = lines.get(diagnostic.line) || { severity: diagnostic.severity, titles: [] };
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
  const lines = payloadField.value.split('\n');

  const gutterLines = document.createElement('div');
  gutterLines.className = 'editor__gutter-lines';
  gutterLines.style.height = `${uiState.padTop * 2 + lines.length * uiState.lineHeight}px`;

  lines.forEach((_line, index) => {
    const lineNo = index + 1;
    const row = document.createElement('div');
    const lineState = lineMap.get(lineNo);
    row.className = `editor__gutter-line${
      lineState ? ` editor__gutter-line--${lineState.severity}` : ''
    }`;
    row.style.top = `${uiState.padTop + index * uiState.lineHeight}px`;
    row.style.height = `${uiState.lineHeight}px`;
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
      uiState.padTop + (diagnostic.line - 1) * uiState.lineHeight + uiState.lineHeight - 4
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

function renderEmpty(container, message) {
  if (!container) {
    return;
  }
  const empty = document.createElement('p');
  empty.className = 'validation__empty';
  empty.textContent = message;
  container.replaceChildren(empty);
}

function renderDiagnosticsList(diagnostics = []) {
  if (!validationDiagnostics) {
    return;
  }
  if (!diagnostics.length) {
    renderEmpty(validationDiagnostics, 'No issues detected.');
    return;
  }

  const items = diagnostics.map((diagnostic) => {
    const item = document.createElement('article');
    item.className = `validation__item validation__item--${diagnostic.severity}`;
    item.title = itemTitle(diagnostic);

    const line = document.createElement('p');
    line.className = 'validation__line';
    line.textContent = `Line ${diagnostic.line}, col ${diagnostic.column}`;

    const message = document.createElement('p');
    message.className = 'validation__message';
    message.textContent = diagnostic.message;

    const hint = document.createElement('p');
    hint.className = 'validation__hint';
    hint.textContent = diagnostic.hint;

    item.appendChild(line);
    item.appendChild(message);
    item.appendChild(hint);
    return item;
  });
  validationDiagnostics.replaceChildren(...items);
}

function renderUnsafeList(items = []) {
  if (!validationUnsafe) {
    return;
  }
  if (!items.length) {
    renderEmpty(validationUnsafe, 'No unsafe commands detected.');
    return;
  }

  const nodes = items.map((itemData) => {
    const item = document.createElement('article');
    item.className = `validation__item validation__item--${itemData.severity}`;
    item.title = itemTitle(itemData);

    const line = document.createElement('p');
    line.className = 'validation__line';
    line.textContent = `Line ${itemData.line}`;

    const message = document.createElement('p');
    message.className = 'validation__message';
    message.textContent = itemData.command;

    const hint = document.createElement('p');
    hint.className = 'validation__hint';
    hint.textContent = itemData.hint;

    item.appendChild(line);
    item.appendChild(message);
    item.appendChild(hint);
    return item;
  });
  validationUnsafe.replaceChildren(...nodes);
}

function renderCommandList(commands = []) {
  if (!validationCommands) {
    return;
  }
  if (!commands.length) {
    renderEmpty(validationCommands, 'No commands parsed yet.');
    return;
  }

  const nodes = commands.map((command) => {
    const item = document.createElement('article');
    item.className = 'validation__item';
    item.style.paddingLeft = `${0.75 + command.depth * 0.8}rem`;

    const line = document.createElement('p');
    line.className = 'validation__line';
    line.textContent = `Line ${command.line}`;

    const label = document.createElement('p');
    label.className = 'validation__command';
    const labelName = document.createElement('span');
    labelName.className = 'validation__command-label';
    labelName.textContent = command.label;
    label.appendChild(labelName);
    if (command.detail) {
      label.appendChild(document.createTextNode(` - ${command.detail}`));
    }

    item.appendChild(line);
    item.appendChild(label);
    return item;
  });
  validationCommands.replaceChildren(...nodes);
}

function renderPendingValidation() {
  setBadge(validationBadge, 'Checking…', 'accent');
  setBoundText('validation_counts', 'Waiting for dry run');
  setBoundText('validation_summary', 'Checking payload...');
  setBoundText(
    'validation_detail',
    `${uiState.modeDescription} Validation updates as you type.`.trim(),
  );
  renderEmpty(validationDiagnostics, 'Checking for line-level issues...');
  renderEmpty(validationUnsafe, 'Checking for unsafe commands...');
  renderEmpty(validationCommands, 'Parsing commands...');
  renderEditorDecorations({ diagnostics: [] });
  updateControls();
}

function renderValidation(validation) {
  uiState.validation = validation;
  setBadge(validationBadge, validation.badge_label || 'Ready', validation.badge_tone || 'success');
  setBoundText('validation_counts', validation.counts_label || '');
  setBoundText('validation_summary', validation.summary || 'Dry run complete.');
  setBoundText(
    'validation_detail',
    `${validation.detail || ''} ${uiState.modeDescription}`.trim(),
  );
  renderDiagnosticsList(validation.diagnostics || []);
  renderUnsafeList(validation.unsafe_commands || []);
  renderCommandList(validation.parsed_commands || []);
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
  }, 180);
}

async function validatePayloadDraft() {
  if (!payloadField) {
    return;
  }
  const requestId = ++uiState.validationRequest;

  try {
    const result = await requestJson('/api/validate', {
      method: 'POST',
      body: JSON.stringify({ payload: payloadField.value }),
    });
    if (requestId !== uiState.validationRequest) {
      return;
    }
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
  setBoundText('ap_ssid', state.ap_ssid);
  setBoundText('ap_password', state.ap_password || 'Open network');
  applyMode(state);
  applyLibraryState(state);
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
  }
  setNotice(state.message || '', state.notice || 'quiet');
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
    applyLibraryState(result);
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

async function loadLibraryPayload(payloadId) {
  if (!payloadId) {
    return;
  }

  uiState.loadingLibrary = true;
  updateControls();
  try {
    const result = await requestJson('/api/payload-library/load', {
      method: 'POST',
      body: JSON.stringify({ id: payloadId }),
    });
    payloadField.value = result.payload || '';
    measureEditor();
    uiState.validating = false;
    if (result.validation) {
      renderValidation(result.validation);
    }
    setBoundText('payload_state', 'Library preview');
    setNotice(result.message, result.notice || 'success');
  } catch (error) {
    if (librarySelect) {
      librarySelect.value = '';
    }
    if (error.data?.validation) {
      renderValidation(error.data.validation);
    }
    setNotice(error.message, 'error');
  } finally {
    uiState.loadingLibrary = false;
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
  queueValidation();
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

if (librarySelect) {
  librarySelect.addEventListener('change', () => {
    loadLibraryPayload(librarySelect.value);
  });
}

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

loadBootstrap().catch((error) => setNotice(error.message, 'error'));
