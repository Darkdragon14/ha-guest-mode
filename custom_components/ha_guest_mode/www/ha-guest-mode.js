import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";
import "https://unpkg.com/share-api-polyfill/dist/share-min.js";
import QRCode from "https://cdn.skypack.dev/qrcode";

function humanSeconds(seconds) {
  return [
    [Math.floor(seconds / 31536000), 'year'],
    [Math.floor((seconds % 31536000) / 86400), 'day'],
    [Math.floor(((seconds % 31536000) % 86400) / 3600), 'hour'],
    [Math.floor((((seconds % 31536000) % 86400) % 3600) / 60), 'minute'],
    [(((seconds % 31536000) % 86400) % 3600) % 60, 'second'],
  ].map(([value, label]) => {
    return value > 0 ? `${value} ${label}${value !== 1 ? 's' : ''} ` : '';
  }).join(' ');
}

function differenceInMinutes(targetDateStr) {
  const now = new Date();
  const targetDate = new Date(targetDateStr);
  const diffInMilliseconds = targetDate - now;
  const diffInMinutes = Math.floor(diffInMilliseconds / 1000 / 60);
  return diffInMinutes;
}

function getNow() {
  const date = new Date()
  return `${date.getFullYear()}-${
    String(date.getMonth() + 1).padStart(2, "0")
  }-${String(date.getDate()).padStart(2, "0")} ${
    String(date.getHours()).padStart(2, "0")
  }:${String(date.getMinutes()).padStart(2, "0")}:${
    String(date.getSeconds()).padStart(2, "0")
  }`;
}

class GuestModePanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      narrow: { type: Boolean },
      route: { type: Object },
      panel: { type: Object },
      users: { type: Array },
      tokens: { type: Array },
      alert: { type: String },
      enableStartDate: { type: Boolean },
      isNeverExpire: { type: Boolean },
      useDuration: { type: Boolean },
      duration: { type: Number },
      usage_limit: { type: Number },
      urls: { type: Object },
      dashboards: { type: Array },
      dashboard: { type: String },
      copyLinkMode: { type: Boolean },
      groups: { type: Array },
      createUser: { type: Boolean },
      newUserName: { type: String },
      selectedGroups: { type: Array },
      groupSelection: { type: String },
    };
  }

  constructor() {
    super();
    this.users = [];
    this.tokens = [];
    this.alert = '';
    this.alertType = '';
    this.loginPath = '';
    this.urls = {};
    this.dashboards = [];
   this.dashboard = '';
   this.copyLinkMode = false;
    this.groups = [];
    this.createUser = false;
    this.newUserName = '';
    this.selectedGroups = [];
    this.groupSelection = '';

    // form inputs
    this.name = null;
    this.user = null;
    this.expire = 0;
    this.startDate = getNow();
    this.expirationDate = getNow();
    this.startDateLabel = "Start Date";
    this.endDtateLabel = "Expiration Date";
    this.enableStartDate = false;
    this.isNeverExpire = false;
    this.useDuration = false;
    this.duration = 1;
  }

  async getCopyLinkMode() {
    try {
      const copyLinkMode = await this.hass.callWS({ type: 'ha_guest_mode/get_copy_link_mode' });
      this.copyLinkMode = copyLinkMode;
    } catch (err) {
      console.error('Error fetching copy link mode:', err);
      this.copyLinkMode = false; // Default to false if there's an error
    }
  }

  async getUrls() {
    try {
      const urls = await this.hass.callWS({ type: 'ha_guest_mode/get_urls' });
      console.log('URLs:', urls);
      if (urls && (urls.internal || urls.external)) {
        delete urls.cloud;
        this.urls = urls;
      } else {
        this.urls = { internal: this.hass.hassUrl(), external: null };
      }
    } catch (err) {
      this.urls = { internal: this.hass.hassUrl(), external: null };
    }    
  }

  async getDashboards() {
    try {
      const dashboards = await this.hass.callWS({ type: 'ha_guest_mode/get_panels' });
      const dashboardPromises = dashboards.map(async (dashboard) => {
        if (dashboard.url_path === 'lovelace') {
          dashboard.title = this.translate("default_dashboard");
        } else if (!dashboard.title) {
          dashboard.title = dashboard.url_path;
        }

        const dashboardEntry = {
          title: dashboard.title,
          url_path: dashboard.url_path,
        };

        const viewEntries = [];

        if (dashboard.component_name === 'lovelace') {
          try {
            const config = await this.hass.callWS({
              type: 'lovelace/config',
              url_path: dashboard.url_path !== 'lovelace' ? dashboard.url_path : null,
              force: false,
            });
            if (config.views && config.views.length > 0) {
              config.views.forEach(view => {
                viewEntries.push({
                  title: `${dashboard.title} / ${view.title || view.path}`,
                  url_path: `${dashboard.url_path}/${view.path}`,
                });
              });
            }
          } catch (err) {
            console.log('Error fetching Lovelace config for dashboard:', dashboard.title, err);
          }
        }
        return [dashboardEntry, ...viewEntries];
      });

      const nestedDashboards = await Promise.all(dashboardPromises);
      this.dashboards = nestedDashboards.flat();
    }
    catch (err) {
      console.error('Error fetching dashboards:', err);
    }
  }

  async getGroups() {
    try {
      const groups = await this.hass.callWS({ type: 'ha_guest_mode/list_groups' });
      this.groups = Array.isArray(groups) ? groups : [];
    } catch (err) {
      console.error('Error fetching groups:', err);
      this.groups = [];
    }
  }

  fetchUsers() {
    const userLocale = navigator.language || navigator.languages[0];
    this.hass.callWS({ type: 'ha_guest_mode/list_users' }).then(users => {
      const previousUser = this.user;
      this.users = [];
      this.tokens = [];
      users.filter(user => !user.system_generated && user.is_active).forEach(user => {
        this.users.push({
          id: user.id,
          name: user.name,
        });
        user.tokens.filter(token => token.type === 'long_lived_access_token' && token.expiration !== 315360000)
          .forEach(token => {
            this.tokens.push({
              id: token.id,
              name: token.name,
              user: user.name,
              endDate: token.isNeverExpire ? this.translate("never") : new Date(token.end_date).toLocaleString(userLocale).replace(/:\d{2}$/, ""),
              remaining: token.remaining,
              isUsed: token.isUsed,
              startDate: token.isNeverExpire ? 'N/A' : new Date(token.start_date).toLocaleString(userLocale).replace(/:\d{2}$/, ""),
              uid: token.uid,
              isNeverExpire: token.isNeverExpire,
              dashboard: token.dashboard || 'lovelace',
              first_used: token.first_used ? new Date(token.first_used).toLocaleString(userLocale).replace(/:\d{2}$/, "") : this.translate("never"),
              last_used: token.last_used ? new Date(token.last_used).toLocaleString(userLocale).replace(/:\d{2}$/, "") : this.translate("never"),
              times_used: token.times_used || 0,
              usage_limit: token.usage_limit,
            });
          });
      });

      if (previousUser) {
        const matched = this.users.find(u => u.id === previousUser);
        this.user = matched ? matched.id : null;
      } else if (!this.createUser) {
        this.user = null;
      }
    });
  }

  update(changedProperties) {
    if (changedProperties.has('hass') && this.hass && !this.users.length) {
      this.fetchUsers();
      this.getUrls();
      this.getDashboards();
      this.getCopyLinkMode();
      this.getGroups();
    }
    super.update(changedProperties);
  }

  userChanged(e) {
    this.user = e.detail.value;
  }

  toggleCreateUser(e) {
    this.createUser = e.target.checked;
    if (this.createUser) {
      this.user = null;
    } else {
      this.newUserName = '';
      this.selectedGroups = [];
      this.groupSelection = '';
    }
  }

  nameChanged(e) {
    this.name = e.target.value;
  }

  newUserNameChanged(e) {
    this.newUserName = e.target.value;
  }

  startDateChanged(e) {
    this.startDate = e.detail.value;
  }

  expireChanged(e) {
    this.expire = e.target.value;
  }

  expirationDateChanged(e) {
    this.expirationDate = e.detail.value;
  }

  toggleEnableStartDate(e) {
    this.enableStartDate = !this.enableStartDate;
  }

  isNeverExpireChanged(e) {
    this.isNeverExpire = e.target.checked;
  }

  toggleUseDuration(e) {
    this.useDuration = !this.useDuration;
  }

  durationChanged(e) {
    this.duration = e.target.value;
  }

  usageLimitChanged(e) {
    this.usage_limit = e.target.value;
  }

  dashboardChanged(e) {
    this.dashboard = e.detail.value;
  }

  groupSelected(e) {
    const value = e.detail.value;
    if (!value) {
      return;
    }

    this.groupSelection = value;

    if (!this.selectedGroups.includes(value)) {
      this.selectedGroups = [...this.selectedGroups, value];
    }

    this.groupSelection = '';
    if (e.target) {
      e.target.value = '';
    }
  }

  removeSelectedGroup(groupId) {
    this.selectedGroups = this.selectedGroups.filter(id => id !== groupId);
  }

  getGroupName(groupId) {
    const group = (this.groups || []).find(entry => entry.id === groupId);
    return group ? (group.name || group.id) : groupId;
  }

  addClick() {
    const payload = {
      type: 'ha_guest_mode/create_token',
      name: this.name,
      isNeverExpire: this.isNeverExpire,
    };
    const hasUsageLimit = this.usage_limit !== undefined && this.usage_limit !== null && this.usage_limit !== '';
    if (hasUsageLimit) {
      const limitValue = parseInt(this.usage_limit, 10);
      if (Number.isNaN(limitValue)) {
        this.alertType = "warning";
        this.showAlert(this.translate("invalid_usage_limit") || "Usage limit must be a number");
        return;
      }
      payload.usage_limit = limitValue;
    }

    if (this.dashboard) {
      payload.dashboard = this.dashboard;
    }

    if (!this.name) {
      this.alertType = "warning";
      this.showAlert(this.translate("missing_token_name") || "Token name is required");
      return;
    }

    if (this.createUser) {
      if (!this.newUserName) {
        this.alertType = "warning";
        this.showAlert(this.translate("missing_user_name") || "Guest name is required");
        return;
      }
      payload.create_user = true;
      payload.new_user_name = this.newUserName;
      const cleanedGroups = Array.from(
        new Set([...(this.selectedGroups || []).filter(Boolean)])
      );
      if (cleanedGroups.length === 0) {
        cleanedGroups.push("system-users");
      }
      payload.group_ids = cleanedGroups;
    } else {
      if (!this.user) {
        this.alertType = "warning";
        this.showAlert(this.translate("missing_user") || "Select a user");
        return;
      }
      payload.user_id = this.user;
    }

    if (!this.isNeverExpire) {
      if (this.useDuration) {
        const startDate = new Date(this.startDate);
        startDate.setHours(startDate.getHours() + parseInt(this.duration, 10));
        payload.expirationDate = differenceInMinutes(startDate);
      } else {
        payload.expirationDate = this.expire ? parseInt(this.expire, 10) : differenceInMinutes(this.expirationDate);
      }
      payload.startDate = differenceInMinutes(this.startDate);
    }

    this.hass.callWS(payload).then(() => {
      this.fetchUsers();
    }).catch(err => {
      this.alertType="warning";
      let messageDisplay = err.message;
      if (err.code === 'invalid_format') {
        const errorMessage = err.message;
        messageDisplay= 'Element(s) missing to create a token:';
        if (errorMessage.includes('name')) {
          messageDisplay += ' an Name,'
        }
        if (errorMessage.includes('user_id')) {
          messageDisplay += ' an User,'
        }
        if (errorMessage.includes('minutes')) {
          messageDisplay += ' an Expiration,'
        }
        messageDisplay.slice(0, -1) + '.';
      }
      this.showAlert(messageDisplay);
    });
  }

  showAlert(text) {
    this.alert = text;
    setTimeout(() => {
      this.alert = '';
    }, 2000);
  }

  deleteClick(e, token) {
    e.stopPropagation();

    this.hass.callWS({
      type: 'ha_guest_mode/delete_token',
      token_id: token.id,
    }).then(() => {
      this.fetchUsers();
    }).catch(err => {
      this.alertType="warning";
      this.showAlert(err.message);
    });
  }

  async getLoginPath() {
    if (this.loginPath) {
      return;
    }
    this.hass.callWS({ type: 'ha_guest_mode/get_path_to_login' }).then(path => {
      this.loginPath = path.slice(1);
    });
  }

  getLoginUrl(token, baseUrl = null) {
    const base = (baseUrl || '').replace(/\/$/, '');
    const path = this.loginPath.replace(/^\//, '');
    const loginUrl = `${base}/${path}`;
    return `${loginUrl}?token=${token.uid}`;
  }

  async listItemClick(e, token) {
    this.alertType="info";

    const accesLinkTranslated = this.translate("access_link");
    const forTranslated = this.translate("for").toLowerCase();
    const title = `${accesLinkTranslated} ${forTranslated} ${token.name}`;

    let baseUrl;
    if (this.urls.external && this.urls.internal) {
      const confirmed = await this.showConfirmationDialog(
        this.translate("choose_url_title"),
        this.translate("choose_url_text"),
        {
          confirm: this.translate("external_url"),
          cancel: this.translate("internal_url"),
        }
      );

      if (confirmed) {
        baseUrl = this.urls.external;
      } else {
        baseUrl = this.urls.internal;
      }
    } else {
      baseUrl = this.urls.external || this.urls.internal || this.hass.hassUrl();
    }

    const shareData = {
        title,
        text: this.getLoginUrl(token, baseUrl),
        url: this.getLoginUrl(token, baseUrl),
    };

    const shareConfig =   {
      copy: true,
      email: true,
      print: false,
      sms: true,
      messenger: true,
      facebook: true,
      whatsapp: true,
      twitter: false,
      linkedin: false,
      telegram: true,
      skype: false,
      pinterest: false,
      language: navigator.language || navigator.languages[0]
    }

    if (navigator.share && !this.copyLinkMode) {
        navigator.share(shareData, shareConfig)
            .then(() => this.showAlert('Partagé avec succès'))
            .catch((error) => console.error("Erreur de partage :", error));
    } else {
        navigator.clipboard.writeText(this.getLoginUrl(token, baseUrl));
        this.showAlert('Copied to clipboard ' + token.name);
    }
  }

  async qrButtonClick(e, token) {
    e.stopPropagation();

    let baseUrl;
    if (this.urls.external && this.urls.internal) {
      const confirmed = await this.showConfirmationDialog(
        this.translate("choose_url_title"),
        this.translate("choose_url_text"),
        { confirm: this.translate("external_url"), cancel: this.translate("internal_url") }
      );
      baseUrl = confirmed ? this.urls.external : this.urls.internal;
    } else {
      baseUrl = this.urls.external || this.urls.internal || this.hass.hassUrl();
    }

    const url = this.getLoginUrl(token, baseUrl);

    // Dialog
    const dialog = document.createElement('ha-dialog');
    dialog.heading = `QR — ${token.name}`;
    dialog.style.setProperty('--dialog-content-padding', '16px');

    const container = document.createElement('div');
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.alignItems = 'center';
    container.style.gap = '12px';

    const canvas = document.createElement('canvas');
    container.appendChild(canvas);

    const linkEl = document.createElement('a');
    linkEl.href = url;
    linkEl.textContent = url;
    linkEl.target = '_blank';
    linkEl.style.wordBreak = 'break-all';
    linkEl.style.textAlign = 'center';
    container.appendChild(linkEl);

    const copyBtn = document.createElement('ha-button');
    copyBtn.slot = 'primaryAction';
    copyBtn.textContent = this.translate("copy") || "Copy";
    copyBtn.addEventListener('click', async () => {
      await navigator.clipboard.writeText(url);
      this.alertType = "info";
      this.showAlert('Copied to clipboard');
    });

    const closeBtn = document.createElement('ha-button');
    closeBtn.slot = 'secondaryAction';
    closeBtn.textContent = this.translate("close") || "Close";
    closeBtn.addEventListener('click', () => dialog.close());

    dialog.appendChild(container);
    dialog.appendChild(copyBtn);
    dialog.appendChild(closeBtn);
    this.shadowRoot.appendChild(dialog);
    dialog.open = true;

    dialog.addEventListener('closed', () => {
      if (this.shadowRoot.contains(dialog)) this.shadowRoot.removeChild(dialog);
    });

    try {
      await QRCode.toCanvas(canvas, url, { width: 256, errorCorrectionLevel: 'H' });
    } catch (err) {
      console.error(err);
      this.alertType = "warning";
      this.showAlert("QR generation failed");
    }
  }

  async showConfirmationDialog(title, text, buttons) {
    return new Promise((resolve) => {
      const dialog = document.createElement('ha-dialog');
      dialog.heading = title;
      dialog.textContent = text;

      const confirmButton = document.createElement('ha-button');
      confirmButton.slot = 'primaryAction';
      confirmButton.variant = 'danger';
      confirmButton.textContent = buttons.confirm;
      confirmButton.addEventListener('click', () => {
        resolve(true);
        dialog.close();
      });

      const cancelButton = document.createElement('ha-button');
      cancelButton.slot = 'secondaryAction';
      cancelButton.variant = 'success';
      cancelButton.textContent = buttons.cancel;
      cancelButton.addEventListener('click', () => {
        resolve(false);
        dialog.close();
      });

      dialog.appendChild(confirmButton);
      dialog.appendChild(cancelButton);
      this.shadowRoot.appendChild(dialog);
      dialog.open = true;

      dialog.addEventListener('closed', () => {
        this.shadowRoot.removeChild(dialog);
      });
    });
  }

  translate(key) {
    return this.hass.localize(`component.ha_guest_mode.entity.frontend.${key}.name`);
  }

  render() {
    this.getLoginPath();
    const availableGroups = Array.isArray(this.groups) ? this.groups : [];
    const selectedGroupSet = new Set(this.selectedGroups || []);
    const groupOptions = availableGroups.filter(group => !selectedGroupSet.has(group.id));
    return html`
      <div>
        <header class="mdc-top-app-bar mdc-top-app-bar--fixed">
          <div class="mdc-top-app-bar__row">
            <section class="mdc-top-app-bar__section mdc-top-app-bar__section--align-start" id="navigation">
              <mwc-icon-button class="menu-button"
                @click=${() => this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }))}
              >
                <svg style="width:24px;height:24px" viewBox="0 0 24 24">
                  <path fill="currentColor" d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z" />
                </svg>
              </mwc-icon-button>
              <span class="mdc-top-app-bar__title">
                ${this.panel.title}
              </span>
            </section>
            <section class="mdc-top-app-bar__section mdc-top-app-bar__section--align-end" id="actions" role="toolbar">
              <slot name="actionItems"></slot>
            </section>
          </div>
        </header>

        <div class="mdc-top-app-bar--fixed-adjust flex content">
          <ha-card>
            <div class="card-content">
              <div class="checkbox-row">
                <mwc-checkbox
                  .checked=${this.createUser}
                  @change=${this.toggleCreateUser}
                ></mwc-checkbox>
                <span>${this.translate("create_new_user")}</span>
              </div>

              <ha-textfield 
                .label=${this.translate("key_name")}
                value="" 
                @input="${this.nameChanged}"
              ></ha-textfield>

              ${this.createUser
                ? html`
                    <ha-textfield
                      .label=${this.translate("new_user_name")}
                      .value=${this.newUserName}
                      @input=${this.newUserNameChanged}
                    ></ha-textfield>
                    <div class="group-picker">
                      <ha-combo-box
                        .items=${groupOptions}
                        .itemLabelPath=${'name'}
                        .itemValuePath=${'id'}
                        .value=${this.groupSelection || ''}
                        .label=${this.translate("assign_group")}
                        @value-changed=${this.groupSelected}
                      >
                      </ha-combo-box>
                      ${this.selectedGroups.length
                        ? html`
                            <div class="selected-groups">
                              ${this.selectedGroups.map(groupId => html`
                                <div class="selected-group">
                                  <span>${this.getGroupName(groupId)}</span>
                                  <button
                                    type="button"
                                    class="selected-group__remove"
                                    @click=${() => this.removeSelectedGroup(groupId)}
                                    title=${this.translate("remove_group")}
                                    aria-label=${this.translate("remove_group")}
                                  >
                                    ×
                                  </button>
                                </div>
                              `)}
                            </div>
                          `
                        : null}
                    </div>
                  `
                : html`
                    <ha-combo-box
                      .items=${this.users}
                      .itemLabelPath=${'name'}
                      .itemValuePath=${'id'}
                      .value=${this.user || ''}
                      .label=${this.translate("user")}
                      @value-changed=${this.userChanged}
                    >
                    </ha-combo-box>
                  `}

              <ha-combo-box
                .items=${this.dashboards}
                .itemLabelPath=${'title'}
                .itemValuePath=${'url_path'}
                .value=${this.dashboard || ''}
                .label=${this.translate("dashboard")}
                @value-changed=${this.dashboardChanged}
              >
              </ha-combo-box>
              <ha-textfield
                .label=${this.translate("usage_limit")}
                type="number"
                min="0"
                .value=${this.usage_limit || ''}
                @input=${this.usageLimitChanged}
              ></ha-textfield>
              <span style="min-width: auto">:</span>

              <div style="display: flex; align-items: center; gap: 4px;">
                <mwc-checkbox
                  .checked=${this.isNeverExpire}
                  @change=${this.isNeverExpireChanged}
                ></mwc-checkbox>
                <span>${this.translate("never_expire")}</span>
              </div>

              ${!this.isNeverExpire ? html`
                <div style="display: flex; align-items: center; gap: 4px;">
                  <mwc-checkbox
                    .checked=${this.enableStartDate}
                    @change=${this.toggleEnableStartDate}
                  ></mwc-checkbox>
                  <span>${this.translate("use_start_date")}</span>
                </div>

                ${this.enableStartDate ?
                  html`
                    <ha-selector
                      .selector=${{
                        datetime: {
                          mode: "both",
                        }
                      }}
                      .label=${this.translate("start_date")}
                      .hass=${this.hass}
                      .required=${false}
                      .value=${this.startDate}
                      @value-changed=${this.startDateChanged}
                    >
                    </ha-selector>
                  ` : ''
                }

                <div style="display: flex; align-items: center; gap: 4px;">
                  <mwc-checkbox
                    .checked=${this.useDuration}
                    @change=${this.toggleUseDuration}
                  ></mwc-checkbox>
                  <span>${this.translate("use_duration")}</span>
                </div>

                ${this.useDuration ? html`
                  <ha-textfield
                    .label=${this.translate("duration_in_hours")}
                    .value=${this.duration}
                    @input=${this.durationChanged}
                    type="number"
                    style="max-width: 250px;"
                  ></ha-textfield>
                ` : html`
                  <ha-selector
                    .selector=${{
                      datetime: {
                        mode: "both",
                      }
                    }}
                    .label=${this.translate("expiration_date")}
                    .hass=${this.hass}
                    .required=${false}
                    .value=${this.expirationDate}
                    @value-changed=${this.expirationDateChanged}
                  >
                  </ha-selector>
                `}
              ` : ''}

              <ha-button
                @click=${this.addClick}
                size="small"
                style="max-width: 250px;"
              >
                ${this.translate("add")}
              </ha-button>
            </div>
          </ha-card>

          ${this.alert.length ? 
            html`
              <div class="container-alert">
                <ha-alert
                  alert-type=${this.alertType}
                >
                  ${this.alert}
                </ha-alert>
              </div>` 
            : ''
          }

          ${this.tokens.length ?
            html`
            <div class="cards-container">
              ${this.tokens.map(token => {
                const dashboard = this.dashboards.find(d => d.url_path === token.dashboard);
                const dashboardTitle = dashboard ? dashboard.title : token.dashboard;
                return html`
                <ha-card class="token-card">
                  <div class="card-content-list">
                    <h3>${token.name} ${this.translate("for").toLowerCase()} ${token.user}</h3>
                    <p>
                      ${token.isNeverExpire ? html`
                        ${this.translate("expiration_date")}: ${this.translate("never")} <br>
                      ` : html`
                        ${this.translate("start_date")}: ${token.startDate} <br>
                        ${this.translate("expiration_date")}: ${token.endDate} <br>
                      `}
                      ${this.translate("used")}: ${token.isUsed ? this.translate("yes").toLowerCase() : this.translate("no").toLowerCase() } <br>
                      ${this.translate("dashboard")}: ${dashboardTitle} <br>
                      ${this.translate("first_used")}: ${token.first_used} <br>
                      ${this.translate("last_used")}: ${token.last_used} <br>
                      ${this.translate("times_used")}: ${token.times_used}${token.usage_limit ? ` / ${token.usage_limit}` : ''} <br>
                    </p>
                    <div class="actions">
                      <ha-button appearance="plain" @click=${e => this.listItemClick(e, token)}>
                        <ha-icon icon="mdi:share-variant"></ha-icon>
                      </ha-button>
                        <ha-button appearance="plain" @click=${e => this.qrButtonClick(e, token)} title="QR Code">
                          <ha-icon icon="mdi:qrcode"></ha-icon>
                        </ha-button>
                      <ha-button appearance="plain" disabled>
                        ${token.isUsed ? html`
                            <ha-icon icon="mdi:lock-open-variant-outline" style="color: var(--success-color);"></ha-icon>
                          ` : html`
                            <ha-icon icon="mdi:lock" style="color: var(--secondary-text-color);"></ha-icon>
                          `}
                      </ha-button>
                      <ha-button appearance="plain" @click=${e => this.deleteClick(e, token)}>
                        <ha-icon icon="mdi:delete" style="color: var(--error-color);"></ha-icon>
                      </ha-button>
                    </div>
                  </div>
                </ha-card>
              `})}
            </div>`
            : null
          }
        </div>

      </div>
    `;
  }

  static get styles() {
    return css`
      :host {
      }
      .mdc-top-app-bar {
        --mdc-typography-headline6-font-weight: 400;
        color: var(--app-header-text-color,var(--mdc-theme-on-primary,#fff));
        background-color: var(--app-header-background-color,var(--mdc-theme-primary));
        width: var(--mdc-top-app-bar-width,100%);
        display: flex;
        position: fixed;
        flex-direction: column;
        justify-content: space-between;
        box-sizing: border-box;
        width: 100%;
        z-index: 4;
      }
      .mdc-top-app-bar--fixed {
        transition: box-shadow 0.2s linear 0s;
      }
      .mdc-top-app-bar--fixed-adjust {
        padding-top: var(--header-height, 64px);
      }
      .mdc-top-app-bar__row {
        height: var(--header-height);
        border-bottom: var(--app-header-border-bottom);
        display: flex;
        position: relative;
        box-sizing: border-box;
        width: 100%;
        height: 64px;
      }
      .mdc-top-app-bar__section--align-start {
        justify-content: flex-start;
        order: -1;
      }
      .mdc-top-app-bar__section {
        display: inline-flex;
        flex: 1 1 auto;
        align-items: center;
        min-width: 0px;
        padding: 8px 12px;
        z-index: 1;
      }
      .mdc-top-app-bar__title {
        -webkit-font-smoothing: antialiased;
        font-family: var(--mdc-typography-headline6-font-family,var(--mdc-typography-font-family,Roboto,sans-serif));
        font-size: var(--mdc-typography-headline6-font-size,1.25rem);
        line-height: var(--mdc-typography-headline6-line-height,2rem);
        font-weight: var(--mdc-typography-headline6-font-weight,500);
        letter-spacing: var(--mdc-typography-headline6-letter-spacing,.0125em);
        text-decoration: var(--mdc-typography-headline6-text-decoration,inherit);
        text-transform: var(--mdc-typography-headline6-text-transform,inherit);
        padding-left: 20px;
        padding-right: 0px;
        text-overflow: ellipsis;
        white-space: nowrap;
        overflow: hidden;
        z-index: 1;
      }

      app-header {
        background-color: var(--primary-color);
        color: var(--text-primary-color);
        font-weight: 400;
      }
      app-toolbar {
        height: var(--header-height);
      }
      app-toolbar [main-title] {
        margin-left: 20px
      }

      ha-card {
        background-color: var(--card-background-color);
        color: var(--primary-text-color);
      }

      .card-content {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
      }

      .card-content > * {
        flex: 1 1 auto; /* Permet aux éléments de s’adapter et d’occuper un espace égal */
        min-width: 150px; /* Assure que les petits écrans n'affichent pas trop d'éléments collés */
      }
      ha-combo-box {
        padding: 8px 0;
        width: auto;
      }
      .checkbox-row {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .group-picker {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .selected-groups {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .selected-group {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 8px;
        border-radius: 12px;
        background: var(--chip-background-color, rgba(0, 0, 0, 0.08));
        color: inherit;
      }
      .selected-group__remove {
        background: none;
        border: none;
        cursor: pointer;
        color: inherit;
        font-size: 16px;
        line-height: 1;
        padding: 0;
      }
      .selected-group__remove:hover {
        opacity: 0.8;
      }
      ha-button {
        padding: 16px 0;
      }
      .content {
        padding-bottom: 16px;
      }
      .flex {
        flex: 1 1 1e-9px;
      }
      .filters {
        align-items: center;
        display: flex;
        flex-wrap: wrap;
        padding: 8px 16px 0px;
      }
      .filters > * {
        margin-right: 8px;
      }

      .container-alert {
        margin-top: 15px;
        padding: 0 2%;
      }

      .container-list {
        margin: 16px;
      }

      ha-textfield[id="sec"] {
        display: none;
      }

      .cards-container {
        margin-top: 16px;
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        justify-content: center;
      }

      .token-card {
        flex: 1 1 250px;
        max-width: 300px;
      }

      .card-content-list {
        padding: 16px;
        gab: 0px;
      }

      .actions {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .menu-button {
        display: none;
      }

      /* Affiche le bouton uniquement en dessous de 1024px */
      @media screen and (max-width: 870px) {
        .menu-button {
          display: inline-flex;
        }
      }
      .card-content > ha-button {
        flex: none;
        margin-left: auto;
      }
    `;
  }
} 

customElements.define('guest-mode-panel', GuestModePanel);
