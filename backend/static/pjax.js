(function () {
  'use strict';

  // Pages that require a real navigation (login, admin panels, librarian)
  const HARD_NAV = /^\/(login|admin|librarian)/;

  function injectStyles(doc) {
    document.querySelectorAll('style[data-pjax]').forEach(s => s.remove());
    doc.querySelectorAll('head style').forEach(s => {
      const el = document.createElement('style');
      el.setAttribute('data-pjax', '1');
      el.textContent = s.textContent;
      document.head.appendChild(el);
    });
  }

  function loadExternalScripts(doc) {
    const existing = new Set(
      Array.from(document.querySelectorAll('script[src]')).map(s => s.src)
    );
    const needed = Array.from(doc.querySelectorAll('body script[src]'))
      .filter(s => s.src && !existing.has(new URL(s.src, location.origin).href));
    return Promise.all(needed.map(s => new Promise((resolve) => {
      const el = document.createElement('script');
      el.src = s.src;
      el.onload = resolve;
      el.onerror = resolve; // don't block on CDN failure
      document.head.appendChild(el);
    })));
  }

  function runPageScripts(doc) {
    const scripts = Array.from(doc.querySelectorAll('body script:not([src])'));
    if (!scripts.length) return;

    // Skip the pjax.js re-injection (prevents infinite recursion)
    const text = scripts
      .map(s => s.textContent)
      .filter(t => !t.includes('pjax.js') && t.trim())
      .join('\n');

    if (!text) return;

    // Execute in global scope. On re-navigation, const redeclarations would
    // throw — retry with const/let replaced by var as a fallback.
    try {
      // indirect eval runs in global scope
      (0, eval)(text);
    } catch (e) {
      if (e instanceof SyntaxError || (e instanceof TypeError && /already been declared|redeclaration/.test(e.message))) {
        try {
          const safe = text.replace(/\bconst\b/g, 'var').replace(/\blet\b(?=\s)/g, 'var');
          (0, eval)(safe);
        } catch (e2) {
          console.error('[pjax] page script failed:', e2);
        }
      } else {
        console.error('[pjax] page script failed:', e);
      }
    }
  }

  function updateActiveNav(url) {
    document.querySelectorAll('.nav-item').forEach(el => {
      const href = el.getAttribute('href');
      if (!href) return;
      // Exact match only — no startsWith, so /teacher never stays lit on /teacher/classes
      el.classList.toggle('active', href === url);
    });
  }

  function navigate(url) {
    if (HARD_NAV.test(url)) { location.href = url; return; }

    // Let the current page clean up (stop media, disconnect sockets, etc.)
    if (typeof window.__pjaxCleanup === 'function') {
      try { window.__pjaxCleanup(); } catch (_) {}
      window.__pjaxCleanup = null;
    }

    fetch(url, { headers: { 'X-Pjax': '1' } })
      .then(r => {
        if (!r.ok) { location.href = url; return Promise.reject(); }
        return r.text();
      })
      .then(html => {
        const doc = new DOMParser().parseFromString(html, 'text/html');

        const newMain = doc.querySelector('.main');
        const oldMain = document.querySelector('.main');
        if (newMain && oldMain) {
          oldMain.replaceWith(newMain.cloneNode(true));
        }

        injectStyles(doc);
        document.title = doc.title;
        history.pushState({ pjax: url }, '', url);
        updateActiveNav(url);
        // Load any external scripts the page needs (e.g. socket.io on meeting),
        // then run the page's inline init scripts.
        loadExternalScripts(doc).then(() => runPageScripts(doc));
      })
      .catch(() => { location.href = url; });
  }

  // Intercept sidebar nav clicks
  document.addEventListener('click', function (e) {
    const link = e.target.closest('a.nav-item');
    if (!link) return;
    const href = link.getAttribute('href');
    if (!href || href.startsWith('http') || href.startsWith('//') || href.startsWith('#')) return;
    e.preventDefault();
    navigate(href);
  });

  // Back / forward button support
  window.addEventListener('popstate', function (e) {
    if (e.state && e.state.pjax) navigate(e.state.pjax);
    else navigate(location.pathname);
  });

  // Record starting page so back button works from the first page
  history.replaceState({ pjax: location.pathname }, '', location.pathname);

  // Correct any hardcoded active class in the HTML to match the actual URL
  updateActiveNav(location.pathname);
})();
