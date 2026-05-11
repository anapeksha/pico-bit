<section class="accordion__section accordion__section--open" id="accordion-ducky">
  <button
    class="accordion__header"
    id="accordion-ducky-btn"
    type="button"
    aria-expanded="true"
    aria-controls="accordion-ducky-body"
  >
    <span class="accordion__title">Ducky Editor</span>
    <span class="badge" data-bind="payload_state">Saved on device</span>
    <svg
      class="accordion__chevron"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>
  </button>

  <div class="accordion__body" id="accordion-ducky-body">
    <div class="editor__bar">
      <div class="editor__file">payload.dd</div>
    </div>

    <div
      class="notice notice--hidden"
      id="notice"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    ></div>

    <div class="editor__stage">
      <div class="editor__gutter" id="editor-gutter" aria-hidden="true"></div>
      <div class="editor__surface">
        <div class="editor__markers" id="editor-markers" aria-hidden="true"></div>
        <div class="editor__highlight" id="editor-highlight" aria-hidden="true"></div>
        <label for="payload" class="sr-only">Payload script</label>
        <textarea
          id="payload"
          class="editor__input"
          spellcheck="false"
          autocapitalize="off"
          autocomplete="off"
          placeholder="REM Write your payload here"
          wrap="off"
          aria-describedby="editor-status"
        ></textarea>
      </div>
    </div>

    <div class="editor__footer">
      <div class="editor__status" id="editor-status">
        <span
          class="badge"
          data-bind="validation_badge"
          aria-live="polite"
          aria-atomic="true"
        >
          Checking...
        </span>
        <span class="editor__status-text" data-bind="validation_summary">
          Dry run runs before save and execution.
        </span>
        <button
          class="editor__info-icon"
          id="info-icon"
          type="button"
          aria-label="Show validation errors"
          style="display: none"
        >
          <svg
            viewBox="0 0 24 24"
            width="14"
            height="14"
            fill="none"
            stroke="currentcolor"
            stroke-width="2.4"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <span data-bind="info_count">View issues</span>
        </button>
      </div>
      <div class="editor__actions">
        <button class="btn btn--ghost" id="refresh" type="button">Reload</button>
        <button class="btn btn--ghost" id="save" type="button">Save</button>
        <button class="btn btn--primary" id="run" type="button">Save &amp; run</button>
      </div>
    </div>
  </div>
</section>
