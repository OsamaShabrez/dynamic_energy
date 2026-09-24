class DynamicEnergyPanel extends HTMLElement {
  constructor() {
    super();

    this._hass = null;
    this._config = null;
    this._sources = [];
    this._interval = 10;
    this._loading = true;
    this._saving = false;
    this._error = null;
    this._expanded = new Set();
    this._adding = false;

    this.attachShadow({ mode: "open" });
  }

  set hass(value) {
    this._hass = value;

    if (this._loading && value) {
      this._loadConfig();
    }

    this._render();
  }

  set panel(value) {
    this._panel = value;
  }

  set narrow(value) {
    this._narrow = value;
    this._render();
  }

  connectedCallback() {
    this._render();
  }

  async _loadConfig() {
    if (!this._hass || !this._loading) {
      return;
    }

    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "dynamic_energy/get_config",
      });

      this._config = result;
      this._sources = (result.sources || []).map((source) => ({ ...source }));
      this._interval = Number(result.observation_interval) || 10;
      this._loading = false;

      this._render();
    } catch (error) {
      this._error =
        error?.message || "Unable to load Dynamic Energy configuration.";
      this._loading = false;
      this._render();
    }
  }

  _entityList(deviceClass) {
    if (!this._hass?.states) {
      return [];
    }

    return Object.entries(this._hass.states)
      .filter(([entityId, state]) => {
        if (!entityId.startsWith("sensor.")) {
          return false;
        }

        if (state.state === "unavailable" || state.state === "unknown") {
          return false;
        }

        return state.attributes?.device_class === deviceClass;
      })
      .map(([entityId, state]) => ({
        entityId,
        name: state.attributes?.friendly_name || entityId,
      }))
      .sort((a, b) =>
        a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
      );
  }

  _powerEntities() {
    return this._entityList("power");
  }

  _energyEntities() {
    return this._entityList("energy");
  }

  _entityName(entityId) {
    if (!entityId) {
      return "Not selected";
    }

    const state = this._hass?.states?.[entityId];

    return state?.attributes?.friendly_name || entityId;
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }

    if (this._loading) {
      this.shadowRoot.innerHTML = `
        <style>${this._styles()}</style>
        <main class="page">
          <div class="loading">
            <div class="spinner"></div>
            <span>Loading Dynamic Energy...</span>
          </div>
        </main>
      `;
      return;
    }

    if (this._error) {
      this.shadowRoot.innerHTML = `
        <style>${this._styles()}</style>
        <main class="page">
          <div class="error-card">
            <div class="error-icon">!</div>
            <div>
              <h2>Unable to load configuration</h2>
              <p>${this._escape(this._error)}</p>
              <button class="primary" id="retry">
                Try again
              </button>
            </div>
          </div>
        </main>
      `;

      this.shadowRoot.querySelector("#retry")?.addEventListener("click", () => {
        this._loading = true;
        this._error = null;
        this._render();
        this._loadConfig();
      });

      return;
    }

    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>

      <main class="page">

        <header class="header">
          <div>
            <div class="eyebrow">CONFIGURATION</div>
            <h1>Dynamic Energy</h1>
            <p>
              Manage monitoring and smart plugs.
            </p>
          </div>

          <button
            class="save-button"
            id="save"
            ${this._saving ? "disabled" : ""}
          >
            ${
              this._saving
                ? '<span class="button-spinner"></span> Saving...'
                : "Save changes"
            }
          </button>
        </header>

        ${this._renderMonitoring()}

        <section class="section">
          <div class="section-heading">
            <div>
              <h2>Smart plugs</h2>
              <p>
                Configure the devices included in
                apartment energy monitoring.
              </p>
            </div>

            <button
              class="secondary"
              id="add"
            >
              <span class="plus">+</span>
              Add smart plug
            </button>
          </div>

          <div class="plug-list">
            ${
              this._sources.length
                ? this._sources
                    .map((source, index) => this._renderSource(source, index))
                    .join("")
                : `
                  <div class="empty-card">
                    <div class="empty-icon">⚡</div>
                    <h3>No smart plugs configured</h3>
                    <p>
                      Add your first smart plug
                      to start energy monitoring.
                    </p>
                    <button
                      class="primary"
                      id="empty-add"
                    >
                      Add smart plug
                    </button>
                  </div>
                `
            }
          </div>

          ${this._adding ? this._renderAddForm() : ""}
        </section>

        <footer class="footer">
          <span>
            ${this._sources.length} smart plug${
              this._sources.length === 1 ? "" : "s"
            }
          </span>

          <button
            class="save-button"
            id="save-bottom"
            ${this._saving ? "disabled" : ""}
          >
            ${
              this._saving
                ? '<span class="button-spinner"></span> Saving...'
                : "Save changes"
            }
          </button>
        </footer>

      </main>
    `;

    this._bindEvents();
  }

  _renderMonitoring() {
    return `
      <section class="section monitoring">
        <div class="section-heading">
          <div>
            <h2>Monitoring</h2>
            <p>
              How often Dynamic Energy updates
              its measurements.
            </p>
          </div>
        </div>

        <div class="monitoring-card">
          <div class="setting-info">
            <div class="setting-icon">↻</div>
            <div>
              <strong>Update interval</strong>
              <span>
                Faster updates use slightly more
                processing.
              </span>
            </div>
          </div>

          <select id="interval">
            ${[5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
              .map(
                (value) => `
                  <option
                    value="${value}"
                    ${value === this._interval ? "selected" : ""}
                  >
                    ${value} seconds
                  </option>
                `,
              )
              .join("")}
          </select>
        </div>
      </section>
    `;
  }

  _renderSource(source, index) {
    const expanded = this._expanded.has(source.source_id);

    const powerName = this._entityName(source.power_entity);

    const energyName = this._entityName(source.energy_entity);

    return `
      <article
        class="plug-card ${expanded ? "expanded" : ""}"
        data-index="${index}"
      >

        <button
          class="plug-header"
          data-action="toggle"
          data-id="${this._escapeAttr(source.source_id)}"
        >
          <div class="plug-identity">
            <div class="plug-icon">
              ${source.icon ? this._icon(source.icon) : "⚡"}
            </div>

            <div>
              <h3>
                ${this._escape(source.name || "Unnamed smart plug")}
              </h3>

              <p>
                ${this._escape(powerName)}
                ·
                ${this._escape(energyName)}
              </p>
            </div>
          </div>

          <div class="header-actions">
            <span
              class="energy-badge ${source.energy_type}"
            >
              ${source.energy_type === "cumulative" ? "Cumulative" : "Monthly"}
            </span>

            <span class="chevron">
              ${expanded ? "⌃" : "⌄"}
            </span>
          </div>
        </button>

        ${expanded ? this._renderSourceEditor(source, index) : ""}

      </article>
    `;
  }

  _renderSourceEditor(source, index) {
    return `
      <div class="editor">

        <div class="form-grid">

          <label class="field full">
            <span>Name</span>
            <input
              data-field="name"
              data-index="${index}"
              value="${this._escapeAttr(source.name || "")}"
              placeholder="e.g. Bedroom Matter Plug"
            />
          </label>

          <label class="field">
            <span>Power sensor</span>
            <select
              data-field="power_entity"
              data-index="${index}"
            >
              <option value="">
                Select power sensor
              </option>
              ${this._entityOptions(this._powerEntities(), source.power_entity)}
            </select>
          </label>

          <label class="field">
            <span>Energy sensor</span>
            <select
              data-field="energy_entity"
              data-index="${index}"
            >
              <option value="">
                Select energy sensor
              </option>
              ${this._entityOptions(
                this._energyEntities(),
                source.energy_entity,
              )}
            </select>
          </label>

          <label class="field">
            <span>Energy type</span>
            <select
              data-field="energy_type"
              data-index="${index}"
            >
              <option
                value="monthly"
                ${source.energy_type === "monthly" ? "selected" : ""}
              >
                Monthly reset
              </option>
              <option
                value="cumulative"
                ${source.energy_type === "cumulative" ? "selected" : ""}
              >
                Cumulative
              </option>
            </select>
          </label>

          <label class="field">
            <span>Icon</span>
            <input
              data-field="icon"
              data-index="${index}"
              value="${this._escapeAttr(source.icon || "")}"
              placeholder="mdi:flash"
            />
          </label>

        </div>

        <div class="editor-footer">

          <button
            class="danger"
            data-action="remove"
            data-index="${index}"
          >
            Remove smart plug
          </button>

          <button
            class="secondary"
            data-action="collapse"
            data-id="${this._escapeAttr(source.source_id)}"
          >
            Done
          </button>

        </div>

      </div>
    `;
  }

  _renderAddForm() {
    return `
      <div class="add-card">

        <div class="add-header">
          <div>
            <h3>Add smart plug</h3>
            <p>
              Add a new device to energy monitoring.
            </p>
          </div>

          <button
            class="icon-button"
            id="cancel-add"
            aria-label="Cancel"
          >
            ×
          </button>
        </div>

        <div class="form-grid">

          <label class="field full">
            <span>Name</span>
            <input
              id="new-name"
              placeholder="e.g. Bedroom Matter Plug"
            />
          </label>

          <label class="field">
            <span>Power sensor</span>
            <select id="new-power">
              <option value="">
                Select power sensor
              </option>
              ${this._entityOptions(this._powerEntities())}
            </select>
          </label>

          <label class="field">
            <span>Energy sensor</span>
            <select id="new-energy">
              <option value="">
                Select energy sensor
              </option>
              ${this._entityOptions(this._energyEntities())}
            </select>
          </label>

          <label class="field">
            <span>Energy type</span>
            <select id="new-type">
              <option value="monthly">
                Monthly reset
              </option>
              <option value="cumulative">
                Cumulative
              </option>
            </select>
          </label>

          <label class="field">
            <span>Icon</span>
            <input
              id="new-icon"
              placeholder="mdi:flash"
            />
          </label>

        </div>

        <div class="editor-footer">
          <button
            class="secondary"
            id="cancel-add-bottom"
          >
            Cancel
          </button>

          <button
            class="primary"
            id="confirm-add"
          >
            Add smart plug
          </button>
        </div>

      </div>
    `;
  }

  _entityOptions(entities, selected = "") {
    return entities
      .map(
        (entity) => `
          <option
            value="${this._escapeAttr(entity.entityId)}"
            ${entity.entityId === selected ? "selected" : ""}
          >
            ${this._escape(entity.name)}
          </option>
        `,
      )
      .join("");
  }

  _icon(icon) {
    if (!icon.startsWith("mdi:")) {
      return "⚡";
    }

    return "⚡";
  }

  _bindEvents() {
    this.shadowRoot
      .querySelector("#interval")
      ?.addEventListener("change", (event) => {
        this._interval = Number(event.target.value);
      });

    this.shadowRoot.querySelectorAll("[data-field]").forEach((element) => {
      element.addEventListener("input", (event) =>
        this._updateField(event.target),
      );

      element.addEventListener("change", (event) =>
        this._updateField(event.target),
      );
    });

    this.shadowRoot
      .querySelectorAll('[data-action="toggle"]')
      .forEach((button) => {
        button.addEventListener("click", () => {
          const id = button.dataset.id;

          if (this._expanded.has(id)) {
            this._expanded.delete(id);
          } else {
            this._expanded.add(id);
          }

          this._render();
        });
      });

    this.shadowRoot
      .querySelectorAll('[data-action="collapse"]')
      .forEach((button) => {
        button.addEventListener("click", () => {
          this._expanded.delete(button.dataset.id);
          this._render();
        });
      });

    this.shadowRoot
      .querySelectorAll('[data-action="remove"]')
      .forEach((button) => {
        button.addEventListener("click", () => {
          const index = Number(button.dataset.index);

          this._removeSource(index);
        });
      });

    this.shadowRoot.querySelector("#add")?.addEventListener("click", () => {
      this._adding = true;
      this._render();
    });

    this.shadowRoot
      .querySelector("#empty-add")
      ?.addEventListener("click", () => {
        this._adding = true;
        this._render();
      });

    this.shadowRoot
      .querySelector("#cancel-add")
      ?.addEventListener("click", () => {
        this._adding = false;
        this._render();
      });

    this.shadowRoot
      .querySelector("#cancel-add-bottom")
      ?.addEventListener("click", () => {
        this._adding = false;
        this._render();
      });

    this.shadowRoot
      .querySelector("#confirm-add")
      ?.addEventListener("click", () => {
        this._addSource();
      });

    this.shadowRoot
      .querySelector("#save")
      ?.addEventListener("click", () => this._save());

    this.shadowRoot
      .querySelector("#save-bottom")
      ?.addEventListener("click", () => this._save());
  }

  _updateField(element) {
    const index = Number(element.dataset.index);

    const field = element.dataset.field;

    if (!this._sources[index] || !field) {
      return;
    }

    this._sources[index] = {
      ...this._sources[index],
      [field]: element.value,
    };
  }

  _removeSource(index) {
    const source = this._sources[index];

    if (!source) {
      return;
    }

    const confirmed = window.confirm(
      `Remove "${source.name}" from Dynamic Energy monitoring?`,
    );

    if (!confirmed) {
      return;
    }

    this._sources.splice(index, 1);
    this._render();
  }

  _addSource() {
    const name = this.shadowRoot.querySelector("#new-name")?.value.trim();

    const power = this.shadowRoot.querySelector("#new-power")?.value;

    const energy = this.shadowRoot.querySelector("#new-energy")?.value;

    const type = this.shadowRoot.querySelector("#new-type")?.value || "monthly";

    const icon = this.shadowRoot.querySelector("#new-icon")?.value.trim() || "";

    if (!name || !power || !energy) {
      window.alert("Please provide a name, power sensor and energy sensor.");
      return;
    }

    const source = {
      source_id: globalThis.crypto?.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random()}`,
      name,
      power_entity: power,
      energy_entity: energy,
      energy_type: type,
      icon,
    };

    this._sources.push(source);
    this._adding = false;
    this._expanded.add(source.source_id);

    this._render();
  }

  async _save() {
    if (!this._hass || this._saving || !this._config) {
      return;
    }

    this._saving = true;
    this._render();

    try {
      await this._hass.connection.sendMessagePromise({
        type: "dynamic_energy/save_config",
        entry_id: this._config.entry_id,
        observation_interval: this._interval,
        sources: this._sources,
      });

      this._saving = false;
      this._render();

      this.dispatchEvent(
        new CustomEvent("dynamic-energy-saved", {
          bubbles: true,
          composed: true,
        }),
      );
    } catch (error) {
      this._saving = false;
      this._error = error?.message || "Unable to save configuration.";
      this._render();
    }
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _escapeAttr(value) {
    return this._escape(value);
  }

  _styles() {
    return `
      :host {
        display: block;
        min-height: 100%;
        background:
          var(
            --primary-background-color,
            #111111
          );
        color:
          var(
            --primary-text-color,
            #f5f5f5
          );
        box-sizing: border-box;
      }

      * {
        box-sizing: border-box;
      }

      button,
      input,
      select {
        font: inherit;
      }

      button {
        cursor: pointer;
      }

      .page {
        width: min(
          1180px,
          calc(100% - 48px)
        );
        margin: 0 auto;
        padding: 42px 0 56px;
      }

      .header {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 24px;
        margin-bottom: 40px;
      }

      .eyebrow {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.16em;
        opacity: 0.55;
        margin-bottom: 8px;
      }

      h1 {
        margin: 0;
        font-size: 32px;
        line-height: 1.15;
        font-weight: 600;
        letter-spacing: -0.025em;
      }

      h2 {
        margin: 0;
        font-size: 20px;
        font-weight: 600;
      }

      h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
      }

      p {
        margin: 7px 0 0;
        color:
          var(
            --secondary-text-color,
            #9b9b9b
          );
        font-size: 14px;
        line-height: 1.5;
      }

      .section {
        margin-bottom: 40px;
      }

      .section-heading {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        gap: 20px;
        margin-bottom: 16px;
      }

      .monitoring-card,
      .plug-card,
      .add-card,
      .empty-card {
        border: 1px solid
          var(
            --divider-color,
            rgba(255,255,255,0.09)
          );
        background:
          var(
            --card-background-color,
            rgba(255,255,255,0.035)
          );
        border-radius: 16px;
        overflow: hidden;
      }

      .monitoring-card {
        min-height: 82px;
        padding: 18px 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 20px;
      }

      .setting-info {
        display: flex;
        align-items: center;
        gap: 14px;
      }

      .setting-info span {
        display: block;
        margin-top: 4px;
        font-size: 13px;
        color:
          var(
            --secondary-text-color,
            #9b9b9b
          );
      }

      .setting-icon,
      .plug-icon {
        width: 42px;
        height: 42px;
        display: grid;
        place-items: center;
        border-radius: 12px;
        background:
          var(
            --secondary-background-color,
            rgba(255,255,255,0.07)
          );
        font-size: 19px;
      }

      select,
      input {
        width: 100%;
        min-height: 44px;
        border: 1px solid
          var(
            --divider-color,
            rgba(255,255,255,0.12)
          );
        border-radius: 10px;
        background:
          var(
            --secondary-background-color,
            rgba(255,255,255,0.06)
          );
        color:
          var(
            --primary-text-color,
            #f5f5f5
          );
        padding: 0 13px;
        outline: none;
      }

      select:focus,
      input:focus {
        border-color:
          var(
            --primary-color,
            #03a9f4
          );
        box-shadow:
          0 0 0 2px
          color-mix(
            in srgb,
            var(--primary-color, #03a9f4) 18%,
            transparent
          );
      }

      .monitoring-card select {
        width: 150px;
      }

      .plug-list {
        display: grid;
        gap: 10px;
      }

      .plug-card {
        transition:
          border-color 160ms ease,
          background 160ms ease;
      }

      .plug-card.expanded {
        border-color:
          color-mix(
            in srgb,
            var(--primary-color, #03a9f4) 35%,
            var(--divider-color, rgba(255,255,255,0.1))
          );
      }

      .plug-header {
        width: 100%;
        border: 0;
        background: transparent;
        color: inherit;
        padding: 15px 17px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 18px;
        text-align: left;
      }

      .plug-identity {
        display: flex;
        align-items: center;
        gap: 13px;
        min-width: 0;
      }

      .plug-identity > div:last-child {
        min-width: 0;
      }

      .plug-identity h3,
      .plug-identity p {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .plug-identity p {
        font-size: 12px;
      }

      .header-actions {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-shrink: 0;
      }

      .energy-badge {
        border-radius: 999px;
        padding: 5px 9px;
        font-size: 11px;
        font-weight: 600;
        background:
          var(
            --secondary-background-color,
            rgba(255,255,255,0.07)
          );
      }

      .energy-badge.cumulative {
        color:
          var(
            --primary-color,
            #03a9f4
          );
      }

      .chevron {
        width: 24px;
        text-align: center;
        opacity: 0.65;
        font-size: 18px;
      }

      .editor,
      .add-card {
        padding: 0 20px 20px;
      }

      .form-grid {
        display: grid;
        grid-template-columns:
          repeat(2, minmax(0, 1fr));
        gap: 16px;
        padding-top: 4px;
      }

      .field {
        display: flex;
        flex-direction: column;
        gap: 7px;
      }

      .field.full {
        grid-column: 1 / -1;
      }

      .field > span {
        font-size: 12px;
        font-weight: 600;
        opacity: 0.75;
      }

      .editor-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        margin-top: 22px;
        padding-top: 18px;
        border-top: 1px solid
          var(
            --divider-color,
            rgba(255,255,255,0.08)
          );
      }

      .add-card {
        margin-top: 12px;
        border-color:
          color-mix(
            in srgb,
            var(--primary-color, #03a9f4) 35%,
            var(--divider-color, rgba(255,255,255,0.1))
          );
      }

      .add-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        margin-bottom: 20px;
      }

      .secondary,
      .primary,
      .danger,
      .save-button {
        min-height: 40px;
        border-radius: 10px;
        padding: 0 15px;
        border: 0;
        font-weight: 600;
        font-size: 13px;
      }

      .secondary {
        background:
          var(
            --secondary-background-color,
            rgba(255,255,255,0.07)
          );
        color: inherit;
      }

      .primary,
      .save-button {
        background:
          var(
            --primary-color,
            #03a9f4
          );
        color:
          var(
            --text-primary-color,
            white
          );
      }

      .save-button {
        min-width: 132px;
      }

      .save-button:disabled,
      .primary:disabled {
        opacity: 0.6;
        cursor: default;
      }

      .danger {
        color:
          var(
            --error-color,
            #f44336
          );
        background: transparent;
        padding-left: 0;
      }

      .icon-button {
        width: 36px;
        height: 36px;
        border: 0;
        border-radius: 50%;
        background:
          var(
            --secondary-background-color,
            rgba(255,255,255,0.07)
          );
        color: inherit;
        font-size: 23px;
      }

      .plus {
        font-size: 18px;
        margin-right: 5px;
      }

      .empty-card {
        text-align: center;
        padding: 46px 20px;
      }

      .empty-icon {
        font-size: 30px;
        margin-bottom: 12px;
      }

      .empty-card button {
        margin-top: 20px;
      }

      .footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 20px;
        padding-top: 10px;
        color:
          var(
            --secondary-text-color,
            #9b9b9b
          );
        font-size: 13px;
      }

      .loading {
        min-height: 60vh;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        color:
          var(
            --secondary-text-color,
            #9b9b9b
          );
      }

      .spinner,
      .button-spinner {
        border: 2px solid
          rgba(255,255,255,0.18);
        border-top-color:
          var(
            --primary-color,
            #03a9f4
          );
        border-radius: 50%;
        animation: spin 700ms linear infinite;
      }

      .spinner {
        width: 22px;
        height: 22px;
      }

      .button-spinner {
        width: 13px;
        height: 13px;
        display: inline-block;
        margin-right: 7px;
        vertical-align: -2px;
      }

      .error-card {
        max-width: 620px;
        margin: 100px auto;
        padding: 24px;
        border-radius: 16px;
        border: 1px solid
          var(
            --error-color,
            #f44336
          );
        display: flex;
        gap: 16px;
      }

      .error-icon {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        display: grid;
        place-items: center;
        background:
          var(
            --error-color,
            #f44336
          );
        color: white;
        font-weight: 700;
      }

      .error-card button {
        margin-top: 18px;
      }

      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }

      @media (max-width: 700px) {
        .page {
          width: min(
            100% - 28px,
            1180px
          );
          padding-top: 24px;
        }

        .header,
        .section-heading {
          align-items: stretch;
          flex-direction: column;
        }

        .header .save-button {
          width: 100%;
        }

        .monitoring-card {
          align-items: stretch;
          flex-direction: column;
        }

        .monitoring-card select {
          width: 100%;
        }

        .form-grid {
          grid-template-columns: 1fr;
        }

        .field.full {
          grid-column: auto;
        }

        .plug-header {
          align-items: flex-start;
        }

        .header-actions {
          flex-direction: column;
          gap: 5px;
        }

        .energy-badge {
          display: none;
        }

        .editor-footer,
        .footer {
          align-items: stretch;
          flex-direction: column;
        }

        .editor-footer button,
        .footer button {
          width: 100%;
        }

        .secondary {
          width: 100%;
        }
      }
    `;
  }
}

if (!customElements.get("dynamic-energy-panel")) {
  customElements.define("dynamic-energy-panel", DynamicEnergyPanel);
}
