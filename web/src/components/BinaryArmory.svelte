<section class="accordion__section" id="accordion-armory">
  <button
    class="accordion__header"
    id="accordion-armory-btn"
    type="button"
    aria-expanded="false"
    aria-controls="accordion-armory-body"
  >
    <span class="accordion__title">Binary Armory</span>
    <span class="badge badge--accent" id="armory-badge" hidden></span>
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

  <div class="accordion__body accordion__body--scroll" id="accordion-armory-body">
    <div
      class="upload-zone"
      id="upload-zone"
      role="button"
      tabindex="0"
      aria-label="Upload binary file"
    >
      <input
        type="file"
        id="binary-file-input"
        class="upload-zone__input"
        aria-hidden="true"
        tabindex="-1"
      />
      <div class="upload-zone__prompt" id="upload-zone-prompt">
        <svg
          class="upload-zone__icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <polyline points="16 16 12 12 8 16"></polyline>
          <line x1="12" y1="12" x2="12" y2="21"></line>
          <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"></path>
        </svg>
        <p class="upload-zone__text">Drag &amp; drop or click to upload</p>
        <p class="upload-zone__hint">
          EXE, ELF, or Mach-O binaries only. Unix binaries may be extensionless.
        </p>
      </div>
      <div class="upload-zone__file" id="upload-file-display" hidden>
        <svg
          class="upload-zone__file-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
          <polyline points="13 2 13 9 20 9"></polyline>
        </svg>
        <span class="upload-zone__filename" id="upload-filename"></span>
        <span class="upload-zone__size" id="upload-filesize"></span>
      </div>
    </div>

    <div class="upload-progress" id="upload-progress" hidden>
      <div class="upload-progress__bar" id="upload-progress-bar" style="width: 0%"></div>
    </div>

    <div
      class="armory__notice notice notice--hidden"
      id="armory-notice"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    ></div>

    <div class="armory__controls">
      <div class="field">
        <label class="field__label" for="inject-os">Target OS</label>
        <select id="inject-os" class="field__input field__input--select">
          <option value="windows">Windows</option>
          <option value="linux">Linux</option>
          <option value="macos">macOS</option>
        </select>
      </div>
      <div class="armory__actions">
        <button class="btn btn--ghost" id="upload-binary-btn" type="button" disabled>
          Upload
        </button>
        <button class="btn btn--primary" id="inject-binary-btn" type="button" disabled>
          Inject
        </button>
      </div>
    </div>

    <div class="armory__snippet" id="armory-snippet" hidden>
      <p class="armory__snippet-label">USB command that will be typed:</p>
      <pre class="armory__snippet-code" id="armory-snippet-code"></pre>
    </div>
  </div>
</section>
