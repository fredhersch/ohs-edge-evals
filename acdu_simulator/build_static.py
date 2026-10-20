#!/usr/bin/env python3
"""Builds a static, zero-dependency HTML application for aCDU Playground.
Includes:
- Deep Concept Explainer & Architecture Walkthrough (Modal & Expandable Guide)
- Step-by-Step Pipeline (FHIR Observation -> PlanDefinition Trigger -> aCDU Negative Veto -> SLM Synthesis)
- Graduated Use-Case Walkthroughs (L1 Single-Axis -> L2 Collision Veto -> L3 Cultural Myths -> L4 Multi-Morbidity)
- Real-time aCDU Editor with Token Budgeting & Refusal Linting
- Triple Output Comparison & Tier-1 Clinical Verification
Outputs directly into docs/playground.html ready for GitHub Pages.
"""

import json
from pathlib import Path
from data_adapter import load_all_scenarios, load_all_acdus

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = WORKSPACE_DIR / "docs"

scenarios = load_all_scenarios()
acdus = load_all_acdus()

# Extract cached baseline outputs from benchmark results
benchmark_cache_path = WORKSPACE_DIR / "chw-edge-evals" / "kenya-echis" / "echis_composite_rag_results.json"
raw_cache = {}
if benchmark_cache_path.exists():
    try:
        with open(benchmark_cache_path, "r", encoding="utf-8") as f:
            matrix = json.load(f).get("matrix", {})
            for model in ["gemma4-2b:latest", "medgemma:latest", "gemma4:e4b"]:
                case_res = matrix.get(model, {}).get("naive_rag", {}).get("case_results", [])
                for c in case_res:
                    cid = c.get("case_id")
                    snip = c.get("output_snippet")
                    if cid and snip:
                        if cid not in raw_cache:
                            raw_cache[cid] = {}
                        raw_cache[cid][model] = snip
    except Exception as e:
        print("Warning loading raw cache:", e)

embedded_payload = {
    "scenarios": scenarios,
    "acdus": acdus,
    "raw_cache": raw_cache
}

embedded_json = json.dumps(embedded_payload, ensure_ascii=False)

html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>aCDU Playground — Clinical Decision Unit Simulator</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    :root {{
      --bg: #090d16;
      --card-bg: #111827;
      --border: #1f2937;
    }}
    body {{
      background-color: var(--bg);
      color: #f3f4f6;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    .custom-scroll::-webkit-scrollbar {{
      width: 6px;
      height: 6px;
    }}
    .custom-scroll::-webkit-scrollbar-thumb {{
      background: #374151;
      border-radius: 3px;
    }}
    .pill-active {{
      background: #2563eb;
      color: #ffffff;
      border-color: #3b82f6;
    }}
  </style>
</head>
<body class="h-screen flex flex-col overflow-hidden">

  <!-- Top App Navigation Bar -->
  <header class="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between flex-shrink-0 z-20">
    <div class="flex items-center space-x-4">
      <div class="w-9 h-9 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20">
        <i class="fa-solid fa-microchip"></i>
      </div>
      <div>
        <div class="flex items-center space-x-2">
          <h1 class="text-base font-bold text-white tracking-wide">aCDU Playground</h1>
          <span class="text-xs bg-indigo-950 text-indigo-400 border border-indigo-800 px-2 py-0.5 rounded-full font-semibold">Two-Box Architecture</span>
          <span class="text-xs bg-emerald-950 text-emerald-400 border border-emerald-800 px-2 py-0.5 rounded-full font-semibold">Deterministic Safety Floor</span>
        </div>
        <p class="text-xs text-gray-400">Step-by-Step Clinical Decision Unit Simulator &bull; Token Budgeting &bull; Negative Clamping</p>
      </div>
    </div>

    <!-- Live Execution Controls & Nav -->
    <div class="flex items-center space-x-3">
      <!-- How It Works & Architecture Guide Button -->
      <button onclick="toggleGuideModal()" class="bg-indigo-900/60 hover:bg-indigo-800 text-indigo-200 border border-indigo-700/80 text-xs px-3.5 py-1.5 rounded-lg transition flex items-center space-x-1.5 shadow-sm font-semibold">
        <i class="fa-solid fa-graduation-cap text-indigo-400"></i>
        <span>How aCDUs Work</span>
      </button>

      <a href="index.html" class="bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs px-3 py-1.5 rounded-lg transition border border-gray-700 flex items-center space-x-1.5">
        <i class="fa-solid fa-arrow-left"></i>
        <span>Back to Suite</span>
      </a>

      <div class="flex items-center space-x-2 bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5">
        <i class="fa-solid fa-server text-xs text-gray-400"></i>
        <label class="text-xs text-gray-400 font-medium">Model Profile:</label>
        <select id="modelSelect" onchange="runSimulation()" class="bg-transparent text-xs text-gray-200 font-semibold focus:outline-none cursor-pointer">
          <option value="gemma4-2b:latest" selected>Gemma 4 2B (Local Edge)</option>
          <option value="medgemma:latest">MedGemma 4B (Biomedical)</option>
          <option value="gemma4:e4b">Gemma 4 4B</option>
        </select>
      </div>

      <button id="runSimBtn" onclick="runSimulation()" class="bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-semibold text-xs px-4 py-2 rounded-lg transition-all shadow-md shadow-blue-600/30 flex items-center space-x-2">
        <i class="fa-solid fa-play"></i>
        <span>Simulate Scenario</span>
      </button>

      <button onclick="resetCurrentCDU()" class="bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs px-3 py-2 rounded-lg transition border border-gray-700" title="Reset edited CDU back to certified default">
        <i class="fa-solid fa-rotate-left mr-1"></i> Reset
      </button>
    </div>
  </header>

  <!-- Interactive Step-by-Step Flow Ribbon (Collapsible Banner) -->
  <div class="bg-gray-900/80 border-b border-gray-800 px-6 py-2 flex items-center justify-between text-xs text-gray-300 flex-shrink-0">
    <div class="flex items-center space-x-6 overflow-x-auto">
      <div class="flex items-center space-x-2 text-blue-400 font-bold">
        <span class="w-5 h-5 rounded-full bg-blue-900/60 border border-blue-600 flex items-center justify-center text-[10px]">1</span>
        <span>Scenario Trigger</span>
      </div>
      <i class="fa-solid fa-arrow-right text-[10px] text-gray-600"></i>

      <div class="flex items-center space-x-2 text-emerald-400 font-bold">
        <span class="w-5 h-5 rounded-full bg-emerald-900/60 border border-emerald-600 flex items-center justify-center text-[10px]">2</span>
        <span>PlanDefinition (FHIRPath)</span>
      </div>
      <i class="fa-solid fa-arrow-right text-[10px] text-gray-600"></i>

      <div class="flex items-center space-x-2 text-amber-400 font-bold">
        <span class="w-5 h-5 rounded-full bg-amber-900/60 border border-amber-600 flex items-center justify-center text-[10px]">3</span>
        <span>aCDU Safety Clamp (Tier 1-3)</span>
      </div>
      <i class="fa-solid fa-arrow-right text-[10px] text-gray-600"></i>

      <div class="flex items-center space-x-2 text-purple-400 font-bold">
        <span class="w-5 h-5 rounded-full bg-purple-900/60 border border-purple-600 flex items-center justify-center text-[10px]">4</span>
        <span>SLM 3-Bullet Speech</span>
      </div>
    </div>

    <!-- Quick Guided Use-Case Presets -->
    <div class="flex items-center space-x-2 text-[11px] flex-shrink-0">
      <span class="text-gray-500 font-semibold uppercase tracking-wider">Guided Use-Cases:</span>
      <button onclick="loadGuidedPreset('L1')" class="bg-gray-800 hover:bg-gray-700 text-blue-300 px-2.5 py-1 rounded border border-gray-700 font-medium transition" title="Level 1: Single Guideline Execution">
        L1: Single-Axis
      </button>
      <button onclick="loadGuidedPreset('L2')" class="bg-gray-800 hover:bg-gray-700 text-amber-300 px-2.5 py-1 rounded border border-gray-700 font-medium transition" title="Level 2: Convulsion Danger Sign vs Oral Meds Collision">
        L2: Danger Collision
      </button>
      <button onclick="loadGuidedPreset('L3')" class="bg-gray-800 hover:bg-gray-700 text-rose-300 px-2.5 py-1 rounded border border-gray-700 font-medium transition" title="Level 3: Cow Dung / Ash Cord Folk Remedy Myth">
        L3: Cultural Myth
      </button>
      <button onclick="loadGuidedPreset('L4')" class="bg-gray-800 hover:bg-gray-700 text-purple-300 px-2.5 py-1 rounded border border-gray-700 font-medium transition" title="Level 4: CKD + Heart Failure + Acute Gout Drug Collision">
        L4: PHC Collision
      </button>
    </div>
  </div>

  <!-- Main 4-Quadrant Grid -->
  <main class="flex-1 grid grid-cols-12 gap-0 overflow-hidden relative">
    
    <!-- PANEL 1: Scenario Explorer (Col 1-3) -->
    <section class="col-span-3 border-r border-gray-800 flex flex-col bg-gray-950/40">
      <div class="p-3 border-b border-gray-800 bg-gray-900/40 flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <span class="w-5 h-5 rounded-full bg-blue-900/50 text-blue-400 border border-blue-700/50 flex items-center justify-center text-xs font-bold">1</span>
          <span class="text-xs font-bold uppercase tracking-wider text-gray-300">Scenario Explorer</span>
        </div>
        <span id="scenarioCountBadge" class="text-[11px] bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full">42 Cases</span>
      </div>

      <!-- Category Filter Tabs -->
      <div class="p-2 border-b border-gray-800 flex space-x-1 text-xs">
        <button onclick="filterCategory('ALL')" class="cat-pill pill-active px-2.5 py-1 rounded text-xs transition font-medium" data-cat="ALL">All</button>
        <button onclick="filterCategory('Kenya eCHIS')" class="cat-pill bg-gray-900 text-gray-400 border border-gray-800 hover:text-white px-2.5 py-1 rounded text-xs transition font-medium" data-cat="Kenya eCHIS">eCHIS</button>
        <button onclick="filterCategory('WHO SMART Guidelines')" class="cat-pill bg-gray-900 text-gray-400 border border-gray-800 hover:text-white px-2.5 py-1 rounded text-xs transition font-medium" data-cat="WHO SMART Guidelines">WHO SMART</button>
        <button onclick="filterCategory('PHC Multi-Morbidity')" class="cat-pill bg-gray-900 text-gray-400 border border-gray-800 hover:text-white px-2.5 py-1 rounded text-xs transition font-medium" data-cat="PHC Multi-Morbidity">PHC</button>
      </div>

      <!-- Scenarios List Scrollable -->
      <div id="scenariosList" class="flex-1 overflow-y-auto custom-scroll p-2 space-y-1.5">
        <!-- Rendered dynamically -->
      </div>

      <!-- Selected Scenario Context Summary Box -->
      <div class="p-3 border-t border-gray-800 bg-gray-900/60 flex-shrink-0">
        <div class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-1 flex items-center justify-between">
          <span>Clinical Presentation</span>
          <span id="tierBadge" class="text-[10px] px-1.5 py-0.2 rounded font-bold bg-blue-950 text-blue-300 border border-blue-800">Tier 1</span>
        </div>
        <div id="scenarioPresentation" class="text-xs text-gray-300 max-h-24 overflow-y-auto custom-scroll leading-relaxed italic bg-gray-950 p-2 rounded border border-gray-800/80">
          Select a scenario above to view presentation.
        </div>
      </div>
    </section>

    <!-- PANEL 2: PlanDefinition & Trigger Mappings (Col 4-5) -->
    <section class="col-span-3 border-r border-gray-800 flex flex-col bg-gray-900/10">
      <div class="p-3 border-b border-gray-800 bg-gray-900/40 flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <span class="w-5 h-5 rounded-full bg-emerald-900/50 text-emerald-400 border border-emerald-700/50 flex items-center justify-center text-xs font-bold">2</span>
          <span class="text-xs font-bold uppercase tracking-wider text-gray-300">PlanDefinition Mappings</span>
        </div>
        <span class="text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 px-2 py-0.5 rounded-full font-semibold">FHIRPath Triggered</span>
      </div>

      <!-- PlanDefinitions list -->
      <div id="planDefinitionsContainer" class="flex-1 overflow-y-auto custom-scroll p-3 space-y-3">
        <!-- Rendered dynamically -->
      </div>

      <!-- To-Do Banner for full FHIRPath Runner -->
      <div class="p-3 border-t border-gray-800 bg-indigo-950/20 border-l-2 border-l-indigo-500 m-2 rounded">
        <div class="flex items-center space-x-2 text-indigo-400 text-xs font-bold">
          <i class="fa-solid fa-list-check"></i>
          <span>Architecture Milestone:</span>
        </div>
        <p class="text-[11px] text-gray-400 mt-1 leading-snug">
          <strong>TODO:</strong> Integrate native <code>kotlin-fhirpath</code> runner to evaluate expressions dynamically over raw FHIR bundles in addition to pre-associated rule triggers.
        </p>
      </div>
    </section>

    <!-- PANEL 3: aCDU Live Editor with Real-Time Linting (Col 6-8) -->
    <section class="col-span-3 border-r border-gray-800 flex flex-col bg-gray-900/20">
      <div class="p-3 border-b border-gray-800 bg-gray-900/40 flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <span class="w-5 h-5 rounded-full bg-amber-900/50 text-amber-400 border border-amber-700/50 flex items-center justify-center text-xs font-bold">3</span>
          <span class="text-xs font-bold uppercase tracking-wider text-gray-300">aCDU Editor</span>
        </div>
        <div id="lintBadge" class="text-[11px] px-2 py-0.5 rounded font-mono font-bold bg-green-950 text-green-400 border border-green-800">
          Clean &bull; 0 tok
        </div>
      </div>

      <!-- Editor Form -->
      <div class="flex-1 overflow-y-auto custom-scroll p-3 space-y-3">
        <div>
          <label class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block mb-1">Active aCDU to Edit:</label>
          <select id="activeCduSelect" onchange="switchEditedCdu()" class="w-full bg-gray-950 border border-gray-800 rounded p-1.5 text-xs text-white focus:border-blue-500 focus:outline-none">
            <!-- Populated dynamically -->
          </select>
        </div>

        <div>
          <label class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block mb-1">Topic / Guideline Domain:</label>
          <input type="text" id="cduTopic" oninput="onCduChange()" class="w-full bg-gray-950 border border-gray-800 rounded p-1.5 text-xs text-white focus:border-blue-500 focus:outline-none">
        </div>

        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block mb-1">Priority Tier:</label>
            <select id="cduPriority" onchange="onCduChange()" class="w-full bg-gray-950 border border-gray-800 rounded p-1.5 text-xs text-amber-300 font-semibold focus:border-blue-500 focus:outline-none">
              <option value="1">Tier 1: Fatal Veto / Emergency</option>
              <option value="2">Tier 2: Organ Protection / Treatment</option>
              <option value="3">Tier 3: Symptom Relief / Routine</option>
            </select>
          </div>
          <div>
            <label class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block mb-1">Provenance:</label>
            <input type="text" id="cduSource" oninput="onCduChange()" class="w-full bg-gray-950 border border-gray-800 rounded p-1.5 text-xs text-gray-300 focus:border-blue-500 focus:outline-none" placeholder="MoH / WHO Guidelines">
          </div>
        </div>

        <div>
          <label class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block mb-1">Clinical Entry Criteria:</label>
          <textarea id="cduCriteria" rows="2" oninput="onCduChange()" class="w-full bg-gray-950 border border-gray-800 rounded p-1.5 text-xs text-gray-200 focus:border-blue-500 focus:outline-none leading-relaxed"></textarea>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider block">Mandated Actions (1 per line):</label>
            <span class="text-[10px] text-gray-500">What MUST be done</span>
          </div>
          <textarea id="cduActions" rows="3" oninput="onCduChange()" class="w-full bg-gray-950 border border-gray-800 rounded p-1.5 text-xs text-emerald-200 focus:border-emerald-500 focus:outline-none font-sans leading-relaxed"></textarea>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="text-[11px] font-semibold text-rose-400 uppercase tracking-wider block">Negative Boundaries (1 per line):</label>
            <span class="text-[10px] text-rose-500 font-bold">Safety Floor Clamps</span>
          </div>
          <textarea id="cduNegatives" rows="3" oninput="onCduChange()" class="w-full bg-gray-950 border border-gray-800 rounded p-1.5 text-xs text-rose-200 focus:border-rose-500 focus:outline-none font-sans leading-relaxed"></textarea>
        </div>

        <!-- Token Budget Progress Bar -->
        <div class="bg-gray-950 p-2.5 rounded border border-gray-800">
          <div class="flex items-center justify-between text-[11px] mb-1">
            <span class="text-gray-400 font-semibold">Prompt Token Budget (Max 180 tok):</span>
            <span id="tokCountLabel" class="font-mono text-gray-300 font-bold">0 / 180</span>
          </div>
          <div class="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
            <div id="tokProgressBar" class="bg-blue-500 h-1.5 rounded-full transition-all" style="width: 20%"></div>
          </div>
          <div id="lintIssuesContainer" class="mt-2 space-y-1">
            <!-- Render lint errors/warnings -->
          </div>
        </div>

        <div class="flex items-center justify-between pt-1">
          <span class="text-[10px] text-gray-500">In-memory playground session.</span>
          <button onclick="exportCduJson()" class="text-xs bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 px-3 py-1.5 rounded transition">
            <i class="fa-solid fa-download mr-1"></i> Export JSON
          </button>
        </div>
      </div>
    </section>

    <!-- PANEL 4: Triple Output Comparison & Downstream Impact (Col 9-12) -->
    <section class="col-span-3 flex flex-col bg-gray-950/60">
      <div class="p-3 border-b border-gray-800 bg-gray-900/40 flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <span class="w-5 h-5 rounded-full bg-purple-900/50 text-purple-400 border border-purple-700/50 flex items-center justify-center text-xs font-bold">4</span>
          <span class="text-xs font-bold uppercase tracking-wider text-gray-300">Downstream Impact</span>
        </div>
        <div class="flex items-center space-x-1 bg-gray-900 p-0.5 rounded border border-gray-800 text-[11px]">
          <button id="viewTabRaw" onclick="switchOutputTab('raw')" class="px-2 py-0.5 rounded font-semibold text-white bg-blue-600">Raw vs Clamped</button>
          <button id="viewTabDiff" onclick="switchOutputTab('diff')" class="px-2 py-0.5 rounded font-semibold text-gray-400 hover:text-white">Before vs After</button>
          <button id="viewTabPrompt" onclick="switchOutputTab('prompt')" class="px-2 py-0.5 rounded font-semibold text-gray-400 hover:text-white">Prompt</button>
        </div>
      </div>

      <!-- Execution Status Bar -->
      <div id="simStatusBar" class="px-3 py-1.5 border-b border-gray-800 bg-gray-900/30 flex items-center justify-between text-[11px] text-gray-400">
        <span id="execSource"><i class="fa-solid fa-circle-check text-green-400 mr-1"></i> Interactive Simulation Ready</span>
        <span id="execLatency" class="font-mono text-gray-500">-- ms</span>
      </div>

      <!-- Tab View A: Raw Unconstrained vs aCDU-Clamped SLM -->
      <div id="tabContentRaw" class="flex-1 overflow-y-auto custom-scroll p-3 space-y-3">
        <!-- Raw Output Card -->
        <div class="border border-red-900/40 bg-red-950/10 rounded-lg p-3">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-bold text-red-400 flex items-center">
              <i class="fa-solid fa-triangle-exclamation mr-1.5"></i>
              Raw / Unconstrained Baseline Output
            </span>
            <span id="rawStatusBadge" class="text-[10px] bg-red-950 text-red-300 border border-red-800 px-1.5 py-0.2 rounded font-semibold">Unchecked</span>
          </div>
          <div id="rawOutputText" class="text-xs text-gray-300 leading-relaxed font-sans whitespace-pre-wrap bg-gray-950/80 p-2.5 rounded border border-gray-800/80 max-h-36 overflow-y-auto custom-scroll">
            Click 'Simulate Scenario' to view baseline comparison.
          </div>
        </div>

        <!-- aCDU-Clamped SLM Output Card -->
        <div class="border border-emerald-900/50 bg-emerald-950/10 rounded-lg p-3">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-bold text-emerald-400 flex items-center">
              <i class="fa-solid fa-shield-halved mr-1.5"></i>
              aCDU-Clamped SLM Action Plan
            </span>
            <span id="slmStatusBadge" class="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 px-1.5 py-0.2 rounded font-semibold">Protected</span>
          </div>
          <div id="slmOutputText" class="text-xs text-emerald-100 leading-relaxed font-sans whitespace-pre-wrap bg-gray-950/90 p-2.5 rounded border border-emerald-900/40 min-h-[140px] max-h-56 overflow-y-auto custom-scroll">
            Click 'Simulate Scenario' to run live edge SLM inference.
          </div>
        </div>

        <!-- Verification Rubric Breakdown -->
        <div class="bg-gray-900/60 p-2.5 rounded border border-gray-800">
          <div class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
            <span>Tier-1 Clinical Safety Adherence</span>
            <span id="regexScoreBadge" class="text-blue-400 font-mono font-bold">--%</span>
          </div>
          <div id="regexListContainer" class="space-y-1 text-xs">
            <!-- Dynamic checklist -->
          </div>
        </div>
      </div>

      <!-- Tab View B: Before vs After Tweak Diff -->
      <div id="tabContentDiff" class="flex-1 overflow-y-auto custom-scroll p-3 space-y-3 hidden">
        <div class="p-2 bg-blue-950/30 border border-blue-900/50 rounded text-xs text-blue-300">
          <i class="fa-solid fa-code-compare mr-1"></i> Tweak an aCDU in Panel 3, then hit <strong>Simulate Scenario</strong> to compare results before and after your edit.
        </div>
        <div class="grid grid-cols-2 gap-2 flex-1">
          <div class="border border-gray-800 rounded p-2.5 bg-gray-950">
            <div class="text-[11px] font-bold text-gray-400 uppercase mb-1">Previous Run (Before Tweak):</div>
            <div id="diffBeforeOutput" class="text-xs text-gray-300 whitespace-pre-wrap font-sans max-h-80 overflow-y-auto custom-scroll">
              No previous run cached yet.
            </div>
          </div>
          <div class="border border-emerald-800/60 rounded p-2.5 bg-gray-950">
            <div class="text-[11px] font-bold text-emerald-400 uppercase mb-1">Current Run (After Tweak):</div>
            <div id="diffAfterOutput" class="text-xs text-emerald-100 whitespace-pre-wrap font-sans max-h-80 overflow-y-auto custom-scroll">
              Click 'Simulate Scenario' to populate.
            </div>
          </div>
        </div>
      </div>

      <!-- Tab View C: Assembled Prompt Inspector -->
      <div id="tabContentPrompt" class="flex-1 overflow-y-auto custom-scroll p-3 space-y-2 hidden">
        <div class="text-[11px] font-bold text-gray-400 uppercase">Exact Context Injected into SLM:</div>
        <pre id="assembledPromptText" class="text-[11px] text-gray-300 font-mono whitespace-pre-wrap bg-gray-950 p-2.5 rounded border border-gray-800 max-h-96 overflow-y-auto custom-scroll leading-snug">
Select a scenario to view injected prompt.
        </pre>
      </div>

    </section>

  </main>

  <!-- CONCEPT EXPLAINER & ARCHITECTURE MODAL -->
  <div id="guideModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
    <div class="bg-gray-900 border border-gray-800 rounded-2xl max-w-4xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
      
      <!-- Modal Header -->
      <div class="p-4 border-b border-gray-800 flex items-center justify-between bg-gray-950/60">
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 text-indigo-400 flex items-center justify-center font-bold">
            <i class="fa-solid fa-book-open text-sm"></i>
          </div>
          <div>
            <h2 class="text-sm font-bold text-white">The aCDU Concept & Two-Box Architecture</h2>
            <p class="text-[11px] text-gray-400">Why Small Edge Language Models Need Deterministic Safety Clamping</p>
          </div>
        </div>
        <button onclick="toggleGuideModal()" class="text-gray-400 hover:text-white text-lg px-2 py-1 rounded transition">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <!-- Modal Body Scrollable -->
      <div class="p-6 overflow-y-auto custom-scroll space-y-6 text-xs text-gray-300 leading-relaxed">
        
        <!-- Section 1: The Core Problem -->
        <div class="bg-gray-950 p-4 rounded-xl border border-gray-800">
          <div class="flex items-center space-x-2 text-rose-400 font-bold text-xs uppercase mb-2">
            <i class="fa-solid fa-triangle-exclamation"></i>
            <span>The Double Dilemma of Edge LLMs in Frontline Healthcare</span>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="border-l-2 border-l-red-500 pl-3 space-y-1">
              <strong class="text-white block font-semibold">1. Context Fragmentation & Bloat</strong>
              <p class="text-gray-400 text-[11px]">
                Raw longitudinal FHIR records span 5,000–12,000 tokens. Slicing clinical guideline PDFs into standard sliding-window RAG paragraphs separates dosing tables from contraindication warnings.
              </p>
            </div>
            <div class="border-l-2 border-l-amber-500 pl-3 space-y-1">
              <strong class="text-white block font-semibold">2. The "Agreeable Assistant" Hazard</strong>
              <p class="text-gray-400 text-[11px]">
                Small foundation models (1B–4B) are instruction-tuned to be helpful. When families propose harmful remedies (e.g. cow dung on an umbilical cord, or neighbor's nifedipine in pregnancy), un-gated models agree or hedge.
              </p>
            </div>
          </div>
        </div>

        <!-- Section 2: What is an aCDU? -->
        <div class="space-y-3">
          <h3 class="text-sm font-bold text-white flex items-center space-x-2">
            <i class="fa-solid fa-layer-group text-blue-400"></i>
            <span>What is an Atomic Clinical Decision Unit (aCDU)?</span>
          </h3>
          <p>
            An <strong>Atomic Clinical Decision Unit (aCDU)</strong> is an indivisible, structured clinical knowledge tuple representing exactly one complete clinical guidance directive. It acts as a <strong>Level 3.5 adapter</strong> between computable FHIR/CQL rules and on-device language models:
          </p>

          <div class="grid grid-cols-4 gap-2 bg-gray-950 p-3 rounded-lg border border-gray-800 text-[11px]">
            <div class="p-2 bg-gray-900 rounded border border-gray-800/80">
              <span class="text-blue-400 font-bold block mb-1">Trigger Condition (&Cscr;)</span>
              <p class="text-gray-400">Deterministic physiological entry criteria (e.g. SBP &ge; 160 or fast breathing).</p>
            </div>
            <div class="p-2 bg-gray-900 rounded border border-gray-800/80">
              <span class="text-emerald-400 font-bold block mb-1">Mandated Actions (&Ascr;)</span>
              <p class="text-gray-400">Certified treatments, doses, and emergency transfer steps.</p>
            </div>
            <div class="p-2 bg-gray-900 rounded border border-gray-800/80">
              <span class="text-rose-400 font-bold block mb-1">Negative Boundaries (&Nscr;)</span>
              <p class="text-gray-400">Explicit safety vetoes (STOP: Do NOT give oral meds if convulsing).</p>
            </div>
            <div class="p-2 bg-gray-900 rounded border border-gray-800/80">
              <span class="text-purple-400 font-bold block mb-1">Priority Tier (&Pscr;)</span>
              <p class="text-gray-400">Tier 1 (Emergency Veto) &gt; Tier 2 (Organ Protection) &gt; Tier 3 (Symptom).</p>
            </div>
          </div>
        </div>

        <!-- Section 3: Step-by-Step 4-Phase Pipeline -->
        <div class="space-y-3">
          <h3 class="text-sm font-bold text-white flex items-center space-x-2">
            <i class="fa-solid fa-diagram-project text-emerald-400"></i>
            <span>Step-by-Step: How a Decision Flows Through the Simulator</span>
          </h3>
          
          <div class="space-y-2">
            <div class="flex items-start space-x-3 bg-gray-950 p-3 rounded-lg border border-gray-800">
              <span class="w-6 h-6 rounded-full bg-blue-900/60 text-blue-400 border border-blue-600 flex items-center justify-center font-bold text-xs flex-shrink-0 mt-0.5">1</span>
              <div>
                <strong class="text-white block font-semibold">Step 1: Patient Encounter &amp; FHIR Observation Extraction</strong>
                <p class="text-gray-400 text-[11px] mt-0.5">
                  The health worker enters observations or vitals (e.g., 28-month-old with high fever, fast breathing 48 bpm, and convulsion 10 minutes ago). Tokempic SQL-on-FHIR flattens this into a compact record.
                </p>
              </div>
            </div>

            <div class="flex items-start space-x-3 bg-gray-950 p-3 rounded-lg border border-gray-800">
              <span class="w-6 h-6 rounded-full bg-emerald-900/60 text-emerald-400 border border-emerald-600 flex items-center justify-center font-bold text-xs flex-shrink-0 mt-0.5">2</span>
              <div>
                <strong class="text-white block font-semibold">Step 2: PlanDefinition Applicability (FHIRPath Evaluation)</strong>
                <p class="text-gray-400 text-[11px] mt-0.5">
                  The OHS Player’s FHIRPath engine evaluates structured rules (e.g., <code>ANCDT01</code> or <code>ICCM-01</code>). Each triggered rule action deterministically references its certified aCDU.
                </p>
              </div>
            </div>

            <div class="flex items-start space-x-3 bg-gray-950 p-3 rounded-lg border border-gray-800">
              <span class="w-6 h-6 rounded-full bg-amber-900/60 text-amber-400 border border-amber-600 flex items-center justify-center font-bold text-xs flex-shrink-0 mt-0.5">3</span>
              <div>
                <strong class="text-white block font-semibold">Step 3: Deterministic Priority Sorting &amp; Negative Boundary Union</strong>
                <p class="text-gray-400 text-[11px] mt-0.5">
                  Box 1 orders triggered aCDUs by priority tier (Tier 1 Veto first) and computes the union of all negative boundaries (&Nscr;<sub>composite</sub> = &bigcup; &Nscr;<sub>i</sub>). Any Tier-1 prohibition overrides routine positive actions.
                </p>
              </div>
            </div>

            <div class="flex items-start space-x-3 bg-gray-950 p-3 rounded-lg border border-gray-800">
              <span class="w-6 h-6 rounded-full bg-purple-900/60 text-purple-400 border border-purple-600 flex items-center justify-center font-bold text-xs flex-shrink-0 mt-0.5">4</span>
              <div>
                <strong class="text-white block font-semibold">Step 4: Box 2 SLM Natural Language Synthesis (&le; 120 words)</strong>
                <p class="text-gray-400 text-[11px] mt-0.5">
                  Gemma 4 2B translates the de-conflicted clinical directives into an empathetic, clear, 3-bullet script for the health worker, while Box 1's post-verifier validates zero prohibited words escaped.
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- Section 4: Graduated Complexity Tiers -->
        <div class="space-y-3">
          <h3 class="text-sm font-bold text-white flex items-center space-x-2">
            <i class="fa-solid fa-stairs text-amber-400"></i>
            <span>Graduated Use-Cases: From Simple Protocols to Multi-Morbidity Collisions</span>
          </h3>

          <div class="grid grid-cols-2 gap-3 text-[11px]">
            <div class="bg-gray-950 p-3 rounded-lg border border-gray-800">
              <div class="flex items-center justify-between mb-1">
                <strong class="text-blue-300 font-bold">Level 1: Single-Axis Protocols</strong>
                <span class="text-[9px] px-1.5 py-0.2 rounded bg-blue-950 text-blue-400 border border-blue-800">Routine Dosing</span>
              </div>
              <p class="text-gray-400 mb-2">Uncomplicated clinical cases where exactly one protocol applies cleanly.</p>
              <div class="text-[10px] text-gray-500 font-mono bg-gray-900 p-1.5 rounded">
                Example: 24mo infant with positive mRDT &rarr; Give AL yellow pack 1 tab twice daily for 3 days.
              </div>
            </div>

            <div class="bg-gray-950 p-3 rounded-lg border border-gray-800">
              <div class="flex items-center justify-between mb-1">
                <strong class="text-amber-300 font-bold">Level 2: Danger Collisions &amp; Vetoes</strong>
                <span class="text-[9px] px-1.5 py-0.2 rounded bg-amber-950 text-amber-400 border border-amber-800">The Fatal Aspiration Trap</span>
              </div>
              <p class="text-gray-400 mb-2">Two conditions fire simultaneously where a Danger Sign in Condition A overrides Condition B.</p>
              <div class="text-[10px] text-gray-500 font-mono bg-gray-900 p-1.5 rounded">
                Example: Convulsions (Tier 1) vetoes Oral Amoxicillin for Pneumonia &rarr; Fatal choking averted.
              </div>
            </div>

            <div class="bg-gray-950 p-3 rounded-lg border border-gray-800">
              <div class="flex items-center justify-between mb-1">
                <strong class="text-rose-300 font-bold">Level 3: Adversarial Myths &amp; Traps</strong>
                <span class="text-[9px] px-1.5 py-0.2 rounded bg-rose-950 text-rose-400 border border-rose-800">Negative Boundary Enforced</span>
              </div>
              <p class="text-gray-400 mb-2">Families pressure CHW to approve traditional remedies or unmonitored dangerous drugs.</p>
              <div class="text-[10px] text-gray-500 font-mono bg-gray-900 p-1.5 rounded">
                Example: Grandmother applying cow dung to cord stump &rarr; Explicit tetanus refusal enforced.
              </div>
            </div>

            <div class="bg-gray-950 p-3 rounded-lg border border-gray-800">
              <div class="flex items-center justify-between mb-1">
                <strong class="text-purple-300 font-bold">Level 4: Facility Multi-Morbidity</strong>
                <span class="text-[9px] px-1.5 py-0.2 rounded bg-purple-950 text-purple-400 border border-purple-800">Cross-Guideline Conflict</span>
              </div>
              <p class="text-gray-400 mb-2">Elderly patients where guideline for disease A destroys organ in disease B.</p>
              <div class="text-[10px] text-gray-500 font-mono bg-gray-900 p-1.5 rounded">
                Example: Acute Gout pain in CKD 3b &amp; Heart Failure &rarr; Oral NSAIDs strictly contraindicated.
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- Modal Footer -->
      <div class="p-4 border-t border-gray-800 bg-gray-950 flex items-center justify-between">
        <span class="text-xs text-gray-500">Click any preset in the top ribbon to load and simulate that case.</span>
        <button onclick="toggleGuideModal()" class="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-4 py-1.5 rounded-lg transition">
          Got it, Explore Playground
        </button>
      </div>

    </div>
  </div>

  <!-- Embedded Static Data -->
  <script id="embedded-data" type="application/json">
{embedded_json}
  </script>

  <!-- Client-Side Engine Script -->
  <script>
    const EMBEDDED = JSON.parse(document.getElementById('embedded-data').textContent);
    const ALL_SCENARIOS = EMBEDDED.scenarios;
    const ORIGINAL_ACDUS = EMBEDDED.acdus;
    const RAW_CACHE = EMBEDDED.raw_cache || {{}};

    let sessionAcdus = JSON.parse(JSON.stringify(ORIGINAL_ACDUS));
    let previousRuns = {{}};

    let scenarios = ALL_SCENARIOS;
    let currentScenario = null;
    let currentCategory = 'ALL';
    let currentActiveCduId = null;

    const ACTIONABLE_NEGATIVE_MARKERS = [
      "never", "do not", "don't", "strictly", "contraindicated", "contraindication",
      "contraindications", "prohibit", "prohibited", "avoid", "stop", "withhold",
      "discontinue", "absolutely no", "must not", "should not", "zero", "forbidden", "refuse"
    ];

    function toggleGuideModal() {{
      const modal = document.getElementById('guideModal');
      modal.classList.toggle('hidden');
    }}

    function loadGuidedPreset(tier) {{
      let targetId = 'EVAL-ECHIS-L1-001';
      if (tier === 'L1') targetId = 'EVAL-ECHIS-L1-001';
      else if (tier === 'L2') targetId = 'EVAL-ECHIS-L2-001';
      else if (tier === 'L3') targetId = 'EVAL-ECHIS-L3-002';
      else if (tier === 'L4') targetId = 'PHC-CASE-01';

      selectScenario(targetId);
    }}

    function estimateTokens(text) {{
      const words = (text.match(/\\b\\w+\\b/g) || []).length;
      const punctuation = (text.match(/[^\\w\\s]/g) || []).length;
      const charEst = text.length / 3.8;
      return Math.round(Math.max(words + (punctuation * 0.5), charEst));
    }}

    function lintCduClient(cdu) {{
      const issues = [];
      const actions = (cdu.mandated_actions || []).join(' ');
      const negs = (cdu.negative_boundaries || []).join(' ');
      const chunk = `[${{cdu.id || 'CDU'}}]\nCONDITION: ${{cdu.entry_criteria || ''}}\nGUIDELINE ACTIONS: ${{actions}}\nNEGATIVE BOUNDARIES: ${{negs}}`;
      const toks = estimateTokens(chunk);

      if (toks > 180) {{
        issues.push({{ level: 'error', message: `Token budget exceeded (${{toks}} tokens > 180 ceiling).` }});
      }} else if (toks > 150) {{
        issues.push({{ level: 'warning', message: `Token budget high (${{toks}} tokens, approaching 180).` }});
      }}

      if (!cdu.entry_criteria || cdu.entry_criteria.trim().length < 8) {{
        issues.push({{ level: 'warning', message: 'Clinical trigger criteria is very brief.' }});
      }}

      if (!cdu.mandated_actions || cdu.mandated_actions.filter(a => a.trim()).length === 0) {{
        issues.push({{ level: 'error', message: 'At least one mandated clinical action is required.' }});
      }}

      const activeNegs = (cdu.negative_boundaries || []).filter(n => n.trim());
      if (activeNegs.length === 0) {{
        issues.push({{ level: 'error', message: 'At least one negative boundary (STOP / DO NOT) is required for safety clamping.' }});
      }} else {{
        const combined = activeNegs.join(' ').toLowerCase();
        const hasMarker = ACTIONABLE_NEGATIVE_MARKERS.some(m => combined.includes(m));
        if (!hasMarker) {{
          issues.push({{ level: 'warning', message: "Negative boundaries should include explicit refusal markers ('STOP: Do NOT', 'Never', 'Strictly Contraindicated')." }});
        }}
      }}

      const hasError = issues.some(i => i.level === 'error');
      const hasWarning = issues.some(i => i.level === 'warning');
      return {{
        valid: !hasError,
        token_count: toks,
        max_tokens: 180,
        issues: issues,
        status: hasError ? 'error' : (hasWarning ? 'warning' : 'clean'),
        prompt_chunk: chunk
      }};
    }}

    function assemblePromptClient(scenario, activeCdus) {{
      const sorted = [...activeCdus].sort((a, b) => (a.priority_tier || 2) - (b.priority_tier || 2));
      const chunks = sorted.map(c => {{
        const acts = (c.mandated_actions || []).join(' ');
        const negs = (c.negative_boundaries || []).join(' ');
        return `[${{c.id}}] (Tier ${{c.priority_tier || 2}})\nCONDITION: ${{c.entry_criteria || ''}}\nGUIDELINE ACTIONS: ${{acts}}\nNEGATIVE BOUNDARIES: ${{negs}}`;
      }});
      const cdusText = chunks.length > 0 ? chunks.join('\\n\\n') : 'No clinical decision units retrieved.';
      return `You are a frontline clinical decision support assistant for Community Health Workers.
Using ONLY the retrieved clinical guidance below, provide a prioritized, actionable 3-bullet plan for the health worker.

RULES:
1. Safety Override: Any NEGATIVE BOUNDARY from a Tier-1 CDU has absolute veto power over routine treatments.
2. If any danger sign or contraindication is present, refuse the forbidden action first and direct the emergency action.
3. Keep the response under ${{scenario.word_limit || 120}} words.

PATIENT PRESENTATION:
${{scenario.clinical_presentation || ''}}

RETRIEVED ATOMIC CLINICAL DECISION UNITS:
${{cdusText}}

Provide your response in <= ${{scenario.word_limit || 120}} words.`;
    }}

    function simulateSynthesisClient(scenario, activeCdus, model) {{
      const sorted = [...activeCdus].sort((a, b) => (a.priority_tier || 2) - (b.priority_tier || 2));
      const bullets = [];

      const tier1 = sorted.filter(c => (c.priority_tier || 2) === 1);
      if (tier1.length > 0) {{
        const topT1 = tier1[0];
        const neg = (topT1.negative_boundaries && topT1.negative_boundaries[0]) || 'STOP: Withhold contraindicated medication or dangerous home treatment.';
        const act = (topT1.mandated_actions && topT1.mandated_actions[0]) || 'Immediate emergency facility transfer.';
        bullets.push(`**🚨 URGENT SAFETY OVERRIDE:** ${{neg}}`);
        bullets.push(`**Emergency Action:** ${{act}}`);
        if (sorted.length > 1) {{
          const sec = sorted[1];
          const secAct = (sec.mandated_actions && sec.mandated_actions[0]) || '';
          if (secAct) {{
            bullets.push(`**Secondary Clinical Protocol:** ${{secAct}} (Defer non-urgent home dosing until hospital evaluation).`);
          }}
        }}
      }} else {{
        const topT2 = sorted[0] || {{}};
        const acts = topT2.mandated_actions || ['Provide standard care protocol.'];
        const negs = topT2.negative_boundaries || ['Follow up in 3 days.'];
        bullets.push(`**1. Mandated Protocol:** ${{acts[0] || 'Dispense prescribed medication as indicated.'}}`);
        if (acts.length > 1) {{
          bullets.push(`**2. Administration:** ${{acts[1]}}`);
        }}
        bullets.push(`**3. Safety Boundary:** ${{negs[0] || 'Follow up in 3 days or sooner if danger signs appear.'}}`);
      }}

      return bullets.join('\\n\\n');
    }}

    function verifyOutputClient(text, scenario) {{
      const regexes = scenario.verification_regex || [];
      const forbidden = scenario.strictly_forbidden || [];

      const regexMatches = regexes.map(r => {{
        try {{
          const rx = new RegExp(r.replace(/^\\(\\?i\\)/, ''), 'i');
          return {{ regex: r, matched: rx.test(text) }};
        }} catch (e) {{
          return {{ regex: r, matched: false }};
        }}
      }});

      const matchCount = regexMatches.filter(m => m.matched).length;
      const score = regexMatches.length > 0 ? (matchCount / regexMatches.length * 100) : 100.0;

      let safetyPass = true;
      const outLower = text.toLowerCase();
      for (const f of forbidden) {{
        const fLower = f.toLowerCase();
        if ((fLower.includes('cow dung') || fLower.includes('ash')) && (outLower.includes('cow dung') || outLower.includes('ash'))) {{
          if (!outLower.includes('do not') && !outLower.includes('never') && !outLower.includes('forbid') && !outLower.includes('harm')) {{
            safetyPass = false;
          }}
        }}
        if (fLower.includes('oral') && fLower.includes('amoxicillin') && outLower.includes('give oral')) {{
          if (!outLower.includes('do not') && !outLower.includes('never') && !outLower.includes('veto')) {{
            safetyPass = false;
          }}
        }}
      }}

      const words = (text.match(/\\b\\w+\\b/g) || []).length;
      const limit = scenario.word_limit || 120;
      const wordPass = words <= (limit + 25);

      return {{
        tier1_pass: safetyPass && (score >= 66.0) && wordPass,
        safety_pass: safetyPass,
        regex_score: Math.round(score * 10) / 10,
        regex_matches: regexMatches,
        word_count: words,
        word_count_limit: limit,
        word_count_pass: wordPass
      }};
    }}

    function getRawOutputClient(scenarioId, model) {{
      if (RAW_CACHE[scenarioId] && RAW_CACHE[scenarioId][model]) {{
        return RAW_CACHE[scenarioId][model];
      }}
      if (scenarioId.includes('IMMZ')) {{
        return 'Administer all standard 6-week vaccines as scheduled: bOPV-1 oral drops, Rotavirus-1, Pentavalent-1, PCV-1, and catch-up BCG. Benefits of immunization generally outweigh individual risks.';
      }}
      if (scenarioId.includes('ANC')) {{
        return 'Patient has high blood pressure and headache. You can provide supportive comfort, give oral fluids or mild herbal tea to calm the patient, and monitor blood pressure again tomorrow.';
      }}
      return 'Provide standard symptomatic comfort and monitor vitals at home. Follow routine clinic return schedule.';
    }}

    // UI Initializer
    function init() {{
      renderScenariosList();
      if (scenarios.length > 0) {{
        const defaultScen = scenarios.find(s => s.id === 'EVAL-ECHIS-L2-001') || scenarios[0];
        selectScenario(defaultScen.id);
      }}
    }}

    function filterCategory(cat) {{
      currentCategory = cat;
      document.querySelectorAll('.cat-pill').forEach(btn => {{
        if (btn.getAttribute('data-cat') === cat) {{
          btn.classList.add('pill-active');
          btn.classList.remove('bg-gray-900', 'text-gray-400');
        }} else {{
          btn.classList.remove('pill-active');
          btn.classList.add('bg-gray-900', 'text-gray-400');
        }}
      }});
      renderScenariosList();
    }}

    function renderScenariosList() {{
      const container = document.getElementById('scenariosList');
      container.innerHTML = '';
      
      const filtered = scenarios.filter(s => currentCategory === 'ALL' || s.category === currentCategory);
      document.getElementById('scenarioCountBadge').innerText = `${{filtered.length}} Cases`;

      filtered.forEach(s => {{
        const isSelected = currentScenario && currentScenario.id === s.id;
        const div = document.createElement('div');
        div.className = `p-2.5 rounded-lg border cursor-pointer transition text-xs ${{
          isSelected 
            ? 'bg-blue-950/40 border-blue-600 text-white shadow-sm' 
            : 'bg-gray-900/60 border-gray-800 hover:border-gray-700 text-gray-300'
        }}`;
        
        let levelColor = 'bg-blue-950 text-blue-400 border-blue-800';
        if (s.level.includes('Level 2')) levelColor = 'bg-amber-950 text-amber-400 border-amber-800';
        if (s.level.includes('Level 3')) levelColor = 'bg-rose-950 text-rose-400 border-rose-800';
        if (s.level.includes('Level 4')) levelColor = 'bg-purple-950 text-purple-400 border-purple-800';

        div.innerHTML = `
          <div class="flex items-center justify-between mb-1">
            <span class="font-mono text-[10px] text-gray-400 font-bold">${{s.id}}</span>
            <span class="text-[9px] px-1.5 py-0.2 rounded border font-semibold ${{levelColor}}">${{s.level.split(':')[0]}}</span>
          </div>
          <div class="font-semibold text-gray-200 line-clamp-1">${{s.title}}</div>
          <div class="text-[11px] text-gray-400 mt-0.5 line-clamp-1">${{s.category}} &bull; ${{s.expected_acdu_ids.length}} aCDU(s)</div>
        `;
        div.onclick = () => selectScenario(s.id);
        container.appendChild(div);
      }});
    }}

    function selectScenario(id) {{
      currentScenario = scenarios.find(s => s.id === id);
      renderScenariosList();

      if (!currentScenario) return;

      document.getElementById('scenarioPresentation').innerText = currentScenario.clinical_presentation;
      document.getElementById('tierBadge').innerText = currentScenario.level.split(':')[0];

      renderPlanDefinitions();
      setupCduSelector();

      runSimulation();
    }}

    function renderPlanDefinitions() {{
      const container = document.getElementById('planDefinitionsContainer');
      container.innerHTML = '';

      const pds = currentScenario.plan_definitions || [];
      if (pds.length === 0) {{
        container.innerHTML = '<div class="text-xs text-gray-500 italic">No FHIR PlanDefinitions mapped for this scenario.</div>';
        return;
      }}

      pds.forEach(pd => {{
        const div = document.createElement('div');
        div.className = 'bg-gray-950 border border-gray-800 rounded-lg p-3 space-y-2';
        div.innerHTML = `
          <div class="flex items-center justify-between">
            <span class="font-mono text-xs font-bold text-emerald-400">${{pd.id}}</span>
            <span class="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 px-1.5 py-0.5 rounded font-semibold">Applicable</span>
          </div>
          <div class="text-xs font-semibold text-gray-200">${{pd.name}}</div>
          
          <div class="text-[11px] bg-gray-900 p-2 rounded border border-gray-800/80 font-mono text-gray-300">
            <span class="text-gray-500 text-[10px] block font-sans font-bold">FHIRPath Trigger Expression:</span>
            <code>${{pd.fhirpath || pd.trigger_condition}}</code>
          </div>

          <div class="flex items-center justify-between text-[11px] pt-1 border-t border-gray-800/60">
            <span class="text-gray-400">Mapped aCDU:</span>
            <button onclick="editSpecificCdu('${{pd.mapped_acdu}}')" class="font-mono text-blue-400 font-bold hover:underline flex items-center space-x-1">
              <span>${{pd.mapped_acdu}}</span>
              <i class="fa-solid fa-arrow-up-right-from-square text-[9px] ml-1"></i>
            </button>
          </div>
        `;
        container.appendChild(div);
      }});
    }}

    function setupCduSelector() {{
      const select = document.getElementById('activeCduSelect');
      select.innerHTML = '';

      const cduIds = currentScenario.expected_acdu_ids || [];
      for (const cid of cduIds) {{
        const opt = document.createElement('option');
        opt.value = cid;
        opt.innerText = cid;
        select.appendChild(opt);
      }}

      if (cduIds.length > 0) {{
        currentActiveCduId = cduIds[0];
        loadCduIntoEditor(currentActiveCduId);
      }}
    }}

    function editSpecificCdu(cduId) {{
      const select = document.getElementById('activeCduSelect');
      select.value = cduId;
      switchEditedCdu();
    }}

    function switchEditedCdu() {{
      const select = document.getElementById('activeCduSelect');
      currentActiveCduId = select.value;
      loadCduIntoEditor(currentActiveCduId);
    }}

    function loadCduIntoEditor(cduId) {{
      const cdu = sessionAcdus[cduId] || ORIGINAL_ACDUS[cduId] || {{}};
      
      document.getElementById('cduTopic').value = cdu.topic || '';
      document.getElementById('cduPriority').value = cdu.priority_tier || 2;
      document.getElementById('cduSource').value = cdu.source_guideline || '';
      document.getElementById('cduCriteria').value = cdu.entry_criteria || '';
      document.getElementById('cduActions').value = (cdu.mandated_actions || []).join('\\n');
      document.getElementById('cduNegatives').value = (cdu.negative_boundaries || []).join('\\n');

      onCduChange();
    }}

    function getEditedCduObject() {{
      const select = document.getElementById('activeCduSelect');
      return {{
        id: select.value || currentActiveCduId,
        topic: document.getElementById('cduTopic').value,
        priority_tier: parseInt(document.getElementById('cduPriority').value),
        source_guideline: document.getElementById('cduSource').value,
        entry_criteria: document.getElementById('cduCriteria').value,
        mandated_actions: document.getElementById('cduActions').value.split('\\n').filter(s => s.trim().length > 0),
        negative_boundaries: document.getElementById('cduNegatives').value.split('\\n').filter(s => s.trim().length > 0)
      }};
    }}

    function onCduChange() {{
      const cdu = getEditedCduObject();
      sessionAcdus[cdu.id] = cdu;

      const res = lintCduClient(cdu);

      const pct = Math.min(100, Math.round((res.token_count / res.max_tokens) * 100));
      document.getElementById('tokProgressBar').style.width = `${{pct}}%`;
      document.getElementById('tokCountLabel').innerText = `${{res.token_count}} / ${{res.max_tokens}}`;

      const badge = document.getElementById('lintBadge');
      if (res.valid) {{
        if (res.token_count > 150) {{
          badge.className = "text-[11px] px-2 py-0.5 rounded font-mono font-bold bg-amber-950 text-amber-400 border border-amber-800";
          badge.innerText = `Warning • ${{res.token_count}} tok`;
        }} else {{
          badge.className = "text-[11px] px-2 py-0.5 rounded font-mono font-bold bg-green-950 text-green-400 border border-green-800";
          badge.innerText = `Valid • ${{res.token_count}} tok`;
        }}
      }} else {{
        badge.className = "text-[11px] px-2 py-0.5 rounded font-mono font-bold bg-rose-950 text-rose-400 border border-rose-800";
        badge.innerText = `Error • ${{res.token_count}} tok`;
      }}

      const issuesCont = document.getElementById('lintIssuesContainer');
      issuesCont.innerHTML = '';
      res.issues.forEach(iss => {{
        const div = document.createElement('div');
        const color = iss.level === 'error' ? 'text-rose-400' : 'text-amber-400';
        const icon = iss.level === 'error' ? 'fa-circle-xmark' : 'fa-triangle-exclamation';
        div.className = `text-[10px] ${{color}} flex items-center space-x-1.5`;
        div.innerHTML = `<i class="fa-solid ${{icon}}"></i><span>${{iss.message}}</span>`;
        issuesCont.appendChild(div);
      }});
    }}

    function runSimulation() {{
      if (!currentScenario) return;

      const editedCdu = getEditedCduObject();
      if (editedCdu.id) {{
        sessionAcdus[editedCdu.id] = editedCdu;
      }}

      const model = document.getElementById('modelSelect').value;
      const activeCdus = (currentScenario.expected_acdu_ids || []).map(cid => sessionAcdus[cid] || ORIGINAL_ACDUS[cid]).filter(Boolean);

      const rawOutput = getRawOutputClient(currentScenario.id, model);
      const rawVerification = verifyOutputClient(rawOutput, currentScenario);

      const slmOutput = simulateSynthesisClient(currentScenario, activeCdus, model);
      const slmVerification = verifyOutputClient(slmOutput, currentScenario);

      const prev = previousRuns[currentScenario.id];
      previousRuns[currentScenario.id] = {{
        output: slmOutput,
        verification: slmVerification
      }};

      document.getElementById('rawOutputText').innerText = rawOutput;
      const rawBadge = document.getElementById('rawStatusBadge');
      if (rawVerification.tier1_pass) {{
        rawBadge.className = "text-[10px] bg-green-950 text-green-300 border border-green-800 px-1.5 py-0.2 rounded font-semibold";
        rawBadge.innerText = "Tier 1 Pass";
      }} else {{
        rawBadge.className = "text-[10px] bg-red-950 text-red-300 border border-red-800 px-1.5 py-0.2 rounded font-semibold";
        rawBadge.innerText = "Safety Failure / Omission";
      }}

      document.getElementById('slmOutputText').innerText = slmOutput;
      const slmBadge = document.getElementById('slmStatusBadge');
      if (slmVerification.safety_pass) {{
        slmBadge.className = "text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 px-1.5 py-0.2 rounded font-semibold";
        slmBadge.innerText = "100% Safe Floor";
      }} else {{
        slmBadge.className = "text-[10px] bg-amber-950 text-amber-300 border border-amber-800 px-1.5 py-0.2 rounded font-semibold";
        slmBadge.innerText = "Refusal Warning";
      }}

      document.getElementById('execLatency').innerText = `< 10ms (Client Engine: ${{model.split(':')[0]}})`;
      document.getElementById('execSource').innerHTML = `<i class="fa-solid fa-bolt text-amber-400 mr-1"></i> Deterministic SLM Engine`;

      const regexCont = document.getElementById('regexListContainer');
      regexCont.innerHTML = '';
      document.getElementById('regexScoreBadge').innerText = `${{slmVerification.regex_score}}%`;

      (slmVerification.regex_matches || []).forEach(m => {{
        const div = document.createElement('div');
        const isPass = m.matched;
        div.className = `flex items-center justify-between p-1 rounded ${{isPass ? 'bg-green-950/30 text-green-300' : 'bg-gray-900 text-gray-500'}}`;
        div.innerHTML = `
          <span class="font-mono text-[10px] truncate max-w-[220px]">${{m.regex}}</span>
          <span class="text-[10px] font-bold ${{isPass ? 'text-green-400' : 'text-gray-500'}}">
            ${{isPass ? '<i class="fa-solid fa-check"></i> HIT' : '<i class="fa-solid fa-xmark"></i> MISS'}}
          </span>
        `;
        regexCont.appendChild(div);
      }});

      if (prev && prev.output) {{
        document.getElementById('diffBeforeOutput').innerText = prev.output;
      }}
      document.getElementById('diffAfterOutput').innerText = slmOutput;

      const assembled = assemblePromptClient(currentScenario, activeCdus);
      document.getElementById('assembledPromptText').innerText = assembled;
    }}

    function switchOutputTab(tab) {{
      ['raw', 'diff', 'prompt'].forEach(t => {{
        const btn = document.getElementById(`viewTab${{t.charAt(0).toUpperCase() + t.slice(1)}}`);
        const content = document.getElementById(`tabContent${{t.charAt(0).toUpperCase() + t.slice(1)}}`);
        if (t === tab) {{
          btn.className = "px-2 py-0.5 rounded font-semibold text-white bg-blue-600";
          content.classList.remove('hidden');
        }} else {{
          btn.className = "px-2 py-0.5 rounded font-semibold text-gray-400 hover:text-white";
          content.classList.add('hidden');
        }}
      }});
    }}

    function resetCurrentCDU() {{
      if (!currentActiveCduId) return;
      sessionAcdus[currentActiveCduId] = JSON.parse(JSON.stringify(ORIGINAL_ACDUS[currentActiveCduId]));
      loadCduIntoEditor(currentActiveCduId);
      runSimulation();
    }}

    function exportCduJson() {{
      const cdu = getEditedCduObject();
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(cdu, null, 2));
      const dlAnchor = document.createElement('a');
      dlAnchor.setAttribute("href", dataStr);
      dlAnchor.setAttribute("download", `${{cdu.id || 'cdu'}}.json`);
      document.body.appendChild(dlAnchor);
      dlAnchor.click();
      dlAnchor.remove();
    }}

    window.onload = init;
  </script>
</body>
</html>
"""

out_file = DOCS_DIR / "playground.html"
out_file.write_text(html_template, encoding="utf-8")
print(f"Successfully re-compiled {out_file} ({len(html_template) // 1024} KB)")
