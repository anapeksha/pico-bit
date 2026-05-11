<aside class="sidebar sidebar--right">
  <div class="panel">
    <p class="panel__title">Layout</p>
    <p class="panel__text">Tell how the host interprets typed text.</p>
    <div class="layout__field__container">
      <div class="field">
        <label class="field__label" for="keyboard-os">Operating system</label>
        <select id="keyboard-os" class="field__input field__input--select"></select>
      </div>
      <div class="field">
        <label class="field__label" for="keyboard-layout">Keyboard layout</label>
        <select id="keyboard-layout" class="field__input field__input--select"></select>
      </div>
    </div>
    <p class="panel__hint" data-bind="keyboard_layout_hint">
      Used for typed text and remembered on the device.
    </p>
  </div>

  <div class="panel">
    <p class="panel__title">Loot</p>
    <div id="loot-body">
      <p class="history__empty">No loot collected yet.</p>
    </div>
    <div class="loot__actions" id="loot-actions">
      <button class="btn btn--ghost btn--wide" id="loot-import-usb" type="button">
        Import USB loot
      </button>
      <button
        class="btn btn--ghost btn--icon"
        id="loot-download"
        type="button"
        aria-label="Download loot.json"
        title="Download loot.json"
        hidden
      >
        <svg
          class="btn__icon btn__icon--only"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="7 10 12 15 17 10"></polyline>
          <line x1="12" y1="15" x2="12" y2="3"></line>
        </svg>
      </button>
    </div>
  </div>

  <div class="panel">
    <p class="panel__title">Recent runs</p>
    <div
      class="history"
      id="run-history"
      aria-live="polite"
      aria-label="Recent runs"
    >
      <p class="history__empty">No payloads have run yet.</p>
    </div>
  </div>
</aside>
