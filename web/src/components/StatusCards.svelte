<div class="stats">
  <div class="stat">
    <div class="stat__label">Access point</div>
    <div class="stat__value" data-bind="ap_ssid">PicoBit</div>
  </div>
  <div class="stat">
    <div class="stat__label">AP password</div>
    <div class="stat__password-row">
      <div
        class="stat__value stat__value--mono stat__value--clip"
        data-bind="ap_password"
        data-password
        id="ap-password-value"
      >
        Open network
      </div>
      <button
        class="stat__eye"
        id="ap-password-toggle"
        aria-label="Show AP password"
        aria-pressed="false"
        type="button"
        hidden
      >
        <svg
          class="stat__eye-icon stat__eye-icon--show"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
          <circle cx="12" cy="12" r="3"></circle>
        </svg>
        <svg
          class="stat__eye-icon stat__eye-icon--hide"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path
            d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"
          ></path>
          <line x1="1" y1="1" x2="23" y2="23"></line>
        </svg>
      </button>
    </div>
  </div>
  <div class="stat">
    <div class="stat__label">Portal auth</div>
    <div class="stat__value" data-bind="auth_label">-</div>
  </div>
  <div class="stat">
    <div class="stat__label">Host HID</div>
    <div class="stat__value" data-bind="hid_state" aria-live="polite">Waiting</div>
  </div>
  <div class="stat" id="host-usb-stat">
    <div class="stat__label">Host USB</div>
    <div class="stat__value stat__value--state" id="host-usb-state" aria-live="polite">
      Waiting
    </div>
  </div>
</div>
