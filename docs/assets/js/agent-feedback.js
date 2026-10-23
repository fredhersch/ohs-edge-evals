/**
 * OHS Edge Evals - Floating Agent Feedback Widget
 * Allows users to inspect any UI element, write comments/directives,
 * and automatically create structured GitHub issues or agent prompts
 * with exact DOM selectors, outer HTML, text context, and page locations.
 */

(function () {
  'use strict';

  // Prevent multiple initializations
  if (window.__OHS_AGENT_FEEDBACK_LOADED__) return;
  window.__OHS_AGENT_FEEDBACK_LOADED__ = true;

  const CONFIG = {
    repoOwner: 'fredhersch',
    repoName: 'ohs-edge-evals',
    defaultLabels: ['agent-task', 'ui-feedback'],
    storageKeyToken: 'ohs_agent_feedback_gh_token',
    storageKeyDraft: 'ohs_agent_feedback_draft'
  };

  let isInspectMode = false;
  let hoveredElement = null;
  let selectedElement = null;
  let selectedData = null;

  // Determine relative file path based on current location
  function getPageLocation() {
    let path = window.location.pathname;
    if (!path || path === '/' || path.endsWith('/')) {
      path += 'index.html';
    }
    // Clean leading slashes
    path = path.replace(/^\//, '');
    return path;
  }

  // Construct a concise and reliable CSS selector for the element
  function generateCssSelector(el) {
    if (!el || el === document.body || el === document.documentElement) {
      return 'body';
    }
    if (el.id) {
      return `#${CSS.escape(el.id)}`;
    }

    const path = [];
    let curr = el;
    while (curr && curr.nodeType === Node.ELEMENT_NODE && curr !== document.body && curr !== document.documentElement) {
      let selector = curr.nodeName.toLowerCase();
      if (curr.id) {
        selector += `#${CSS.escape(curr.id)}`;
        path.unshift(selector);
        break; // IDs are unique enough root
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
      if (path.length >= 4) break; // Keep selector manageable
    }
    return path.join(' > ');
  }

  // Format outer HTML snippet nicely
  function getCleanOuterHtml(el) {
    if (!el) return '';
    const clone = el.cloneNode(true);
    // Remove widget itself if accidentally included
    clone.querySelectorAll('#ohs-agent-feedback-root').forEach(n => n.remove());
    let html = clone.outerHTML;
    if (html.length > 500) {
      // Truncate inner children if too long, keep opening tag and key text
      const tagName = el.tagName.toLowerCase();
      const openTag = el.outerHTML.match(/^<[^>]+>/)?.[0] || `<${tagName}>`;
      const textPreview = (el.innerText || '').trim().substring(0, 100);
      html = `${openTag}\n  ${textPreview}\n</${tagName}>`;
    }
    return html;
  }

  // Inject Stylesheet
  const styleEl = document.createElement('style');
  styleEl.textContent = `
    #ohs-agent-feedback-root {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      line-height: 1.4;
      color: #0f172a;
    }
    .dark #ohs-agent-feedback-root {
      color: #f8fafc;
    }

    /* Floating Launcher Pill */
    #oaf-fab {
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 999990;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 18px;
      border-radius: 9999px;
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      color: #ffffff;
      border: 1px solid rgba(255, 255, 255, 0.2);
      box-shadow: 0 8px 24px -4px rgba(37, 99, 235, 0.4), 0 4px 10px rgba(0, 0, 0, 0.15);
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      user-select: none;
    }
    #oaf-fab:hover {
      transform: translateY(-2px) scale(1.02);
      box-shadow: 0 12px 28px -4px rgba(37, 99, 235, 0.5), 0 6px 14px rgba(0, 0, 0, 0.2);
      background: linear-gradient(135deg, #3b82f6, #2563eb);
    }
    #oaf-fab:active {
      transform: translateY(0) scale(0.98);
    }
    #oaf-fab .oaf-pulse {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #34d399;
      box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.7);
      animation: oaf-pulse-anim 2s infinite;
    }
    @keyframes oaf-pulse-anim {
      0% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.7); }
      70% { box-shadow: 0 0 0 8px rgba(52, 211, 153, 0); }
      100% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0); }
    }

    /* Target Inspector Hover Box */
    #oaf-inspect-overlay {
      position: fixed;
      pointer-events: none;
      z-index: 999980;
      border: 2px solid #3b82f6;
      background: rgba(59, 130, 246, 0.15);
      border-radius: 4px;
      transition: top 0.05s ease, left 0.05s ease, width 0.05s ease, height 0.05s ease;
      display: none;
      box-shadow: 0 0 12px rgba(59, 130, 246, 0.4);
    }
    #oaf-inspect-tooltip {
      position: absolute;
      top: -26px;
      left: 0;
      background: #1e293b;
      color: #93c5fd;
      padding: 3px 7px;
      font-size: 11px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      border-radius: 4px;
      white-space: nowrap;
      pointer-events: none;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
      border: 1px solid #334155;
    }

    /* Inspector Active Banner */
    #oaf-inspect-banner {
      position: fixed;
      top: 16px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 999995;
      background: #0f172a;
      color: #ffffff;
      padding: 10px 20px;
      border-radius: 9999px;
      border: 1px solid #3b82f6;
      box-shadow: 0 10px 25px rgba(0,0,0,0.4);
      display: none;
      align-items: center;
      gap: 12px;
      font-size: 13px;
      animation: oaf-slide-down 0.25s ease-out;
    }
    @keyframes oaf-slide-down {
      from { transform: translate(-50%, -20px); opacity: 0; }
      to { transform: translate(-50%, 0); opacity: 1; }
    }

    /* Selected Persistent Box */
    #oaf-selected-overlay {
      position: absolute;
      pointer-events: none;
      z-index: 999970;
      border: 2px dashed #10b981;
      background: rgba(16, 185, 129, 0.1);
      border-radius: 4px;
      display: none;
    }

    /* Main Modal Dialog */
    #oaf-modal-card {
      position: fixed;
      bottom: 80px;
      right: 24px;
      width: 420px;
      max-width: calc(100vw - 48px);
      max-height: calc(100vh - 120px);
      z-index: 999992;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 16px;
      box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(0, 0, 0, 0.05);
      display: none;
      flex-direction: column;
      overflow: hidden;
      animation: oaf-pop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .dark #oaf-modal-card {
      background: #0f172a;
      border-color: #334155;
      box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.08);
    }
    @keyframes oaf-pop {
      from { transform: scale(0.95) translateY(10px); opacity: 0; }
      to { transform: scale(1) translateY(0); opacity: 1; }
    }

    .oaf-header {
      padding: 14px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #e2e8f0;
      background: #f8fafc;
    }
    .dark .oaf-header {
      background: #1e293b;
      border-color: #334155;
    }

    .oaf-body {
      padding: 16px 18px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
      max-height: calc(100vh - 220px);
    }

    .oaf-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    }

    .oaf-target-box {
      padding: 10px 12px;
      border-radius: 8px;
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      font-size: 12px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .dark .oaf-target-box {
      background: #172033;
      border-color: #263352;
    }

    .oaf-input, .oaf-textarea, .oaf-select {
      width: 100%;
      border-radius: 8px;
      padding: 8px 12px;
      font-size: 13px;
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: inherit;
      box-sizing: border-box;
      outline: none;
      transition: border-color 0.15s ease;
      font-family: inherit;
    }
    .dark .oaf-input, .dark .oaf-textarea, .dark .oaf-select {
      background: #090d16;
      border-color: #334155;
      color: #f8fafc;
    }
    .oaf-input:focus, .oaf-textarea:focus, .oaf-select:focus {
      border-color: #3b82f6;
      box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
    }

    .oaf-footer {
      padding: 12px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      border-top: 1px solid #e2e8f0;
      background: #f8fafc;
    }
    .dark .oaf-footer {
      background: #1e293b;
      border-color: #334155;
    }

    .oaf-btn {
      padding: 7px 14px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid transparent;
      transition: all 0.15s ease;
    }
    .oaf-btn-primary {
      background: #2563eb;
      color: #ffffff;
    }
    .oaf-btn-primary:hover {
      background: #1d4ed8;
    }
    .oaf-btn-secondary {
      background: #ffffff;
      color: #334155;
      border-color: #cbd5e1;
    }
    .dark .oaf-btn-secondary {
      background: #090d16;
      color: #cbd5e1;
      border-color: #334155;
    }
    .oaf-btn-secondary:hover {
      background: #f1f5f9;
    }
    .dark .oaf-btn-secondary:hover {
      background: #1e293b;
    }
    .oaf-btn-sm {
      padding: 4px 8px;
      font-size: 11px;
    }

    .oaf-tag-pill {
      cursor: pointer;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 11px;
      border: 1px solid #cbd5e1;
      background: #f8fafc;
      user-select: none;
    }
    .dark .oaf-tag-pill {
      background: #172033;
      border-color: #334155;
      color: #cbd5e1;
    }
    .oaf-tag-pill.active {
      background: #3b82f6;
      color: #ffffff;
      border-color: #2563eb;
    }
  `;
  document.head.appendChild(styleEl);

  // Widget DOM Skeleton
  const root = document.createElement('div');
  root.id = 'ohs-agent-feedback-root';
  root.innerHTML = `
    <!-- Floating Inspector Outline -->
    <div id="oaf-inspect-overlay">
      <div id="oaf-inspect-tooltip">&lt;tag&gt;</div>
    </div>

    <!-- Inspector Active Banner -->
    <div id="oaf-inspect-banner">
      <span style="font-size: 16px;">🎯</span>
      <span><strong>Select Element Mode:</strong> Click any UI component to target.</span>
      <button id="oaf-cancel-inspect-btn" class="oaf-btn oaf-btn-secondary oaf-btn-sm" style="color: #fff; background: #334155; border-color: #475569;">
        Cancel (Esc)
      </button>
    </div>

    <!-- Floating Action Button -->
    <div id="oaf-fab" title="Guide Agent to Fix UI / Add Comments">
      <div class="oaf-pulse"></div>
      <i class="fa-solid fa-crosshairs" style="font-size: 13px;"></i>
      <span>Agent Feedback</span>
    </div>

    <!-- Feedback Modal Card -->
    <div id="oaf-modal-card">
      <div class="oaf-header">
        <div style="display: flex; align-items: center; gap: 8px;">
          <div style="width: 24px; height: 24px; border-radius: 6px; background: rgba(59, 130, 246, 0.15); display: flex; align-items: center; justify-content: center; color: #3b82f6;">
            <i class="fa-solid fa-wand-magic-sparkles" style="font-size: 11px;"></i>
          </div>
          <div>
            <div style="font-size: 13px; font-weight: 700;">Direct AI Agent</div>
            <div style="font-size: 10px; color: #64748b;">Targeted UI comments for intelligent agents</div>
          </div>
        </div>
        <button id="oaf-close-btn" style="background:none; border:none; color:#64748b; font-size: 16px; cursor:pointer; padding: 4px;" title="Close (Esc)">✕</button>
      </div>

      <div class="oaf-body">
        <!-- Target Selection Preview -->
        <div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <label style="font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b;">Target UI Element</label>
            <button id="oaf-repick-btn" class="oaf-btn oaf-btn-secondary oaf-btn-sm">
              <i class="fa-solid fa-bullseye"></i>
              <span id="oaf-repick-label">Pick Element</span>
            </button>
          </div>
          <div id="oaf-target-summary" class="oaf-target-box">
            <div style="display:flex; align-items:center; justify-content:space-between; gap: 6px;">
              <span id="oaf-target-tag" class="oaf-badge" style="background: rgba(59,130,246,0.15); color: #3b82f6;">Whole Page</span>
              <span id="oaf-target-file" style="font-size: 11px; font-family: monospace; color: #64748b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${getPageLocation()}</span>
            </div>
            <div id="oaf-target-selector" style="font-family: monospace; font-size: 11px; color: #94a3b8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              body
            </div>
            <div id="oaf-target-text-preview" style="font-size: 11px; color: #64748b; font-style: italic; display: none;">
            </div>
          </div>
        </div>

        <!-- Issue Category Chips -->
        <div>
          <label style="font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; display: block; margin-bottom: 6px;">Category</label>
          <div id="oaf-category-chips" style="display: flex; gap: 6px; flex-wrap: wrap;">
            <span class="oaf-tag-pill active" data-cat="UI Fix">🎨 UI Fix</span>
            <span class="oaf-tag-pill" data-cat="Bug">🐛 Bug</span>
            <span class="oaf-tag-pill" data-cat="Copy/Content">✍️ Copy</span>
            <span class="oaf-tag-pill" data-cat="Feature">💡 Feature</span>
          </div>
        </div>

        <!-- Comment / Instruction Input -->
        <div>
          <label for="oaf-comment-input" style="font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; display: block; margin-bottom: 4px;">Agent Directive / Issue</label>
          <textarea id="oaf-comment-input" class="oaf-textarea" rows="3" placeholder="What should the agent change? e.g., 'Change button color to emerald and align text to left'"></textarea>
        </div>

        <!-- Optional Proposed Fix or Note -->
        <div>
          <label for="oaf-solution-input" style="font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; display: block; margin-bottom: 4px;">Proposed Solution (Optional)</label>
          <input id="oaf-solution-input" class="oaf-input" placeholder="e.g. Use class 'bg-emerald-600 hover:bg-emerald-500'"></input>
        </div>
      </div>

      <div class="oaf-footer">
        <button id="oaf-copy-agent-btn" class="oaf-btn oaf-btn-secondary" title="Copy markdown task to clipboard for immediate paste into chat">
          <i class="fa-regular fa-clipboard"></i>
          <span>Copy for Agent</span>
        </button>
        <button id="oaf-create-issue-btn" class="oaf-btn oaf-btn-primary" title="Create GitHub Issue on fredhersch/ohs-edge-evals">
          <i class="fa-brands fa-github"></i>
          <span>Create Issue ↗</span>
        </button>
      </div>
    </div>
  `;
  document.body.appendChild(root);

  // Cache elements
  const fab = document.getElementById('oaf-fab');
  const modalCard = document.getElementById('oaf-modal-card');
  const closeBtn = document.getElementById('oaf-close-btn');
  const inspectOverlay = document.getElementById('oaf-inspect-overlay');
  const inspectTooltip = document.getElementById('oaf-inspect-tooltip');
  const inspectBanner = document.getElementById('oaf-inspect-banner');
  const cancelInspectBtn = document.getElementById('oaf-cancel-inspect-btn');
  const repickBtn = document.getElementById('oaf-repick-btn');
  const repickLabel = document.getElementById('oaf-repick-label');
  const commentInput = document.getElementById('oaf-comment-input');
  const solutionInput = document.getElementById('oaf-solution-input');
  const targetTag = document.getElementById('oaf-target-tag');
  const targetFile = document.getElementById('oaf-target-file');
  const targetSelector = document.getElementById('oaf-target-selector');
  const targetTextPreview = document.getElementById('oaf-target-text-preview');
  const copyAgentBtn = document.getElementById('oaf-copy-agent-btn');
  const createIssueBtn = document.getElementById('oaf-create-issue-btn');
  const categoryChips = document.querySelectorAll('#oaf-category-chips .oaf-tag-pill');

  let activeCategory = 'UI Fix';

  // Category chip toggle
  categoryChips.forEach(chip => {
    chip.addEventListener('click', () => {
      categoryChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeCategory = chip.dataset.cat || 'UI Fix';
    });
  });

  // Start Inspect Mode
  function startInspector() {
    isInspectMode = true;
    modalCard.style.display = 'none';
    inspectBanner.style.display = 'flex';
    document.body.style.cursor = 'crosshair';

    window.addEventListener('mousemove', handleMouseMove, true);
    window.addEventListener('click', handleElementClick, true);
    window.addEventListener('keydown', handleKeyDown, true);
  }

  // Stop Inspect Mode
  function stopInspector(keepModalClosed = false) {
    isInspectMode = false;
    inspectOverlay.style.display = 'none';
    inspectBanner.style.display = 'none';
    document.body.style.cursor = '';

    window.removeEventListener('mousemove', handleMouseMove, true);
    window.removeEventListener('click', handleElementClick, true);
    window.removeEventListener('keydown', handleKeyDown, true);

    if (!keepModalClosed) {
      modalCard.style.display = 'flex';
    }
  }

  function handleMouseMove(e) {
    if (!isInspectMode) return;

    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (!el || root.contains(el)) {
      inspectOverlay.style.display = 'none';
      return;
    }

    hoveredElement = el;
    const rect = el.getBoundingClientRect();

    inspectOverlay.style.display = 'block';
    inspectOverlay.style.top = `${rect.top}px`;
    inspectOverlay.style.left = `${rect.left}px`;
    inspectOverlay.style.width = `${rect.width}px`;
    inspectOverlay.style.height = `${rect.height}px`;

    const tag = el.tagName.toLowerCase();
    const id = el.id ? `#${el.id}` : '';
    const firstClass = el.classList.length ? `.${el.classList[0]}` : '';
    inspectTooltip.textContent = `<${tag}${id || firstClass}>`;
  }

  function handleElementClick(e) {
    if (!isInspectMode) return;

    // Ignore clicks on banner itself
    if (root.contains(e.target)) return;

    e.preventDefault();
    e.stopPropagation();

    if (hoveredElement) {
      selectedElement = hoveredElement;
      const selector = generateCssSelector(selectedElement);
      const outerHtml = getCleanOuterHtml(selectedElement);
      const innerText = (selectedElement.innerText || '').trim().replace(/\s+/g, ' ').substring(0, 160);

      selectedData = {
        tagName: selectedElement.tagName.toLowerCase(),
        selector: selector,
        outerHtml: outerHtml,
        innerText: innerText,
        page: getPageLocation(),
        url: window.location.href,
        viewport: `${window.innerWidth}x${window.innerHeight}`
      };

      // Update Modal Target Info
      targetTag.textContent = `<${selectedData.tagName}>`;
      targetSelector.textContent = selector;
      targetFile.textContent = selectedData.page;
      repickLabel.textContent = 'Change Target';

      if (innerText) {
        targetTextPreview.textContent = `"${innerText}"`;
        targetTextPreview.style.display = 'block';
      } else {
        targetTextPreview.style.display = 'none';
      }
    }

    stopInspector(false);
    commentInput.focus();
  }

  function handleKeyDown(e) {
    if (e.key === 'Escape') {
      if (isInspectMode) {
        stopInspector(false);
      } else if (modalCard.style.display === 'flex') {
        modalCard.style.display = 'none';
      }
    }
  }

  // Construct structured Markdown for the AI Agent
  function buildAgentInstruction(directive, solution) {
    const page = selectedData ? selectedData.page : getPageLocation();
    const selector = selectedData ? selectedData.selector : 'N/A';
    const outerHtml = selectedData ? selectedData.outerHtml : '<!-- Target: Full Page -->';
    const innerText = selectedData && selectedData.innerText ? selectedData.innerText : 'N/A';
    const viewport = `${window.innerWidth}x${window.innerHeight}`;

    return [
      `### 🎯 UI Directive for Agent`,
      `**Category**: \`${activeCategory}\` | **Page**: [\`${page}\`](file:///${page})`,
      ``,
      `#### 💬 User Instruction`,
      `> ${directive}`,
      solution ? `\n**Suggested Fix / Code**:\n\`\`\`\n${solution}\n\`\`\`\n` : ``,
      `---`,
      `#### 📍 Element Grounding (Zero Ambiguity)`,
      `- **Target Page / File**: \`${page}\``,
      `- **CSS Selector**: \`${selector}\``,
      `- **Element Text**: \`${innerText}\``,
      `- **Viewport**: \`${viewport}\``,
      ``,
      `\`\`\`html`,
      outerHtml,
      `\`\`\``,
      ``,
      `> 🤖 **Agent Guidance**: Locate this element in \`${page}\` using the text, class, or selector above and apply the requested changes cleanly.`
    ].join('\n');
  }

  // Copy structured prompt for AI coding assistant
  function copyPromptForAgent() {
    const directive = commentInput.value.trim();
    if (!directive) {
      alert('Please enter an instruction or description of what needs fixing.');
      commentInput.focus();
      return;
    }

    const solution = solutionInput.value.trim();
    const markdown = buildAgentInstruction(directive, solution);

    navigator.clipboard.writeText(markdown).then(() => {
      const originalText = copyAgentBtn.innerHTML;
      copyAgentBtn.innerHTML = `<i class="fa-solid fa-check text-emerald-400"></i><span>Copied!</span>`;
      setTimeout(() => {
        copyAgentBtn.innerHTML = originalText;
      }, 2000);
    }).catch(err => {
      alert('Failed to copy to clipboard: ' + err);
    });
  }

  // Create GitHub Issue with pre-filled Markdown
  function createGitHubIssue() {
    const directive = commentInput.value.trim();
    if (!directive) {
      alert('Please enter an instruction or description of what needs fixing.');
      commentInput.focus();
      return;
    }

    const solution = solutionInput.value.trim();
    const page = selectedData ? selectedData.page : getPageLocation();
    const tagPrefix = selectedData ? `<${selectedData.tagName}> ` : '';
    const title = `[${activeCategory}] ${page}: ${tagPrefix}${directive.substring(0, 50)}`;
    const body = buildAgentInstruction(directive, solution);
    const labels = [
      ...CONFIG.defaultLabels,
      activeCategory.toLowerCase().replace(/[^a-z0-9]/g, '-')
    ];

    const issueUrl = `https://github.com/${CONFIG.repoOwner}/${CONFIG.repoName}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}&labels=${encodeURIComponent(labels.join(','))}`;

    window.open(issueUrl, '_blank');
    modalCard.style.display = 'none';
    commentInput.value = '';
    solutionInput.value = '';
  }

  // Event Listeners
  fab.addEventListener('click', () => {
    if (modalCard.style.display === 'flex') {
      modalCard.style.display = 'none';
    } else {
      modalCard.style.display = 'flex';
      targetFile.textContent = getPageLocation();
      commentInput.focus();
    }
  });

  closeBtn.addEventListener('click', () => {
    modalCard.style.display = 'none';
  });

  cancelInspectBtn.addEventListener('click', () => {
    stopInspector(false);
  });

  repickBtn.addEventListener('click', () => {
    startInspector();
  });

  copyAgentBtn.addEventListener('click', copyPromptForAgent);
  createIssueBtn.addEventListener('click', createGitHubIssue);

  // Shortcut: Cmd+Enter or Ctrl+Enter submits
  commentInput.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      createGitHubIssue();
    }
  });

  console.log('[OHS Edge Evals] Agent Feedback Widget initialized.');
})();
