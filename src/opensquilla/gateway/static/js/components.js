/** OpenSquilla Web UI — Reusable UI components. */

const UI = (() => {

  // -- Toast notifications --
  let _toastContainer = null;

  function toast(message, type = 'info', duration = 3000) {
    if (!_toastContainer) {
      _toastContainer = document.createElement('div');
      _toastContainer.className = 'toast-stack';
      document.body.appendChild(_toastContainer);
    }
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    _toastContainer.appendChild(el);
    setTimeout(() => { el.remove(); }, duration);
  }

  // -- Modal --
  let _modalSeq = 0;
  function modal(title, contentHtml, actions = []) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-backdrop';
    const titleId = `modal-title-${++_modalSeq}`;
    overlay.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="${titleId}">
        <div class="modal-title" id="${titleId}">${title}</div>
        <div class="modal-body">${contentHtml}</div>
        <div class="modal-foot"></div>
      </div>`;
    const actionsEl = overlay.querySelector('.modal-foot');
    actions.forEach(({ label, cls, onClick }) => {
      const btn = document.createElement('button');
      btn.className = `btn ${cls || ''}`;
      btn.textContent = label;
      btn.addEventListener('click', () => { onClick?.(); overlay.remove(); });
      actionsEl.appendChild(btn);
    });
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });
    // Esc closes the modal — matches user expectation for any dialog.
    const onKey = (e) => {
      if (e.key === 'Escape' && document.body.contains(overlay)) {
        overlay.remove();
        document.removeEventListener('keydown', onKey);
      }
    };
    document.addEventListener('keydown', onKey);
    document.body.appendChild(overlay);
    // Move focus into the modal for keyboard users.
    const firstAction = actionsEl.querySelector('button');
    if (firstAction) firstAction.focus();
    return overlay;
  }

  // -- Data table with sort + pagination --
  function dataTable(container, { columns, data, pageSize = 20 }) {
    let sortCol = null;
    let sortAsc = true;
    let page = 0;

    function _render() {
      let sorted = [...data];
      if (sortCol !== null) {
        const key = columns[sortCol].key;
        sorted.sort((a, b) => {
          const va = a[key] ?? '', vb = b[key] ?? '';
          const cmp = va < vb ? -1 : va > vb ? 1 : 0;
          return sortAsc ? cmp : -cmp;
        });
      }
      const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
      page = Math.min(page, totalPages - 1);
      const slice = sorted.slice(page * pageSize, (page + 1) * pageSize);

      let html = '<table class="data-table"><thead><tr>';
      columns.forEach((col, i) => {
        const arrow = sortCol === i ? (sortAsc ? ' \u25b2' : ' \u25bc') : '';
        html += `<th data-col="${i}">${col.label}<span class="sort-arrow">${arrow}</span></th>`;
      });
      html += '</tr></thead><tbody>';
      slice.forEach(row => {
        html += '<tr>';
        columns.forEach(col => {
          const val = col.render ? col.render(row[col.key], row) : (row[col.key] ?? '');
          html += `<td>${val}</td>`;
        });
        html += '</tr>';
      });
      if (slice.length === 0) {
        html += `<tr><td colspan="${columns.length}" style="text-align:center;color:var(--text-muted);padding:var(--sp-6)">No data</td></tr>`;
      }
      html += '</tbody></table>';

      if (totalPages > 1) {
        html += `<div class="pagination">
          <button class="btn btn--sm" data-page="prev" ${page === 0 ? 'disabled' : ''}>Prev</button>
          <span>${page + 1} / ${totalPages}</span>
          <button class="btn btn--sm" data-page="next" ${page >= totalPages - 1 ? 'disabled' : ''}>Next</button>
        </div>`;
      }

      container.innerHTML = html;
      container.querySelectorAll('th[data-col]').forEach(th => {
        th.addEventListener('click', () => {
          const ci = Number(th.dataset.col);
          if (sortCol === ci) { sortAsc = !sortAsc; } else { sortCol = ci; sortAsc = true; }
          _render();
        });
      });
      container.querySelectorAll('[data-page]').forEach(btn => {
        btn.addEventListener('click', () => {
          page += btn.dataset.page === 'prev' ? -1 : 1;
          _render();
        });
      });
    }

    _render();
    return { refresh: (newData) => { data = newData; _render(); } };
  }

  // -- Skeleton placeholder --
  function skeleton(width = '100%', height = '1em') {
    return `<div class="skel" style="width:${width};height:${height}"></div>`;
  }

  // -- Chip/Badge --
  function chip(label, type = '') {
    const cls = type ? `chip chip-${type}` : 'chip';
    return `<span class="${cls}">${label}</span>`;
  }

  // -- Relative time --
  function relTime(isoOrTs) {
    const d = typeof isoOrTs === 'number' ? new Date(isoOrTs * 1000) : new Date(isoOrTs);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  // -- Session status helpers --
  // Mirrors SessionStatus enum in session/models.py. Backend types status
  // as plain str, so helpers default-branch on unknown / legacy inputs.
  // Maps a status to the .dot color variant and the .chip color modifier
  // from the design system (components.css). Running and timeout get a
  // visible color; done is informational; failed is danger; killed is muted.
  const _SESSION_STATUS_DOT = {
    running: 'ok',
    done:    'off',
    failed:  'err',
    killed:  'off',
    timeout: 'warn',
  };
  const _SESSION_STATUS_CHIP = {
    running: 'chip-ok',
    done:    'chip-info',
    failed:  'chip-danger',
    killed:  '',
    timeout: 'chip-warn',
  };
  const _SESSION_STATUS_LABEL = {
    running: 'Running',
    done:    'Completed',
    failed:  'Failed',
    killed:  'Aborted by operator',
    timeout: 'Timed out',
  };

  /** Returns the .dot color variant ("ok"/"warn"/"err"/"off") for a SessionStatus. */
  function sessionStatusClass(status) {
    const k = String(status || '').toLowerCase();
    return _SESSION_STATUS_DOT[k] || 'off';
  }

  /** Returns the .chip color modifier (e.g. "chip-ok", "chip-info") for a SessionStatus. Empty string for the muted variant. */
  function sessionStatusChip(status) {
    const k = String(status || '').toLowerCase();
    return _SESSION_STATUS_CHIP[k] != null ? _SESSION_STATUS_CHIP[k] : '';
  }

  /** Returns human-readable tooltip text for a SessionStatus value. Falls back to the raw string, or 'Unknown' if empty. */
  function sessionStatusLabel(status) {
    const k = String(status || '').toLowerCase();
    return _SESSION_STATUS_LABEL[k] || (status ? String(status) : 'Unknown');
  }

  return { toast, modal, dataTable, skeleton, chip, relTime, sessionStatusClass, sessionStatusChip, sessionStatusLabel };
})();

window.UI = UI;
