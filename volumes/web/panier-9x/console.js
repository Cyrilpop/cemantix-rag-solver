(function () {
  'use strict';
  // Chemin de l'API d'administration : lu dans la balise <meta name="admin-api-path">
  // de index.html, seule source à mettre à jour quand ADMIN_API_PATH change.
  // Le repli correspond au défaut du serveur, pour que la page reste utilisable
  // si la balise venait à manquer.
  var meta = document.querySelector('meta[name="admin-api-path"]');
  var API = (meta && meta.getAttribute('content')) || '/api/snap-9x';
  var token = sessionStorage.getItem('cemantix_admin_token') || '';
  var stream = null;

  function el(id) { return document.getElementById(id); }

  function toast(msg, kind) {
    var t = el('toast');
    t.textContent = msg;
    t.className = 'toast show ' + (kind || '');
    setTimeout(function () { t.className = 'toast ' + (kind || ''); }, 4000);
  }

  function authHeaders() {
    return { 'Content-Type': 'application/json', 'X-Admin-Token': token };
  }

  function stopFollow() {
    if (stream) { stream.close(); stream = null; el('btn-log-follow').textContent = 'Suivre en direct'; }
  }

  function logout() {
    stopFollow();
    var wasLoggedIn = !!token;
    token = '';
    sessionStorage.removeItem('cemantix_admin_token');
    el('app').classList.add('hide');
    el('gate').classList.remove('hide');
    el('btn-refresh').disabled = true;
    el('state-dot').className = 'dot';
    el('password').value = '';
    el('uptime').textContent = '';
    if (!wasLoggedIn) {
      window.location.href = '/';
    }
  }

  function api(path, options) {
    return fetch(API + path, options).then(function (res) {
      if (res.status === 401) { logout(); throw new Error('Session expirée'); }
      return res.json();
    });
  }

  // --- Whitelist « Défier le bot » (DEFI-18) --------------------------------
  function esc(s) {
    return String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function renderWhitelist(entries) {
    var box = el('wl-list');
    if (!box) return;
    if (!entries || !entries.length) { box.textContent = 'Aucune IP exemptée.'; return; }
    box.innerHTML = entries.map(function (e) {
      return '<div style="display:flex;gap:8px;align-items:center;margin:4px 0">'
        + '<code style="flex:0 0 auto">' + esc(e.ip_address) + '</code>'
        + '<span style="flex:1">' + esc(e.description || '') + '</span>'
        + '<button class="secondary wl-remove" data-ip="' + esc(e.ip_address) + '">Retirer</button>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.wl-remove').forEach(function (b) {
      b.addEventListener('click', function () { removeWhitelist(b.getAttribute('data-ip')); });
    });
  }

  function loadWhitelist() {
    api('/whitelist', { headers: authHeaders() })
      .then(function (r) { renderWhitelist(r.entries || []); })
      .catch(function () {});
  }

  function addWhitelist() {
    var ip = (el('wl-ip').value || '').trim();
    if (!ip) { toast('Adresse IP requise', 'ko'); return; }
    api('/whitelist', {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ ip_address: ip, description: (el('wl-desc').value || '').trim() })
    })
      .then(function (r) {
        renderWhitelist(r.entries || []);
        el('wl-ip').value = ''; el('wl-desc').value = '';
        toast('IP exemptée ajoutée', 'ok');
      })
      .catch(function (e) { toast(e.message, 'ko'); });
  }

  function removeWhitelist(ip) {
    api('/whitelist/' + encodeURIComponent(ip), { method: 'DELETE', headers: authHeaders() })
      .then(function (r) { renderWhitelist(r.entries || []); toast('IP retirée', 'ok'); })
      .catch(function (e) { toast(e.message, 'ko'); });
  }

  function unlock() {
    el('gate').classList.add('hide');
    el('app').classList.remove('hide');
    el('btn-logout').disabled = false;
    el('btn-refresh').disabled = false;
    el('state-dot').className = 'dot on';
    loadStats();
    loadWhitelist();
  }

  function fmt(n) { return (n === null || n === undefined) ? '—' : n; }

  function loadStats() {
    api('/stats', { headers: authHeaders() }).then(function (s) {
      var b = s.base || {}, pool = b.pool || {}, solde = b.solde || {}, idx = s.index || {}, d = s.demon || {};
      var cards = [
        ['Moteur base', fmt(b.moteur)],
        ['Connexions pool', (pool.in_use || 0) + ' / ' + fmt(pool.max)],
        ['Puzzles résolus', fmt(solde.total_solved)],
        ['Taux de réussite', (solde.win_rate !== undefined ? solde.win_rate + ' %' : '—')],
        ['Coups moyens', fmt(solde.avg_tries)],
        ['Index Chroma', idx.chroma_existe ? (fmt(idx.chroma_mega_octets) + ' Mo') : 'absent'],
        ['Démon', fmt(d.status)],
        ['Sessions de jeu', fmt((s.api || {}).sessions_jeu)],
        ['Action en cours', fmt((s.api || {}).action_en_cours)]
      ];
      el('stats-grid').innerHTML = cards.map(function (c) {
        return '<div class="stat"><span>' + c[0] + '</span><b>' + c[1] + '</b></div>';
      }).join('');
      el('stats-raw').textContent = JSON.stringify(s, null, 2);
      var up = Math.round(s.uptime_seconds || 0);
      el('uptime').textContent = 'API en ligne depuis ' + Math.floor(up / 3600) + ' h ' + Math.floor((up % 3600) / 60) + ' min';
    }).catch(function (e) { toast(e.message, 'ko'); });
  }

  function appendLog(lines) {
    var box = el('log');
    box.textContent += (Array.isArray(lines) ? lines.join('\n') : lines) + '\n';
    box.scrollTop = box.scrollHeight;
  }

  function loadLogs() {
    var source = el('log-source').value;
    var tail = el('log-tail').value;
    api('/logs?source=' + encodeURIComponent(source) + '&tail=' + encodeURIComponent(tail),
        { headers: authHeaders() })
      .then(function (r) { el('log').textContent = ''; appendLog(r.lines || []); })
      .catch(function (e) { toast(e.message, 'ko'); });
  }

  function startFollow(forcedSource) {
    stopFollow();
    var source = forcedSource || el('log-source').value;
    el('log-source').value = source;
    // EventSource ne permet pas d'en-tête custom : le jeton voyage en paramètre.
    stream = new EventSource(API + '/logs/stream?source=' + encodeURIComponent(source)
                             + '&token=' + encodeURIComponent(token));
    stream.onmessage = function (evt) { appendLog(evt.data); };
    stream.onerror = function () { stopFollow(); };
    el('btn-log-follow').textContent = 'Arrêter le suivi';
  }

  function toggleFollow() {
    if (stream) {
      stopFollow();
    } else {
      startFollow();
    }
  }

  function switchTab(name) {
    ['stats', 'logs', 'actions'].forEach(function (t) {
      el('tab-' + t).classList.toggle('hide', t !== name);
    });
    document.querySelectorAll('.tabs button').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-tab') === name);
    });
  }

  var ACTION_INFOS = {
    'solve': {
      title: 'Forcer la découverte du mot du jour',
      desc: 'Une résolution complète va être lancée immédiatement par le worker. Voulez-vous continuer ?'
    },
    'chroma': {
      title: 'Reconstruire l\'index ChromaDB',
      desc: 'Cette opération supprime et régénère l\'ensemble de l\'index vectoriel (plusieurs minutes). Êtes-vous sûr ?'
    },
    'export': {
      title: 'Régénérer data.json et le SEO',
      desc: 'Cette action ré-exporte les statistiques et regénère les pages publiques et les fichiers du tableau de bord.'
    }
  };

  function confirmAction(name) {
    return new Promise(function (resolve) {
      var modal = el('confirm-modal');
      var info = ACTION_INFOS[name] || {
        title: 'Confirmer l\'action',
        desc: 'Voulez-vous vraiment exécuter l\'action « ' + name + ' » ?'
      };
      el('modal-title').textContent = info.title;
      el('modal-desc').textContent = info.desc;

      function onConfirm() {
        cleanup();
        modal.close();
        resolve(true);
      }
      function onCancel() {
        cleanup();
        modal.close();
        resolve(false);
      }
      function cleanup() {
        el('modal-confirm').removeEventListener('click', onConfirm);
        el('modal-cancel').removeEventListener('click', onCancel);
        modal.removeEventListener('cancel', onCancel);
      }

      el('modal-confirm').addEventListener('click', onConfirm);
      el('modal-cancel').addEventListener('click', onCancel);
      modal.addEventListener('cancel', onCancel);

      if (typeof modal.showModal === 'function') {
        modal.showModal();
      } else {
        resolve(window.confirm(info.desc));
      }
    });
  }

  function runAction(name) {
    confirmAction(name).then(function (confirmed) {
      if (!confirmed) return;
      var targetSource = (name === 'solve') ? 'worker' : 'app';
      api('/actions/' + encodeURIComponent(name), { method: 'POST', headers: authHeaders(), body: '{}' })
        .then(function (r) {
          toast(r.message || 'Action lancée', 'ok');
          el('log').textContent = '';
          switchTab('logs');
          startFollow(targetSource);
          setTimeout(loadStats, 1500);
        })
        .catch(function (e) { toast(e.message, 'ko'); });
    });
  }

  el('btn-login').addEventListener('click', function () {
    fetch(API + '/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: el('password').value })
    })
      .then(function (res) {
        return res.json().then(function (j) { return { ok: res.ok, j: j }; });
      })
      .then(function (r) {
        if (!r.ok || !r.j.token) { toast(r.j.error || 'Accès refusé', 'ko'); return; }
        token = r.j.token;
        sessionStorage.setItem('cemantix_admin_token', token);
        el('password').value = '';
        unlock();
      })
      .catch(function () { toast('API indisponible', 'ko'); });
  });

  el('password').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') el('btn-login').click();
  });
  el('btn-logout').addEventListener('click', logout);
  el('btn-refresh').addEventListener('click', loadStats);
  el('btn-log-load').addEventListener('click', loadLogs);
  el('btn-log-follow').addEventListener('click', toggleFollow);
  el('btn-log-clear').addEventListener('click', function () { el('log').textContent = ''; });
  document.querySelectorAll('.tabs button').forEach(function (b) {
    b.addEventListener('click', function () { switchTab(b.getAttribute('data-tab')); });
  });
  document.querySelectorAll('[data-action]').forEach(function (b) {
    b.addEventListener('click', function () { runAction(b.getAttribute('data-action')); });
  });
  var wlAdd = el('wl-add');
  if (wlAdd) wlAdd.addEventListener('click', addWhitelist);

  if (token) {
    api('/whoami', { headers: authHeaders() }).then(unlock).catch(function () { logout(); });
  }
})();

