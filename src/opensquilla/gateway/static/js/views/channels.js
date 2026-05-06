/** OpenSquilla Web UI — Channels view (FE-007 part 1). */

const ChannelsView = (() => {
  let _el = null;
  let _rpc = null;
  let _unsubs = [];
  let _intervals = [];
  let _channels = [];

  function _ensureCss() {
    if (document.querySelector('link[data-view-css="channels"]')) return;
    const data = document.getElementById('opensquilla-data');
    const base = data?.dataset.basePath || '';
    const cssVersion = data?.dataset.version || '';
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = `${base}/static/css/views/channels.css${cssVersion ? '?v=' + encodeURIComponent(cssVersion) : ''}`;
    link.dataset.viewCss = 'channels';
    document.head.appendChild(link);
  }

  function render(el) {
    _el = el;
    _rpc = App.getRpc();
    _ensureCss();

    _el.innerHTML = `
      <div class="ch-stage">
        <header class="ch-stage__header">
          <div class="ch-stage__title-block">
            <span class="ch-stage__eyebrow">Control · Channels</span>
            <h2 class="ch-stage__title">Channels</h2>
            <p class="ch-stage__subtitle">External adapters that bridge OpenSquilla to chat platforms, queues, and other services.</p>
          </div>
          <div class="ch-stage__actions">
            <button class="btn btn--ghost" id="ch-refresh" title="Refresh">
              ${icons.refresh()}<span>Refresh</span>
            </button>
            <button class="btn btn--primary" id="ch-add" title="Add channel">
              <span>+ Add channel</span>
            </button>
          </div>
        </header>

        <section class="stat-row" id="stat-row"></section>

        <section class="ch-list">
          <div class="ch-list__head">
            <h3 class="ch-list__title" id="ch-list-title">Configured channels</h3>
          </div>
          <div id="ch-cards" class="ch-cards"></div>
        </section>
      </div>`;

    _el.querySelector('#ch-refresh').addEventListener('click', _loadData);
    _el.querySelector('#ch-add').addEventListener('click', _openAddModal);

    // Subscribe to real-time channel status events
    const unsub = _rpc.on('channel.status', () => _loadData());
    _unsubs.push(unsub);

    _loadData();

    const id = setInterval(_loadData, 30000);
    _intervals.push(id);
  }

  function destroy() {
    _unsubs.forEach(fn => fn());
    _unsubs = [];
    _intervals.forEach(id => clearInterval(id));
    _intervals = [];
    _channels = [];
    _el = null;
    _rpc = null;
  }

  async function _loadData() {
    if (!_el) return;
    await _rpc.waitForConnection();

    _rpc.call('channels.status').then(data => {
      if (!_el) return;
      const raw = data.channels || [];

      // Sort: running first, then stopped, then dead
      const order = { running: 0, connected: 0, stopped: 1, dead: 2 };
      _channels = [...raw].sort((a, b) => {
        const oa = order[a.status] ?? 1;
        const ob = order[b.status] ?? 1;
        return oa - ob;
      });

      _renderStats();
      _renderCards();
    }).catch(err => UI.toast('Failed to load channels: ' + err.message, 'err'));
  }

  function _renderStats() {
    const wrap = _el && _el.querySelector('#stat-row');
    if (!wrap) return;
    const total = _channels.length;
    const connected = _channels.filter(c => c.status === 'running' || c.status === 'connected').length;
    const dead = _channels.filter(c => c.status === 'dead').length;
    const stopped = total - connected - dead;
    const restarts = _channels.reduce((acc, c) => acc + (Number(c.restart_attempts) || 0), 0);
    const types = new Set();
    _channels.forEach(c => { if (c.type) types.add(c.type); });

    wrap.innerHTML = `
      <div class="stat stat--hero">
        <div class="stat-label">Total channels</div>
        <div class="stat-value">${total}</div>
        <div class="stat-hint">${types.size} type${types.size === 1 ? '' : 's'}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Connected</div>
        <div class="stat-value">
          ${connected}${connected ? '<span class="dot ok"></span>' : ''}
        </div>
        <div class="stat-hint">${connected ? 'live' : 'all idle'}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Stopped</div>
        <div class="stat-value">${stopped}</div>
        <div class="stat-hint">${dead ? `<span class="ch-neg">${dead} dead</span>` : 'all healthy'}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Restart attempts</div>
        <div class="stat-value mono">${restarts}</div>
        <div class="stat-hint">since gateway start</div>
      </div>`;
  }

  function _renderCards() {
    const container = _el && _el.querySelector('#ch-cards');
    const titleEl = _el && _el.querySelector('#ch-list-title');
    if (!container) return;
    if (titleEl) {
      titleEl.innerHTML = _channels.length
        ? `Configured channels <span class="ch-list__count">${_channels.length}</span>`
        : 'Configured channels';
    }

    if (_channels.length === 0) {
      container.innerHTML = `<div class="ch-empty">
        <div class="ch-empty__art" aria-hidden="true">
          <svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <radialGradient id="cg2" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stop-color="rgba(240,160,48,0.18)"/>
                <stop offset="60%" stop-color="rgba(240,160,48,0.04)"/>
                <stop offset="100%" stop-color="rgba(240,160,48,0)"/>
              </radialGradient>
            </defs>
            <circle cx="60" cy="60" r="58" fill="url(#cg2)"/>
            <g fill="none" stroke="currentColor" stroke-width="1.4" opacity="0.55">
              <rect x="20" y="40" width="36" height="40" rx="6"/>
              <line x1="28" y1="52" x2="48" y2="52"/>
              <line x1="28" y1="60" x2="44" y2="60"/>
            </g>
            <g fill="none" stroke="var(--accent)" stroke-width="1.6">
              <rect x="64" y="40" width="36" height="40" rx="6"/>
              <line x1="72" y1="52" x2="92" y2="52"/>
              <line x1="72" y1="60" x2="88" y2="60"/>
            </g>
            <g stroke="var(--accent)" stroke-width="1.4" stroke-dasharray="2 4" opacity="0.7">
              <line x1="56" y1="60" x2="64" y2="60"/>
            </g>
          </svg>
        </div>
        <div class="ch-empty__title">No channels configured.</div>
        <p class="ch-empty__msg">Channels connect OpenSquilla to outside services like Slack, Discord, or your own gateway.<br/>Add a channel adapter in the gateway configuration to bring one online.</p>
        <code class="ch-empty__code">opensquilla.toml → [channels] + [[channels.channels]]</code>
      </div>`;
      return;
    }

    container.innerHTML = _channels.map((ch, i) => {
      const name = ch.name || ch.id || 'Unknown';
      const status = ch.status || (ch.connected ? 'connected' : 'stopped');
      const isRunning = status === 'running' || status === 'connected';
      const isDead = status === 'dead';
      const dotCls = isRunning ? 'ok' : isDead ? 'err' : 'off';
      const chipCls = isRunning ? 'chip-ok' : isDead ? 'chip-danger' : '';
      const since = ch.connected_since ? UI.relTime(ch.connected_since) : '—';
      const attempts = ch.restart_attempts != null ? String(ch.restart_attempts) : '0';

      let configJson = '';
      try {
        configJson = JSON.stringify(ch, null, 2);
      } catch {
        configJson = String(ch);
      }

      return `<article class="ch-card" style="--i:${i}">
        <header class="ch-card__head">
          <span class="dot ${dotCls}"></span>
          <span class="ch-card__name" title="${_esc(name)}">${_esc(name)}</span>
          <span class="chip mono">${_esc(ch.type || 'unknown')}</span>
        </header>
        <div class="ch-card__status">
          <span class="chip ${chipCls}">${_esc(status)}</span>
        </div>
        <dl class="ch-card__meta">
          <div><dt>Connected</dt><dd class="ch-mono">${_esc(since)}</dd></div>
          <div><dt>Restart attempts</dt><dd class="ch-mono">${_esc(attempts)}</dd></div>
        </dl>
        <details class="ch-card__config">
          <summary>Adapter config</summary>
          <pre class="ch-card__config-pre">${_esc(configJson)}</pre>
        </details>
        <footer class="ch-card__actions">
          ${isRunning
            ? `<button class="ch-iconbtn ch-iconbtn--danger" data-ch-logout="${_esc(name)}" title="Disconnect">${icons.stop()}<span>Disconnect</span></button>`
            : `<span class="ch-card__hint">${isDead ? 'Adapter died — check gateway logs.' : 'Configured but not started.'}</span>`}
          <button class="ch-iconbtn" data-ch-toggle="${_esc(name)}" data-ch-enabled="${ch.enabled !== false}" title="Toggle enabled">
            <span>${ch.enabled === false ? 'Enable' : 'Disable'}</span>
          </button>
          <button class="ch-iconbtn ch-iconbtn--danger" data-ch-remove="${_esc(name)}" title="Remove">
            <span>Remove</span>
          </button>
        </footer>
      </article>`;
    }).join('');

    container.querySelectorAll('[data-ch-logout]').forEach(btn => {
      btn.addEventListener('click', () => {
        const name = btn.dataset.chLogout;
        _rpc.call('channels.logout', { channel: name })
          .then(() => { UI.toast('Disconnected ' + name, 'info'); _loadData(); })
          .catch(err => UI.toast('Disconnect failed: ' + err.message, 'err'));
      });
    });

    container.querySelectorAll('[data-ch-toggle]').forEach(btn => {
      btn.addEventListener('click', () => {
        const name = btn.dataset.chToggle;
        const isEnabled = btn.dataset.chEnabled === 'true';
        const method = isEnabled ? 'onboarding.channel.disable' : 'onboarding.channel.enable';
        _rpc.call(method, { name })
          .then(() => {
            UI.toast(`${isEnabled ? 'Disabled' : 'Enabled'} ${name}. Restart gateway to apply.`, 'info');
            _loadData();
          })
          .catch(err => UI.toast('Toggle failed: ' + err.message, 'err'));
      });
    });

    container.querySelectorAll('[data-ch-remove]').forEach(btn => {
      btn.addEventListener('click', () => {
        const name = btn.dataset.chRemove;
        if (!confirm(`Remove channel "${name}"? Restart gateway to apply.`)) return;
        _rpc.call('onboarding.channel.remove', { name })
          .then(() => { UI.toast(`Removed ${name}. Restart gateway to apply.`, 'info'); _loadData(); })
          .catch(err => UI.toast('Remove failed: ' + err.message, 'err'));
      });
    });
  }

  async function _openAddModal() {
    let catalog;
    try {
      catalog = await _rpc.call('onboarding.catalog');
    } catch (err) {
      UI.toast('Failed to load catalog: ' + err.message, 'err');
      return;
    }
    const channels = catalog.channels || [];
    const overlay = document.createElement('div');
    overlay.className = 'ch-modal__overlay';
    const modal = document.createElement('div');
    modal.className = 'ch-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'ch-modal-title');
    modal.innerHTML = `
      <header class="ch-modal__head">
        <div class="ch-modal__title-block">
          <span class="ch-modal__eyebrow">Adapter · New</span>
          <h3 id="ch-modal-title">Add channel</h3>
        </div>
        <button class="ch-iconbtn" id="ch-modal-close" aria-label="Close">×</button>
      </header>
      <div class="ch-modal__body">
        <label class="ch-field">
          <span>Channel type</span>
          <select id="ch-type-select">
            ${channels.map(c => `<option value="${_esc(c.type)}">${_esc(c.label)} (${_esc(c.type)})</option>`).join('')}
          </select>
        </label>
        <div id="ch-form-host"></div>
        <p class="ch-modal__hint">Saving requires a gateway restart to take effect.</p>
      </div>
      <footer class="ch-modal__foot">
        <button class="btn btn--ghost" id="ch-modal-cancel">Cancel</button>
        <button class="btn btn--primary" id="ch-modal-save">Save channel</button>
      </footer>`;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const closeModal = () => overlay.remove();
    modal.querySelector('#ch-modal-close').addEventListener('click', closeModal);
    modal.querySelector('#ch-modal-cancel').addEventListener('click', closeModal);

    const select = modal.querySelector('#ch-type-select');
    const formHost = modal.querySelector('#ch-form-host');

    function renderFields(typeName) {
      const spec = channels.find(c => c.type === typeName);
      if (!spec) return;
      formHost.innerHTML = spec.fields.map(f => {
        const id = `ch-f-${f.name}`;
        const required = f.required ? ' *' : '';
        const isPwd = f.secret || f.type === 'password';
        if (f.type === 'select') {
          return `<label class="ch-field"><span>${_esc(f.label)}${required}</span>
            <select id="${id}" data-name="${_esc(f.name)}" data-type="${_esc(f.type)}">
              ${(f.choices || []).map(c => `<option value="${_esc(c)}"${c === f.default ? ' selected' : ''}>${_esc(c)}</option>`).join('')}
            </select></label>`;
        }
        if (f.type === 'bool') {
          return `<label class="ch-field ch-field--inline">
            <input type="checkbox" id="${id}" data-name="${_esc(f.name)}" data-type="${_esc(f.type)}"${f.default ? ' checked' : ''}>
            <span>${_esc(f.label)}${required}</span></label>`;
        }
        const inputType = isPwd ? 'password' : (f.type === 'int' || f.type === 'float' ? 'number' : 'text');
        const placeholder = isPwd ? '(leave blank to keep current)' : '';
        const defaultVal = isPwd ? '' : (f.default ?? '');
        return `<label class="ch-field"><span>${_esc(f.label)}${required}</span>
          <input type="${inputType}" id="${id}" data-name="${_esc(f.name)}" data-type="${_esc(f.type)}" data-secret="${isPwd}" placeholder="${_esc(placeholder)}" value="${_esc(String(defaultVal))}"></label>`;
      }).join('');
    }
    renderFields(select.value);
    select.addEventListener('change', () => renderFields(select.value));

    modal.querySelector('#ch-modal-save').addEventListener('click', async () => {
      const entry = { type: select.value };
      formHost.querySelectorAll('[data-name]').forEach(el => {
        const name = el.dataset.name;
        const type = el.dataset.type;
        const isSecret = el.dataset.secret === 'true';
        if (type === 'bool') {
          entry[name] = el.checked;
        } else if (type === 'int') {
          if (el.value !== '') entry[name] = parseInt(el.value, 10);
        } else if (type === 'float') {
          if (el.value !== '') entry[name] = parseFloat(el.value);
        } else {
          if (el.value !== '' || !isSecret) entry[name] = el.value;
        }
      });
      try {
        await _rpc.call('onboarding.channel.upsert', { entry });
        UI.toast('Channel saved. Restart gateway to apply.', 'info');
        closeModal();
        _loadData();
      } catch (err) {
        UI.toast('Save failed: ' + err.message, 'err');
      }
    });
  }

  function _esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  return { render, destroy };
})();

window.ChannelsView = ChannelsView;
