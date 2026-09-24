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
    if (!this.hass?.connection || this.saving) {
      return;
    }

    if (!this.config?.entry_id) {
      this.error =
        "Dynamic Energy config entry could not be identified. Please reload the page.";

      this.render();
      return;
    }

    this.saving = true;
    this.error = null;
    this.render();

    try {
      const result = await this.hass.connection.sendMessagePromise({
        type: "dynamic_energy/save_config",
        entry_id: this.config.entry_id,
        observation_interval: Number(this.config.observation_interval || 10),
        sources: this.sources,
      });

      if (!result?.success) {
        throw new Error(result?.error || "Unable to save configuration.");
      }

      this.saving = false;

      await this.loadConfig();
    } catch (error) {
      console.error("Dynamic Energy: failed to save configuration", error);

      this.error =
        error?.message || "Unable to save Dynamic Energy configuration.";

      this.saving = false;
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

  renderSourceCard(source) {
    const powerState = this.hass?.states?.[source.power_entity];

    const energyState = this.hass?.states?.[source.energy_entity];

    const power = powerState
      ? `${powerState.state} ${
          powerState.attributes?.unit_of_measurement || "W"
        }`
      : "Unavailable";

    const energy = energyState
      ? `${energyState.state} ${
          energyState.attributes?.unit_of_measurement || "kWh"
        }`
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

            <span class="stat-value">
              ${this.escapeHtml(power)}
            </span>
          </div>

          <div class="stat">
            <span class="stat-label">
              Energy
            </span>

            <span class="stat-value">
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

            <div class="field full-width">
              <label for="source-name">
                Name
              </label>

              <input
                id="source-name"
                type="text"
                value="${this.escapeAttribute(form.name)}"
                placeholder="e.g. Bedroom Matter Plug"
                data-field="name"
              />
            </div>

            <div class="field-grid">

              <div class="field">
                <label for="power-entity">
                  Power sensor
                </label>

                <select
                  id="power-entity"
                  data-field="power_entity"
                >
                  <option value="">
                    Select power sensor
                  </option>

                  ${this.powerEntities
                    .map(
                      (entity) => `
                        <option
                          value="${this.escapeAttribute(entity.entity_id)}"
                          ${
                            form.power_entity === entity.entity_id
                              ? "selected"
                              : ""
                          }
                        >
                          ${this.escapeHtml(this.formatEntityOption(entity))}
                        </option>
                      `,
                    )
                    .join("")}
                </select>
              </div>

              <div class="field">
                <label for="energy-entity">
                  Energy sensor
                </label>

                <select
                  id="energy-entity"
                  data-field="energy_entity"
                >
                  <option value="">
                    Select energy sensor
                  </option>

                  ${this.energyEntities
                    .map(
                      (entity) => `
                        <option
                          value="${this.escapeAttribute(entity.entity_id)}"
                          ${
                            form.energy_entity === entity.entity_id
                              ? "selected"
                              : ""
                          }
                        >
                          ${this.escapeHtml(this.formatEntityOption(entity))}
                        </option>
                      `,
                    )
                    .join("")}
                </select>
              </div>

              <div class="field">
                <label for="energy-type">
                  Energy type
                </label>

                <select
                  id="energy-type"
                  data-field="energy_type"
                >
                  <option
                    value="monthly"
                    ${form.energy_type === "monthly" ? "selected" : ""}
                  >
                    Monthly reset
                  </option>

                  <option
                    value="cumulative"
                    ${form.energy_type === "cumulative" ? "selected" : ""}
                  >
                    Cumulative
                  </option>
                </select>
              </div>

              <div class="field">
                <label for="source-icon">
                  Icon
                </label>

                <input
                  id="source-icon"
                  type="text"
                  value="${this.escapeAttribute(form.icon)}"
                  placeholder="mdi:flash"
                  data-field="icon"
                />
              </div>

            </div>

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
              ${editing ? "Save smart plug" : "Add smart plug"}
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
        }

        * {
          box-sizing: border-box;
        }

        .page {
          width: min(1180px, 100%);
          margin: 0 auto;
          padding: 36px 28px 56px;
        }

        .header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 24px;
          margin-bottom: 34px;
        }

        .header-left {
          display: flex;
          align-items: flex-start;
          gap: 14px;
          min-width: 0;
        }

        .header-brand {
          display: flex;
          align-items: center;
          gap: 16px;
          min-width: 0;
        }

        .logo {
          width: 52px;
          height: 52px;
          flex-shrink: 0;
          object-fit: contain;
          border-radius: 14px;
        }

        .back-button {
          width: 42px;
          height: 42px;
          margin-top: 3px;
          flex-shrink: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 11px;
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
        }

        .back-button:hover {
          background: var(--divider-color);
        }

        .back-button ha-icon {
          --mdc-icon-size: 22px;
        }

        .title-block {
          min-width: 0;
        }

        .title-block h1 {
          margin: 0;
          font-size: 32px;
          line-height: 1.2;
          font-weight: 650;
          letter-spacing: -0.02em;
        }

        .title-block p {
          margin: 10px 0 0;
          color: var(--secondary-text-color);
          font-size: 16px;
          line-height: 1.5;
        }

        .header-actions {
          display: flex;
          align-items: center;
          gap: 12px;
          flex-shrink: 0;
        }

        button {
          font: inherit;
          border: 0;
          cursor: pointer;
        }

        .primary-button {
          min-height: 46px;
          padding: 0 22px;
          border-radius: 12px;
          background: var(--primary-color);
          color: var(--text-primary-color, #fff);
          font-weight: 600;
          transition:
            transform 120ms ease,
            opacity 120ms ease;
        }

        .primary-button:hover {
          transform: translateY(-1px);
        }

        .primary-button:disabled {
          opacity: 0.55;
          cursor: default;
          transform: none;
        }

        .secondary-button {
          min-height: 46px;
          padding: 0 20px;
          border-radius: 12px;
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
          font-weight: 600;
        }

        .settings-card {
          background: var(--card-background-color);
          border: 1px solid var(--divider-color);
          border-radius: 18px;
          padding: 26px 28px;
          margin-bottom: 28px;
        }

        .settings-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 20px;
        }

        .settings-title {
          font-size: 18px;
          font-weight: 650;
        }

        .settings-description {
          margin-top: 5px;
          color: var(--secondary-text-color);
          font-size: 14px;
        }

        .interval-select {
          min-width: 180px;
          height: 44px;
          padding: 0 14px;
          border: 1px solid var(--divider-color);
          border-radius: 10px;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font: inherit;
        }

        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 20px;
          margin-bottom: 20px;
        }

        .section-title {
          font-size: 20px;
          font-weight: 650;
        }

        .source-count {
          color: var(--secondary-text-color);
          font-size: 14px;
          margin-top: 4px;
        }

        .sources {
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .source-card {
          display: grid;
          grid-template-columns:
            minmax(220px, 1fr)
            auto
            auto;
          align-items: center;
          gap: 24px;
          min-height: 88px;
          padding: 18px 20px;
          border: 1px solid var(--divider-color);
          border-radius: 15px;
          background: var(--card-background-color);
        }

        .source-card-main {
          display: flex;
          align-items: center;
          gap: 16px;
          min-width: 0;
        }

        .source-icon {
          width: 44px;
          height: 44px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          border-radius: 12px;
          background: color-mix(
            in srgb,
            var(--primary-color) 14%,
            transparent
          );
          color: var(--primary-color);
        }

        .source-icon ha-icon {
          --mdc-icon-size: 22px;
        }

        .source-information {
          min-width: 0;
        }

        .source-name {
          font-size: 16px;
          font-weight: 600;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .source-entities {
          margin-top: 5px;
          color: var(--secondary-text-color);
          font-size: 12px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .source-entities span {
          margin: 0 5px;
        }

        .source-stats {
          display: flex;
          gap: 28px;
        }

        .stat {
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 82px;
        }

        .stat-label {
          color: var(--secondary-text-color);
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.06em;
        }

        .stat-value {
          font-size: 13px;
          font-weight: 600;
        }

        .source-actions {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .icon-button {
          width: 40px;
          height: 40px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 10px;
          background: transparent;
          color: var(--secondary-text-color);
        }

        .icon-button:hover {
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
        }

        .icon-button.danger:hover {
          color: var(--error-color);
        }

        .empty-state {
          padding: 48px 24px;
          text-align: center;
          border: 1px dashed var(--divider-color);
          border-radius: 16px;
          color: var(--secondary-text-color);
        }

        .empty-icon {
          margin-bottom: 12px;
          color: var(--primary-color);
        }

        .empty-icon ha-icon {
          --mdc-icon-size: 38px;
        }

        .empty-title {
          color: var(--primary-text-color);
          font-size: 17px;
          font-weight: 600;
        }

        .empty-description {
          max-width: 480px;
          margin: 8px auto 0;
          line-height: 1.5;
        }

        .page-footer {
          display: flex;
          justify-content: flex-end;
          align-items: center;
          gap: 16px;
          margin-top: 32px;
        }

        .error-message {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          padding: 13px 15px;
          border-radius: 10px;
          background: color-mix(
            in srgb,
            var(--error-color) 10%,
            transparent
          );
          color: var(--error-color);
          font-size: 14px;
          line-height: 1.4;
        }

        .modal-backdrop {
          position: fixed;
          inset: 0;
          z-index: 1000;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 32px;
          background: rgba(0, 0, 0, 0.58);
          overflow-y: auto;
        }

        .modal {
          width: min(920px, 100%);
          max-height: calc(100vh - 64px);
          overflow-y: auto;
          border: 1px solid color-mix(
            in srgb,
            var(--primary-color) 55%,
            var(--divider-color)
          );
          border-radius: 20px;
          background: var(--card-background-color);
          box-shadow:
            0 24px 80px rgba(0, 0, 0, 0.4);
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 24px;
          padding: 30px 32px 10px;
        }

        .modal-header h2 {
          margin: 0;
          font-size: 24px;
          line-height: 1.25;
          font-weight: 650;
        }

        .modal-header p {
          margin: 9px 0 0;
          color: var(--secondary-text-color);
          font-size: 15px;
          line-height: 1.5;
        }

        .close-button {
          width: 48px;
          height: 48px;
          flex-shrink: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 50%;
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
        }

        .close-button:hover {
          background: var(--divider-color);
        }

        .close-button ha-icon {
          --mdc-icon-size: 24px;
        }

        .modal-content {
          padding: 28px 32px 32px;
        }

        .field-grid {
          display: grid;
          grid-template-columns:
            minmax(0, 1fr)
            minmax(0, 1fr);
          column-gap: 24px;
          row-gap: 26px;
          margin-top: 26px;
        }

        .field {
          min-width: 0;
        }

        .field.full-width {
          width: 100%;
        }

        .field label {
          display: block;
          margin-bottom: 10px;
          color: var(--primary-text-color);
          font-size: 14px;
          font-weight: 600;
        }

        .field input,
        .field select {
          width: 100%;
          height: 50px;
          padding: 0 16px;
          border: 1px solid var(--divider-color);
          border-radius: 12px;
          outline: none;
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
          font: inherit;
          font-size: 15px;
          transition:
            border-color 120ms ease,
            box-shadow 120ms ease;
        }

        .field select {
          padding-right: 40px;
          cursor: pointer;
        }

        .field input::placeholder {
          color: var(--secondary-text-color);
          opacity: 0.7;
        }

        .field input:focus,
        .field select:focus {
          border-color: var(--primary-color);
          box-shadow:
            0 0 0 3px color-mix(
              in srgb,
              var(--primary-color) 16%,
              transparent
            );
        }

        .modal-content > .error-message {
          margin-top: 26px;
        }

        .modal-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 18px;
          padding: 20px 32px 30px;
          border-top: 1px solid var(--divider-color);
        }

        .modal-footer .primary-button {
          min-width: 170px;
        }

        .loading {
          display: flex;
          justify-content: center;
          padding: 80px 20px;
          color: var(--secondary-text-color);
        }

        @media (max-width: 800px) {
          .page {
            padding: 24px 18px 40px;
          }

          .header {
            flex-direction: column;
            margin-bottom: 26px;
          }

          .header-actions {
            width: 100%;
          }

          .header-actions .primary-button {
            width: 100%;
          }

          .settings-header,
          .section-header {
            align-items: flex-start;
            flex-direction: column;
          }

          .interval-select {
            width: 100%;
          }

          .source-card {
            grid-template-columns: 1fr auto;
            gap: 16px;
          }

          .source-stats {
            grid-column: 1 / -1;
            padding-left: 60px;
            gap: 20px;
            flex-wrap: wrap;
          }

          .source-actions {
            grid-column: 2;
            grid-row: 1;
          }

          .page-footer {
            justify-content: stretch;
          }

          .page-footer button {
            flex: 1;
          }

          .modal-backdrop {
            align-items: flex-start;
            padding: 14px;
          }

          .modal {
            max-height: calc(100vh - 28px);
            border-radius: 16px;
          }

          .modal-header {
            padding: 24px 22px 8px;
          }

          .modal-content {
            padding: 22px;
          }

          .field-grid {
            grid-template-columns: 1fr;
            row-gap: 22px;
            margin-top: 22px;
          }

          .modal-footer {
            padding: 18px 22px 22px;
            flex-direction: column-reverse;
            align-items: stretch;
          }

          .modal-footer button {
            width: 100%;
          }
        }

        @media (max-width: 520px) {
          .header-brand {
            gap: 12px;
          }

          .logo {
            width: 44px;
            height: 44px;
          }

          .title-block h1 {
            font-size: 27px;
          }

          .title-block p {
            font-size: 14px;
          }

          .settings-card {
            padding: 20px;
          }

          .source-card {
            padding: 16px;
          }

          .source-stats {
            padding-left: 0;
          }

          .source-actions {
            grid-column: 1 / -1;
            justify-content: flex-end;
          }
        }
      </style>

      <div class="page">

        ${
          this.loading
            ? `
              <div class="loading">
                Loading Dynamic Energy…
              </div>
            `
            : `
              <header class="header">

                <div class="header-left">

                  <button
                    class="back-button"
                    data-action="back"
                    title="Back"
                    aria-label="Back"
                  >
                    <ha-icon
                      icon="mdi:arrow-left"
                    ></ha-icon>
                  </button>

                  <div class="header-brand">

                    <img
                      class="logo"
                      src="${this.escapeAttribute(this.getLogoUrl())}"
                      alt="Dynamic Energy"
                    />

                    <div class="title-block">
                      <h1>Dynamic Energy</h1>

                      <p>
                        Configure the devices used for apartment energy monitoring.
                      </p>
                    </div>

                  </div>

                </div>

                <div class="header-actions">
                  <button
                    class="primary-button"
                    data-action="add"
                  >
                    Add smart plug
                  </button>
                </div>

              </header>

              <section class="settings-card">

                <div class="settings-header">

                  <div>
                    <div class="settings-title">
                      Monitoring interval
                    </div>

                    <div class="settings-description">
                      How frequently Dynamic Energy samples power usage.
                    </div>
                  </div>

                  <select
                    class="interval-select"
                    id="observation-interval"
                  >
                    ${[5, 10, 15, 20, 30, 45, 60]
                      .map(
                        (value) => `
                          <option
                            value="${value}"
                            ${
                              Number(this.config?.observation_interval) ===
                              value
                                ? "selected"
                                : ""
                            }
                          >
                            Every ${value} seconds
                          </option>
                        `,
                      )
                      .join("")}
                  </select>

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
                        this.sources.length === 1 ? "smart plug" : "smart plugs"
                      }
                    </div>
                  </div>

                </div>

                ${
                  this.sources.length
                    ? `
                      <div class="sources">
                        ${this.sources
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
            `
        }

      </div>

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
