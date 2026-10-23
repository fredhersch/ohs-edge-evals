/**
 * OHS Edge Evals - Inline Agent Feedback & Directives Widget
 * Strictly in-page workflow: Never redirects to GitHub.
 * Features:
 *  - High-visibility launcher dock on all pages
 *  - 1-click Authentication dialog for GitHub Personal Access Tokens (PAT)
 *  - Inline element inspection & speech-bubble popovers anchored directly to elements
 *  - Direct REST API issue creation on fredhersch/ohs-edge-evals with in-card confirmation
 *  - Persistent inline pin badges (#issue) anchored on target elements
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

  let authUser = null;
  let isInspectMode = false;
  let hoveredElement = null;
  let activePin = null;

  function getPageLocation() {
    let path = window.location.pathname || 'index.html';
    if (path === '/' || path.endsWith('/')) path += 'index.html';
    return path.replace(/^\//, '');
  }

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

  function injectWidget() {
    if (document.getElementById('oaf-root')) return;

    // Stylesheet
    const styleEl = document.createElement('style');
    styleEl.textContent = `
      #oaf-dock {
        position: fixed !important;
        bottom: 24px !important;
        right: 24px !important;
        z-index: 9999999 !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        padding: 6px 14px !important;
        border-radius: 9999px !important;
        background: #090d16 !important;
        color: #f8fafc !important;
        border: 1px solid #334155 !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.1) !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        font-size: 12px !important;
        user-select: none !important;
        transition: transform 0.2s ease, border-color 0.2s ease !important;
      }
      #oaf-dock:hover {
        transform: translateY(-2px);
        border-color: #3b82f6 !important;
      }

      .oaf-dock-btn {
        background: #172033 !important;
        border: 1px solid #334155 !important;
        color: #f8fafc !important;
        padding: 5px 12px !important;
        border-radius: 8px !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 6px !important;
        transition: all 0.15s ease !important;
        line-height: 1.2 !important;
      }
      .oaf-dock-btn:hover {
        background: #1e2942 !important;
        border-color: #3b82f6 !important;
      }
      .oaf-dock-btn-primary {
        background: #2563eb !important;
        border-color: #1d4ed8 !important;
        color: #ffffff !important;
      }
      .oaf-dock-btn-primary:hover {
        background: #1d4ed8 !important;
      }

      .oaf-pulse-dot {
        width: 8px !important;
        height: 8px !important;
        border-radius: 50% !important;
        background: #34d399 !important;
        box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.7) !important;
        animation: oaf-pulse-anim 2s infinite !important;
      }
      @keyframes oaf-pulse-anim {
        0% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.7); }
        70% { box-shadow: 0 0 0 7px rgba(52, 211, 153, 0); }
        100% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0); }
      }

      /* Inspector Box */
      #oaf-inspect-box {
        position: fixed !important;
        pointer-events: none !important;
        z-index: 9999980 !important;
        border: 2px solid #3b82f6 !important;
        background: rgba(59, 130, 246, 0.15) !important;
        border-radius: 4px !important;
        display: none;
        transition: top 0.03s ease, left 0.03s ease, width 0.03s ease, height 0.03s ease !important;
      }
      #oaf-inspect-tooltip {
        position: absolute !important;
        top: -24px !important;
        left: 0 !important;
        background: #090d16 !important;
        color: #93c5fd !important;
        padding: 2px 7px !important;
        font-size: 11px !important;
        font-family: ui-monospace, SFMono-Regular, monospace !important;
        border-radius: 4px !important;
        border: 1px solid #334155 !important;
        white-space: nowrap !important;
        pointer-events: none !important;
      }

      /* Target Mode Banner */
      #oaf-target-banner {
        position: fixed !important;
        top: 20px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 9999995 !important;
        background: #090d16 !important;
        color: #ffffff !important;
        padding: 9px 20px !important;
        border-radius: 9999px !important;
        border: 1px solid #3b82f6 !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.6) !important;
        display: none;
        align-items: center !important;
        gap: 12px !important;
        font-size: 13px !important;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif !important;
      }

      /* Pins */
      .oaf-pin {
        position: absolute !important;
        z-index: 9999900 !important;
        transform: translate(-50%, -50%) !important;
        min-width: 26px !important;
        height: 26px !important;
        padding: 0 6px !important;
        border-radius: 9999px !important;
        background: #2563eb !important;
        color: #ffffff !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.3), 0 4px 10px rgba(0,0,0,0.4) !important;
        cursor: pointer !important;
        transition: transform 0.15s ease, background-color 0.15s ease !important;
        user-select: none !important;
      }
      .oaf-pin:hover {
        transform: translate(-50%, -50%) scale(1.15) !important;
        background: #1d4ed8 !important;
      }
      .oaf-pin.has-issue {
        background: #059669 !important;
        box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.3), 0 4px 10px rgba(0,0,0,0.4) !important;
      }

      /* Popover Card */
      #oaf-inline-popover {
        position: absolute !important;
        z-index: 9999992 !important;
        width: 370px !important;
        max-width: calc(100vw - 32px) !important;
        background: #0f172a !important;
        color: #f8fafc !important;
        border-radius: 14px !important;
        border: 1px solid #334155 !important;
        box-shadow: 0 20px 45px -10px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.08) !important;
        padding: 14px !important;
        display: none;
        flex-direction: column !important;
        gap: 10px !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        font-size: 12px !important;
      }
      #oaf-inline-popover::before {
        content: '';
        position: absolute;
        width: 10px;
        height: 10px;
        background: #0f172a;
        border-left: 1px solid #334155;
        border-top: 1px solid #334155;
        transform: rotate(45deg);
        top: -6px;
        left: 20px;
      }
      #oaf-inline-popover.arrow-bottom::before {
        top: auto;
        bottom: -6px;
        border-left: none;
        border-top: none;
        border-right: 1px solid #334155;
        border-bottom: 1px solid #334155;
      }

      .oaf-textarea, .oaf-input {
        width: 100% !important;
        border-radius: 8px !important;
        padding: 8px 10px !important;
        font-size: 12px !important;
        background: #090d16 !important;
        border: 1px solid #334155 !important;
        color: #f8fafc !important;
        box-sizing: border-box !important;
        outline: none !important;
        font-family: inherit !important;
      }
      .oaf-textarea:focus, .oaf-input:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25) !important;
      }

      /* Dedicated Auth Modal */
      #oaf-auth-modal {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        background: rgba(0, 0, 0, 0.75) !important;
        backdrop-filter: blur(4px) !important;
        z-index: 99999999 !important;
        display: none;
        align-items: center !important;
        justify-content: center !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
      }
      #oaf-auth-card {
        width: 440px !important;
        max-width: calc(100vw - 32px) !important;
        background: #0f172a !important;
        border: 1px solid #334155 !important;
        border-radius: 16px !important;
        padding: 22px !important;
        color: #f8fafc !important;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7) !important;
        display: flex !important;
        flex-direction: column !important;
        gap: 14px !important;
      }
    `;
    document.head.appendChild(styleEl);

    // Root Container
    const root = document.createElement('div');
    root.id = 'oaf-root';
    root.innerHTML = `
      <div id="oaf-inspect-box">
        <div id="oaf-inspect-tooltip">&lt;tag&gt;</div>
      </div>

      <div id="oaf-target-banner">
        <span class="oaf-pulse-dot"></span>
        <span><strong>Targeting Mode:</strong> Click any element to pin a comment (Esc to cancel)</span>
        <button id="oaf-cancel-target-btn" class="oaf-dock-btn" style="padding:3px 8px; font-size:11px;">Cancel</button>
      </div>

      <!-- Anchored Popover -->
      <div id="oaf-inline-popover">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div style="display:flex; align-items:center; gap:6px;">
            <span id="oaf-pop-tag" style="font-family:monospace; font-size:11px; color:#60a5fa; background:rgba(37,99,235,0.15); padding:2px 6px; border-radius:4px;">&lt;element&gt;</span>
            <span id="oaf-pop-page" style="font-size:10px; color:#94a3b8; font-family:monospace;">${getPageLocation()}</span>
          </div>
          <button id="oaf-pop-close-btn" style="background:none; border:none; color:#94a3b8; cursor:pointer; font-size:14px; padding:2px;">✕</button>
        </div>

        <div id="oaf-pop-view-main" style="display:flex; flex-direction:column; gap:8px;">
          <div style="display:flex; gap:4px;" id="oaf-pop-cats">
            <button class="oaf-dock-btn oaf-cat-btn oaf-dock-btn-primary" data-cat="UI Fix" style="font-size:10px; padding:2px 7px;">🎨 UI Fix</button>
            <button class="oaf-dock-btn oaf-cat-btn" data-cat="Bug" style="font-size:10px; padding:2px 7px;">🐛 Bug</button>
            <button class="oaf-dock-btn oaf-cat-btn" data-cat="Copy" style="font-size:10px; padding:2px 7px;">✍️ Copy</button>
            <button class="oaf-dock-btn oaf-cat-btn" data-cat="Feature" style="font-size:10px; padding:2px 7px;">💡 Feature</button>
          </div>

          <textarea id="oaf-pop-textarea" class="oaf-textarea" rows="3" placeholder="Describe what should be changed or fixed on this element..."></textarea>

          <div style="display:flex; justify-content:space-between; align-items:center; pt-1;">
            <button id="oaf-pop-copy-btn" class="oaf-dock-btn" title="Copy markdown task to clipboard for AI coding agent">
              <i class="fa-regular fa-clipboard"></i>
              <span>Copy for Agent</span>
            </button>
            <button id="oaf-pop-submit-btn" class="oaf-dock-btn oaf-dock-btn-primary" title="Post issue directly to GitHub without leaving this page">
              <i class="fa-solid fa-paper-plane"></i>
              <span id="oaf-pop-submit-label">Create Issue</span>
            </button>
          </div>
        </div>

        <!-- Success View -->
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
          <div id="oaf-success-body" style="font-size:11px; color:#cbd5e1; background:#090d16; padding:8px 10px; border-radius:6px; border:1px solid #334155; max-height:80px; overflow-y:auto;"></div>
          <div style="display:flex; justify-content:flex-end; gap:6px; pt-1;">
            <button id="oaf-success-done-btn" class="oaf-dock-btn oaf-dock-btn-primary" style="padding:4px 12px;">Done</button>
          </div>
        </div>

        <!-- Existing Pin View -->
        <div id="oaf-pop-view-existing" style="display:none; flex-direction:column; gap:8px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span id="oaf-existing-badge" style="font-size:11px; font-weight:700; color:#34d399; background:rgba(16,185,129,0.15); padding:2px 8px; border-radius:4px;">#Issue</span>
            <span id="oaf-existing-cat" style="font-size:10px; color:#94a3b8;">UI Fix</span>
          </div>
          <div id="oaf-existing-comment" style="font-size:12px; color:#f8fafc; background:#090d16; padding:8px 10px; border-radius:6px; border:1px solid #334155; line-height:1.4;"></div>
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

      <!-- Floating Dock (Bottom Right on All Pages) -->
      <div id="oaf-dock">
        <div class="oaf-pulse-dot"></div>
        <img id="oaf-dock-avatar" src="" alt="user" style="width:20px; height:20px; border-radius:50%; border:1px solid #3b82f6; display:none;" />
        <span id="oaf-dock-user" style="font-weight:600; font-size:11px; display:none;">@user</span>
        <span id="oaf-dock-role" style="font-size:9px; text-transform:uppercase; padding:2px 5px; border-radius:4px; background:rgba(37,99,235,0.2); color:#60a5fa; display:none;">Admin</span>
        <button id="oaf-dock-pin-btn" class="oaf-dock-btn oaf-dock-btn-primary" title="Click to pin a comment inline to any UI element (Hotkey: C)">
          <i class="fa-solid fa-map-pin"></i>
          <span>Inline Comment</span>
        </button>
        <button id="oaf-dock-auth-btn" class="oaf-dock-btn" title="Connect GitHub Account" style="padding:5px 9px;">
          <i class="fa-solid fa-key text-xs" style="color:#fbbf24;"></i>
          <span id="oaf-dock-auth-label">Connect</span>
        </button>
      </div>

      <!-- Dedicated Authentication Modal -->
      <div id="oaf-auth-modal">
        <div id="oaf-auth-card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:8px;">
              <div style="width:28px; height:28px; border-radius:8px; background:rgba(59,130,246,0.15); display:flex; align-items:center; justify-content:center; color:#60a5fa;">
                <i class="fa-solid fa-shield-halved"></i>
              </div>
              <div>
                <strong style="font-size:14px;">Connect GitHub Account</strong>
                <div style="font-size:11px; color:#94a3b8;">Direct in-page issue creation for collaborators</div>
              </div>
            </div>
            <button id="oaf-auth-close-btn" style="background:none; border:none; color:#94a3b8; font-size:16px; cursor:pointer;">✕</button>
          </div>

          <div style="font-size:12px; color:#cbd5e1; line-height:1.5;">
            Authenticate with a GitHub Personal Access Token (PAT) to post issues directly without leaving the page.
            <div style="margin-top:6px; font-size:11px; color:#94a3b8;">
              Target Repository: <code style="color:#60a5fa;">${CONFIG.repoOwner}/${CONFIG.repoName}</code>
            </div>
          </div>

          <div>
            <label style="font-size:11px; font-weight:600; text-transform:uppercase; color:#94a3b8; display:block; margin-bottom:4px;">Personal Access Token (PAT)</label>
            <input id="oaf-auth-token-input" type="password" placeholder="ghp_... or github_pat_..." class="oaf-input" style="height:38px;" />
            <div style="margin-top:4px; font-size:10px; color:#64748b; display:flex; justify-content:space-between;">
              <span>Requires <code>repo</code> or <code>issues:write</code> permission.</span>
              <a href="https://github.com/settings/tokens/new?scopes=repo&description=OHS+Edge+Evals+Inline+Widget" target="_blank" style="color:#60a5fa; text-decoration:underline;">Generate Token ↗</a>
            </div>
          </div>

          <div id="oaf-auth-error" style="color:#f87171; font-size:11px; display:none; padding:6px 10px; border-radius:6px; background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.2);"></div>

          <div style="display:flex; justify-content:space-between; align-items:center; pt-2;">
            <button id="oaf-auth-clear-btn" class="oaf-dock-btn" style="color:#94a3b8; display:none;">Disconnect</button>
            <div style="display:flex; gap:8px; margin-left:auto;">
              <button id="oaf-auth-cancel-btn" class="oaf-dock-btn">Cancel</button>
              <button id="oaf-auth-save-btn" class="oaf-dock-btn oaf-dock-btn-primary">
                <span>Verify &amp; Connect</span>
              </button>
            </div>
          </div>

          <!-- Pins Local Cache & GitHub Synchronization -->
          <div style="border-top:1px solid #1e293b; padding-top:10px; margin-top:8px; display:flex; justify-content:space-between; align-items:center;">
            <div style="font-size:11px; color:#94a3b8;">
              <i class="fa-solid fa-map-pin" style="color:#60a5fa;"></i> <span id="oaf-pin-cache-count">0 pins cached</span>
            </div>
            <div style="display:flex; gap:6px;">
              <button id="oaf-sync-pins-btn" class="oaf-dock-btn" style="font-size:10px; padding:3px 7px;" title="Check GitHub issue status and remove closed pins">
                <i class="fa-solid fa-rotate text-[10px]"></i> Sync GitHub
              </button>
              <button id="oaf-purge-pins-btn" class="oaf-dock-btn" style="font-size:10px; padding:3px 7px; color:#f87171;" title="Clear local pin cache">
                <i class="fa-solid fa-trash text-[10px]"></i> Clear Pins
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(root);

    initEventHandlers();
  }

  function initEventHandlers() {
    const dockAvatar = document.getElementById('oaf-dock-avatar');
    const dockUser = document.getElementById('oaf-dock-user');
    const dockRole = document.getElementById('oaf-dock-role');
    const dockPinBtn = document.getElementById('oaf-dock-pin-btn');
    const dockAuthBtn = document.getElementById('oaf-dock-auth-btn');
    const dockAuthLabel = document.getElementById('oaf-dock-auth-label');
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
    const authModal = document.getElementById('oaf-auth-modal');
    const authCloseBtn = document.getElementById('oaf-auth-close-btn');
    const authCancelBtn = document.getElementById('oaf-auth-cancel-btn');
    const authSaveBtn = document.getElementById('oaf-auth-save-btn');
    const authClearBtn = document.getElementById('oaf-auth-clear-btn');
    const authTokenInput = document.getElementById('oaf-auth-token-input');
    const authError = document.getElementById('oaf-auth-error');

    let activeCategory = 'UI Fix';

    // Category Selector
    document.querySelectorAll('#oaf-pop-cats .oaf-cat-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#oaf-pop-cats .oaf-cat-btn').forEach(b => b.classList.remove('oaf-dock-btn-primary'));
        btn.classList.add('oaf-dock-btn-primary');
        activeCategory = btn.dataset.cat;
      });
    });

    // Verify GitHub Token
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
        throw new Error(`@${userData.login} only has read access. Write access is required to create issues.`);
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

    function updateAuthUI(user) {
      if (user) {
        authUser = user;
        dockAvatar.src = user.avatar_url || 'https://github.com/ghost.png';
        dockAvatar.style.display = 'block';
        dockUser.textContent = `@${user.login}`;
        dockUser.style.display = 'inline';
        dockRole.textContent = user.role;
        dockRole.style.display = 'inline';
        dockAuthLabel.textContent = 'Connected';
        authClearBtn.style.display = 'inline-block';
        authTokenInput.value = user.token;
      } else {
        authUser = null;
        dockAvatar.style.display = 'none';
        dockUser.style.display = 'none';
        dockRole.style.display = 'none';
        dockAuthLabel.textContent = 'Connect';
        authClearBtn.style.display = 'none';
        authTokenInput.value = '';
      }
    }

    // Load auth from localStorage
    const stored = localStorage.getItem(CONFIG.storageAuthKey);
    if (stored) {
      try {
        const cached = JSON.parse(stored);
        if (cached && cached.token) {
          updateAuthUI(cached);
        }
      } catch (e) {
        localStorage.removeItem(CONFIG.storageAuthKey);
      }
    }

    // Check if URL has ?feedback=true or #login
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('feedback') || window.location.hash === '#feedback' || window.location.hash === '#login') {
      authModal.style.display = 'flex';
      authTokenInput.focus();
    }

    // Open Auth Modal
    function openAuthModal() {
      authError.style.display = 'none';
      updatePinCacheCount();
      authModal.style.display = 'flex';
      authTokenInput.focus();
    }

    dockAuthBtn.addEventListener('click', openAuthModal);
    authCloseBtn.addEventListener('click', () => { authModal.style.display = 'none'; });
    authCancelBtn.addEventListener('click', () => { authModal.style.display = 'none'; });

    // Disconnect Token
    authClearBtn.addEventListener('click', () => {
      if (confirm('Disconnect GitHub token?')) {
        localStorage.removeItem(CONFIG.storageAuthKey);
        updateAuthUI(null);
        authModal.style.display = 'none';
      }
    });

    // Save & Verify Token in Modal
    authSaveBtn.addEventListener('click', async () => {
      const token = authTokenInput.value.trim();
      if (!token) {
        authError.textContent = 'Please enter a GitHub Personal Access Token.';
        authError.style.display = 'block';
        return;
      }

      authSaveBtn.disabled = true;
      authSaveBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Checking permissions...`;
      authError.style.display = 'none';

      try {
        const verified = await verifyToken(token);
        localStorage.setItem(CONFIG.storageAuthKey, JSON.stringify(verified));
        updateAuthUI(verified);
        authModal.style.display = 'none';
      } catch (err) {
        authError.textContent = err.message;
        authError.style.display = 'block';
      } finally {
        authSaveBtn.disabled = false;
        authSaveBtn.innerHTML = `Verify &amp; Connect`;
      }
    });

    // Hotkey: Cmd+Shift+F or Ctrl+Shift+F opens auth modal; C activates comment mode
    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        openAuthModal();
      } else if (e.key.toLowerCase() === 'c' && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
        e.preventDefault();
        toggleInspectMode();
      } else if (e.key === 'Escape') {
        if (isInspectMode) stopInspectMode();
        if (inlinePopover.style.display === 'flex') inlinePopover.style.display = 'none';
        if (authModal.style.display === 'flex') authModal.style.display = 'none';
      }
    });

    // Pin Persistence
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

    // Inspect Mode
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
      const rootEl = document.getElementById('oaf-root');
      const el = document.elementFromPoint(e.clientX, e.clientY);
      if (!el || (rootEl && rootEl.contains(el)) || el.classList.contains('oaf-pin')) {
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
      const rootEl = document.getElementById('oaf-root');
      if (rootEl && rootEl.contains(e.target)) return;

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

        positionPopover(selected, null);
        popTextarea.focus();
      }
    }

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

    async function submitIssueInPage() {
      if (!activePin) return;
      const comment = popTextarea.value.trim();
      if (!comment) {
        alert('Please describe what needs to be changed.');
        popTextarea.focus();
        return;
      }

      // Check auth token
      if (!authUser || !authUser.token) {
        openAuthModal();
        return;
      }

      popSubmitBtn.disabled = true;
      popSubmitLabel.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Posting...`;

      activePin.category = activeCategory;
      activePin.comment = comment;

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
          const errJson = await res.json().catch(() => ({}));
          throw new Error(errJson.message || `GitHub API error (${res.status})`);
        }

        const issue = await res.json();
        activePin.issueNumber = issue.number;
        activePin.issueUrl = issue.html_url;

        const pins = getPins();
        pins.push(activePin);
        savePins(pins);

        createPinBadge(activePin, pins.length);

        popViewMain.style.display = 'none';
        popViewSuccess.style.display = 'flex';
        successTitle.textContent = `Issue #${issue.number} Created!`;
        successBody.textContent = `"${comment}"`;
      } catch (err) {
        alert(`Could not create issue: ${err.message}`);
      } finally {
        popSubmitBtn.disabled = false;
        popSubmitLabel.textContent = 'Create Issue';
      }
    }

    popCopyBtn.addEventListener('click', () => {
      if (!activePin) return;
      const comment = popTextarea.value.trim();
      if (!comment) {
        alert('Please enter a comment.');
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

    successDoneBtn.addEventListener('click', () => {
      inlinePopover.style.display = 'none';
    });

    dockPinBtn.addEventListener('click', toggleInspectMode);
    cancelTargetBtn.addEventListener('click', stopInspectMode);
    popCloseBtn.addEventListener('click', () => { inlinePopover.style.display = 'none'; });
    popSubmitBtn.addEventListener('click', submitIssueInPage);

    // Sync & Cache Helpers
    function updatePinCacheCount() {
      const pinCountEl = document.getElementById('oaf-pin-cache-count');
      if (pinCountEl) {
        const pins = getPins();
        pinCountEl.textContent = `${pins.length} pin${pins.length === 1 ? '' : 's'} cached`;
      }
    }

    async function syncPinsWithGitHub() {
      const pins = getPins();
      if (!pins.length) return;
      try {
        const headers = { 'Accept': 'application/vnd.github.v3+json' };
        if (authUser && authUser.token) {
          headers['Authorization'] = `Bearer ${authUser.token}`;
        }
        const res = await fetch(`https://api.github.com/repos/${CONFIG.repoOwner}/${CONFIG.repoName}/issues?state=open&per_page=100`, { headers });
        if (!res.ok) return;
        const openIssues = await res.json();
        const openNumbers = new Set(openIssues.map(i => i.number));

        // Auto-remove any pin whose GitHub issue is no longer open (closed / resolved)
        const activePins = pins.filter(p => !p.issueNumber || openNumbers.has(p.issueNumber));

        if (activePins.length !== pins.length) {
          savePins(activePins);
          loadPinsForPage();
          updatePinCacheCount();
        }
      } catch (e) {
        // Fallback silently if offline or rate limited
      }
    }

    const purgePinsBtn = document.getElementById('oaf-purge-pins-btn');
    if (purgePinsBtn) {
      purgePinsBtn.addEventListener('click', () => {
        savePins([]);
        loadPinsForPage();
        updatePinCacheCount();
      });
    }

    const syncPinsBtn = document.getElementById('oaf-sync-pins-btn');
    if (syncPinsBtn) {
      syncPinsBtn.addEventListener('click', async () => {
        syncPinsBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Syncing...`;
        await syncPinsWithGitHub();
        syncPinsBtn.innerHTML = `<i class="fa-solid fa-check" style="color:#34d399;"></i> Synced`;
        setTimeout(() => {
          syncPinsBtn.innerHTML = `<i class="fa-solid fa-rotate text-[10px]"></i> Sync GitHub`;
        }, 1500);
      });
    }

    loadPinsForPage();
    updatePinCacheCount();
    syncPinsWithGitHub();
  }

  // Safe Mount Trigger
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectWidget);
  } else {
    injectWidget();
  }
})();
