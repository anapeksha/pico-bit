<div class="modal" id="validation-modal" aria-hidden="true">
  <div class="modal__backdrop" id="modal-backdrop"></div>
  <div
    class="modal__dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-title"
    aria-describedby="modal-subtitle"
  >
    <div class="modal__header">
      <div class="modal__heading">
        <h3 class="modal__title" id="modal-title">Validation issues</h3>
        <p class="modal__subtitle" id="modal-subtitle">Errors found in the payload</p>
      </div>
      <button class="modal__close" type="button" aria-label="Close" id="modal-close">
        <svg
          viewBox="0 0 24 24"
          width="16"
          height="16"
          fill="none"
          stroke="currentcolor"
          stroke-width="2.2"
          stroke-linecap="round"
        >
          <line x1="6" y1="6" x2="18" y2="18"></line>
          <line x1="18" y1="6" x2="6" y2="18"></line>
        </svg>
      </button>
    </div>
    <div class="modal__body" id="modal-body">
      <p class="modal__empty">No issues detected.</p>
    </div>
  </div>
</div>
