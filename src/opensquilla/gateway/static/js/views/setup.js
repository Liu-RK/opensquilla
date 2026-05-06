/** OpenSquilla Web UI — Setup view (provider configuration).
 *
 * Renders the runtime-supported LLM providers as cards. Unsupported
 * providers are shown but disabled. Saves go through onboarding RPC so
 * mutations land in the same shared core as the CLI.
 *
 * The SPA routes this at /setup so WebUI setup uses the same mutations as
 * the CLI and DMG launchers.
 */

const SetupView = (() => {
  let _el = null;
  let _rpc = null;
  let _catalog = null;
  let _status = null;
  let _config = null;

  async function render(el) {
    _el = el;
    _rpc = App.getRpc();
    await _rpc.waitForConnection();

    try {
      [_catalog, _status, _config] = await Promise.all([
        _rpc.call('onboarding.catalog'),
        _rpc.call('onboarding.status'),
        _rpc.call('config.get'),
      ]);
    } catch (err) {
      _el.innerHTML = `<div class="setup-error">Failed to load setup catalog: ${_esc(err.message)}</div>`;
      return;
    }

    const providers = (_catalog.providers || []).filter(p => p.runtimeSupported);
    const disabled = (_catalog.providers || []).filter(p => !p.runtimeSupported);
    const imageProviders = (_catalog.imageGenerationProviders || []).filter(p => p.runtimeSupported);
    const memoryProviders = _catalog.memoryEmbeddingProviders || [];

    _el.innerHTML = `
      <section class="setup">
        <header class="setup__head">
          <h2>OpenSquilla Setup</h2>
          ${_status.needsOnboarding
            ? '<p class="setup__banner">No LLM provider configured yet — pick one to continue.</p>'
            : '<p class="setup__banner setup__banner--ok">LLM provider configured. You can switch to a different one below.</p>'}
        </header>
        <h3>Supported providers</h3>
        <div class="setup__grid">
          ${providers.map(p => _renderProviderCard(p, false)).join('')}
        </div>
        <h3>Memory embedding</h3>
        <p class="setup__banner setup__banner--ok">Memory embeddings are configured separately from the chat LLM. Auto uses the bundled local BGE model when available.</p>
        <div class="setup__grid">
          ${memoryProviders.map(p => _renderMemoryProviderCard(p)).join('')}
        </div>
        ${imageProviders.length ? `
          <h3>Image generation</h3>
          <div class="setup__grid">
            ${imageProviders.map(p => _renderImageProviderCard(p)).join('')}
          </div>` : ''}
        <h3>Disabled (runtime not yet supported)</h3>
        <div class="setup__grid setup__grid--muted">
          ${disabled.map(p => _renderProviderCard(p, true)).join('')}
        </div>
      </section>`;

    _el.querySelectorAll('[data-provider-id]').forEach(card => {
      const pid = card.dataset.providerId;
      const isDisabled = card.dataset.disabled === 'true';
      if (isDisabled) return;
      card.querySelector('[data-action="configure"]').addEventListener(
        'click', () => _openConfigureForm(pid)
      );
    });
    _el.querySelectorAll('[data-image-provider-id]').forEach(card => {
      const pid = card.dataset.imageProviderId;
      card.querySelector('[data-action="configure-image"]').addEventListener(
        'click', () => _openImageConfigureForm(pid)
      );
    });
    _el.querySelectorAll('[data-memory-provider-id]').forEach(card => {
      const pid = card.dataset.memoryProviderId;
      card.querySelector('[data-action="configure-memory"]').addEventListener(
        'click', () => _openMemoryEmbeddingForm(pid)
      );
    });
  }

  function _renderProviderCard(p, isDisabled) {
    return `<article class="setup-card${isDisabled ? ' is-disabled' : ''}" data-provider-id="${_esc(p.providerId)}" data-disabled="${isDisabled}">
      <header><h4>${_esc(p.label)}</h4><span class="setup-card__id">${_esc(p.providerId)}</span></header>
      <ul class="setup-card__meta">
        <li>backend: <code>${_esc(p.backend)}</code></li>
        <li>requires key: ${p.requiresApiKey ? 'yes' : 'no'}</li>
        <li>requires base url: ${p.requiresBaseUrl ? 'yes' : 'no'}</li>
      </ul>
      ${isDisabled
        ? '<p class="setup-card__note">Cannot be configured: runtime support not available.</p>'
        : '<button class="setup-card__btn" data-action="configure">Configure</button>'}
    </article>`;
  }

  function _renderImageProviderCard(p) {
    const primary = _status.imageGenerationPrimary || '';
    const primaryProvider = primary.includes('/') ? primary.split('/')[0] : '';
    const statusProvider = _status.imageGenerationProvider || primaryProvider;
    const active = statusProvider === p.providerId;
    const capabilityDisabled = active && _status.imageGenerationEnabled === false;
    const configured = !capabilityDisabled && active && _status.imageGenerationConfigured;
    const source = capabilityDisabled ? 'disabled' : (configured ? _imageSourceLabel(_status.imageGenerationSource) : 'not configured');
    return `<article class="setup-card setup-card--image" data-image-provider-id="${_esc(p.providerId)}">
      <header><h4>${_esc(p.label)}</h4><span class="setup-card__id">${_esc(p.providerId)}</span></header>
      <ul class="setup-card__meta">
        <li>default model: <code>${_esc(p.defaultModel)}</code></li>
        <li>key env: <code>${_esc(p.envKey)}</code></li>
        <li>status: <span class="setup-card__badge${configured ? ' is-ok' : ''}">${_esc(source)}</span></li>
      </ul>
      <button class="setup-card__btn" data-action="configure-image">Configure</button>
    </article>`;
  }

  function _imageSourceLabel(source) {
    if (source === 'explicit') return 'configured';
    if (source === 'env') return 'environment';
    if (source === 'llm_fallback') return 'LLM key';
    return 'not configured';
  }

  function _renderMemoryProviderCard(p) {
    return `<article class="setup-card" data-memory-provider-id="${_esc(p.providerId)}">
      <header><h4>${_esc(p.label)}</h4><span class="setup-card__id">${_esc(p.providerId)}</span></header>
      <ul class="setup-card__meta">
        <li>requires key: ${p.requiresApiKey ? 'yes' : 'no'}</li>
        <li>requires base url: ${p.requiresBaseUrl ? 'yes' : 'no'}</li>
      </ul>
      <button class="setup-card__btn" data-action="configure-memory">Configure</button>
    </article>`;
  }

  function _openConfigureForm(providerId) {
    const spec = _catalog.providers.find(p => p.providerId === providerId);
    if (!spec) return;
    const overlay = document.createElement('div');
    overlay.className = 'setup-modal__overlay';
    const modal = document.createElement('div');
    modal.className = 'setup-modal';
    modal.innerHTML = `
      <header class="setup-modal__head">
        <h3>Configure ${_esc(spec.label)}</h3>
        <button data-act="close">×</button>
      </header>
      <div class="setup-modal__body">
        ${spec.fields.map(f => {
          const isPwd = f.secret || f.type === 'password';
          if (f.type === 'select') {
            return `<label><span>${_esc(f.label)}${f.required ? ' *' : ''}</span>
              <select data-name="${_esc(f.name)}">
                ${(f.choices || []).map(c => `<option value="${_esc(c)}"${c === f.default ? ' selected' : ''}>${_esc(c)}</option>`).join('')}
              </select></label>`;
          }
          if (f.type === 'bool') {
            return `<label class="setup-modal__inline"><input type="checkbox" data-name="${_esc(f.name)}"${f.default ? ' checked' : ''}><span>${_esc(f.label)}</span></label>`;
          }
          const inputType = isPwd ? 'password' : (f.type === 'int' || f.type === 'float' ? 'number' : 'text');
          const defaultVal = isPwd ? '' : (f.default ?? '');
          return `<label><span>${_esc(f.label)}${f.required ? ' *' : ''}</span>
            <input type="${inputType}" data-name="${_esc(f.name)}" data-secret="${isPwd}" value="${_esc(String(defaultVal))}" placeholder="${isPwd ? '(leave blank to keep current)' : ''}"></label>`;
        }).join('')}
      </div>
      <footer class="setup-modal__foot">
        <button data-act="cancel">Cancel</button>
        <button data-act="save" class="setup-card__btn">Save</button>
      </footer>`;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const close = () => overlay.remove();
    modal.querySelector('[data-act="close"]').addEventListener('click', close);
    modal.querySelector('[data-act="cancel"]').addEventListener('click', close);
    modal.querySelector('[data-act="save"]').addEventListener('click', async () => {
      const params = { providerId };
      modal.querySelectorAll('[data-name]').forEach(el => {
        const name = el.dataset.name;
        if (el.type === 'checkbox') {
          params[_camel(name)] = el.checked;
        } else if (el.value !== '' || el.dataset.secret !== 'true') {
          params[_camel(name)] = el.value;
        }
      });
      // Backend expects model + apiKey + baseUrl in camelCase
      try {
        await _rpc.call('onboarding.provider.configure', params);
        UI.toast('Provider saved.', 'info');
        close();
        render(_el);
      } catch (err) {
        UI.toast('Save failed: ' + err.message, 'err');
      }
    });
  }

  function _openImageConfigureForm(providerId) {
    const spec = (_catalog.imageGenerationProviders || []).find(p => p.providerId === providerId);
    if (!spec) return;
    const overlay = document.createElement('div');
    overlay.className = 'setup-modal__overlay';
    const modal = document.createElement('div');
    modal.className = 'setup-modal';
    modal.innerHTML = `
      <header class="setup-modal__head">
        <h3>Configure ${_esc(spec.label)}</h3>
        <button data-act="close">×</button>
      </header>
      <div class="setup-modal__body">
        ${spec.fields.map(f => {
          const isPwd = f.secret || f.type === 'password';
          const current = _imageFieldDefault(spec, f);
          if (f.type === 'select') {
            return `<label><span>${_esc(f.label)}${f.required ? ' *' : ''}</span>
              <select data-name="${_esc(f.name)}">
                ${(f.choices || []).map(c => `<option value="${_esc(c)}"${c === current ? ' selected' : ''}>${_esc(c)}</option>`).join('')}
              </select></label>`;
          }
          if (f.type === 'bool') {
            return `<label class="setup-modal__inline"><input type="checkbox" data-name="${_esc(f.name)}"${current ? ' checked' : ''}><span>${_esc(f.label)}</span></label>`;
          }
          const inputType = isPwd ? 'password' : 'text';
          const defaultVal = isPwd ? '' : current;
          return `<label><span>${_esc(f.label)}${f.required ? ' *' : ''}</span>
            <input type="${inputType}" data-name="${_esc(f.name)}" data-secret="${isPwd}" value="${_esc(String(defaultVal ?? ''))}" placeholder="${isPwd ? '(leave blank to keep current)' : ''}"></label>`;
        }).join('')}
      </div>
      <footer class="setup-modal__foot">
        <button data-act="cancel">Cancel</button>
        <button data-act="save" class="setup-card__btn">Save</button>
      </footer>`;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const close = () => overlay.remove();
    modal.querySelector('[data-act="close"]').addEventListener('click', close);
    modal.querySelector('[data-act="cancel"]').addEventListener('click', close);
    modal.querySelector('[data-act="save"]').addEventListener('click', async () => {
      const params = { providerId };
      modal.querySelectorAll('[data-name]').forEach(el => {
        const name = el.dataset.name;
        if (el.type === 'checkbox') {
          params[_camel(name)] = el.checked;
        } else if (el.value !== '' || el.dataset.secret !== 'true') {
          params[_camel(name)] = el.value;
        }
      });
      try {
        await _rpc.call('onboarding.imageGeneration.configure', params);
        UI.toast('Image generation saved.', 'info');
        close();
        render(_el);
      } catch (err) {
        UI.toast('Save failed: ' + err.message, 'err');
      }
    });
  }

  function _openMemoryEmbeddingForm(providerId) {
    const spec = (_catalog.memoryEmbeddingProviders || []).find(p => p.providerId === providerId);
    if (!spec) return;
    const current = (((_config || {}).memory || {}).embedding || {});
    const currentProvider = current.provider || 'auto';
    const effectiveProvider = currentProvider === 'auto' && current.mode ? current.mode : currentProvider;
    const remote = current.remote || {};
    const local = current.local || {};
    const ollama = current.ollama || {};
    const overlay = document.createElement('div');
    overlay.className = 'setup-modal__overlay';
    const modal = document.createElement('div');
    modal.className = 'setup-modal';
    const showRemote = providerId === 'auto' || providerId === 'openai' || providerId === 'openai-compatible';
    const showLocal = providerId === 'local';
    const showOllama = providerId === 'ollama';
    const remoteModel = remote.model || ((effectiveProvider === 'openai' || effectiveProvider === 'openai-compatible') ? current.model : '') || (providerId === 'auto' ? '' : 'text-embedding-3-small');
    const remoteBaseUrl = remote.base_url || current.base_url || (providerId === 'auto' ? '' : 'https://api.openai.com/v1');
    const ollamaModel = ollama.model || (effectiveProvider === 'ollama' ? current.model : '') || 'nomic-embed-text';
    modal.innerHTML = `
      <header class="setup-modal__head">
        <h3>Configure ${_esc(spec.label)}</h3>
        <button data-act="close">×</button>
      </header>
      <div class="setup-modal__body">
        ${showRemote ? `<label><span>${providerId === 'auto' ? 'Remote fallback model id' : 'Model id'}</span>
          <input type="text" data-name="model" value="${_esc(remoteModel)}" placeholder="text-embedding-3-small"></label>
          <label><span>${providerId === 'auto' ? 'Remote fallback API key' : 'API key *'}</span><input type="password" data-name="api_key" data-secret="true" placeholder="(leave blank to keep current)"></label>
          <label><span>${providerId === 'auto' ? 'Remote fallback API root' : 'API root'}</span><input type="text" data-name="base_url" value="${_esc(remoteBaseUrl)}" placeholder="https://api.openai.com/v1"></label>` : ''}
        ${showLocal ? `<label><span>ONNX directory</span><input type="text" data-name="onnx_dir" value="${_esc(local.onnx_dir || '')}" placeholder="leave empty for bundled BGE"></label>` : ''}
        ${showOllama ? `<label><span>Model id</span>
          <input type="text" data-name="model" value="${_esc(ollamaModel)}"></label>
          <label><span>Base URL</span><input type="text" data-name="base_url" value="${_esc(ollama.base_url || 'http://localhost:11434')}"></label>` : ''}
      </div>
      <footer class="setup-modal__foot">
        <button data-act="cancel">Cancel</button>
        <button data-act="save" class="setup-card__btn">Save</button>
      </footer>`;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const close = () => overlay.remove();
    modal.querySelector('[data-act="close"]').addEventListener('click', close);
    modal.querySelector('[data-act="cancel"]').addEventListener('click', close);
    modal.querySelector('[data-act="save"]').addEventListener('click', async () => {
      const params = { providerId };
      modal.querySelectorAll('[data-name]').forEach(el => {
        const name = el.dataset.name;
        if (el.value !== '') {
          params[_camel(name)] = el.value;
        }
      });
      try {
        const res = await _rpc.call('onboarding.memory_embedding.configure', params);
        UI.toast(res && res.restartRequired ? 'Memory embedding saved. Restart required.' : 'Memory embedding saved.', 'info');
        close();
        render(_el);
      } catch (err) {
        UI.toast('Save failed: ' + err.message, 'err');
      }
    });
  }

  function _imageFieldDefault(spec, field) {
    if (field.name === 'enabled') {
      const hasConfiguredProvider = _status.imageGenerationConfigured || _status.imageGenerationProvider;
      return hasConfiguredProvider ? _status.imageGenerationEnabled === true : field.default !== false;
    }
    if (field.name === 'primary') {
      const primary = _status.imageGenerationPrimary || '';
      return primary.startsWith(spec.providerId + '/') ? primary : field.default;
    }
    return field.default ?? '';
  }

  function _camel(name) {
    return name.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
  }

  function _esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function destroy() { _el = null; _rpc = null; _catalog = null; _status = null; _config = null; }

  return { render, destroy };
})();

window.SetupView = SetupView;
