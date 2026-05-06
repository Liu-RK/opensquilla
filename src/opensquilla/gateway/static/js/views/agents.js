/** OpenSquilla Web UI — Agents view. */

const AgentsView = (() => {
  let _el = null;
  let _rpc = null;
  let _unsubs = [];
  let _intervals = [];
  let _agents = [];

  function _ensureCss() {
    if (document.querySelector('link[data-view-css="agents"]')) return;
    const data = document.getElementById('opensquilla-data');
    const base = data?.dataset.basePath || '';
    const cssVersion = data?.dataset.version || '';
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = `${base}/static/css/views/agents.css${cssVersion ? '?v=' + encodeURIComponent(cssVersion) : ''}`;
    link.dataset.viewCss = 'agents';
    document.head.appendChild(link);
  }

  function render(el) {
    _el = el;
    _rpc = App.getRpc();
    _ensureCss();

    _el.innerHTML = `
      <div class="ag-stage">
        <header class="ag-stage__header">
          <div class="ag-stage__title-block">
            <span class="ag-stage__eyebrow">Control · Agents</span>
            <h2 class="ag-stage__title">Agents</h2>
            <p class="ag-stage__subtitle">Reasoning units that drive sessions, run skills, and coordinate work.</p>
          </div>
          <div class="ag-stage__actions">
            <button class="btn btn--ghost" id="agents-refresh" title="Refresh">
              ${icons.refresh()}<span>Refresh</span>
            </button>
          </div>
        </header>

        <section class="stat-row" id="stat-row"></section>

        <section class="ag-create">
          <form id="agent-add-form" class="ag-create__form">
            <label class="ag-field">
              <span>Agent ID</span>
              <input id="agent-add-id" class="ag-input" name="id" autocomplete="off" required />
            </label>
            <label class="ag-field">
              <span>Model</span>
              <input id="agent-add-model" class="ag-input" name="model" autocomplete="off" placeholder="provider/model" />
            </label>
            <label class="ag-field ag-field--wide">
              <span>Workspace</span>
              <input id="agent-add-workspace" class="ag-input" name="workspace" autocomplete="off" />
            </label>
            <button class="btn btn--primary" type="submit">${icons.plus()}<span>Add</span></button>
          </form>
        </section>

        <section class="ag-list">
          <div class="ag-list__head">
            <h3 class="ag-list__title" id="ag-list-title">Configured agents</h3>
          </div>
          <div id="ag-cards" class="ag-cards"></div>
        </section>
      </div>`;

    _el.querySelector('#agents-refresh').addEventListener('click', _loadData);
    _el.querySelector('#agent-add-form').addEventListener('submit', _onAddAgent);
    _loadData();
  }

  function destroy() {
    _unsubs.forEach(fn => fn());
    _unsubs = [];
    _intervals.forEach(id => clearInterval(id));
    _intervals = [];
    _agents = [];
    _el = null;
    _rpc = null;
  }

  async function _loadData() {
    await _rpc.waitForConnection();
    _rpc.call('agents.list').then(data => {
      _agents = data.agents || [];
      _renderStats();
      _renderCards();
    }).catch(err => UI.toast('Failed to load agents: ' + err.message, 'err'));
  }

  function _renderStats() {
    const wrap = _el && _el.querySelector('#stat-row');
    if (!wrap) return;
    const total = _agents.length;
    const builtins = _agents.filter(a => a.type === 'builtin' || a.isBuiltin).length;
    const customs = total - builtins;
    const tools = _agents.reduce((acc, a) => acc + (Array.isArray(a.tools) ? a.tools.length : 0), 0);
    const models = new Set();
    _agents.forEach(a => { if (a.model) models.add(a.model); });

    wrap.innerHTML = `
      <div class="stat stat--hero">
        <div class="stat-label">Total agents</div>
        <div class="stat-value">${total}</div>
        <div class="stat-hint">${builtins ? `${builtins} built-in` : ''}${builtins && customs ? ' · ' : ''}${customs ? `${customs} custom` : ''}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Models in use</div>
        <div class="stat-value mono">${models.size || '—'}</div>
        <div class="stat-hint">${models.size ? 'distinct models' : 'unset'}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Tools wired</div>
        <div class="stat-value">${tools}</div>
        <div class="stat-hint">across all agents</div>
      </div>`;
  }

  function _renderCards() {
    const wrap = _el && _el.querySelector('#ag-cards');
    const titleEl = _el && _el.querySelector('#ag-list-title');
    if (!wrap) return;

    if (titleEl) {
      titleEl.innerHTML = _agents.length
        ? `Configured agents <span class="ag-list__count">${_agents.length}</span>`
        : 'Configured agents';
    }

    if (_agents.length === 0) {
      wrap.innerHTML = `<div class="state">
        <div class="state-icon">${icons.agents()}</div>
        <div class="state-title">No agents configured.</div>
        <p class="state-text">Agents are declared in the gateway configuration. The default <code>main</code> agent is created automatically.</p>
      </div>`;
      return;
    }

    wrap.innerHTML = _agents.map((a, i) => {
      const id = a.id || a.name || '—';
      const name = a.name || a.id || '—';
      const type = a.type || (a.isBuiltin ? 'builtin' : 'custom');
      const isBuiltin = a.isBuiltin || type === 'builtin';
      const desc = a.description || '';
      const model = a.model;
      const tools = Array.isArray(a.tools) ? a.tools : [];
      const skills = Array.isArray(a.skills) ? a.skills : [];

      return `<article class="ag-card${isBuiltin ? ' is-builtin' : ''}" style="--i:${i}">
        <header class="ag-card__head">
          <div class="ag-card__id-block">
            <span class="ag-card__id">${_esc(id)}</span>
            <span class="chip ${isBuiltin ? 'chip-ok' : 'chip-info'}">${_esc(type)}</span>
          </div>
          <div class="ag-card__actions">
            <button class="ag-iconbtn" data-open-chat="${_esc(id)}" title="Open chat">${icons.chat()}<span>Chat</span></button>
            ${isBuiltin ? '' : `<button class="ag-iconbtn ag-iconbtn--danger" data-delete-agent="${_esc(id)}" title="Delete">${icons.trash()}<span>Delete</span></button>`}
          </div>
        </header>
        <div class="ag-card__name">${_esc(name)}</div>
        ${desc ? `<p class="ag-card__desc">${_esc(desc)}</p>` : ''}
        <dl class="ag-card__meta">
          ${model ? `<div><dt>Model</dt><dd class="ag-mono">${_esc(model)}</dd></div>` : ''}
          ${tools.length ? `<div><dt>Tools</dt><dd>${tools.length}</dd></div>` : ''}
          ${skills.length ? `<div><dt>Skills</dt><dd>${skills.length}</dd></div>` : ''}
        </dl>
        ${tools.length ? `<div class="ag-card__chips">
          <span class="ag-chips-label">Tools</span>
          ${tools.slice(0, 8).map(t => `<span class="ag-chip">${_esc(t)}</span>`).join('')}
          ${tools.length > 8 ? `<span class="ag-chip ag-chip--dim">+${tools.length - 8}</span>` : ''}
        </div>` : ''}
      </article>`;
    }).join('');

    wrap.querySelectorAll('[data-open-chat]').forEach(btn => {
      btn.addEventListener('click', () => {
        Router.navigate('/chat?agent=' + encodeURIComponent(btn.dataset.openChat));
      });
    });
    wrap.querySelectorAll('[data-delete-agent]').forEach(btn => {
      btn.addEventListener('click', () => _deleteAgent(btn.dataset.deleteAgent));
    });
  }

  function _onAddAgent(event) {
    event.preventDefault();
    const id = (_el.querySelector('#agent-add-id')?.value || '').trim();
    const model = (_el.querySelector('#agent-add-model')?.value || '').trim();
    const workspace = (_el.querySelector('#agent-add-workspace')?.value || '').trim();
    if (!id) return;
    const payload = { id };
    if (model) payload.model = model;
    if (workspace) payload.workspace = workspace;
    _rpc.call('agents.create', payload).then(() => {
      UI.toast('Agent saved: ' + id, 'ok');
      _el.querySelector('#agent-add-form')?.reset();
      _loadData();
    }).catch(err => UI.toast('Failed to save agent: ' + err.message, 'err'));
  }

  function _deleteAgent(id) {
    if (!id) return;
    if (!confirm(`Delete agent "${id}" from config?`)) return;
    _rpc.call('agents.delete', { id }).then(() => {
      UI.toast('Agent deleted: ' + id, 'ok');
      _loadData();
    }).catch(err => UI.toast('Failed to delete agent: ' + err.message, 'err'));
  }

  function _esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  return { render, destroy };
})();

window.AgentsView = AgentsView;
