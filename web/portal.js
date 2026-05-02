const notice = document.getElementById('notice');
const payloadField = document.getElementById('payload');
const saveButton = document.getElementById('save');
const runButton = document.getElementById('run');
const refreshButton = document.getElementById('refresh');
const unsafeToggle = document.getElementById('unsafe-toggle');
const runHistory = document.getElementById('run-history');
const editorGutter = document.getElementById('editor-gutter');
const editorMarkers = document.getElementById('editor-markers');
const infoIcon = document.getElementById('info-icon');
const validationModal = document.getElementById('validation-modal');
const modalBackdrop = document.getElementById('modal-backdrop');
const modalBody = document.getElementById('modal-body');
const modalSubtitle = document.getElementById('modal-subtitle');
const modalClose = document.getElementById('modal-close');
const validationBadge = document.querySelector('[data-bind="validation_badge"]');

const uiState = {
  charWidth: 8,
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
  if (unsafeToggle) {
    unsafeToggle.disabled = uiState.togglingUnsafe;
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

    item.appendChild(top);
    item.appendChild(preview);
    item.appendChild(meta);

    if (entry.message) {
      const message = document.createElement('p');
      message.className = 'history__message';
      const firstLine = (entry.message || '').split('\n')[0];
      const truncated = firstLine.length > 60 ? firstLine.slice(0, 60) + '…' : firstLine;
      message.textContent = truncated;
      message.title = entry.message;
      item.appendChild(message);
    }

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
    item.title = [diagnostic.message, diagnostic.hint].filter(Boolean).join('\n\n');

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
  setBadge(validationBadge, validation.badge_label || 'Ready', validation.badge_tone || 'success');
  setBoundText('validation_summary', validation.summary || 'Dry run complete.');

  const diagnostics = validation.diagnostics || [];
  renderModalDiagnostics(diagnostics);

  const errorCount = diagnostics.filter((d) => d.severity === 'error').length;
  const warningCount = diagnostics.filter((d) => d.severity === 'warning').length;

  if (infoIcon) {
    const hasIssues = diagnostics.length > 0;
    infoIcon.style.display = hasIssues ? 'inline-flex' : 'none';
    if (hasIssues) {
      const labelParts = [];
      if (errorCount) labelParts.push(`${errorCount} error${errorCount > 1 ? 's' : ''}`);
      if (warningCount) labelParts.push(`${warningCount} warning${warningCount > 1 ? 's' : ''}`);
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

loadBootstrap().catch((error) => setNotice(error.message, 'error'));
