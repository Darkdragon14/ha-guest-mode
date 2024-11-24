import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

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
    };
  }

  constructor() {
    super();
    this.users = [];
    this.tokens = [];
    this.alert = '';
    this.alertType = '';

    // form inputs
    this.name = null;
    this.user = null;
    this.expire = 0;
    this.startDate = getNow();
    this.expirationDate = getNow();
    this.startDateLabel = "Start Date";
    this.endDtateLabel = "Expiration Date";
    this.enableStartDate = false;
  }

  fetchUsers() {
    const userLocale = navigator.language || navigator.languages[0];
    this.hass.callWS({ type: 'ha_guest_mode/list_users' }).then(users => {
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
              jwt_token: token.jwt_token,
              endDate: new Date(token.end_date).toLocaleString(userLocale).replace(/:\d{2}$/, ""),
              remaining: token.remaining,
              isUsed: token.isUsed,
              startDate: new Date(token.start_date).toLocaleString(userLocale).replace(/:\d{2}$/, "")
            });
          });
      });
    });
  }

  update(changedProperties) {
    if (changedProperties.has('hass') && this.hass) {
      this.fetchUsers();
    }
    super.update(changedProperties);
  }

  userChanged(e) {
    this.user = e.detail.value;
  }

  nameChanged(e) {
    this.name = e.target.value;
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

  addClick() {
    this.hass.callWS({
      type: 'ha_guest_mode/create_token',
      name: this.name,
      user_id: this.user,
      startDate: differenceInMinutes(this.startDate),
      expirationDate: this.expire ? parseInt(this.expire, 10) : differenceInMinutes(this.expirationDate)
    }).then(() => {
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

  getLoginUrl(token) {
    return this.hass.hassUrl() + 'guest-mode/login?token=' + token.jwt_token;
  }

  listItemClick(e, token) {
    navigator.clipboard.writeText(this.getLoginUrl(token));
    this.alertType="info";
    this.showAlert('Copied to clipboard ' + token.name);
  }

  translate(key) {
    return this.hass.localize(`component.ha_guest_mode.entity.frontend.${key}`);
  }

  render() {
    return html`
      <div>
        <header class="mdc-top-app-bar mdc-top-app-bar--fixed">
          <div class="mdc-top-app-bar__row">
            <section class="mdc-top-app-bar__section mdc-top-app-bar__section--align-start" id="navigation">
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
          <div class="filters">
            <ha-textfield 
              .label=${this.translate("key_name")}
              value="" 
              @input="${this.nameChanged}"
            ></ha-textfield>

            <ha-combo-box
              .items=${this.users}
              .itemLabelPath=${'name'}
              .itemValuePath=${'id'}
              .value="1"
              .label=${this.translate("user")}
              @value-changed=${this.userChanged}
            >
            </ha-combo-box>
            <span>:</span>

            <mwc-button
              .label="${this.enableStartDate ? this.translate("use_now") : this.translate("use_start_date")}"
              Outlined 
              @click=${this.toggleEnableStartDate}
            ></mwc-button>

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

            <mwc-button 
              raised 
              label="${this.translate("add")}" 
              @click=${this.addClick}
            ></mwc-button>
          </div>

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
            <ha-card class="container-list">
              <mwc-list>
                ${this.tokens.map(token => html`
                  <mwc-list-item hasMeta twoline @click=${e => this.listItemClick(e, token)}>
                    <a href="${this.getLoginUrl(token)}">
                      ${token.name} ${this.translate("for").toLowerCase()} ${token.user}
                      ${token.isUsed ?
                        html`
                        <ha-icon style="width: 17px; color: green;" icon="mdi:power"></ha-icon>
                        `:
                        html`
                        <ha-icon style="width: 17px; color: red;" icon="mdi:power"></ha-icon>
                        `
                      }
                    </a>
                    <span slot="secondary">${this.translate("start_date")}: ${token.startDate}, ${this.translate("expiration_date")}: ${token.endDate}</span>
                    <ha-icon slot="meta" @click=${e => this.deleteClick(e, token)} icon="mdi:delete"></ha-icon>
                  </mwc-list-item>
                `)}
              </mwc-list>
            </ha-card>`
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
        padding-top: var(--header-height);
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
      ha-combo-box {
        padding: 8px 0;
        width: auto;
      }
      mwc-button {
        padding: 16px 0;
      }
      .content {
        padding-left: 16px;
        padding-right: 16px;
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
        margin-top: 15px;
      }

      ha-textfield[id="sec"] {
        display: none;
      }
    `;
  }
} 

customElements.define('guest-mode-panel', GuestModePanel);
