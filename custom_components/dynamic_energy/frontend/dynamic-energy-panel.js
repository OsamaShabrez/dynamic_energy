class DynamicEnergyPanel extends HTMLElement {
  constructor() {
    super();

    this.attachShadow({ mode: "open" });

    this.hass = null;
    this.config = null;
    this.sources = [];
    this.editingId = null;
    this.modalOpen = false;
    this.loading = true;
    this.saving = false;
    this.error = null;
    this.brandToken = null;
  }

  set hass(value) {
    this._hass = value;

    if (value && !this._initialized) {
      this._initialized = true;
      this.initialize();
      return;
    }

    if (value && this._initialized) {
      this.updateLiveValues();
    }
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this.render();
  }

  async initialize() {
    await this.loadBrandToken();
    await this.loadConfig();
  }

  async loadBrandToken() {
    if (!this.hass?.connection) {
      return;
    }

    try {
      const result = await this.hass.connection.sendMessagePromise({
        type: "brands/access_token",
      });

      this.brandToken = result?.token || null;
    } catch (error) {
      console.warn("Dynamic Energy: unable to obtain brand image token", error);
    }
  }

  getLogoUrl() {
    const base = "/api/brands/integration/dynamic_energy";

    if (!this.brandToken) {
      return `${base}/icon.png`;
    }

    return `${base}/icon@2x.png?token=${encodeURIComponent(this.brandToken)}`;
  }

  async loadConfig() {
    if (!this.hass?.connection) {
      return;
    }

    this.loading = true;
    this.render();

    try {
      const result = await this.hass.connection.sendMessagePromise({
        type: "dynamic_energy/get_config",
      });

      this.config = result;

      this.sources = Array.isArray(result.sources)
        ? structuredClone(result.sources)
        : [];

      this.error = null;
    } catch (error) {
      console.error("Dynamic Energy: failed to load configuration", error);

      this.error = "Unable to load Dynamic Energy configuration.";
    } finally {
      this.loading = false;
      this.render();
    }
  }

  goBack() {
    if (this.modalOpen) {
      this.closeModal();
      return;
    }

    window.history.back();
  }

  get powerEntities() {
    if (!this.hass?.states) {
      return [];
    }

    return Object.values(this.hass.states)
      .filter((state) => {
        if (!state.entity_id.startsWith("sensor.")) {
          return false;
        }

        const deviceClass = state.attributes?.device_class;

        const unit = String(
          state.attributes?.unit_of_measurement || "",
        ).toLowerCase();

        return deviceClass === "power" || unit === "w" || unit === "kw";
      })
      .sort((a, b) => this.entityLabel(a).localeCompare(this.entityLabel(b)));
  }

  get energyEntities() {
    if (!this.hass?.states) {
      return [];
    }

    return Object.values(this.hass.states)
      .filter((state) => {
        if (!state.entity_id.startsWith("sensor.")) {
          return false;
        }

        const deviceClass = state.attributes?.device_class;

        const unit = String(
          state.attributes?.unit_of_measurement || "",
        ).toLowerCase();

        return deviceClass === "energy" || unit === "kwh" || unit === "wh";
      })
      .sort((a, b) => this.entityLabel(a).localeCompare(this.entityLabel(b)));
  }

  entityLabel(state) {
    return state.attributes?.friendly_name || state.entity_id;
  }

  formatEntityOption(state) {
    const friendly = this.entityLabel(state);

    if (friendly === state.entity_id) {
      return friendly;
    }

    return `${friendly} — ${state.entity_id}`;
  }

  get currentForm() {
    return (
      this._form || {
        name: "",
        power_entity: "",
        energy_entity: "",
        energy_type: "monthly",
        icon: "mdi:flash",
      }
    );
  }

  openAdd() {
    this.editingId = null;

    this._form = {
      name: "",
      power_entity: "",
      energy_entity: "",
      energy_type: "monthly",
      icon: "mdi:flash",
    };

    this.modalOpen = true;
    this.error = null;

    this.render();

    requestAnimationFrame(() => {
      this.shadowRoot?.querySelector("#source-name")?.focus();
    });
  }

  openEdit(source) {
    this.editingId = source.source_id;

    this._form = {
      name: source.name || "",
      power_entity: source.power_entity || "",
      energy_entity: source.energy_entity || "",
      energy_type: source.energy_type || "monthly",
      icon: source.icon || "mdi:flash",
    };

    this.modalOpen = true;
    this.error = null;

    this.render();
  }

  closeModal() {
    if (this.saving) {
      return;
    }

    this.modalOpen = false;
    this.editingId = null;
    this._form = null;
    this.error = null;

    this.render();
  }

  updateForm(field, value) {
    if (!this._form) {
      return;
    }

    this._form[field] = value;
  }

  async submitSource() {
    if (!this._form) {
      return;
    }

    const name = this._form.name.trim();
    const powerEntity = this._form.power_entity;
    const energyEntity = this._form.energy_entity;

    if (!name) {
      this.error = "Please enter a name for the smart plug.";

      this.render();
      return;
    }

    if (!powerEntity) {
      this.error = "Please select a power sensor.";

      this.render();
      return;
    }

    if (!energyEntity) {
      this.error = "Please select an energy sensor.";

      this.render();
      return;
    }

    const duplicateName = this.sources.some(
      (source) =>
        source.name.toLowerCase() === name.toLowerCase() &&
        source.source_id !== this.editingId,
    );

    if (duplicateName) {
      this.error = "A smart plug with this name already exists.";

      this.render();
      return;
    }

    const duplicateSensors = this.sources.some(
      (source) =>
        source.power_entity === powerEntity &&
        source.energy_entity === energyEntity &&
        source.source_id !== this.editingId,
    );

    if (duplicateSensors) {
      this.error = "These power and energy sensors are already configured.";

      this.render();
      return;
    }

    if (this.editingId) {
      const index = this.sources.findIndex(
        (source) => source.source_id === this.editingId,
      );

      if (index !== -1) {
        this.sources[index] = {
          ...this.sources[index],
          name,
          power_entity: powerEntity,
          energy_entity: energyEntity,
          energy_type: this._form.energy_type,
          icon: this._form.icon.trim() || "mdi:flash",
        };
      }
    } else {
      this.sources.push({
        source_id: crypto.randomUUID(),
        name,
        power_entity: powerEntity,
        energy_entity: energyEntity,
        energy_type: this._form.energy_type,
        icon: this._form.icon.trim() || "mdi:flash",
      });
    }

    this.modalOpen = false;
    this.editingId = null;
    this._form = null;
    this.error = null;

    this.render();
  }

  removeSource(source) {
    const confirmed = window.confirm(
      `Remove "${source.name}" from energy monitoring?\n\nHistorical energy data will be kept.`,
    );

    if (!confirmed) {
      return;
    }

    this.sources = this.sources.filter(
      (item) => item.source_id !== source.source_id,
    );

    this.render();
  }

  async saveChanges() {
    if (!this.config?.entry_id) {
      this.error = "Configuration entry ID is missing.";
      this.render();
      return;
    }

    this.saving = true;
    this.error = null;
    this.render();

    try {
      await this.hass.connection.sendMessagePromise({
        type: "dynamic_energy/save_config",
        entry_id: this.config.entry_id,
        observation_interval: Number(this.config.observation_interval || 3),
        observation_window: Number(this.config.observation_window || 10),
        challenge_threshold: Number(this.config.challenge_threshold ?? 5),
        challenge_confirmations: Number(
          this.config.challenge_confirmations || 2,
        ),
        minimum_power: Number(this.config.minimum_power ?? 3),
        ranking_method: this.config.ranking_method || "recent_weighted",
        sources: this.sources,
      });

      this.saving = false;
      this.render();

      window.history.back();
    } catch (error) {
      this.saving = false;
      this.error = error?.message || "Unable to save configuration.";
      this.render();
    }
  }

  updateObservationInterval(value) {
    if (!this.config) {
      return;
    }

    const parsed = Number(value);

    if (!Number.isFinite(parsed)) {
      return;
    }

    this.config.observation_interval = parsed;
  }

  updateRankingSetting(field, value) {
    if (!this.config) {
      return;
    }

    const parsed = Number(value);

    if (!Number.isFinite(parsed)) {
      return;
    }

    this.config[field] = parsed;
  }

  updateRankingMethod(value) {
    if (!this.config) {
      return;
    }

    this.config.ranking_method = value;
  }

  formatPower(value, unit = "W") {
    const numeric = Number(value);

    if (!Number.isFinite(numeric)) {
      return "Unavailable";
    }

    const normalizedUnit = String(unit || "W").toLowerCase();

    if (normalizedUnit === "kw") {
      return `${numeric.toFixed(2).replace(/\.?0+$/, "")} kW`;
    }

    const decimals = Math.abs(numeric) < 100 ? 1 : 0;

    return `${numeric.toFixed(decimals).replace(/\.?0+$/, "")} W`;
  }

  formatEnergy(value, unit = "kWh") {
    const numeric = Number(value);

    if (!Number.isFinite(numeric)) {
      return "Unavailable";
    }

    const normalizedUnit = String(unit || "kWh").toLowerCase();

    return `${numeric.toFixed(3).replace(/\.?0+$/, "")} ${normalizedUnit}`;
  }

  updateLiveValues() {
    if (!this.shadowRoot || !this.hass?.states) {
      return;
    }

    for (const element of this.shadowRoot.querySelectorAll(
      "[data-live-power-entity]",
    )) {
      const entityId = element.dataset.livePowerEntity;
      const state = this.hass.states[entityId];

      element.textContent = state
        ? this.formatPower(state.state, state.attributes?.unit_of_measurement)
        : "Unavailable";
    }

    for (const element of this.shadowRoot.querySelectorAll(
      "[data-live-energy-entity]",
    )) {
      const entityId = element.dataset.liveEnergyEntity;
      const state = this.hass.states[entityId];

      element.textContent = state
        ? this.formatEnergy(state.state, state.attributes?.unit_of_measurement)
        : "Unavailable";
    }
  }

  renderSourceCard(source) {
    const powerState = this.hass?.states?.[source.power_entity];
    const energyState = this.hass?.states?.[source.energy_entity];

    const power = powerState
      ? this.formatPower(
          powerState.state,
          powerState.attributes?.unit_of_measurement,
        )
      : "Unavailable";

    const energy = energyState
      ? this.formatEnergy(
          energyState.state,
          energyState.attributes?.unit_of_measurement,
        )
      : "Unavailable";

    return `
      <article class="source-card">
        <div class="source-card-main">
          <div class="source-icon">
            <ha-icon
              icon="${this.escapeAttribute(source.icon || "mdi:flash")}"
            ></ha-icon>
          </div>

          <div class="source-information">
            <div class="source-name">
              ${this.escapeHtml(source.name)}
            </div>

            <div class="source-entities">
              ${this.escapeHtml(source.power_entity)}
              <span>•</span>
              ${this.escapeHtml(source.energy_entity)}
            </div>
          </div>
        </div>

        <div class="source-stats">
          <div class="stat">
            <span class="stat-label">
              Power
            </span>

            <span
              class="stat-value"
              data-live-power-entity="${this.escapeAttribute(source.power_entity)}"
            >
              ${this.escapeHtml(power)}
            </span>
          </div>

          <div class="stat">
            <span class="stat-label">
              Energy
            </span>

            <span
              class="stat-value"
              data-live-energy-entity="${this.escapeAttribute(source.energy_entity)}"
            >
              ${this.escapeHtml(energy)}
            </span>
          </div>

          <div class="stat">
            <span class="stat-label">
              Type
            </span>

            <span class="stat-value">
              ${
                source.energy_type === "cumulative"
                  ? "Cumulative"
                  : "Monthly reset"
              }
            </span>
          </div>
        </div>

        <div class="source-actions">
          <button
            class="icon-button"
            data-action="edit"
            data-source-id="${this.escapeAttribute(source.source_id)}"
            title="Edit"
          >
            <ha-icon
              icon="mdi:pencil"
            ></ha-icon>
          </button>

          <button
            class="icon-button danger"
            data-action="remove"
            data-source-id="${this.escapeAttribute(source.source_id)}"
            title="Remove"
          >
            <ha-icon
              icon="mdi:delete-outline"
            ></ha-icon>
          </button>
        </div>
      </article>
    `;
  }

  renderModal() {
    if (!this.modalOpen) {
      return "";
    }

    const form = this.currentForm;
    const editing = Boolean(this.editingId);

    return `
      <div class="modal-backdrop">
        <div
          class="modal"
          role="dialog"
          aria-modal="true"
        >

          <div class="modal-header">
            <div>
              <h2>
                ${editing ? "Edit smart plug" : "Add smart plug"}
              </h2>

              <p>
                ${
                  editing
                    ? "Update the device used for energy monitoring."
                    : "Add a new device to energy monitoring."
                }
              </p>
            </div>

            <button
              class="close-button"
              data-action="close-modal"
              aria-label="Close"
            >
              <ha-icon
                icon="mdi:close"
              ></ha-icon>
            </button>
          </div>

          <div class="modal-content">

            ${
              this.error
                ? `
                  <div class="error-message">
                    <ha-icon
                      icon="mdi:alert-circle-outline"
                    ></ha-icon>

                    <span>
                      ${this.escapeHtml(this.error)}
                    </span>
                  </div>
                `
                : ""
            }

            <div class="form-grid">

              <div class="form-field full-width">
                <label
                  class="field-label"
                  for="source-name"
                >
                  Smart plug name
                </label>

                <input
                  class="text-input"
                  id="source-name"
                  data-field="name"
                  type="text"
                  placeholder="e.g. Living room TV"
                  value="${this.escapeAttribute(form.name)}"
                  autocomplete="off"
                >
              </div>

              <div class="form-field">
                <label
                  class="field-label"
                  for="power-entity"
                >
                  Power sensor
                </label>

                <select
                  class="text-input"
                  id="power-entity"
                  data-field="power_entity"
                >
                  <option value="">Select a power sensor</option>

                  ${this.powerEntities
                    .map(
                      (state) => `
                        <option
                          value="${this.escapeAttribute(state.entity_id)}"
                          ${
                            form.power_entity === state.entity_id
                              ? "selected"
                              : ""
                          }
                        >
                          ${this.escapeHtml(this.formatEntityOption(state))}
                        </option>
                      `,
                    )
                    .join("")}
                </select>
              </div>

              <div class="form-field">
                <label
                  class="field-label"
                  for="energy-entity"
                >
                  Energy sensor
                </label>

                <select
                  class="text-input"
                  id="energy-entity"
                  data-field="energy_entity"
                >
                  <option value="">Select an energy sensor</option>

                  ${this.energyEntities
                    .map(
                      (state) => `
                        <option
                          value="${this.escapeAttribute(state.entity_id)}"
                          ${
                            form.energy_entity === state.entity_id
                              ? "selected"
                              : ""
                          }
                        >
                          ${this.escapeHtml(this.formatEntityOption(state))}
                        </option>
                      `,
                    )
                    .join("")}
                </select>
              </div>

              <div class="form-field">
                <label
                  class="field-label"
                  for="energy-type"
                >
                  Energy sensor behavior
                </label>

                <select
                  class="text-input"
                  id="energy-type"
                  data-field="energy_type"
                >
                  <option
                    value="monthly"
                    ${form.energy_type === "monthly" ? "selected" : ""}
                  >
                    Resets monthly
                  </option>

                  <option
                    value="cumulative"
                    ${form.energy_type === "cumulative" ? "selected" : ""}
                  >
                    Cumulative (never resets)
                  </option>
                </select>
              </div>

              <div class="form-field">
                <label
                  class="field-label"
                  for="source-icon"
                >
                  Icon
                </label>

                <input
                  class="text-input"
                  id="source-icon"
                  data-field="icon"
                  type="text"
                  placeholder="mdi:flash"
                  value="${this.escapeAttribute(form.icon)}"
                  autocomplete="off"
                >

                <div class="field-help">
                  Use a Material Design Icon, e.g. mdi:television.
                </div>
              </div>

            </div>

          </div>

          <div class="modal-footer">
            <button
              class="secondary-button"
              data-action="close-modal"
            >
              Cancel
            </button>

            <button
              class="primary-button"
              data-action="submit-source"
            >
              ${editing ? "Update smart plug" : "Add smart plug"}
            </button>
          </div>

        </div>
      </div>
    `;
  }

  render() {
    if (!this.shadowRoot) {
      return;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          min-height: 100%;
          color: var(--primary-text-color);
          background: var(--primary-background-color);
          font-family: var(--paper-font-body1_-_font-family, inherit);
        }

        * {
          box-sizing: border-box;
        }

        .page {
          width: 100%;
          max-width: 1200px;
          margin: 0 auto;
          padding: 28px 24px 36px;
        }

        .page-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 20px;
          margin-bottom: 28px;
        }

        .header-brand {
          display: flex;
          align-items: center;
          gap: 16px;
          min-width: 0;
        }

        .brand-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 56px;
          height: 56px;
          flex: 0 0 56px;
          overflow: hidden;
          border: 1px solid var(--divider-color);
          border-radius: 16px;
          background: var(--card-background-color);
        }

        .brand-icon img {
          width: 100%;
          height: 100%;
          object-fit: contain;
          padding: 8px;
        }

        .brand-icon ha-icon {
          --mdc-icon-size: 30px;
          color: var(--primary-color);
        }

        .header-copy {
          min-width: 0;
        }

        .eyebrow {
          margin-bottom: 5px;
          color: var(--secondary-text-color);
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.13em;
          text-transform: uppercase;
        }

        h1 {
          margin: 0;
          font-size: clamp(25px, 4vw, 34px);
          line-height: 1.2;
          font-weight: 700;
          letter-spacing: -0.035em;
        }

        .subtitle {
          max-width: 620px;
          margin-top: 8px;
          color: var(--secondary-text-color);
          font-size: 14px;
          line-height: 1.55;
        }

        .header-actions {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-shrink: 0;
        }

        button {
          font: inherit;
          cursor: pointer;
          transition:
            background 140ms ease,
            border-color 140ms ease,
            transform 140ms ease,
            opacity 140ms ease;
        }

        button:active:not(:disabled) {
          transform: translateY(1px);
        }

        button:disabled {
          cursor: not-allowed;
          opacity: 0.55;
        }

        .primary-button,
        .secondary-button {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          min-height: 42px;
          padding: 0 16px;
          border: 1px solid transparent;
          border-radius: 11px;
          font-size: 13px;
          font-weight: 650;
          white-space: nowrap;
        }

        .primary-button {
          color: var(--text-primary-color, #fff);
          background: var(--primary-color);
        }

        .primary-button:hover:not(:disabled) {
          filter: brightness(1.06);
        }

        .secondary-button {
          color: var(--primary-text-color);
          border-color: var(--divider-color);
          background: var(--card-background-color);
        }

        .secondary-button:hover:not(:disabled) {
          background: var(--secondary-background-color);
        }

        .primary-button ha-icon,
        .secondary-button ha-icon {
          --mdc-icon-size: 18px;
        }

        .page-content {
          display: flex;
          flex-direction: column;
          gap: 26px;
        }

        section {
          min-width: 0;
          padding: 22px;
          border: 1px solid var(--divider-color);
          border-radius: 18px;
          background: var(--card-background-color);
          box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0, 0, 0, 0.025));
        }

        .section-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 20px;
        }

        .section-title {
          font-size: 17px;
          font-weight: 700;
          letter-spacing: -0.015em;
        }

        .section-description {
          margin-top: 6px;
          color: var(--secondary-text-color);
          font-size: 12px;
          line-height: 1.5;
        }

        .source-count {
          margin-top: 5px;
          color: var(--secondary-text-color);
          font-size: 12px;
        }

        .settings-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 18px;
        }

        .setting {
          min-width: 0;
          padding: 16px;
          border: 1px solid var(--divider-color);
          border-radius: 13px;
          background: var(--secondary-background-color);
        }

        .setting-label {
          display: block;
          margin-bottom: 6px;
          font-size: 13px;
          font-weight: 650;
        }

        .setting-description {
          min-height: 34px;
          margin-bottom: 13px;
          color: var(--secondary-text-color);
          font-size: 11px;
          line-height: 1.5;
        }

        .interval-select,
        .text-input {
          width: 100%;
          min-width: 0;
          min-height: 42px;
          padding: 0 12px;
          border: 1px solid var(--divider-color);
          border-radius: 9px;
          outline: none;
          color: var(--primary-text-color);
          background: var(--card-background-color);
          font: inherit;
          font-size: 13px;
        }

        .interval-select:focus,
        .text-input:focus {
          border-color: var(--primary-color);
          box-shadow: 0 0 0 2px color-mix(in srgb, var(--primary-color) 15%, transparent);
        }

        .sources {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 14px;
        }

        .source-card {
          min-width: 0;
          padding: 16px;
          border: 1px solid var(--divider-color);
          border-radius: 14px;
          background: var(--card-background-color);
          transition: border-color 140ms ease;
        }

        .source-card:hover {
          border-color: var(--outline-color, var(--secondary-text-color));
        }

        .source-card-main {
          display: flex;
          align-items: center;
          gap: 12px;
          min-width: 0;
          margin-bottom: 17px;
        }

        .source-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 42px;
          height: 42px;
          flex: 0 0 42px;
          border-radius: 12px;
          color: var(--primary-color);
          background: var(--secondary-background-color);
        }

        .source-icon ha-icon {
          --mdc-icon-size: 23px;
        }

        .source-information {
          min-width: 0;
          flex: 1;
        }

        .source-name {
          overflow: hidden;
          font-size: 14px;
          font-weight: 700;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .source-entities {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 5px;
          margin-top: 5px;
          color: var(--secondary-text-color);
          font-size: 10px;
          overflow-wrap: anywhere;
        }

        .source-entities span {
          opacity: 0.65;
        }

        .source-stats {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 8px;
          margin-bottom: 15px;
        }

        .stat {
          min-width: 0;
          padding: 10px;
          border-radius: 10px;
          background: var(--secondary-background-color);
        }

        .stat-label {
          display: block;
          margin-bottom: 6px;
          color: var(--secondary-text-color);
          font-size: 10px;
          font-weight: 600;
        }

        .stat-value {
          display: block;
          overflow: hidden;
          font-size: 13px;
          font-weight: 700;
          line-height: 1.35;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-variant-numeric: tabular-nums;
        }

        .source-actions {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
        }

        .icon-button {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 34px;
          height: 34px;
          padding: 0;
          border: 1px solid var(--divider-color);
          border-radius: 9px;
          color: var(--secondary-text-color);
          background: var(--card-background-color);
        }

        .icon-button:hover {
          color: var(--primary-text-color);
          background: var(--secondary-background-color);
        }

        .icon-button.danger:hover {
          color: var(--error-color, #db4437);
          border-color: var(--error-color, #db4437);
        }

        .icon-button ha-icon {
          --mdc-icon-size: 18px;
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 38px 20px;
          border: 1px dashed var(--divider-color);
          border-radius: 14px;
          text-align: center;
        }

        .empty-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 54px;
          height: 54px;
          margin-bottom: 15px;
          border-radius: 16px;
          color: var(--primary-color);
          background: var(--secondary-background-color);
        }

        .empty-icon ha-icon {
          --mdc-icon-size: 28px;
        }

        .empty-title {
          font-size: 14px;
          font-weight: 700;
        }

        .empty-description {
          max-width: 350px;
          margin-top: 7px;
          color: var(--secondary-text-color);
          font-size: 12px;
          line-height: 1.6;
        }

        .error-message {
          display: flex;
          align-items: flex-start;
          gap: 9px;
          padding: 12px 14px;
          border: 1px solid color-mix(in srgb, var(--error-color, #db4437) 35%, transparent);
          border-radius: 10px;
          color: var(--error-color, #db4437);
          background: color-mix(in srgb, var(--error-color, #db4437) 7%, transparent);
          font-size: 12px;
          line-height: 1.5;
        }

        .error-message ha-icon {
          --mdc-icon-size: 18px;
          flex: 0 0 auto;
        }

        .page-footer {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
          padding-top: 2px;
        }

        .modal-backdrop {
          position: fixed;
          z-index: 1000;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 20px;
          overflow-y: auto;
          background: rgba(0, 0, 0, 0.48);
          backdrop-filter: blur(5px);
        }

        .modal {
          width: min(100%, 650px);
          max-height: min(88vh, 850px);
          overflow-y: auto;
          border: 1px solid var(--divider-color);
          border-radius: 18px;
          background: var(--card-background-color);
          box-shadow: 0 24px 70px rgba(0, 0, 0, 0.28);
        }

        .modal-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
          padding: 22px 24px 18px;
          border-bottom: 1px solid var(--divider-color);
        }

        .modal-header h2 {
          margin: 0;
          font-size: 19px;
          font-weight: 700;
          letter-spacing: -0.02em;
        }

        .modal-header p {
          margin: 7px 0 0;
          color: var(--secondary-text-color);
          font-size: 12px;
          line-height: 1.5;
        }

        .close-button {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 34px;
          height: 34px;
          flex: 0 0 34px;
          padding: 0;
          border: 1px solid var(--divider-color);
          border-radius: 9px;
          color: var(--secondary-text-color);
          background: var(--card-background-color);
        }

        .close-button:hover {
          color: var(--primary-text-color);
          background: var(--secondary-background-color);
        }

        .close-button ha-icon {
          --mdc-icon-size: 20px;
        }

        .modal-content {
          padding: 22px 24px;
        }

        .form-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 18px;
        }

        .form-field {
          min-width: 0;
        }

        .form-field.full-width {
          grid-column: 1 / -1;
        }

        .field-label {
          display: block;
          margin-bottom: 8px;
          font-size: 12px;
          font-weight: 650;
        }

        .field-help {
          margin-top: 7px;
          color: var(--secondary-text-color);
          font-size: 11px;
          line-height: 1.5;
        }

        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
          padding: 16px 24px 22px;
          border-top: 1px solid var(--divider-color);
        }

        @media (max-width: 760px) {
          .page {
            padding: 20px 14px 28px;
          }

          .page-header {
            flex-direction: column;
            align-items: stretch;
          }

          .header-actions {
            justify-content: flex-start;
          }

          section {
            padding: 16px;
          }

          .sources {
            grid-template-columns: minmax(0, 1fr);
          }

          .settings-grid {
            grid-template-columns: minmax(0, 1fr);
          }

          .setting-description {
            min-height: 0;
          }
        }

        @media (max-width: 480px) {
          .header-brand {
            align-items: flex-start;
            gap: 12px;
          }

          .brand-icon {
            width: 46px;
            height: 46px;
            flex-basis: 46px;
            border-radius: 13px;
          }

          .subtitle {
            font-size: 12px;
          }

          .header-actions {
            display: grid;
            grid-template-columns: 1fr;
          }

          .header-actions button {
            width: 100%;
          }

          .source-stats {
            gap: 6px;
          }

          .stat {
            padding: 8px;
          }

          .stat-value {
            font-size: 12px;
          }

          .form-grid {
            grid-template-columns: minmax(0, 1fr);
          }

          .form-field.full-width {
            grid-column: auto;
          }

          .modal-backdrop {
            align-items: flex-end;
            padding: 0;
          }

          .modal {
            width: 100%;
            max-height: 92vh;
            border-radius: 18px 18px 0 0;
          }

          .modal-header,
          .modal-content {
            padding-right: 18px;
            padding-left: 18px;
          }

          .modal-footer {
            padding-right: 18px;
            padding-left: 18px;
          }

          .page-footer {
            flex-direction: column-reverse;
          }

          .page-footer button {
            width: 100%;
          }
        }
      </style>

      ${
        this.loading
          ? `
            <div class="page">
              <section class="empty-state">
                <ha-circular-progress active></ha-circular-progress>
                <div class="empty-title" style="margin-top: 16px;">
                  Loading Dynamic Energy…
                </div>
              </section>
            </div>
          `
          : `
            <div class="page">

              <header class="page-header">

                <div class="header-brand">

                  <div class="brand-icon">
                    ${
                      this.brandToken
                        ? `<img src="${this.escapeAttribute(this.getLogoUrl())}" alt="Dynamic Energy">`
                        : `<ha-icon icon="mdi:lightning-bolt"></ha-icon>`
                    }
                  </div>

                  <div class="header-copy">
                    <div class="eyebrow">
                      Home Assistant integration
                    </div>

                    <h1>
                      Dynamic Energy
                    </h1>

                    <div class="subtitle">
                      Monitor live power, track monthly energy consumption,
                      and dynamically rank your highest-consuming devices.
                    </div>
                  </div>

                </div>

                <div class="header-actions">

                  <button
                    class="secondary-button"
                    data-action="add"
                  >
                    <ha-icon icon="mdi:plus"></ha-icon>
                    Add smart plug
                  </button>

                </div>

              </header>

              <div class="page-content">

                <section>

                  <div class="section-header">

                    <div>
                      <div class="section-title">
                        Monitoring settings
                      </div>

                      <div class="section-description">
                        Tune how often power readings are sampled and how
                        device rankings respond to changes in consumption.
                      </div>
                    </div>

                  </div>

                  <div class="settings-grid">

                    <div class="setting">

                      <label
                        class="setting-label"
                        for="observation-interval"
                      >
                        Observation interval
                      </label>

                      <div class="setting-description">
                        How often the integration samples power readings.
                      </div>

                      <select
                        class="interval-select"
                        id="observation-interval"
                      >
                        ${[1, 2, 3, 5, 10, 15, 30, 60]
                          .map(
                            (value) => `
                              <option
                                value="${value}"
                                ${
                                  Number(
                                    this.config?.observation_interval || 3,
                                  ) === value
                                    ? "selected"
                                    : ""
                                }
                              >
                                ${value} second${value === 1 ? "" : "s"}
                              </option>
                            `,
                          )
                          .join("")}
                      </select>

                    </div>

                    <div class="setting">

                      <label
                        class="setting-label"
                        for="observation-window"
                      >
                        Observation window
                      </label>

                      <div class="setting-description">
                        How much recent power history is used to calculate
                        the ranking score.
                      </div>

                      <select
                        class="interval-select"
                        id="observation-window"
                      >
                        ${[5, 10, 15, 30, 60, 120, 300, 600]
                          .map(
                            (value) => `
                              <option
                                value="${value}"
                                ${
                                  Number(
                                    this.config?.observation_window || 10,
                                  ) === value
                                    ? "selected"
                                    : ""
                                }
                              >
                                ${value < 60 ? `${value} seconds` : `${value / 60} minute${value === 60 ? "" : "s"}`}
                              </option>
                            `,
                          )
                          .join("")}
                      </select>

                    </div>

                    <div class="setting">

                      <label
                        class="setting-label"
                        for="ranking-method"
                      >
                        Ranking method
                      </label>

                      <div class="setting-description">
                        Choose how recent power readings are combined into
                        a device's ranking score.
                      </div>

                      <select
                        class="interval-select"
                        id="ranking-method"
                      >
                        <option
                          value="average"
                          ${
                            (this.config?.ranking_method ||
                              "recent_weighted") === "average"
                              ? "selected"
                              : ""
                          }
                        >
                          Average power
                        </option>

                        <option
                          value="recent_weighted"
                          ${
                            (this.config?.ranking_method ||
                              "recent_weighted") === "recent_weighted"
                              ? "selected"
                              : ""
                          }
                        >
                          Recent-weighted power
                        </option>

                        <option
                          value="peak"
                          ${
                            (this.config?.ranking_method ||
                              "recent_weighted") === "peak"
                              ? "selected"
                              : ""
                          }
                        >
                          Peak power
                        </option>
                      </select>

                    </div>

                    <div class="setting">

                      <label
                        class="setting-label"
                        for="challenge-threshold"
                      >
                        Ranking challenge threshold
                      </label>

                      <div class="setting-description">
                        A challenger must exceed the fourth-ranked device
                        by this percentage before replacing it.
                      </div>

                      <select
                        class="interval-select"
                        id="challenge-threshold"
                      >
                        ${[0, 2, 5, 10, 15, 20, 25, 30]
                          .map(
                            (value) => `
                              <option
                                value="${value}"
                                ${
                                  Number(
                                    this.config?.challenge_threshold ?? 5,
                                  ) === value
                                    ? "selected"
                                    : ""
                                }
                              >
                                ${value}%
                              </option>
                            `,
                          )
                          .join("")}
                      </select>

                    </div>

                    <div class="setting">

                      <label
                        class="setting-label"
                        for="challenge-confirmations"
                      >
                        Challenge confirmations
                      </label>

                      <div class="setting-description">
                        Consecutive ranking checks required before replacing a device.
                      </div>

                      <select
                        class="interval-select"
                        id="challenge-confirmations"
                      >
                        ${[1, 2, 3, 4, 5]
                          .map(
                            (value) => `
                              <option
                                value="${value}"
                                ${
                                  Number(
                                    this.config?.challenge_confirmations ?? 2,
                                  ) === value
                                    ? "selected"
                                    : ""
                                }
                              >
                                ${value}
                              </option>
                            `,
                          )
                          .join("")}
                      </select>

                    </div>

                    <div class="setting">

                      <label
                        class="setting-label"
                        for="minimum-power"
                      >
                        Minimum ranking power
                      </label>

                      <div class="setting-description">
                        Ignore devices below this power when building the Top 4.
                      </div>

                      <select
                        class="interval-select"
                        id="minimum-power"
                      >
                        ${[0, 1, 3, 5, 10, 20]
                          .map(
                            (value) => `
                              <option
                                value="${value}"
                                ${
                                  Number(this.config?.minimum_power ?? 3) ===
                                  value
                                    ? "selected"
                                    : ""
                                }
                              >
                                ${value} W
                              </option>
                            `,
                          )
                          .join("")}
                      </select>

                    </div>

                  </div>

                </section>

                <section>

                  <div class="section-header">

                    <div>
                      <div class="section-title">
                        Smart plugs
                      </div>

                      <div class="source-count">
                        ${this.sources.length}
                        ${
                          this.sources.length === 1
                            ? "smart plug"
                            : "smart plugs"
                        }
                      </div>
                    </div>

                  </div>

                  ${
                    this.sources.length
                      ? `
                        <div class="sources">
                        ${[...this.sources]
                          .sort((a, b) =>
                            String(a.name || "").localeCompare(
                              String(b.name || ""),
                              undefined,
                              { sensitivity: "base", numeric: true },
                            ),
                          )
                          .map((source) => this.renderSourceCard(source))
                          .join("")}
                        </div>
                      `
                      : `
                        <div class="empty-state">

                          <div class="empty-icon">
                            <ha-icon
                              icon="mdi:flash-outline"
                            ></ha-icon>
                          </div>

                          <div class="empty-title">
                            No smart plugs configured
                          </div>

                          <div class="empty-description">
                            Add your first smart plug to start monitoring
                            device-level energy consumption.
                          </div>

                          <div style="margin-top: 22px;">
                            <button
                              class="primary-button"
                              data-action="add"
                            >
                              Add smart plug
                            </button>
                          </div>

                        </div>
                      `
                  }

                </section>

                ${
                  this.error && !this.modalOpen
                    ? `
                      <div
                        class="error-message"
                        style="margin-top: 24px;"
                      >
                        <ha-icon
                          icon="mdi:alert-circle-outline"
                        ></ha-icon>

                        <span>
                          ${this.escapeHtml(this.error)}
                        </span>
                      </div>
                    `
                    : ""
                }

                <div class="page-footer">
                  <button
                    class="secondary-button"
                    data-action="back"
                  >
                    Cancel
                  </button>

                  <button
                    class="primary-button"
                    data-action="save"
                    ${this.saving ? "disabled" : ""}
                  >
                    ${this.saving ? "Saving…" : "Save changes"}
                  </button>
                </div>
              </div>
            </div>
          `
      }

      ${this.renderModal()}
    `;

    this.attachEventListeners();
  }

  attachEventListeners() {
    this.shadowRoot?.querySelectorAll("[data-action]").forEach((element) => {
      element.addEventListener("click", (event) => {
        const action = event.currentTarget.dataset.action;
        const sourceId = event.currentTarget.dataset.sourceId;

        if (action === "add") {
          this.openAdd();
          return;
        }

        if (action === "back") {
          this.goBack();
          return;
        }

        if (action === "close-modal") {
          this.closeModal();
          return;
        }

        if (action === "submit-source") {
          this.submitSource();
          return;
        }

        if (action === "save") {
          this.saveChanges();
          return;
        }

        if (action === "edit") {
          const source = this.sources.find(
            (item) => item.source_id === sourceId,
          );

          if (source) {
            this.openEdit(source);
          }

          return;
        }

        if (action === "remove") {
          const source = this.sources.find(
            (item) => item.source_id === sourceId,
          );

          if (source) {
            this.removeSource(source);
          }
        }
      });
    });

    this.shadowRoot
      ?.querySelector("#observation-interval")
      ?.addEventListener("change", (event) => {
        this.updateObservationInterval(event.target.value);
      });

    this.shadowRoot
      ?.querySelector("#observation-window")
      ?.addEventListener("change", (event) => {
        this.updateRankingSetting("observation_window", event.target.value);
      });

    this.shadowRoot
      ?.querySelector("#challenge-threshold")
      ?.addEventListener("change", (event) => {
        this.updateRankingSetting("challenge_threshold", event.target.value);
      });

    this.shadowRoot
      ?.querySelector("#challenge-confirmations")
      ?.addEventListener("change", (event) => {
        this.updateRankingSetting(
          "challenge_confirmations",
          event.target.value,
        );
      });

    this.shadowRoot
      ?.querySelector("#minimum-power")
      ?.addEventListener("change", (event) => {
        this.updateRankingSetting("minimum_power", event.target.value);
      });

    this.shadowRoot
      ?.querySelector("#ranking-method")
      ?.addEventListener("change", (event) => {
        this.updateRankingMethod(event.target.value);
      });

    this.shadowRoot?.querySelectorAll("[data-field]").forEach((element) => {
      element.addEventListener("input", (event) => {
        this.updateForm(event.target.dataset.field, event.target.value);
      });

      element.addEventListener("change", (event) => {
        this.updateForm(event.target.dataset.field, event.target.value);
      });
    });

    this.shadowRoot
      ?.querySelector(".modal-backdrop")
      ?.addEventListener("click", (event) => {
        if (event.target.classList.contains("modal-backdrop")) {
          this.closeModal();
        }
      });
  }

  escapeHtml(value) {
    const div = document.createElement("div");

    div.textContent = String(value ?? "");

    return div.innerHTML;
  }

  escapeAttribute(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
}

if (!customElements.get("dynamic-energy-panel")) {
  customElements.define("dynamic-energy-panel", DynamicEnergyPanel);
}
