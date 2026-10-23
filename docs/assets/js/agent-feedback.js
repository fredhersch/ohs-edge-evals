/**
 * OHS Edge Evals - Inline Agent Feedback & Directives Widget
 * Role-Based Access Control (RBAC): Visible ONLY to repository collaborators with write/admin roles.
 * Features: Inline element pinning, anchored popover comments, and direct GitHub Issue dispatch for AI agents.
 */

(function () {
  'use strict';

  if (window.__OHS_AGENT_FEEDBACK_LOADED__) return;
  window.__OHS_AGENT_FEEDBACK_LOADED__ = true;

  const CONFIG = {
    repoOwner: 'fredhersch',
    repoName: 'ohs-edge-evals',
    defaultLabels: ['agent-task', 'ui-feedback'],
    storageKey: 'ohs_agent_feedback_auth_v1',
    storagePinsKey: 'ohs_agent_feedback_pins_v1'
  };

  // State
  let authUser = null; // { token, login, role, avatar_url, checkedAt }
  let isInspectMode = false;
  let hoveredElement = null;
  let activePin = null;
  let placedPins = [];

  // Determine current page location in repo
  function getPageLocation() {
    let path = window.location.pathname || 'index.html';
    if (path === '/' || path.endsWith('/')) path += 'index.html';
    return path.replace(/^\//, '');
  }

  // Construct stable, clean CSS selector
  function generateCssSelector(el) {
    if (!el || el === document.body || el === document.documentElement) return 'body';
    if (el.id) return `#${CSS.escape(el.id)}`;

    const path = [];
    let curr = el;
    while (curr && curr.nodeType === Node.ELEMENT_NODE && curr !== document.body && curr !== document.documentElement) {
      let selector = curr.nodeName.toLowerCase();
      if (curr.id) {
        selector += `#${CSS.escape(curr.id)}`;
        path.unshift(selector);
        break;
      } else if (curr.className && typeof curr.className === 'string') {
        const classes = curr.className
          .trim()
          .split(/\s+/)
          .filter(c => c && !c.startsWith('oaf-') && !c.includes(':') && !c.includes('/'));
        if (classes.length > 0) {
          selector += '.' + classes.slice(0, 2).map(CSS.escape).join('.');
        }
      }
      path.unshift(selector);
      curr = curr.parentNode;
      if (path.length >= 4) break;
    }
    return path.join(' > ');
  }

  function getCleanOuterHtml(el) {
    if (!el) return '';
    const clone = el.cloneNode(true);
    clone.querySelectorAll('.oaf-pin, #oaf-root').forEach(n => n.remove());
    let html = clone.outerHTML;
    if (html.length > 400) {
      const tagName = el.tagName.toLowerCase();
      const openTag = el.outerHTML.match(/^<[^>]+>/)?.[0] || `<${tagName}>`;
      const textPreview = (el.innerText || '').trim().substring(0, 80);
      html = `${openTag}\n  ${textPreview}\n</${tagName}>`;
    }
    return html;
  }

  // Stylesheet
  const styleEl = document.createElement('style');
  styleEl.textContent = `
    /* Collaborator Bar (Bottom Dock) */
    #oaf-collab-bar {
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: 999990;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 6px 14px;
      border-radius: 9999px;
      background: #090d16;
      color: #f8fafc;
      border: 1px solid #263352;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 12px;
      user-select: none;
      animation: oaf-fade-in 0.25s ease-out;
    }
    @keyframes oaf-fade-in {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    #oaf-collab-bar img {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      border: 1px solid #3b82f6;
    }

    .oaf-badge-role {
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      padding: 2px 6px;
      border-radius: 4px;
      background: rgba(37, 99, 235, 0.2);
      color: #60a5fa;
      border: 1px solid rgba(59, 130, 246, 0.4);
    }

    .oaf-bar-btn {
      background: #172033;
      border: 1px solid #263352;
      color: #f8fafc;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.15s ease;
    }
    .oaf-bar-btn:hover {
      background: #1e2942;
      border-color: #3b82f6;
    }
    .oaf-bar-btn-primary {
      background: #2563eb;
      border-color: #1d4ed8;
      color: #ffffff;
    }
    .oaf-bar-btn-primary:hover {
      background: #1d4ed8;
    }

    /* Inspector Overlay */
    #oaf-inspect-box {
      position: fixed;
      pointer-events: none;
      z-index: 999980;
      border: 2px solid #3b82f6;
      background: rgba(59, 130, 246, 0.12);
      border-radius: 4px;
      display: none;
      transition: top 0.04s ease, left 0.04s ease, width 0.04s ease, height 0.04s ease;
    }
    #oaf-inspect-tooltip {
      position: absolute;
      top: -24px;
      left: 0;
      background: #090d16;
      color: #93c5fd;
      padding: 2px 6px;
      font-size: 11px;
      font-family: ui-monospace, monospace;
      border-radius: 4px;
      border: 1px solid #263352;
      white-space: nowrap;
    }

    /* Target Mode Banner */
    #oaf-target-banner {
      position: fixed;
      top: 16px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 999995;
      background: #090d16;
      color: #ffffff;
      padding: 8px 18px;
      border-radius: 9999px;
      border: 1px solid #3b82f6;
      box-shadow: 0 10px 25px rgba(0,0,0,0.4);
      display: none;
      align-items: center;
      gap: 12px;
      font-size: 12px;
      font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Anchored Inline Pin */
    .oaf-pin {
      position: absolute;
      z-index: 999900;
      transform: translate(-50%, -50%);
      width: 26px;
      height: 26px;
      border-radius: 50%;
      background: #2563eb;
      color: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 700;
      font-family: -apple-system, BlinkMacSystemFont, sans-serif;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.3), 0 4px 10px rgba(0,0,0,0.3);
      cursor: pointer;
      transition: transform 0.15s ease, background-color 0.15s ease;
    }
    .oaf-pin:hover {
      transform: translate(-50%, -50%) scale(1.15);
      background: #1d4ed8;
    }
    .oaf-pin.has-issue {
      background: #10b981;
      box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.3), 0 4px 10px rgba(0,0,0,0.3);
    }

    /* Inline Popover Card (Anchored directly next to element) */
    #oaf-inline-popover {
      position: absolute;
      z-index: 999992;
      width: 360px;
      background: #0f172a;
      color: #f8fafc;
      border-radius: 12px;
      border: 1px solid #263352;
      box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.08);
      padding: 14px;
      display: none;
      flex-direction: column;
      gap: 10px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 12px;
      animation: oaf-pop 0.15s ease-out;
    }
    @keyframes oaf-pop {
      from { opacity: 0; transform: scale(0.96); }
      to { opacity: 1; transform: scale(1); }
    }

    /* Popover Arrow */
    #oaf-inline-popover::before {
      content: '';
      position: absolute;
      width: 10px;
      height: 10px;
      background: #0f172a;
      border-left: 1px solid #263352;
      border-top: 1px solid #263352;
      transform: rotate(45deg);
      top: -6px;
      left: 20px;
    }
    #oaf-inline-popover.arrow-bottom::before {
      top: auto;
      bottom: -6px;
      border-left: none;
      border-top: none;
      border-right: 1px solid #263352;
      border-bottom: 1px solid #263352;
    }

    .oaf-target-tag {
      font-family: ui-monospace, monospace;
      font-size: 11px;
      color: #60a5fa;
      background: rgba(37, 99, 235, 0.15);
      padding: 2px 6px;
      border-radius: 4px;
      max-width: 200px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .oaf-popover-textarea {
      width: 100%;
      border-radius: 8px;
      padding: 8px 10px;
      font-size: 12px;
      background: #090d16;
      border: 1px solid #263352;
      color: #f8fafc;
      box-sizing: border-box;
      outline: none;
      resize: vertical;
      font-family: inherit;
    }
    .oaf-popover-textarea:focus {
      border-color: #3b82f6;
      box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
    }

    /* Auth Dialog */
    #oaf-auth-modal {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(4px);
      z-index: 999999;
      display: none;
      align-items: center;
      justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    #oaf-auth-card {
      width: 420px;
      max-width: calc(100vw - 32px);
      background: #0f172a;
      border: 1px solid #263352;
      border-radius: 14px;
      padding: 22px;
      color: #f8fafc;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
  `;
  document.head.appendChild(styleEl);

  // Root container
  const root = document.createElement('div');
  root.id = 'oaf-root';
  root.innerHTML = `
    <!-- Inspector Hover Box -->
    <div id="oaf-inspect-box">
      <div id="oaf-inspect-tooltip">&lt;tag&gt;</div>
    </div>

    <!-- Inspector Active Banner -->
    <div id="oaf-target-banner">
      <span>🎯 <strong>Inline Targeting Active:</strong> Click any element to pin a comment.</span>
      <button id="oaf-cancel-inspect-btn" class="oaf-bar-btn">Cancel (Esc)</button>
    </div>

    <!-- Anchored Inline Popover -->
    <div id="oaf-inline-popover">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div style="display:flex; align-items:center; gap:6px;">
          <span id="oaf-pop-tag" class="oaf-target-tag">&lt;button&gt;</span>
          <span id="oaf-pop-page" style="font-size:10px; color:#94a3b8; font-family:monospace;">${getPageLocation()}</span>
        </div>
        <button id="oaf-pop-close" style="background:none; border:none; color:#94a3b8; cursor:pointer; font-size:14px;">✕</button>
      </div>

      <div style="display:flex; gap:4px;" id="oaf-pop-cats">
        <button class="oaf-bar-btn oaf-cat-btn" data-cat="UI Fix" style="font-size:10px; padding:2px 6px;">🎨 UI Fix</button>
        <button class="oaf-bar-btn oaf-cat-btn" data-cat="Bug" style="font-size:10px; padding:2px 6px;">🐛 Bug</button>
        <button class="oaf-bar-btn oaf-cat-btn" data-cat="Copy" style="font-size:10px; padding:2px 6px;">✍️ Copy</button>
      </div>

      <textarea id="oaf-pop-input" class="oaf-popover-textarea" rows="3" placeholder="Describe the change or fix needed for this element..."></textarea>

      <div style="display:flex; justify-content:space-between; align-items:center; gap:6px; pt-1;">
        <button id="oaf-pop-copy-btn" class="oaf-bar-btn" title="Copy markdown task to clipboard for AI agent">
          <i class="fa-regular fa-clipboard"></i>
          <span>Copy for Agent</span>
        </button>
        <button id="oaf-pop-submit-btn" class="oaf-bar-btn oaf-bar-btn-primary" title="Post directly to GitHub Issues">
          <i class="fa-brands fa-github"></i>
          <span id="oaf-pop-submit-label">Create Issue</span>
        </button>
      </div>
    </div>

    <!-- Collaborator Bar (Rendered only when authenticated) -->
    <div id="oaf-collab-bar" style="display:none;">
      <img id="oaf-bar-avatar" src="" alt="avatar" />
      <span id="oaf-bar-user" style="font-weight:600;">@user</span>
      <span id="oaf-bar-role" class="oaf-badge-role">Admin</span>
      <button id="oaf-bar-pin-btn" class="oaf-bar-btn oaf-bar-btn-primary" title="Pin comment directly to any element on page (Hotkey: C)">
        <i class="fa-solid fa-map-pin"></i>
        <span>Inline Comment</span>
      </button>
      <button id="oaf-bar-logout-btn" class="oaf-bar-btn" title="Log out and hide widget" style="padding:4px 6px;">
        <i class="fa-solid fa-arrow-right-from-bracket"></i>
      </button>
    </div>

    <!-- Auth Modal (Shown via shortcut or ?feedback=login) -->
    <div id="oaf-auth-modal">
      <div id="oaf-auth-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div style="display:flex; align-items:center; gap:8px;">
            <i class="fa-solid fa-shield-halved" style="color:#60a5fa; font-size:16px;"></i>
            <strong style="font-size:14px;">Collaborator Access Verification</strong>
          </div>
          <button id="oaf-auth-close" style="background:none; border:none; color:#94a3b8; font-size:16px; cursor:pointer;">✕</button>
        </div>
        <p style="font-size:12px; color:#94a3b8; margin:0; line-height:1.5;">
          This inline widget is restricted to repository collaborators on <code style="color:#60a5fa;">${CONFIG.repoOwner}/${CONFIG.repoName}</code>.
          Enter your GitHub Personal Access Token to verify your collaborator role.
        </p>
        <div>
          <label style="font-size:11px; font-weight:600; text-transform:uppercase; color:#94a3b8; display:block; margin-bottom:4px;">GitHub Personal Access Token (PAT)</label>
          <input id="oaf-auth-token-input" type="password" placeholder="ghp_... or github_pat_..." class="oaf-popover-textarea" style="height:36px; padding:6px 10px;" />
          <span style="font-size:10px; color:#64748b; margin-top:3px; display:block;">Requires read repo metadata &amp; write issues permission. Token is saved only in your browser.</span>
        </div>
        <div id="oaf-auth-error" style="color:#f87171; font-size:11px; display:none;"></div>
        <div style="display:flex; justify-content:flex-end; gap:8px;">
          <button id="oaf-auth-cancel" class="oaf-bar-btn">Cancel</button>
          <button id="oaf-auth-submit" class="oaf-bar-btn oaf-bar-btn-primary">
            <span>Verify &amp; Unlock</span>
          </button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(root);

  // Cached DOM elements
  const collabBar = document.getElementById('oaf-collab-bar');
  const barAvatar = document.getElementById('oaf-bar-avatar');
  const barUser = document.getElementById('oaf-bar-user');
  const barRole = document.getElementById('oaf-bar-role');
  const barPinBtn = document.getElementById('oaf-bar-pin-btn');
  const barLogoutBtn = document.getElementById('oaf-bar-logout-btn');
  const inspectBox = document.getElementById('oaf-inspect-box');
  const inspectTooltip = document.getElementById('oaf-inspect-tooltip');
  const targetBanner = document.getElementById('oaf-target-banner');
  const cancelInspectBtn = document.getElementById('oaf-cancel-inspect-btn');
  const inlinePopover = document.getElementById('oaf-inline-popover');
  const popTag = document.getElementById('oaf-pop-tag');
  const popPage = document.getElementById('oaf-pop-page');
  const popClose = document.getElementById('oaf-pop-close');
  const popInput = document.getElementById('oaf-pop-input');
  const popSubmitBtn = document.getElementById('oaf-pop-submit-btn');
  const popSubmitLabel = document.getElementById('oaf-pop-submit-label');
  const popCopyBtn = document.getElementById('oaf-pop-copy-btn');
  const authModal = document.getElementById('oaf-auth-modal');
  const authClose = document.getElementById('oaf-auth-close');
  const authCancel = document.getElementById('oaf-auth-cancel');
  const authSubmit = document.getElementById('oaf-auth-submit');
  const authTokenInput = document.getElementById('oaf-auth-token-input');
  const authError = document.getElementById('oaf-auth-error');

  let activeCategory = 'UI Fix';

  // Category buttons
  document.querySelectorAll('#oaf-pop-cats .oaf-cat-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#oaf-pop-cats .oaf-cat-btn').forEach(b => b.classList.remove('oaf-bar-btn-primary'));
      btn.classList.add('oaf-bar-btn-primary');
      activeCategory = btn.dataset.cat;
    });
  });

  // Verify GitHub Token & Repo Role
  async function verifyGitHubAccess(token) {
    try {
      // 1. Fetch user profile
      const userRes = await fetch('https://api.github.com/user', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/vnd.github.v3+json'
        }
      });
      if (!userRes.ok) throw new Error('Invalid token: unable to fetch authenticated user.');
      const userData = await userRes.json();

      // 2. Fetch repository permissions for this user
      const repoRes = await fetch(`https://api.github.com/repos/${CONFIG.repoOwner}/${CONFIG.repoName}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/vnd.github.v3+json'
        }
      });
      if (!repoRes.ok) throw new Error(`Unable to access ${CONFIG.repoOwner}/${CONFIG.repoName} with this token.`);
      const repoData = await repoRes.json();

      const perms = repoData.permissions || {};
      const hasWrite = perms.admin || perms.maintain || perms.push;

      if (!hasWrite) {
        throw new Error(`Access Denied: @${userData.login} has read-only access. Write/collaborator access is required.`);
      }

      let roleName = 'Collaborator';
      if (perms.admin) roleName = 'Admin';
      else if (perms.maintain) roleName = 'Maintainer';
      else if (perms.push) roleName = 'Write';

      return {
        token,
        login: userData.login,
        role: roleName,
        avatar_url: userData.avatar_url || '',
        checkedAt: Date.now()
      };
    } catch (err) {
      throw err;
    }
  }

  // Mount UI when collaborator access is confirmed
  function mountCollaboratorUI(user) {
    authUser = user;
    barAvatar.src = user.avatar_url || 'https://github.com/ghost.png';
    barUser.textContent = `@${user.login}`;
    barRole.textContent = user.role;
    collabBar.style.display = 'flex';
    authModal.style.display = 'none';

    // Render stored pins for this page if any
    loadPinsForPage();
  }

  // Check stored auth on initialization
  async function checkAuth() {
    // Check URL parameters for manual trigger
    const params = new URLSearchParams(window.location.search);
    const wantsLogin = params.has('feedback') || params.has('agent_feedback');

    const stored = localStorage.getItem(CONFIG.storageKey);
    if (stored) {
      try {
        const cached = JSON.parse(stored);
        // If checked in last 12 hours, trust; otherwise re-verify
        if (cached.token && Date.now() - (cached.checkedAt || 0) < 12 * 3600 * 1000) {
          mountCollaboratorUI(cached);
          return;
        } else if (cached.token) {
          const fresh = await verifyGitHubAccess(cached.token);
          localStorage.setItem(CONFIG.storageKey, JSON.stringify(fresh));
          mountCollaboratorUI(fresh);
          return;
        }
      } catch (e) {
        localStorage.removeItem(CONFIG.storageKey);
      }
    }

    // Only if URL param explicitly requests login
    if (wantsLogin) {
      authModal.style.display = 'flex';
      authTokenInput.focus();
    }
  }

  // Handle Auth submission
  authSubmit.addEventListener('click', async () => {
    const token = authTokenInput.value.trim();
    if (!token) {
      authError.textContent = 'Please enter a GitHub Personal Access Token.';
      authError.style.display = 'block';
      return;
    }

    authSubmit.disabled = true;
    authSubmit.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Checking permissions...`;
    authError.style.display = 'none';

    try {
      const verified = await verifyGitHubAccess(token);
      localStorage.setItem(CONFIG.storageKey, JSON.stringify(verified));
      mountCollaboratorUI(verified);
    } catch (err) {
      authError.textContent = err.message;
      authError.style.display = 'block';
    } finally {
      authSubmit.disabled = false;
      authSubmit.innerHTML = `Verify &amp; Unlock`;
    }
  });

  authClose.addEventListener('click', () => { authModal.style.display = 'none'; });
  authCancel.addEventListener('click', () => { authModal.style.display = 'none'; });

  // Logout
  barLogoutBtn.addEventListener('click', () => {
    if (confirm('Log out of Agent Feedback collaborator mode?')) {
      localStorage.removeItem(CONFIG.storageKey);
      authUser = null;
      collabBar.style.display = 'none';
      inlinePopover.style.display = 'none';
      document.querySelectorAll('.oaf-pin').forEach(p => p.remove());
    }
  });

  // Shortcut: Cmd+Shift+F or Ctrl+Shift+F opens auth if logged out, or toggles comment mode if logged in
  window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'f') {
      e.preventDefault();
      if (!authUser) {
        authModal.style.display = 'flex';
        authTokenInput.focus();
      } else {
        toggleInspectMode();
      }
    } else if (authUser && e.key.toLowerCase() === 'c' && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
      e.preventDefault();
      toggleInspectMode();
    } else if (e.key === 'Escape') {
      if (isInspectMode) stopInspectMode();
      if (inlinePopover.style.display === 'flex') inlinePopover.style.display = 'none';
      if (authModal.style.display === 'flex') authModal.style.display = 'none';
    }
  });

  // Inline Pin Management
  function getPins() {
    try {
      return JSON.parse(localStorage.getItem(CONFIG.storagePinsKey) || '[]');
    } catch {
      return [];
    }
  }

  function savePins(pins) {
    localStorage.setItem(CONFIG.storagePinsKey, JSON.stringify(pins));
  }

  function loadPinsForPage() {
    document.querySelectorAll('.oaf-pin').forEach(p => p.remove());
    const all = getPins();
    const page = getPageLocation();
    const current = all.filter(p => p.page === page);

    current.forEach((pinData, idx) => {
      createPinBadge(pinData, idx + 1);
    });
  }

  function createPinBadge(pinData, indexNum) {
    const el = document.querySelector(pinData.selector);
    let top = pinData.top;
    let left = pinData.left;

    // If element still exists in DOM, snap to current element coordinates
    if (el) {
      const rect = el.getBoundingClientRect();
      top = rect.top + window.scrollY;
      left = rect.left + window.scrollX;
    }

    const pin = document.createElement('div');
    pin.className = 'oaf-pin' + (pinData.issueNumber ? ' has-issue' : '');
    pin.style.top = `${top}px`;
    pin.style.left = `${left}px`;
    pin.innerHTML = pinData.issueNumber ? `#${pinData.issueNumber}` : `${indexNum}`;
    pin.title = pinData.comment || 'Click to view comment';

    pin.addEventListener('click', (e) => {
      e.stopPropagation();
      openPopoverForPin(pinData, pin);
    });

    document.body.appendChild(pin);
    return pin;
  }

  // Positioning the Inline Popover next to element
  function positionPopover(targetEl, pinEl) {
    const rect = targetEl ? targetEl.getBoundingClientRect() : pinEl.getBoundingClientRect();
    const popWidth = 360;
    const popHeight = 240;

    let left = (targetEl ? rect.left : rect.left) + window.scrollX;
    let top = (targetEl ? rect.bottom : rect.bottom) + window.scrollY + 8;

    // Check bottom viewport boundary
    if (rect.bottom + popHeight > window.innerHeight && rect.top - popHeight > 0) {
      top = rect.top + window.scrollY - popHeight - 8;
      inlinePopover.classList.add('arrow-bottom');
    } else {
      inlinePopover.classList.remove('arrow-bottom');
    }

    // Keep within left/right viewport boundaries
    if (left + popWidth > window.innerWidth - 20) {
      left = window.innerWidth - popWidth - 20;
    }
    if (left < 10) left = 10;

    inlinePopover.style.top = `${top}px`;
    inlinePopover.style.left = `${left}px`;
    inlinePopover.style.display = 'flex';
  }

  function openPopoverForPin(pinData, pinEl) {
    activePin = pinData;
    popTag.textContent = `<${pinData.tagName || 'element'}>`;
    popPage.textContent = pinData.page;
    popInput.value = pinData.comment || '';

    if (pinData.issueNumber) {
      popSubmitLabel.innerHTML = `Issue #${pinData.issueNumber} ↗`;
      popSubmitBtn.onclick = () => window.open(pinData.issueUrl, '_blank');
    } else {
      popSubmitLabel.innerHTML = `Create Issue`;
      popSubmitBtn.onclick = submitInlineComment;
    }

    const targetEl = document.querySelector(pinData.selector);
    positionPopover(targetEl, pinEl);
    popInput.focus();
  }

  // Targeting / Inspect Mode
  function toggleInspectMode() {
    if (isInspectMode) stopInspectMode();
    else startInspectMode();
  }

  function startInspectMode() {
    isInspectMode = true;
    targetBanner.style.display = 'flex';
    document.body.style.cursor = 'crosshair';
    inlinePopover.style.display = 'none';

    window.addEventListener('mousemove', onMouseMove, true);
    window.addEventListener('click', onElementClick, true);
  }

  function stopInspectMode() {
    isInspectMode = false;
    targetBanner.style.display = 'none';
    inspectBox.style.display = 'none';
    document.body.style.cursor = '';

    window.removeEventListener('mousemove', onMouseMove, true);
    window.removeEventListener('click', onElementClick, true);
  }

  function onMouseMove(e) {
    if (!isInspectMode) return;
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (!el || root.contains(el) || el.classList.contains('oaf-pin')) {
      inspectBox.style.display = 'none';
      return;
    }

    hoveredElement = el;
    const rect = el.getBoundingClientRect();
    inspectBox.style.display = 'block';
    inspectBox.style.top = `${rect.top}px`;
    inspectBox.style.left = `${rect.left}px`;
    inspectBox.style.width = `${rect.width}px`;
    inspectBox.style.height = `${rect.height}px`;

    const tag = el.tagName.toLowerCase();
    const id = el.id ? `#${el.id}` : '';
    const firstClass = el.classList.length ? `.${el.classList[0]}` : '';
    inspectTooltip.textContent = `<${tag}${id || firstClass}>`;
  }

  function onElementClick(e) {
    if (!isInspectMode) return;
    if (root.contains(e.target)) return;

    e.preventDefault();
    e.stopPropagation();

    if (hoveredElement) {
      const selected = hoveredElement;
      stopInspectMode();

      const rect = selected.getBoundingClientRect();
      const selector = generateCssSelector(selected);
      const outerHtml = getCleanOuterHtml(selected);
      const innerText = (selected.innerText || '').trim().replace(/\s+/g, ' ').substring(0, 140);

      activePin = {
        id: 'pin_' + Date.now(),
        page: getPageLocation(),
        selector: selector,
        outerHtml: outerHtml,
        innerText: innerText,
        tagName: selected.tagName.toLowerCase(),
        top: rect.top + window.scrollY,
        left: rect.left + window.scrollX,
        comment: '',
        category: activeCategory
      };

      popTag.textContent = `<${activePin.tagName}>`;
      popPage.textContent = activePin.page;
      popInput.value = '';
      popSubmitLabel.textContent = 'Create Issue';
      popSubmitBtn.onclick = submitInlineComment;

      positionPopover(selected, null);
      popInput.focus();
    }
  }

  // Construct Markdown for coding agent
  function buildAgentInstruction(pinData, comment) {
    return [
      `### 🎯 UI Directive for Agent (Inline Pin)`,
      `**Category**: \`${activeCategory}\` | **Page**: [\`${pinData.page}\`](file:///${pinData.page})`,
      ``,
      `#### 💬 User Instruction`,
      `> ${comment}`,
      ``,
      `---`,
      `#### 📍 Element Grounding (Zero Ambiguity)`,
      `- **Target Page / File**: \`${pinData.page}\``,
      `- **CSS Selector**: \`${pinData.selector}\``,
      `- **Element Text**: \`${pinData.innerText || 'N/A'}\``,
      `- **Coordinates**: x=${Math.round(pinData.left)}, y=${Math.round(pinData.top)}`,
      ``,
      `\`\`\`html`,
      pinData.outerHtml,
      `\`\`\``,
      ``,
      `> 🤖 **Agent Guidance**: Locate this element in \`${pinData.page}\` using the text, class, or selector above and apply the requested change.`
    ].join('\n');
  }

  // Submit issue directly via GitHub REST API with collaborator token
  async function submitInlineComment() {
    if (!activePin) return;
    const comment = popInput.value.trim();
    if (!comment) {
      alert('Please enter an instruction or description of the fix.');
      popInput.focus();
      return;
    }

    popSubmitBtn.disabled = true;
    popSubmitLabel.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Submitting...`;

    const title = `[${activeCategory}] ${activePin.page}: <${activePin.tagName}> ${comment.substring(0, 50)}`;
    const body = buildAgentInstruction(activePin, comment);
    const labels = [...CONFIG.defaultLabels, activeCategory.toLowerCase().replace(/[^a-z0-9]/g, '-')];

    try {
      const res = await fetch(`https://api.github.com/repos/${CONFIG.repoOwner}/${CONFIG.repoName}/issues`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authUser.token}`,
          'Accept': 'application/vnd.github.v3+json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ title, body, labels })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.message || 'Failed to create GitHub issue via API');
      }

      const issue = await res.json();
      activePin.comment = comment;
      activePin.issueNumber = issue.number;
      activePin.issueUrl = issue.html_url;

      // Save pin locally
      const pins = getPins();
      pins.push(activePin);
      savePins(pins);

      // Render pin badge on element
      createPinBadge(activePin, pins.length);

      inlinePopover.style.display = 'none';
      alert(`✅ Issue #${issue.number} created on GitHub and pinned inline!`);
    } catch (err) {
      alert(`API Error: ${err.message}\nFalling back to opening pre-filled issue URL.`);
      const fallbackUrl = `https://github.com/${CONFIG.repoOwner}/${CONFIG.repoName}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
      window.open(fallbackUrl, '_blank');
    } finally {
      popSubmitBtn.disabled = false;
      popSubmitLabel.textContent = 'Create Issue';
    }
  }

  // Copy structured prompt for AI agent
  popCopyBtn.addEventListener('click', () => {
    if (!activePin) return;
    const comment = popInput.value.trim();
    if (!comment) {
      alert('Please enter a comment or instruction.');
      popInput.focus();
      return;
    }

    const markdown = buildAgentInstruction(activePin, comment);
    navigator.clipboard.writeText(markdown).then(() => {
      const orig = popCopyBtn.innerHTML;
      popCopyBtn.innerHTML = `<i class="fa-solid fa-check" style="color:#34d399;"></i><span>Copied!</span>`;
      setTimeout(() => { popCopyBtn.innerHTML = orig; }, 2000);
    });
  });

  // UI Event bindings
  barPinBtn.addEventListener('click', toggleInspectMode);
  cancelInspectBtn.addEventListener('click', stopInspectMode);
  popClose.addEventListener('click', () => { inlinePopover.style.display = 'none'; });

  // Initialize Auth Check on page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkAuth);
  } else {
    checkAuth();
  }
})();
