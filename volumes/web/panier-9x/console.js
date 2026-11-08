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
    token = '';
    sessionStorage.removeItem('cemantix_admin_token');
    window.location.href = '/';
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

  // --- Dictionnaires Joueurs M14 -------------------------------------------
  function renderDictList(containerId, countId, items) {
    var box = el(containerId);
    var countEl = el(countId);
    if (countEl) countEl.textContent = (items || []).length;
    if (!box) return;
    if (!items || !items.length) { box.textContent = 'Aucun mot.'; return; }
    box.innerHTML = items.map(function (w) {
      return '<div style="display:flex;justify-content:space-between;align-items:center;padding:2px 0;border-bottom:1px solid #21262d">'
        + '<span>' + esc(w.word) + '</span>'
        + '<button class="secondary dict-del" data-id="' + esc(w.id) + '" style="padding:1px 6px;font-size:11px">✕</button>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.dict-del').forEach(function (b) {
      b.addEventListener('click', function () { deleteDictWord(b.getAttribute('data-id')); });
    });
  }

  function renderDictionary(data) {
    renderDictList('list-nouns', 'count-nouns', (data && data.nouns) || []);
    renderDictList('list-adjectives', 'count-adjectives', (data && data.adjectives) || []);
    renderDictList('list-recovery', 'count-recovery', (data && data.recovery) || []);
  }

  function loadDictionary() {
    api('/dictionary', { headers: authHeaders() })
      .then(function (r) { renderDictionary(r); })
      .catch(function () {});
  }

  function addDictWord() {
    var type = (el('dict-type').value || '').trim();
    var word = (el('dict-word').value || '').trim();
    if (!word) { toast('Mot requis', 'ko'); return; }
    api('/dictionary', {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ word_type: type, word: word })
    })
      .then(function () {
        el('dict-word').value = '';
        toast('Mot ajouté au dictionnaire', 'ok');
        loadDictionary();
      })
      .catch(function (e) { toast(e.message, 'ko'); });
  }

  function deleteDictWord(id) {
    api('/dictionary/' + encodeURIComponent(id), { method: 'DELETE', headers: authHeaders() })
      .then(function () {
        toast('Mot supprimé', 'ok');
        loadDictionary();
      })
      .catch(function (e) { toast(e.message, 'ko'); });
  }

  // --- Gestion des Utilisateurs en BDD (M14) -------------------------------
  var userPage = 0;
  var userLimit = 25;
  var userSearch = '';
  var userFilter = '';
  var userTotal = 0;

  function renderUserStats(stats) {
    stats = stats || {};
    if (el('stat-users-total')) el('stat-users-total').textContent = fmt(stats.total);
    if (el('stat-users-claimed')) el('stat-users-claimed').textContent = fmt(stats.claimed);
    if (el('stat-users-guests')) el('stat-users-guests').textContent = fmt(stats.guests);
    if (el('stat-users-active')) el('stat-users-active').textContent = fmt(stats.active_7d);
  }

  function updateUserPagination() {
    var info = el('users-pagination-info');
    var btnPrev = el('btn-users-prev');
    var btnNext = el('btn-users-next');
    var totalPages = Math.max(1, Math.ceil(userTotal / userLimit));
    var curPage = userPage + 1;
    if (info) {
      info.textContent = 'Page ' + curPage + ' sur ' + totalPages + ' (' + userTotal + ' utilisateurs)';
    }
    if (btnPrev) btnPrev.disabled = (userPage <= 0);
    if (btnNext) btnNext.disabled = (curPage >= totalPages);
  }

  function renderUsers(users) {
    var tbody = el('users-tbody');
    if (!tbody) return;
    if (!users || !users.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="muted" style="padding:16px;text-align:center">Aucun utilisateur trouvé.</td></tr>';
      return;
    }
    tbody.innerHTML = users.map(function (u) {
      var statusBadge = u.is_claimed
        ? '<span class="badge badge-claimed">Sécurisé (' + esc(u.auth_provider || 'local') + ')</span>'
        : '<span class="badge badge-guest">Invité</span>';
      var renameBadge = u.can_change_username
        ? '<span class="badge badge-active">Autorisé</span>'
        : '<span class="badge badge-locked">Verrouillé</span>';
      return '<tr data-user-id="' + esc(u.id) + '">'
        + '<td style="font-weight:600"><div>' + esc(u.username) + '</div><div class="muted" style="font-size:10px;font-family:monospace">' + esc(String(u.id).substring(0, 8)) + '…</div></td>'
        + '<td>' + statusBadge + '</td>'
        + '<td>' + renameBadge + '</td>'
        + '<td class="muted" style="font-size:12px">' + fmtDate(u.created_at) + '</td>'
        + '<td class="muted" style="font-size:12px">' + fmtDate(u.last_seen_at) + '</td>'
        + '<td style="text-align:right;white-space:nowrap">'
        + '  <button class="secondary btn-user-edit" data-id="' + esc(u.id) + '" data-user="' + esc(u.username) + '" data-can-rename="' + (u.can_change_username ? '1' : '0') + '" style="padding:4px 8px;font-size:12px;margin-right:4px">Modifier</button>'
        + '  <button class="danger btn-user-del" data-id="' + esc(u.id) + '" data-user="' + esc(u.username) + '" style="padding:4px 8px;font-size:12px">Supprimer</button>'
        + '</td>'
        + '</tr>';
    }).join('');

    tbody.querySelectorAll('.btn-user-edit').forEach(function (b) {
      b.addEventListener('click', function () {
        openUserEdit(b.getAttribute('data-id'), b.getAttribute('data-user'), b.getAttribute('data-can-rename') === '1');
      });
    });

    tbody.querySelectorAll('.btn-user-del').forEach(function (b) {
      b.addEventListener('click', function () {
        deleteUser(b.getAttribute('data-id'), b.getAttribute('data-user'));
      });
    });
  }

  function loadUsers() {
    var q = '/users?limit=' + userLimit + '&offset=' + (userPage * userLimit);
    if (userSearch) q += '&search=' + encodeURIComponent(userSearch);
    if (userFilter) q += '&filter=' + encodeURIComponent(userFilter);

    api(q, { headers: authHeaders() })
      .then(function (r) {
        renderUsers(r.users || []);
        renderUserStats(r.stats || {});
        userTotal = r.total || 0;
        updateUserPagination();
      })
      .catch(function (e) { toast(e.message, 'ko'); });
  }

  function openUserEdit(id, username, canRename) {
    var modal = el('user-edit-modal');
    el('edit-user-id').value = id;
    el('edit-user-username').value = username;
    el('edit-user-can-rename').checked = canRename;
    if (typeof modal.showModal === 'function') {
      modal.showModal();
    } else {
      modal.classList.remove('hide');
    }
  }

  function closeUserEdit() {
    var modal = el('user-edit-modal');
    if (typeof modal.close === 'function') {
      modal.close();
    } else {
      modal.classList.add('hide');
    }
  }

  function saveUserEdit() {
    var id = el('edit-user-id').value;
    var username = (el('edit-user-username').value || '').trim();
    var canRename = el('edit-user-can-rename').checked;
    if (!username) { toast('Pseudo requis', 'ko'); return; }
    api('/users/' + encodeURIComponent(id), {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ username: username, can_change_username: canRename })
    })
      .then(function (r) {
        if (r.error) { toast(r.error, 'ko'); return; }
        toast('Utilisateur mis à jour', 'ok');
        closeUserEdit();
        loadUsers();
      })
      .catch(function (e) { toast(e.message, 'ko'); });
  }

  function deleteUser(id, username) {
    var confirmModal = el('confirm-modal');
    el('modal-title').textContent = 'Supprimer l\'utilisateur';
    el('modal-desc').textContent = 'Voulez-vous vraiment supprimer définitivement le joueur « ' + username + ' » ? Cette action est irréversible.';

    function onConfirm() {
      cleanup();
      confirmModal.close();
      api('/users/' + encodeURIComponent(id), { method: 'DELETE', headers: authHeaders() })
        .then(function () {
          toast('Utilisateur « ' + username + ' » supprimé', 'ok');
          loadUsers();
        })
        .catch(function (e) { toast(e.message, 'ko'); });
    }
    function onCancel() {
      cleanup();
      confirmModal.close();
    }
    function cleanup() {
      el('modal-confirm').removeEventListener('click', onConfirm);
      el('modal-cancel').removeEventListener('click', onCancel);
      confirmModal.removeEventListener('cancel', onCancel);
    }
    el('modal-confirm').addEventListener('click', onConfirm);
    el('modal-cancel').addEventListener('click', onCancel);
    confirmModal.addEventListener('cancel', onCancel);

    if (typeof confirmModal.showModal === 'function') {
      confirmModal.showModal();
    } else if (window.confirm('Supprimer ' + username + ' ?')) {
      onConfirm();
    }
  }

  function createUser() {
    var username = (el('new-user-name').value || '').trim();
    var password = (el('new-user-pass').value || '').trim();
    var isClaimed = el('new-user-claimed').checked;
    if (!username || username.length < 3) {
      toast('Pseudo requis (au moins 3 caractères)', 'ko');
      return;
    }
    api('/users', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ username: username, password: password, is_claimed: isClaimed })
    })
      .then(function (r) {
        if (r.error) { toast(r.error, 'ko'); return; }
        toast('Utilisateur « ' + username + ' » créé', 'ok');
        el('new-user-name').value = '';
        el('new-user-pass').value = '';
        el('users-create-panel').classList.add('hide');
        loadUsers();
      })
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
    loadDictionary();
    loadUsers();
  }

  function fmt(n) { return (n === null || n === undefined) ? '—' : n; }

  function fmtDate(d) {
    if (!d) return '—';
    try {
      var dt = new Date(d);
      if (isNaN(dt.getTime())) return String(d);
      return dt.toLocaleString('fr-FR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch (e) {
      return String(d);
    }
  }

  function loadStats() {
    api('/stats', { headers: authHeaders() }).then(function (s) {
      var b = s.base || {}, pool = b.pool || {}, solde = b.solde || {}, idx = s.index || {}, d = s.demon || {}, j = b.joueurs || {};
      var cards = [
        ['Moteur base', fmt(b.moteur)],
        ['Connexions pool', (pool.in_use || 0) + ' / ' + fmt(pool.max)],
        ['Joueurs inscrits', j.total !== undefined ? (fmt(j.total) + ' (' + fmt(j.claimed) + ' sécurisés)') : '—'],
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
    ['stats', 'logs', 'actions', 'dictionary', 'users'].forEach(function (t) {
      var elem = el('tab-' + t);
      if (elem) elem.classList.toggle('hide', t !== name);
    });
    document.querySelectorAll('.tabs button').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-tab') === name);
    });
    if (name === 'dictionary') {
      loadDictionary();
    }
    if (name === 'users') {
      loadUsers();
    }
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
  var dictAdd = el('dict-add');
  if (dictAdd) dictAdd.addEventListener('click', addDictWord);

  // Événements Utilisateurs
  var btnUsersSearch = el('btn-users-search');
  if (btnUsersSearch) {
    btnUsersSearch.addEventListener('click', function () {
      userSearch = (el('users-search').value || '').trim();
      userFilter = el('users-filter').value;
      userPage = 0;
      loadUsers();
    });
  }
  var usersSearchInput = el('users-search');
  if (usersSearchInput) {
    usersSearchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        if (btnUsersSearch) btnUsersSearch.click();
      }
    });
  }
  var usersFilterSelect = el('users-filter');
  if (usersFilterSelect) {
    usersFilterSelect.addEventListener('change', function () {
      if (btnUsersSearch) btnUsersSearch.click();
    });
  }
  var btnUsersRefresh = el('btn-users-refresh');
  if (btnUsersRefresh) {
    btnUsersRefresh.addEventListener('click', function () {
      loadUsers();
    });
  }
  var btnUsersCreateToggle = el('btn-users-create-toggle');
  if (btnUsersCreateToggle) {
    btnUsersCreateToggle.addEventListener('click', function () {
      el('users-create-panel').classList.toggle('hide');
    });
  }
  var btnUsersCreateCancel = el('btn-users-create-cancel');
  if (btnUsersCreateCancel) {
    btnUsersCreateCancel.addEventListener('click', function () {
      el('users-create-panel').classList.add('hide');
    });
  }
  var btnUsersCreate = el('btn-users-create');
  if (btnUsersCreate) {
    btnUsersCreate.addEventListener('click', createUser);
  }
  var btnUsersPrev = el('btn-users-prev');
  if (btnUsersPrev) {
    btnUsersPrev.addEventListener('click', function () {
      if (userPage > 0) {
        userPage--;
        loadUsers();
      }
    });
  }
  var btnUsersNext = el('btn-users-next');
  if (btnUsersNext) {
    btnUsersNext.addEventListener('click', function () {
      var totalPages = Math.ceil(userTotal / userLimit);
      if (userPage + 1 < totalPages) {
        userPage++;
        loadUsers();
      }
    });
  }
  var btnUserEditSave = el('btn-user-edit-save');
  if (btnUserEditSave) {
    btnUserEditSave.addEventListener('click', saveUserEdit);
  }
  var btnUserEditCancel = el('btn-user-edit-cancel');
  if (btnUserEditCancel) {
    btnUserEditCancel.addEventListener('click', closeUserEdit);
  }

  if (token) {
    api('/whoami', { headers: authHeaders() }).then(unlock).catch(function () { logout(); });
  }
})();

