(function () {
  'use strict';

  // ── Styles ────────────────────────────────────────────────────────────────
  const css = `
.notif-bell-wrap{position:relative;display:inline-flex;}
.notif-badge{position:absolute;top:-4px;right:-4px;min-width:16px;height:16px;border-radius:20px;background:linear-gradient(135deg,#3dd68c,#38bdf8);color:#fff;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;padding:0 4px;pointer-events:none;transition:opacity 0.2s;}
.notif-badge.hidden{opacity:0;}
.notif-dropdown{position:absolute;top:calc(100% + 10px);right:0;width:340px;max-height:480px;background:var(--bg2,#1a1a1a);border:1px solid var(--border,rgba(255,255,255,0.08));border-radius:14px;box-shadow:0 8px 32px rgba(0,0,0,0.4);z-index:9999;display:none;flex-direction:column;overflow:hidden;}
.notif-dropdown.open{display:flex;}
.notif-header{display:flex;align-items:center;justify-content:space-between;padding:14px 16px 10px;border-bottom:1px solid var(--border,rgba(255,255,255,0.08));flex-shrink:0;}
.notif-header-title{font-size:13px;font-weight:600;color:var(--text,#f0f0f0);}
.notif-read-all{font-size:12px;color:var(--text3,#888);background:none;border:none;cursor:pointer;padding:0;}
.notif-read-all:hover{color:var(--g1,#3dd68c);}
.notif-list{overflow-y:auto;flex:1;}
.notif-list::-webkit-scrollbar{width:3px;}
.notif-list::-webkit-scrollbar-thumb{background:var(--bg4,#2c2c2c);border-radius:3px;}
.notif-item{display:flex;gap:10px;padding:12px 16px;border-bottom:1px solid var(--border,rgba(255,255,255,0.08));cursor:pointer;transition:background 0.15s;text-decoration:none;}
.notif-item:hover{background:var(--bg3,#222);}
.notif-item.unread{background:linear-gradient(135deg,rgba(61,214,140,0.04),rgba(56,189,248,0.04));}
.notif-dot{width:7px;height:7px;border-radius:50%;background:linear-gradient(135deg,#3dd68c,#38bdf8);flex-shrink:0;margin-top:5px;transition:opacity 0.2s;}
.notif-dot.read{opacity:0;}
.notif-item-body{flex:1;min-width:0;}
.notif-item-title{font-size:13px;font-weight:500;color:var(--text,#f0f0f0);margin-bottom:2px;}
.notif-item-body-text{font-size:12px;color:var(--text2,#888);line-height:1.4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.notif-item-time{font-size:11px;color:var(--text3,#444);margin-top:3px;}
.notif-empty{padding:32px 16px;text-align:center;color:var(--text3,#444);font-size:13px;}
`;

  function injectStyles() {
    const s = document.createElement('style');
    s.textContent = css;
    document.head.appendChild(s);
  }

  // ── State ─────────────────────────────────────────────────────────────────
  let notifications = [];
  let unread = 0;
  let dropdownOpen = false;
  let myUserId = null;

  // ── DOM refs (set after inject) ───────────────────────────────────────────
  let bellBtn, badge, dropdown, list;

  // ── Helpers ───────────────────────────────────────────────────────────────
  function timeAgo(iso) {
    const diff = (Date.now() - new Date(iso)) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
  }

  function typeIcon(type) {
    return {
      deadline: '⏰',
      grade:    '📊',
      study:    '📚',
      info:     '💡',
    }[type] || '🔔';
  }

  // ── Render ────────────────────────────────────────────────────────────────
  function renderList() {
    if (!list) return;
    if (notifications.length === 0) {
      list.innerHTML = '<div class="notif-empty">No notifications yet</div>';
      return;
    }
    list.innerHTML = notifications.map(n => `
      <div class="notif-item${n.read ? '' : ' unread'}" data-id="${n.id}" data-link="${n.link || ''}">
        <div class="notif-dot${n.read ? ' read' : ''}"></div>
        <div class="notif-item-body">
          <div class="notif-item-title">${typeIcon(n.type)} ${escHtml(n.title)}</div>
          ${n.body ? `<div class="notif-item-body-text">${escHtml(n.body)}</div>` : ''}
          <div class="notif-item-time">${timeAgo(n.created_at)}</div>
        </div>
      </div>`).join('');

    list.querySelectorAll('.notif-item').forEach(el => {
      el.addEventListener('click', () => onItemClick(+el.dataset.id, el.dataset.link));
    });
  }

  function escHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function updateBadge() {
    if (!badge) return;
    badge.textContent = unread > 9 ? '9+' : unread;
    badge.classList.toggle('hidden', unread === 0);
  }

  // ── Actions ───────────────────────────────────────────────────────────────
  async function onItemClick(id, link) {
    const n = notifications.find(n => n.id === id);
    if (n && !n.read) {
      n.read = true;
      unread = Math.max(0, unread - 1);
      updateBadge();
      renderList();
      fetch(`/api/notifications/${id}/read`, { method: 'POST' }).catch(() => {});
    }
    if (link) { window.location.href = link; }
  }

  async function markAllRead() {
    notifications.forEach(n => { n.read = true; });
    unread = 0;
    updateBadge();
    renderList();
    fetch('/api/notifications/read-all', { method: 'POST' }).catch(() => {});
  }

  function toggleDropdown() {
    dropdownOpen = !dropdownOpen;
    dropdown.classList.toggle('open', dropdownOpen);
    if (dropdownOpen) {
      // Mark visible unread items as read after a moment
      setTimeout(() => {
        const hadUnread = unread > 0;
        notifications.forEach(n => { n.read = true; });
        unread = 0;
        updateBadge();
        if (hadUnread) {
          fetch('/api/notifications/read-all', { method: 'POST' }).catch(() => {});
        }
      }, 1500);
    }
  }

  // ── Fetch from server ─────────────────────────────────────────────────────
  async function fetchNotifications() {
    try {
      const data = await fetch('/api/notifications').then(r => r.ok ? r.json() : null);
      if (!data) return;
      notifications = data.notifications;
      unread = data.unread;
      updateBadge();
      renderList();
    } catch (_) {}
  }

  // ── SocketIO real-time ────────────────────────────────────────────────────
  function connectSocketIO() {
    if (typeof io === 'undefined') return;
    const socket = io({ transports: ['websocket', 'polling'] });
    window._armuSock = socket;
    socket.on('connect', () => {
      if (myUserId) socket.emit('user_join', { user_id: myUserId });
    });
    socket.on('notification', (n) => {
      notifications.unshift(n);
      unread++;
      updateBadge();
      renderList();
      showToast(n);
    });
  }

  // ── Toast pop-up ──────────────────────────────────────────────────────────
  function showToast(n) {
    const t = document.createElement('div');
    t.style.cssText = `position:fixed;bottom:24px;right:24px;background:var(--bg2,#1a1a1a);border:1px solid var(--border-accent,rgba(61,214,140,0.2));border-radius:12px;padding:14px 18px;max-width:320px;box-shadow:0 8px 32px rgba(0,0,0,0.4);z-index:99999;cursor:pointer;transition:opacity 0.3s;`;
    t.innerHTML = `<div style="font-size:13px;font-weight:600;color:var(--text,#f0f0f0);margin-bottom:3px;">${typeIcon(n.type)} ${escHtml(n.title)}</div>${n.body ? `<div style="font-size:12px;color:var(--text2,#888);">${escHtml(n.body)}</div>` : ''}`;
    t.onclick = () => { t.remove(); if (n.link) window.location.href = n.link; };
    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 5000);
  }

  // ── Inject bell into topbar ───────────────────────────────────────────────
  function inject() {
    const topbarRight = document.querySelector('.topbar-right');
    if (!topbarRight) return;

    const wrap = document.createElement('div');
    wrap.className = 'notif-bell-wrap';
    wrap.style.position = 'relative';

    wrap.innerHTML = `
      <div class="icon-btn" id="notifBell" title="Notifications" style="position:relative;">
        <svg style="width:18px;height:18px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
        <div class="notif-badge hidden" id="notifBadge">0</div>
      </div>
      <div class="notif-dropdown" id="notifDropdown">
        <div class="notif-header">
          <span class="notif-header-title">Notifications</span>
          <button class="notif-read-all" id="notifReadAll">Mark all read</button>
        </div>
        <div class="notif-list" id="notifList">
          <div class="notif-empty">Loading…</div>
        </div>
      </div>`;

    // Insert before the first child (theme toggle)
    topbarRight.insertBefore(wrap, topbarRight.firstChild);

    bellBtn  = wrap.querySelector('#notifBell');
    badge    = wrap.querySelector('#notifBadge');
    dropdown = wrap.querySelector('#notifDropdown');
    list     = wrap.querySelector('#notifList');

    bellBtn.addEventListener('click', (e) => { e.stopPropagation(); toggleDropdown(); });
    wrap.querySelector('#notifReadAll').addEventListener('click', (e) => { e.stopPropagation(); markAllRead(); });

    document.addEventListener('click', (e) => {
      if (dropdownOpen && !wrap.contains(e.target)) {
        dropdownOpen = false;
        dropdown.classList.remove('open');
      }
    });
  }

  // ── Tab visibility ────────────────────────────────────────────────────────
  const TAB_ROUTES = {
    calendar: '/calendar', homework: '/homework', tests: '/tests',
    schedule: '/schedule', activities: '/activities', grades: '/grades',
    conduct: '/conduct', leaderboard: '/leaderboard', tutor: '/tutor',
    whiteboard: '/whiteboard', library: '/library', groups: '/groups',
    messages: '/messages',
  };

  async function applyTabVisibility() {
    const CACHE_KEY = 'mokyai_hidden_tabs';
    const DATE_KEY  = 'mokyai_hidden_tabs_date';
    const today = new Date().toISOString().slice(0, 10);

    let hidden = null;
    if (sessionStorage.getItem(DATE_KEY) === today) {
      try { hidden = JSON.parse(sessionStorage.getItem(CACHE_KEY)); } catch {}
    }
    if (!hidden) {
      try {
        const data = await fetch('/api/settings/tabs').then(r => r.ok ? r.json() : {});
        hidden = data.hidden || [];
        sessionStorage.setItem(CACHE_KEY, JSON.stringify(hidden));
        sessionStorage.setItem(DATE_KEY, today);
      } catch { hidden = []; }
    }
    if (!hidden.length) return;
    hidden.forEach(tab => {
      const href = TAB_ROUTES[tab];
      if (!href) return;
      document.querySelectorAll(`.nav-item[href="${href}"]`).forEach(el => {
        el.style.display = 'none';
      });
      if (location.pathname === href) location.href = '/dashboard';
    });
  }

  // ── Boot ──────────────────────────────────────────────────────────────────
  async function boot() {
    injectStyles();
    inject();

    // Get user info for SocketIO room join and tab visibility gating
    let myRole = null;
    try {
      const me = await fetch('/api/auth/me').then(r => r.ok ? r.json() : null);
      if (me && !me.error) { myUserId = me.id; myRole = me.role; }
    } catch (_) {}

    await fetchNotifications();
    connectSocketIO();
    if (myRole === 'student') applyTabVisibility();

    // Refresh every 60s as fallback
    setInterval(fetchNotifications, 60000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
