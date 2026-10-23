/**
 * OHS Edge Evals - Inline Agent Feedback & Directives Widget
 * Strictly in-page workflow: Never redirects to GitHub.
 * Features:
 *  - Inline element inspection & speech-bubble popovers anchored directly to elements
 *  - Direct REST API issue creation on fredhersch/ohs-edge-evals with in-card confirmation
 *  - Persistent inline pin badges (#issue) anchored on target elements
 *  - Role-based collaborator verification (Admin, Maintainer, Write) with inline token capture
 */

(function () {
  'use strict';

  if (window.__OHS_AGENT_FEEDBACK_LOADED__) return;
  window.__OHS_AGENT_FEEDBACK_LOADED__ = true;

  const CONFIG = {
    repoOwner: 'fredhersch',
    repoName: 'ohs-edge-evals',
    defaultLabels: ['agent-task', 'ui-feedback'],
    storageAuthKey: 'ohs_agent_feedback_auth_v1',
    storagePinsKey: 'ohs_agent_feedback_pins_v1'
  };

  // State
  let authUser = null; // { token, login, role, avatar_url, checkedAt }
  let isInspectMode = false;
  let hoveredElement = null;
  let activePin = null;

  // Relative file path in repository
  function getPageLocation() {
    let path = window.location.pathname || 'index.html';
    if (path === '/' || path.endsWith('/')) path += 'index.html';
    return path.replace(/^\//, '');
  }

  // Reliable CSS Selector Generator
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

  // Inject Scoped Stylesheet
  const styleEl = document.createElement('style');
  styleEl.textContent = `
    /* Floating Dock */
    #oaf-dock {
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: 999990;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      border-radius: 9999px;
      background: #090d16;
      color: #f8fafc;
      border: 1px solid #263352;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 12px;
      user-select: none;
      transition: all 0.2s ease;
    }
    #oaf-dock:hover {
      border-color: #3b82f6;
    }

    #oaf-dock-avatar {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      border: 1px solid #3b82f6;
      display: none;
    }

    .oaf-dock-btn {
      background: #172033;
      border: 1px solid #263352;
      color: #f8fafc;
      padding: 5px 12px;
      border-radius: 8px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .oaf-dock-btn:hover {
      background: #1e2942;
      border-color: #3b82f6;
    }
    .oaf-dock-btn-primary {
      background: #2563eb;
      border-color: #1d4ed8;
      color: #ffffff;
    }
    .oaf-dock-btn-primary:hover {
      background: #1d4ed8;
    }

    .oaf-pulse-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #34d399;
      box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.7);
      animation: oaf-pulse-anim 2s infinite;
    }
    @keyframes oaf-pulse-anim {
      0% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.7); }
      70% { box-shadow: 0 0 0 6px rgba(52, 211, 153, 0); }
      100% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0); }
    }

    /* Inspector Overlay */
    #oaf-inspect-box {
      position: fixed;
      pointer-events: none;
      z-index: 999980;
      border: 2px solid #3b82f6;
      background: rgba(59, 130, 246, 0.14);
      border-radius: 4px;
      display: none;
      transition: top 0.03s ease, left 0.03s ease, width 0.03s ease, height 0.03s ease;
    }
    #oaf-inspect-tooltip {
      position: absolute;
      top: -24px;
      left: 0;
      background: #090d16;
      color: #93c5fd;
      padding: 2px 7px;
      font-size: 11px;
      font-family: ui-monospace, SFMono-Regular, monospace;
      border-radius: 4px;
      border: 1px solid #263352;
      white-space: nowrap;
      pointer-events: none;
    }

    /* Targeting Banner */
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
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      display: none;
      align-items: center;
      gap: 12px;
      font-size: 12px;
      font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Anchored Pin */
    .oaf-pin {
      position: absolute;
      z-index: 999900;
      transform: translate(-50%, -50%);
      min-width: 26px;
      height: 26px;
      padding: 0 6px;
      border-radius: 9999px;
      background: #2563eb;
      color: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 700;
      font-family: -apple-system, BlinkMacSystemFont, sans-serif;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.3), 0 4px 10px rgba(0,0,0,0.4);
      cursor: pointer;
      transition: transform 0.15s ease, background-color 0.15s ease;
      user-select: none;
    }
    .oaf-pin:hover {
      transform: translate(-50%, -50%) scale(1.15);
      background: #1d4ed8;
    }
    .oaf-pin.has-issue {
      background: #059669;
      box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.3), 0 4px 10px rgba(0,0,0,0.4);
    }

    /* Anchored Speech Bubble Popover */
    #oaf-inline-popover {
      position: absolute;
      z-index: 999992;
      width: 370px;
      max-width: calc(100vw - 32px);
      background: #0f172a;
      color: #f8fafc;
      border-radius: 14px;
      border: 1px solid #263352;
      box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.08);
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

    /* Arrow Pointer */
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

    .oaf-pop-tag {
      font-family: ui-monospace, monospace;
      font-size: 11px;
      color: #60a5fa;
      background: rgba(37, 99, 235, 0.15);
      padding: 2px 6px;
      border-radius: 4px;
      max-width: 220px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .oaf-textarea, .oaf-input {
      width: 100%;
      border-radius: 8px;
      padding: 8px 10px;
      font-size: 12px;
      background: #090d16;
      border: 1px solid #263352;
      color: #f8fafc;
      box-sizing: border-box;
      outline: none;
      font-family: inherit;
    }
    .oaf-textarea:focus, .oaf-input:focus {
      border-color: #3b82f6;
      box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
    }
  `;
  document.head.appendChild(styleEl);

  // Widget DOM
  const root = document.createElement('div');
  root.id = 'oaf-root';
  root.innerHTML = `
    <!-- Inspector Hover Box -->
    <div id="oaf-inspect-box">
      <div id="oaf-inspect-tooltip">&lt;tag&gt;</div>
    </div>

    <!-- Target Mode Banner -->
    <div id="oaf-target-banner">
      <span class="oaf-pulse-dot"></span>
      <span><strong>Inline Mode:</strong> Click any element to anchor a comment</span>
      <button id="oaf-cancel-target-btn" class="oaf-dock-btn" style="padding:3px 8px; font-size:11px;">Cancel (Esc)</button>
    </div>

    <!-- Anchored Inline Popover -->
    <div id="oaf-inline-popover">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div style="display:flex; align-items:center; gap:6px;">
          <span id="oaf-pop-tag" class="oaf-pop-tag">&lt;element&gt;</span>
          <span id="oaf-pop-page" style="font-size:10px; color:#94a3b8; font-family:monospace;">${getPageLocation()}</span>
        </div>
        <button id="oaf-pop-close-btn" style="background:none; border:none; color:#94a3b8; cursor:pointer; font-size:14px; padding:2px;">✕</button>
      </div>

      <!-- Main Comment View -->
      <div id="oaf-pop-view-main" style="display:flex; flex-direction:column; gap:8px;">
        <div style="display:flex; gap:4px;" id="oaf-pop-cats">
          <button class="oaf-dock-btn oaf-cat-btn oaf-dock-btn-primary" data-cat="UI Fix" style="font-size:10px; padding:2px 7px;">🎨 UI Fix</button>
          <button class="oaf-dock-btn oaf-cat-btn" data-cat="Bug" style="font-size:10px; padding:2px 7px;">🐛 Bug</button>
          <button class="oaf-dock-btn oaf-cat-btn" data-cat="Copy" style="font-size:10px; padding:2px 7px;">✍️ Copy</button>
          <button class="oaf-dock-btn oaf-cat-btn" data-cat="Feature" style="font-size:10px; padding:2px 7px;">💡 Feature</button>
        </div>

        <textarea id="oaf-pop-textarea" class="oaf-textarea" rows="3" placeholder="Describe the change, fix, or directive for this element..."></textarea>

        <!-- Inline Token Entry (only shown if not yet authorized) -->
        <div id="oaf-pop-token-box" style="display:none; padding:10px; border-radius:8px; background:rgba(37,99,235,0.08); border:1px solid rgba(59,130,246,0.3); flex-direction:column; gap:6px;">
          <div style="font-size:11px; font-weight:600; color:#93c5fd; display:flex; align-items:center; gap:5px;">
            <i class="fa-solid fa-key text-[10px]"></i>
            <span>Enter GitHub Token Once for Direct In-Page Creation:</span>
          </div>
          <input id="oaf-pop-token-input" type="password" placeholder="ghp_... (saved securely in your local browser)" class="oaf-input" style="font-size:11px; padding:5px 8px;" />
          <div id="oaf-pop-token-error" style="color:#f87171; font-size:10px; display:none;"></div>
        </div>

        <!-- Buttons Row -->
        <div style="display:flex; justify-content:space-between; align-items:center; pt-1;">
          <button id="oaf-pop-copy-btn" class="oaf-dock-btn" title="Copy structured task markdown to clipboard for agent">
            <i class="fa-regular fa-clipboard"></i>
            <span>Copy for Agent</span>
          </button>
          <button id="oaf-pop-submit-btn" class="oaf-dock-btn oaf-dock-btn-primary" title="Post issue directly to GitHub without leaving this page">
            <i class="fa-solid fa-paper-plane"></i>
            <span id="oaf-pop-submit-label">Create Issue</span>
          </button>
        </div>
      </div>

      <!-- Success View (Shown in-card after issue is created) -->
      <div id="oaf-pop-view-success" style="display:none; flex-direction:column; gap:8px; padding:4px 0;">
        <div style="display:flex; align-items:center; gap:8px; color:#34d399;">
          <div style="width:24px; height:24px; border-radius:50%; background:rgba(16,185,129,0.2); display:flex; align-items:center; justify-content:center;">
            <i class="fa-solid fa-check text-xs"></i>
          </div>
          <div>
            <strong style="font-size:13px; color:#f8fafc;" id="oaf-success-title">Issue Created!</strong>
            <div style="font-size:10px; color:#94a3b8;">Anchored inline on this element</div>
          </div>
        </div>
        <div id="oaf-success-body" style="font-size:11px; color:#cbd5e1; background:#090d16; padding:8px 10px; border-radius:6px; border:1px solid #263352; max-height:80px; overflow-y:auto;"></div>
        <div style="display:flex; justify-content:flex-end; gap:6px; pt-1;">
          <button id="oaf-success-done-btn" class="oaf-dock-btn oaf-dock-btn-primary" style="padding:4px 12px;">Done</button>
        </div>
      </div>

      <!-- Existing Pin View (When clicking an already submitted pin) -->
      <div id="oaf-pop-view-existing" style="display:none; flex-direction:column; gap:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span id="oaf-existing-badge" style="font-size:11px; font-weight:700; color:#34d399; background:rgba(16,185,129,0.15); padding:2px 8px; border-radius:4px;">#Issue</span>
          <span id="oaf-existing-cat" style="font-size:10px; color:#94a3b8;">UI Fix</span>
        </div>
        <div id="oaf-existing-comment" style="font-size:12px; color:#f8fafc; background:#090d16; padding:8px 10px; border-radius:6px; border:1px solid #263352; line-height:1.4;"></div>
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <button id="oaf-delete-pin-btn" class="oaf-dock-btn" style="color:#f87171; border-color:rgba(239,68,68,0.3); font-size:11px;">
            <i class="fa-regular fa-trash-can"></i>
            <span>Remove Pin</span>
          </button>
          <button id="oaf-existing-copy-btn" class="oaf-dock-btn">
            <i class="fa-regular fa-clipboard"></i>
            <span>Copy Task</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Floating Dock (Present on every page) -->
    <div id="oaf-dock" title="Inline Agent Feedback">
      <div class="oaf-pulse-dot"></div>
      <img id="oaf-dock-avatar" src="" alt="user" />
      <span id="oaf-dock-user" style="font-weight:600; display:none;">@user</span>
      <span id="oaf-dock-role" style="font-size:10px; text-transform:uppercase; padding:2px 5px; border-radius:4px; background:rgba(37,99,235,0.2); color:#60a5fa; display:none;">Admin</span>
      <button id="oaf-dock-pin-btn" class="oaf-dock-btn oaf-dock-btn-primary" title="Click to pin a comment inline to any UI element (Hotkey: C)">
        <i class="fa-solid fa-map-pin"></i>
        <span>Inline Comment</span>
      </button>
      <button id="oaf-dock-settings-btn" class="oaf-dock-btn" title="GitHub Connection Settings" style="padding:5px 8px;">
        <i class="fa-solid fa-gear text-xs"></i>
      </button>
    </div>
  `;
  document.body.appendChild(root);

  // Cached DOM
  const dock = document.getElementById('oaf-dock');
  const dockAvatar = document.getElementById('oaf-dock-avatar');
  const dockUser = document.getElementById('oaf-dock-user');
  const dockRole = document.getElementById('oaf-dock-role');
  const dockPinBtn = document.getElementById('oaf-dock-pin-btn');
  const dockSettingsBtn = document.getElementById('oaf-dock-settings-btn');
  const inspectBox = document.getElementById('oaf-inspect-box');
  const inspectTooltip = document.getElementById('oaf-inspect-tooltip');
  const targetBanner = document.getElementById('oaf-target-banner');
  const cancelTargetBtn = document.getElementById('oaf-cancel-target-btn');
  const inlinePopover = document.getElementById('oaf-inline-popover');
  const popTag = document.getElementById('oaf-pop-tag');
  const popPage = document.getElementById('oaf-pop-page');
  const popCloseBtn = document.getElementById('oaf-pop-close-btn');
  const popViewMain = document.getElementById('oaf-pop-view-main');
  const popViewSuccess = document.getElementById('oaf-pop-view-success');
  const popViewExisting = document.getElementById('oaf-pop-view-existing');
  const popTextarea = document.getElementById('oaf-pop-textarea');
  const popTokenBox = document.getElementById('oaf-pop-token-box');
  const popTokenInput = document.getElementById('oaf-pop-token-input');
  const popTokenError = document.getElementById('oaf-pop-token-error');
  const popSubmitBtn = document.getElementById('oaf-pop-submit-btn');
  const popSubmitLabel = document.getElementById('oaf-pop-submit-label');
  const popCopyBtn = document.getElementById('oaf-pop-copy-btn');
  const successTitle = document.getElementById('oaf-success-title');
  const successBody = document.getElementById('oaf-success-body');
  const successDoneBtn = document.getElementById('oaf-success-done-btn');
  const existingBadge = document.getElementById('oaf-existing-badge');
  const existingCat = document.getElementById('oaf-existing-cat');
  const existingComment = document.getElementById('oaf-existing-comment');
  const existingCopyBtn = document.getElementById('oaf-existing-copy-btn');
  const deletePinBtn = document.getElementById('oaf-delete-pin-btn');

  let activeCategory = 'UI Fix';

  // Category Toggle
  document.querySelectorAll('#oaf-pop-cats .oaf-cat-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#oaf-pop-cats .oaf-cat-btn').forEach(b => b.classList.remove('oaf-dock-btn-primary'));
      btn.classList.add('oaf-dock-btn-primary');
      activeCategory = btn.dataset.cat;
    });
  });

  // Verify GitHub Token & Collaborator Access
  async function verifyToken(token) {
    const userRes = await fetch('https://api.github.com/user', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github.v3+json'
      }
    });
    if (!userRes.ok) throw new Error('Invalid token: unable to fetch authenticated user.');
    const userData = await userRes.json();

    const repoRes = await fetch(`https://api.github.com/repos/${CONFIG.repoOwner}/${CONFIG.repoName}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github.v3+json'
      }
    });
    if (!repoRes.ok) throw new Error(`Token lacks access to ${CONFIG.repoOwner}/${CONFIG.repoName}.`);
    const repoData = await repoRes.json();

    const perms = repoData.permissions || {};
    const hasWrite = perms.admin || perms.maintain || perms.push;
    if (!hasWrite) {
      throw new Error(`@${userData.login} has read-only access. Write/collaborator access is required.`);
    }

    let roleName = 'Write';
    if (perms.admin) roleName = 'Admin';
    else if (perms.maintain) roleName = 'Maintainer';

    return {
      token: token,
      login: userData.login,
      role: roleName,
      avatar_url: userData.avatar_url || '',
      checkedAt: Date.now()
    };
  }

  // Update Dock UI when user is authenticated
  function updateDockAuth(user) {
    if (user) {
      authUser = user;
      dockAvatar.src = user.avatar_url || 'https://github.com/ghost.png';
      dockAvatar.style.display = 'block';
      dockUser.textContent = `@${user.login}`;
      dockUser.style.display = 'inline';
      dockRole.textContent = user.role;
      dockRole.style.display = 'inline';
      popTokenBox.style.display = 'none';
    } else {
      authUser = null;
      dockAvatar.style.display = 'none';
      dockUser.style.display = 'none';
      dockRole.style.display = 'none';
    }
  }

  // Check stored credentials
  async function initAuth() {
    const stored = localStorage.getItem(CONFIG.storageAuthKey);
    if (stored) {
      try {
        const cached = JSON.parse(stored);
        if (cached && cached.token) {
          updateDockAuth(cached);
          // Background re-verify if older than 12h
          if (Date.now() - (cached.checkedAt || 0) > 12 * 3600 * 1000) {
            verifyToken(cached.token).then(fresh => {
              localStorage.setItem(CONFIG.storageAuthKey, JSON.stringify(fresh));
              updateDockAuth(fresh);
            }).catch(() => {
              // Ignore background network blip
            });
          }
        }
      } catch (e) {
        localStorage.removeItem(CONFIG.storageAuthKey);
      }
    }
    loadPinsForPage();
  }

  // Settings / Disconnect
  dockSettingsBtn.addEventListener('click', () => {
    if (authUser) {
      if (confirm(`Connected as @${authUser.login} (${authUser.role}).\n\nLog out of inline feedback mode?`)) {
        localStorage.removeItem(CONFIG.storageAuthKey);
        updateDockAuth(null);
        alert('Logged out. You can enter a new token when placing a comment.');
      }
    } else {
      const token = prompt('Enter your GitHub Personal Access Token (PAT) with repo/issues permissions:');
      if (token && token.trim()) {
        verifyToken(token.trim()).then(user => {
          localStorage.setItem(CONFIG.storageAuthKey, JSON.stringify(user));
          updateDockAuth(user);
          alert(`✅ Verified as @${user.login} (${user.role})!`);
        }).catch(err => {
          alert(`Authentication error: ${err.message}`);
        });
      }
    }
  });

  // Hotkey support: C to pin, Esc to cancel
  window.addEventListener('keydown', (e) => {
    if (e.key.toLowerCase() === 'c' && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
      e.preventDefault();
      toggleInspectMode();
    } else if (e.key === 'Escape') {
      if (isInspectMode) stopInspectMode();
      if (inlinePopover.style.display === 'flex') inlinePopover.style.display = 'none';
    }
  });

  // Pins Persistence
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
      openExistingPin(pinData, pin);
    });

    document.body.appendChild(pin);
    return pin;
  }

  // Positioning the Popover directly next to element
  function positionPopover(targetEl, pinEl) {
    const rect = targetEl ? targetEl.getBoundingClientRect() : pinEl.getBoundingClientRect();
    const popWidth = 370;
    const popHeight = 220;

    let left = rect.left + window.scrollX;
    let top = rect.bottom + window.scrollY + 8;

    if (rect.bottom + popHeight > window.innerHeight && rect.top - popHeight > 0) {
      top = rect.top + window.scrollY - popHeight - 8;
      inlinePopover.classList.add('arrow-bottom');
    } else {
      inlinePopover.classList.remove('arrow-bottom');
    }

    if (left + popWidth > window.innerWidth - 20) {
      left = window.innerWidth - popWidth - 20;
    }
    if (left < 10) left = 10;

    inlinePopover.style.top = `${top}px`;
    inlinePopover.style.left = `${left}px`;
    inlinePopover.style.display = 'flex';
  }

  // Open Popover for Existing Pin
  function openExistingPin(pinData, pinEl) {
    activePin = pinData;
    popTag.textContent = `<${pinData.tagName || 'element'}>`;
    popPage.textContent = pinData.page;

    popViewMain.style.display = 'none';
    popViewSuccess.style.display = 'none';
    popViewExisting.style.display = 'flex';

    existingBadge.textContent = pinData.issueNumber ? `Issue #${pinData.issueNumber}` : 'Draft Pin';
    existingCat.textContent = pinData.category || 'UI Fix';
    existingComment.textContent = pinData.comment || '(No description)';

    const targetEl = document.querySelector(pinData.selector);
    positionPopover(targetEl, pinEl);
  }

  // Delete Existing Pin
  deletePinBtn.addEventListener('click', () => {
    if (!activePin) return;
    let pins = getPins();
    pins = pins.filter(p => p.id !== activePin.id);
    savePins(pins);
    loadPinsForPage();
    inlinePopover.style.display = 'none';
  });

  existingCopyBtn.addEventListener('click', () => {
    if (!activePin) return;
    const markdown = buildAgentInstruction(activePin, activePin.comment);
    navigator.clipboard.writeText(markdown).then(() => {
      existingCopyBtn.innerHTML = `<i class="fa-solid fa-check" style="color:#34d399;"></i><span>Copied!</span>`;
      setTimeout(() => {
        existingCopyBtn.innerHTML = `<i class="fa-regular fa-clipboard"></i><span>Copy Task</span>`;
      }, 1500);
    });
  });

  // Inspection / Target Mode
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
      popTextarea.value = '';

      popViewMain.style.display = 'flex';
      popViewSuccess.style.display = 'none';
      popViewExisting.style.display = 'none';

      // Show token box if not yet authenticated
      popTokenBox.style.display = authUser ? 'none' : 'flex';

      positionPopover(selected, null);
      popTextarea.focus();
    }
  }

  // Construct structured Markdown for AI Coding Assistant
  function buildAgentInstruction(pinData, comment) {
    return [
      `### 🎯 UI Directive for Agent (Inline Element Pin)`,
      `**Category**: \`${pinData.category || activeCategory}\` | **Page**: [\`${pinData.page}\`](file:///${pinData.page})`,
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
      `> 🤖 **Agent Guidance**: Locate this element in \`${pinData.page}\` using the text, class, or selector above and apply the requested change cleanly.`
    ].join('\n');
  }

  // Submit Issue Strictly In-Page (Never Opens GitHub!)
  async function submitIssueInPage() {
    if (!activePin) return;
    const comment = popTextarea.value.trim();
    if (!comment) {
      alert('Please describe what needs to be changed.');
      popTextarea.focus();
      return;
    }

    // If not authenticated, verify token from inline box first
    let token = authUser ? authUser.token : null;
    if (!token) {
      const enteredToken = popTokenInput.value.trim();
      if (!enteredToken) {
        popTokenBox.style.display = 'flex';
        popTokenError.textContent = 'Please paste your GitHub Personal Access Token to submit.';
        popTokenError.style.display = 'block';
        popTokenInput.focus();
        return;
      }

      popSubmitBtn.disabled = true;
      popSubmitLabel.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Verifying...`;

      try {
        const verified = await verifyToken(enteredToken);
        localStorage.setItem(CONFIG.storageAuthKey, JSON.stringify(verified));
        updateDockAuth(verified);
        token = verified.token;
      } catch (err) {
        popTokenError.textContent = err.message;
        popTokenError.style.display = 'block';
        popSubmitBtn.disabled = false;
        popSubmitLabel.textContent = 'Create Issue';
        return;
      }
    }

    // Now submit issue via GitHub REST API
    popSubmitBtn.disabled = true;
    popSubmitLabel.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Posting in-page...`;

    activePin.category = activeCategory;
    activePin.comment = comment;

    const title = `[${activeCategory}] ${activePin.page}: <${activePin.tagName}> ${comment.substring(0, 50)}`;
    const body = buildAgentInstruction(activePin, comment);
    const labels = [...CONFIG.defaultLabels, activeCategory.toLowerCase().replace(/[^a-z0-9]/g, '-')];

    try {
      const res = await fetch(`https://api.github.com/repos/${CONFIG.repoOwner}/${CONFIG.repoName}/issues`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/vnd.github.v3+json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ title, body, labels })
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.message || `GitHub API error (${res.status})`);
      }

      const issue = await res.json();
      activePin.issueNumber = issue.number;
      activePin.issueUrl = issue.html_url;

      // Save locally
      const pins = getPins();
      pins.push(activePin);
      savePins(pins);

      // Render pin badge directly on element
      createPinBadge(activePin, pins.length);

      // Show inline success view inside popover (NO redirection!)
      popViewMain.style.display = 'none';
      popViewSuccess.style.display = 'flex';
      successTitle.textContent = `Issue #${issue.number} Created!`;
      successBody.textContent = `"${comment}"`;
    } catch (err) {
      alert(`Could not create issue: ${err.message}\n\nPlease verify your token permissions (requires repo/issues write access).`);
    } finally {
      popSubmitBtn.disabled = false;
      popSubmitLabel.textContent = 'Create Issue';
    }
  }

  // Copy structured prompt
  popCopyBtn.addEventListener('click', () => {
    if (!activePin) return;
    const comment = popTextarea.value.trim();
    if (!comment) {
      alert('Please enter a comment or instruction.');
      popTextarea.focus();
      return;
    }
    const markdown = buildAgentInstruction(activePin, comment);
    navigator.clipboard.writeText(markdown).then(() => {
      popCopyBtn.innerHTML = `<i class="fa-solid fa-check" style="color:#34d399;"></i><span>Copied!</span>`;
      setTimeout(() => {
        popCopyBtn.innerHTML = `<i class="fa-regular fa-clipboard"></i><span>Copy for Agent</span>`;
      }, 1500);
    });
  });

  // Done button on success view
  successDoneBtn.addEventListener('click', () => {
    inlinePopover.style.display = 'none';
  });

  // UI Event bindings
  dockPinBtn.addEventListener('click', toggleInspectMode);
  cancelTargetBtn.addEventListener('click', stopInspectMode);
  popCloseBtn.addEventListener('click', () => { inlinePopover.style.display = 'none'; });
  popSubmitBtn.addEventListener('click', submitIssueInPage);

  // Initialize Auth on page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAuth);
  } else {
    initAuth();
  }
})();
