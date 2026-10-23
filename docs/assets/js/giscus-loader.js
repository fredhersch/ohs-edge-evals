/**
 * OHS Edge Evals - Giscus (GitHub Discussions Comments & Directives Widget)
 * Dynamically loads and themes Giscus on all research and documentation pages.
 */

(function () {
  // Global Giscus Configuration
  const GISCUS_CONFIG = {
    repo: 'fredhersch/ohs-edge-evals',
    repoId: 'R_kgDOVOAdWQ',
    category: 'General',
    // Paste your Discussion Category ID here once GitHub Discussions is enabled:
    // (e.g. DIC_kwDOVOAdWQ4Cm...)
    categoryId: '',
    mapping: 'pathname',
    strict: '0',
    reactionsEnabled: '1',
    emitMetadata: '0',
    inputPosition: 'top',
    lang: 'en',
    loading: 'lazy'
  };

  // Allow runtime override from localStorage or window
  if (typeof window !== 'undefined' && window.GISCUS_CATEGORY_ID) {
    GISCUS_CONFIG.categoryId = window.GISCUS_CATEGORY_ID;
  } else if (typeof localStorage !== 'undefined') {
    const savedId = localStorage.getItem('ohs_giscus_category_id');
    if (savedId) {
      GISCUS_CONFIG.categoryId = savedId;
    }
  }

  function getGiscusTheme() {
    return document.documentElement.classList.contains('light')
      ? 'light'
      : 'dark_dimmed';
  }

  function sendThemeUpdate(theme) {
    const iframe = document.querySelector('iframe.giscus-frame');
    if (iframe && iframe.contentWindow) {
      iframe.contentWindow.postMessage(
        {
          giscus: {
            setConfig: {
              theme: theme
            }
          }
        },
        'https://giscus.app'
      );
    }
  }

  function renderSetupBanner(container) {
    container.innerHTML = `
      <div class="rounded-xl border border-blue-500/30 bg-blue-950/20 p-5 space-y-4">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-sm">
              <i class="fa-solid fa-wrench"></i>
            </div>
            <div>
              <h3 class="text-sm font-bold text-white">GitHub Discussions &amp; Giscus Setup</h3>
              <p class="text-xs text-slate-300">Complete these 2 quick steps on GitHub to enable comments on this repository:</p>
            </div>
          </div>
          <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">Action Required</span>
        </div>

        <ol class="text-xs space-y-2.5 text-slate-300 list-decimal list-inside pl-1">
          <li class="leading-relaxed">
            <strong class="text-white">Enable Discussions:</strong> Open
            <a href="https://github.com/fredhersch/ohs-edge-evals/settings#features" target="_blank" class="text-blue-400 underline hover:text-blue-300">Repository Settings &rarr; Features</a>
            and check the <strong class="text-white">Discussions</strong> checkbox.
          </li>
          <li class="leading-relaxed">
            <strong class="text-white">Install Giscus App:</strong> Visit
            <a href="https://github.com/apps/giscus" target="_blank" class="text-blue-400 underline hover:text-blue-300">github.com/apps/giscus</a>,
            click <em>Install</em>, and grant access to <code class="px-1 py-0.5 rounded bg-slate-800 text-blue-200">fredhersch/ohs-edge-evals</code>.
          </li>
          <li class="leading-relaxed">
            <strong class="text-white">Connect Category:</strong> Visit
            <a href="https://giscus.app" target="_blank" class="text-blue-400 underline hover:text-blue-300">giscus.app</a>, enter <code class="px-1 py-0.5 rounded bg-slate-800 text-blue-200">fredhersch/ohs-edge-evals</code>, select a category (e.g. <em>General</em>), and paste the generated <code class="px-1 py-0.5 rounded bg-slate-800 text-blue-200">data-category-id</code> below:
          </li>
        </ol>

        <form id="giscus-setup-form" class="flex flex-col sm:flex-row gap-2 pt-1">
          <input
            type="text"
            id="giscus-cat-input"
            placeholder="e.g. DIC_kwDOVOAdWQ4Cm..."
            class="flex-1 px-3 py-2 text-xs rounded-lg bg-slate-900 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono"
            required
          />
          <button
            type="submit"
            class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition flex items-center justify-center gap-1.5 shrink-0"
          >
            <i class="fa-solid fa-link"></i>
            <span>Save &amp; Connect Widget</span>
          </button>
        </form>

        <div class="text-[11px] text-slate-400 flex items-center justify-between border-t border-slate-800/80 pt-3">
          <span>Repository ID: <code class="font-mono text-slate-300">R_kgDOVOAdWQ</code></span>
          <span class="text-slate-500">Configured in <code class="font-mono text-slate-400">assets/js/giscus-loader.js</code></span>
        </div>
      </div>
    `;

    const form = document.getElementById('giscus-setup-form');
    if (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        const val = document.getElementById('giscus-cat-input').value.trim();
        if (val) {
          localStorage.setItem('ohs_giscus_category_id', val);
          GISCUS_CONFIG.categoryId = val;
          container.innerHTML = '';
          mountGiscus(container);
        }
      });
    }
  }

  function mountGiscus(container) {
    if (!GISCUS_CONFIG.categoryId) {
      renderSetupBanner(container);
      return;
    }

    // Add a toolbar with quick links and config reset
    const toolbar = document.createElement('div');
    toolbar.className = 'flex items-center justify-between text-xs text-slate-400 mb-3 px-1';
    toolbar.innerHTML = `
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        <span class="text-[11px] text-slate-400">Connected to GitHub Discussions &bull; <span class="font-mono text-slate-300">${GISCUS_CONFIG.category}</span></span>
      </div>
      <button id="giscus-reconfigure-btn" class="text-[11px] text-slate-400 hover:text-white transition flex items-center gap-1" title="Change Discussion Category or ID">
        <i class="fa-solid fa-gear text-[10px]"></i>
        <span>Configure</span>
      </button>
    `;

    container.appendChild(toolbar);

    const reconfigBtn = toolbar.querySelector('#giscus-reconfigure-btn');
    if (reconfigBtn) {
      reconfigBtn.addEventListener('click', () => {
        if (confirm('Reconfigure Giscus Category ID?')) {
          localStorage.removeItem('ohs_giscus_category_id');
          GISCUS_CONFIG.categoryId = '';
          container.innerHTML = '';
          renderSetupBanner(container);
        }
      });
    }

    // Embed the Giscus script
    const script = document.createElement('script');
    script.src = 'https://giscus.app/client.js';
    script.setAttribute('data-repo', GISCUS_CONFIG.repo);
    script.setAttribute('data-repo-id', GISCUS_CONFIG.repoId);
    script.setAttribute('data-category', GISCUS_CONFIG.category);
    script.setAttribute('data-category-id', GISCUS_CONFIG.categoryId);
    script.setAttribute('data-mapping', GISCUS_CONFIG.mapping);
    script.setAttribute('data-strict', GISCUS_CONFIG.strict);
    script.setAttribute('data-reactions-enabled', GISCUS_CONFIG.reactionsEnabled);
    script.setAttribute('data-emit-metadata', GISCUS_CONFIG.emitMetadata);
    script.setAttribute('data-input-position', GISCUS_CONFIG.inputPosition);
    script.setAttribute('data-theme', getGiscusTheme());
    script.setAttribute('data-lang', GISCUS_CONFIG.lang);
    script.setAttribute('data-loading', GISCUS_CONFIG.loading);
    script.setAttribute('crossorigin', 'anonymous');
    script.async = true;

    container.appendChild(script);
  }

  function init() {
    const containers = document.querySelectorAll('.giscus');
    if (!containers.length) return;

    containers.forEach((el) => {
      // Don't mount multiple times
      if (el.dataset.giscusLoaded) return;
      el.dataset.giscusLoaded = 'true';
      mountGiscus(el);
    });

    // Theme observer: sync Giscus whenever theme changes on page
    const observer = new MutationObserver(() => {
      const theme = getGiscusTheme();
      sendThemeUpdate(theme);
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class']
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
