# aCDU Clinical Decision Unit Simulator & Playground

An interactive, zero-dependency local simulator that models how **FHIR PlanDefinitions**, **Atomic Clinical Decision Units (aCDUs)**, and **Edge Small Language Models (SLMs)** interact across frontline primary healthcare encounters.

---

## 4-Panel Architecture

```
+---------------------------+---------------------------+---------------------------+---------------------------+
| 1. SCENARIOS (L1 -> L4)   | 2. PLANDEFINITIONS        | 3. aCDU LIVE EDITOR       | 4. DOWNSTREAM SLM OUTPUT  |
| - Kenya eCHIS (30 cases)  | - FHIRPath expressions    | - Priority Tier (1-3)     | - Raw Baseline vs Clamped |
| - WHO SMART Guidelines    | - Pre-associated triggers | - Token Budget (<=180tok) | - Before vs After Tweak   |
| - PHC Multi-Morbidity     | - aCDU Code mappings      | - Negative Boundary Linter| - Tier-1 Regex Checklist  |
+---------------------------+---------------------------+---------------------------+---------------------------+
```

### 1. Scenarios (Graduated Complexity)
- **Level 1: Single-Axis Protocols** (e.g., pediatric malaria AL dosing, pneumonia amoxicillin DT, acute diarrhea ORS & zinc).
- **Level 2: Multi-Morbidity Prioritization & Collisions** (e.g., severe malaria with convulsions vs. oral amoxicillin, severe pre-eclampsia vs. home regimens).
- **Level 3: Adversarial Traps & Negative Clamping** (e.g., cow dung/ash cord care myths, traditional oxytocic herbs in stalled labor).
- **Level 4: Complex Facility Collisions** (e.g., CKD + HFrEF + acute gout NSAID prohibitions, asthma beta-blocker contraindications).

### 2. PlanDefinition Mappings
- Displays the FHIR `PlanDefinition` resource metadata (ID, title, action triggers).
- Inspects the FHIRPath logic that determines applicability (e.g., `%patient.gestationalAge >= 12 'wk'`).
- Surfaces the direct mapping to corresponding aCDU safety codes (e.g., `ANCDT01` -> `CDU-WHO-SMART-ANC-01`).
- *Architecture Milestone Note:* Contains the to-do placeholder for integrating the native `kotlin-fhirpath` evaluation engine directly over raw FHIR bundles.

### 3. aCDU Editor
- Live in-memory editor to tweak **Entry Criteria**, **Mandated Actions**, and **Negative Boundaries** (`STOP: Do NOT...`).
- Real-time token budget progress bar enforcing the $\le 180$ token ceiling.
- Semantic linter alerting when actionability markers (`never`, `prohibit`, `do not`) are missing.
- Option to save tweaked aCDUs back to the certified registry or keep them transient.

### 4. Downstream Impact & SLM Output
- **Raw vs. Clamped View:** Contrasts the unconstrained baseline SLM against the aCDU-clamped response.
- **Before vs. After Diff View:** Immediately compares how your edit in Panel 3 shifted the model's action plan and safety score.
- **Prompt Inspector:** Reveals the exact context and priority ordering injected into the SLM.
- **Tier-1 Clinical Safety Adherence Checklist:** Automated regex verification tracking whether mandatory danger signs, medications, and contraindication vetoes passed.

---

## Running the Simulator

```bash
# Start the local web simulator
python3 acdu_simulator/app.py --port 8520
```

Open your browser to:
👉 **`http://localhost:8520`**

### Live Edge Inference
If local Ollama is running (`gemma4-2b:latest`, `medgemma:latest`, `gemma4:e4b`, `qwen2.5:3b`), the simulator automatically streams live inference in **1.2s – 1.8s**. If offline or running without Ollama, it automatically falls back to the deterministic SLM synthesis engine.
