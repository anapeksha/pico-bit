<aside class="sidebar sidebar--left">
  <div class="panel">
    <p class="panel__title">About</p>
    <p class="panel__text">
      Two-stage drop-shell workflow for authorized security assessment.
    </p>
    <ul class="panel__list">
      <li>
        <strong>Stage&nbsp;1&nbsp;&middot;&nbsp;Recon</strong> - write DuckyScript to type
        commands or exfiltrate data from the target
      </li>
      <li>
        <strong>Stage&nbsp;2&nbsp;&middot;&nbsp;Inject</strong> - upload an agent binary,
        then HID-inject the USB execution stager; the agent writes loot back to the
        Pico drive
      </li>
      <li>Loot panel live-updates as data arrives</li>
    </ul>
  </div>

  <div class="panel">
    <p class="panel__title">Status</p>
    <dl class="meta">
      <div class="meta__row">
        <span class="meta__label">Seeded this boot</span>
        <span class="meta__value" data-bind="seeded">No</span>
      </div>
      <div class="meta__row">
        <span class="meta__label">Typing target</span>
        <span class="meta__value" data-bind="keyboard_target_label">
          Windows &middot; English (US)
        </span>
      </div>
    </dl>
    <div class="divider"></div>
    <form action="/logout" method="post">
      <button class="btn btn--danger btn--wide" type="submit">Sign out</button>
    </form>
  </div>
</aside>
