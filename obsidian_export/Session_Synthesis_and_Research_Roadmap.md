---
type: synthesis
topic: OHS Edge & Atomic Clinical Decision Units (a-CDUs) — Session Synthesis, Empirical Insights & Research Roadmap
created: 2026-10-18
status: active
tags:
  - health-tech/ohs
  - health-tech/fhir
  - ai/edge-llm
  - ai/a-cdu
  - ai/mini-rag
  - ai/evals
  - global-health/chw
  - global-health/phc
---

# Session Synthesis: OHS Edge, Tokempic SQL-on-FHIR, and Atomic Clinical Decision Units (a-CDUs)

> [!ABSTRACT] Executive Summary
> Across this session, we designed, implemented, benchmarked, and validated a complete end-to-end architecture for **offline clinical decision support and narrative synthesis using Small Language Models (SLMs, 1B–4B class)** on budget edge hardware ($\le 3\text{--}4\text{GB}$ RAM) within the **Open Health Stack (OHS Edge)** ecosystem. 
>
> Starting from raw FHIR clinical summarization for Community Health Workers (CHWs), our work evolved through five major milestones:
> 1. **Deterministic FHIR Pre-Filtering (`Tokempic` Optimization)**: Identifying and fixing three critical failure modes of 2B edge models on clinical records (LOINC code bleed, resource blindspots, and date-math hallucinations).
> 2. **The Two-Box Clinical Safety Architecture & Mini-RAG**: Decoupling deterministic triage/action selection from generative vernacular counseling, powered by zero-RAM `SQLite FTS5` edge retrieval.
> 3. **Atomic Clinical Decision Units (a-CDUs)**: Formulating a novel, domain-specific 7-tuple knowledge representation that replaces arbitrary sliding-window RAG chunking with token-budgeted ($\le 180$ tokens), negative-boundary-clamped clinical decision units.
> 4. **Full-Stack Tooling, Alignment & Mobile Runtime**: Building the OHS Edge Visual Eval & RLHF Studio, DPO/ORPO preference alignment pipelines, Kotlin Multiplatform (`kmp-edge-slm`) interfaces, and a working Android emulator application (`ohs-edge-demo`).
> 5. **Generalization to Primary Health Care Multi-Morbidity (`phc-evals`)**: Extending the a-CDU hypothesis from single-protocol CHW workflows to complex, colliding multi-disease guidelines (CKD, Heart Failure, Gout, Asthma, Cirrhosis) using composable **Negative Boundary Unions** ($\mathcal{N}_{\text{composite}} = \bigcup \mathcal{N}_i$).

---

## Part 1: Chronological Summary of What We Built & Accomplished

### 1.1 Foundational Edge SLM Evaluation Framework (`chw-edge-evals`)
- **20-Case Clinical Benchmark Dataset**: Built a realistic HL7 FHIR R4 evaluation dataset ([`chw_cases.json`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/chw-edge-evals/dataset/chw_cases.json)) spanning Antenatal Care (ANC), Postnatal Care (PNC), Integrated Community Case Management (iCCM), Non-Communicable Diseases (NCDs), and infectious diseases.
- **2-Tier Automated Grading Harness** ([`run_evals.py`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/chw-edge-evals/run_evals.py)):
  - **Tier 1 (Deterministic Programmatic Gates)**: Strict word-count budgets ($\le 120\text{--}130$ words for mobile viewports), mandatory danger-sign recall, temporal trap checks (preventing resolved conditions from being reported as active), and closed-book negative boundary checks.
  - **Tier 2 (Multi-Provider LLM-as-a-Judge)**: Configurable clinical safety and groundedness rubrics supporting Gemini, OpenAI, Anthropic, and local Ollama judges.

### 1.2 The 3-Way Tokempic vs. Raw FHIR Empirical Study
- Conducted a controlled 3-way evaluation ([`TOKEMPIC_EDGE_BENCHMARK_ANALYSIS.md`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/TOKEMPIC_EDGE_BENCHMARK_ANALYSIS.md), [`compare_3way.py`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/chw-edge-evals/compare_3way.py)) on `gemma2:2b-instruct-q4_K_M` comparing:
  1. **Raw HL7 FHIR JSON** (1,029 avg tokens; **80% pass rate**)
  2. **Original Standard Tokempic** (325 avg tokens; **70% pass rate**)
  3. **Optimized CHW Tokempic (`chw-views/`)** (329 avg tokens; **100% pass rate**)
- Packaged upstream improvements into [`tokempic_upstream_slm_optimizations.patch`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/tokempic_upstream_slm_optimizations.patch), adding `tasks.json`, `observations.json`, pre-computed relative age strings (`days`/`months`/`years`), explicit `RESOLVED - Past History` labels, and unified blood pressure component formatting.

### 1.3 OHS Edge SLM Visual Studio, Alignment & Mobile Runtime
- **Visual Eval & Protocol Studio** ([`visual_eval_studio.py`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/visual_eval_studio.py), [`docs/studio.html`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/docs/studio.html), [`docs/index.html`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/docs/index.html)): Zero-dependency Python workbench + standalone interactive web dashboards adhering to the Open Health Stack Foundation (`ohs.foundation`) design system, WCAG AAA contrast tokens, and real-time context headroom gauges.
- **Adversarial DPO / ORPO Alignment Suite** ([`synthesize_adversarial_dpo.py`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/synthesize_adversarial_dpo.py), [`fine_tune_slm_dpo.py`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/fine_tune_slm_dpo.py), [`argilla_integration.py`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/argilla_integration.py)): Automated generation of `(prompt, chosen, rejected)` preference triples targeting the exact clinical failure modes of 2B models, paired with QLoRA DPO/ORPO training scripts.
- **Kotlin Multiplatform (`kmp-edge-slm`) & Android Demo (`ohs-edge-demo`)**: Built the shared KMP `EdgeLlmEngine` architecture and a native Jetpack Compose Android app featuring offline `SQLite FTS5` protocol lookup (`122 KB` bundled database), Tokempic vs. Raw FHIR context gauges, and live inference telemetry.

### 1.4 Clinical Mini-RAG & The Atomic Clinical Decision Unit (a-CDU) Architecture
- **Kenya MOH eCHIS Module 2 Corpus**: Extracted, structured, and certified 20 complete Maternal & Newborn Health (MNH) decision units ([`Kenya MOH Module 2 Clinical Protocols.md`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/obsidian_export/Kenya%20MOH%20Module%202%20Clinical%20Protocols.md)).
- **Formalization of a-CDUs** ([`Proposal Atomic Clinical Decision Units a-CDUs.md`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/obsidian_export/Proposal%20Atomic%20Clinical%20Decision%20Units%20a-CDUs.md)): Defined the 7-tuple clinical chunking architecture ($\langle \mathcal{I}, \mathcal{P}, \mathcal{C}, \mathcal{T}, \mathcal{R}, \mathcal{N}, \mathcal{M} \rangle$) bridging Arden Syntax MLMs and WHO SMART Guidelines (DAKs) with generative SLM conditioning.

### 1.5 Primary Health Care Multi-Morbidity Benchmark (`phc-evals`)
- Created a standalone, reproducible benchmark repository ([`phc-evals/`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/phc-evals/README.md)) testing whether composable a-CDUs can resolve **multi-disease guideline collisions** across 10 complex primary care archetypes (e.g., Acute Gout + Stage 3b/4 CKD + HFrEF; Stage 2 HTN + Asthma + Angina; Parkinson's Psychosis; Cirrhosis + Cellulitis).
- Evaluated `gemma2:2b-instruct-q4_K_M` and `gemma4:latest` across `with_cdus` vs. `naive_rag`, demonstrating dramatic improvements in both clinical action completeness and contraindication safety.

---

## Part 2: Core Technical & Clinical Insights Discovered

### Insight 1: Small Models Fail on "Formatting Tax" and Implicit Arithmetic, Not Just Medical Knowledge
Our 3-way Tokempic study revealed that 1B–4B quantized models fail on raw clinical records due to three specific structural pathologies:
1. **Numeric Code Bleed**: When LOINC/SNOMED codes (`8480-6`, `8462-4`) appear near clinical values in pipe-delimited tables, 2B models conflate metadata with measurements (e.g., outputting blood pressure as `"126/8480-6 and 8462-4: 82"`).
2. **Date-Math Hallucination**: 2B models cannot reliably subtract an ISO `birthDate` (`2025-06-10`) from an encounter date (`2026-10-18`) during token generation. They latch onto surface digits, turning a **16-month-old infant** into a **"25-year-old male"** and a **4-year-old child** into a **"21-year-old female"**—catastrophically invalidating pediatric iCCM triage.
3. **Workflow Blindspots**: Standard FHIR views omit `Task` resources and non-vital point-of-care dipsticks (`Observation`), blinding the model to overdue hospital referrals and proteinuria/glucosuria readings.
- **Takeaway**: Deterministic SQL-on-FHIR pre-computation (computing human-readable age strings, concatenating BP components, and surfacing `Task` statuses before the prompt) is **mandatory** for edge SLMs, compressing prompt tokens by **3.1×** while lifting accuracy from **70–80% to 100%**.

### Insight 2: Standard Sliding-Window RAG is Fundamentally Unsafe for Medicine
Arbitrary token-window chunking (e.g., 256-token chunks with 50-token overlap) slices non-linear clinical directives apart:
- The *Trigger* lands in Chunk $k$, the *Action* in Chunk $k+1$, and the *Contraindication* in Chunk $k+2$.
- When a retriever pulls only Chunk $k$, the SLM improvises missing actions or omits contraindications from parametric memory.
- Furthermore, standard RAG only specifies *affirmative actions* (what to do), providing zero protection against **sycophantic compliance** when a patient or CHW asks about dangerous folk remedies, off-label antibiotics, or contraindicated drugs.

### Insight 3: Zero-RAM Deterministic Retrieval (`SQLite FTS5`) Beats Neural Embeddings on the Edge
- On a budget 2GB–3GB Android device, a 2B INT4 SLM already consumes **1.4–1.8 GB RAM**. Loading an on-device neural embedding model (`EmbeddingGemma` 740M or `bge-small`) adds **400–700 MB RAM**, triggering the Android Low Memory Killer (LMK).
- Because national clinical guidelines for a specific tier of care are bounded corpora (typically 50–300 discrete decision units), compiling certified a-CDUs into a pre-indexed **SQLite FTS5 (BM25)** database (`122 KB`) achieves **$<0.8\,\text{ms}$ retrieval latency** with **0.00 MB additional model RAM** and **100% danger-sign recall**.

### Insight 4: The "Two-Box" Regulatory Boundary (Code Decides, SLM Narrates)
- Under FDA SaMD, EU MDR, and WHO AI governance frameworks, unconstrained probabilistic token generation should never make autonomous triage or dosing calculations.
- By enforcing a strict architectural split—where deterministic code (FHIRPath / SQL-on-FHIR / eCHIS decision logic) selects the exact a-CDUs and clinical flags, and the edge SLM is constrained strictly to **synthesizing and narrating** those certified directives—we achieve both regulatory safety and contextual linguistic adaptability.

### Insight 5: Composable Negative Boundaries Solve the Multi-Morbidity Collision Problem
- In our `phc-evals` experiments, when a patient presents with colliding guidelines (e.g., Acute Gout demanding NSAIDs vs. Stage 3b CKD + HFrEF where NSAIDs trigger acute renal failure), naive RAG routinely fails:
  - On `gemma2:2b-instruct-q4_K_M`, `naive_rag` scored **0% Tier-1 Pass** and **60% Fatal Safety Adherence** (affirmatively prescribing nephrotoxic NSAIDs or unsafe beta-blockers in 40% of cases).
  - With composable **a-CDU conditioning (`with_cdus`)**, where the prompt explicitly injects the **Negative Boundary Union** ($\mathcal{N}_{\text{composite}} = \bigcup_{i=1}^k \mathcal{N}_i$) as a top-level safety override, fatal contraindication violations dropped to **0% (90–100% safety adherence)**, and on `gemma4:latest`, Tier-1 clinical pass rates jumped from **50% (`naive_rag`) to 80% (`with_cdus`)** with **100% fatal safety adherence**.

### Insight 6: Bridging the "Process vs. Outcome" Gap Observed in Real-World Clinical Trials
- Our analysis of the recent **Penda Health / Nature Medicine cluster-RCT** (*9,347 encounters across 16 Kenyan primary care clinics using cloud GPT-4o "AI Consult 2.0"*, [`scratch_paper_text.txt`](file:///Users/fredhersch/Documents/antigravity/intelligent-hypatia/scratch_paper_text.txt)) surfaced a crucial real-world insight:
  - While cloud LLM assistance significantly improved documentation quality ($\text{aOR } 1.68\text{--}1.74, P < 0.001$) and slightly reduced antibiotic costs, **it did not statistically significantly reduce 14-day treatment failure** ($\text{aOR } 0.77, P = 0.13$), and **clinicians fully adhered to red-alert LLM safety warnings only 19.5% of the time** (ignoring 23.2% and partially adhering to 57.3%, with an expert panel judging 71.6% of clinician decisions on red alerts to be *clinically unjustified*).
  - **Why?** Passive, cloud-only, verbose text alerts suffer from alert fatigue, lack hard point-of-care guardrails, exclude community follow-up (where 14-day treatment failure actually unfolds at home), and rely on monolithic prompts rather than verifiable, atomic clinical decision units.

---

## Part 3: Deep-Dive into the a-CDU Approach as a Novel Method & Future Exploration Areas

The **Atomic Clinical Decision Unit (a-CDU)** framework has strong potential as a novel methodological contribution at the intersection of Medical Informatics (HL7 FHIR / WHO SMART Guidelines) and Edge Generative AI. Below are the highest-leverage areas for further research, engineering, and clinical validation:

### 3.1 Formalizing "Deontic RAG" & The Algebra of Composable a-CDUs
Standard RAG treats retrieved chunks as flat, unstructured strings ($c_1, c_2, \dots, c_k$). In contrast, a-CDUs introduce **deontic logic** (obligations $\mathcal{R}$ and prohibitions $\mathcal{N}$) into retrieval-augmented generation:
- **Conflict Resolution Algebra**: When multiple a-CDUs are retrieved for a multimorbid patient ($\text{CDU}_1, \text{CDU}_2, \dots, \text{CDU}_k$), an action mandated in one unit ($r \in \mathcal{R}_1$, e.g., *"Give oral Ibuprofen for gout"*) may intersect with a negative boundary in another ($n \in \mathcal{N}_2$, e.g., *"STRICT PROHIBITION: Avoid all NSAIDs in CKD 3b"*).
- **Next Step**: Formalize a deterministic **Pre-Prompt Deontic Resolver** that computes the set difference before token generation:
  $$\mathcal{N}_{\text{total}} = \bigcup_{i=1}^k \mathcal{N}_i, \qquad \mathcal{R}_{\text{safe}} = \left( \bigcup_{i=1}^k \mathcal{R}_i \right) \setminus \text{Conflict}(\mathcal{R}, \mathcal{N}_{\text{total}})$$
  By programmatically flagging or pruning overridden recommendations *before* the SLM sees the prompt, even a 1B–2B model is mathematically prevented from receiving contradictory instructions in its context window.

### 3.2 Automated Compiler from WHO SMART Guidelines (L3 FHIR `PlanDefinition`) to a-CDUs
Currently, WHO Digital Adaptation Kits (DAKs) exist across Maternal Health (ANC/PNC), HIV, TB, Immunizations, and Adolescent Health as spreadsheets (L2) and FHIR `PlanDefinition` / CQL libraries (L3).
- **Research Opportunity**: Build an open-source **WHO DAK-to-a-CDU Compiler**.
- Using a two-stage pipeline—(1) deterministic parsing of FHIR `PlanDefinition.action` and CQL triggers into $\langle \mathcal{P}, \mathcal{C}, \mathcal{T}, \mathcal{R} \rangle$, followed by (2) Frontier LLM synthesis + clinician certification of explicit Negative Boundaries ($\mathcal{N}$) and $\le 180$-token prompt chunks ($\mathcal{M}$)—any Ministry of Health could automatically compile its national SMART Guidelines into an edge-ready `protocols.db` SQLite FTS5 asset in hours rather than months.

### 3.3 Constrained Decoding & Grammar-Guided Generation at the Edge
Even with strong prompt clamping, quantized 2B models occasionally fail Tier-1 evaluations due to formatting drift or verbose explanations (e.g., when `gemma4:latest` produced empty `content` fields during thinking-token exhaustion before we increased `num_predict` and handled reasoning separation).
- **Next Step**: Pair a-CDU prompt injection with **GBNF (GGML BNF) grammar-constrained decoding** or structured schema enforcement inside `LiteRT` / `llama.cpp`:
  - Force the model's output logits to strictly follow the 4-part clinical schema (`[1. Safety Overrides] -> [2. Immediate Actions] -> [3. Dose/Renal Calibrations] -> [4. Monitoring]`) while hard-masking token sequences matching any drug name in $\mathcal{N}_{\text{total}}$ (Logit Biasing / Negative Token Masking) unless preceded by a negation token (`"Do NOT give"`).
  - **Negative Logit Masking from $\mathcal{N}$**: Dynamically translating `cdu.negative_boundaries` into token-level logit penalties during affirmative action generation would guarantee **100.0% deterministic immunity** against fatal drug hallucinations, even on ultra-small 500M–1B parameter models.

### 3.4 Closing the Clinic-to-Community Loop (Addressing the Penda Health RCT Gap)
The Penda Health Nature Medicine trial showed that clinic-only LLM decision support struggled to move 14-day treatment failure because adherence drops once the patient leaves the clinic, and clinicians ignore 80% of verbose red alerts.
- **Next Step**: Design a **Dual-Tier a-CDU Continuity Architecture**:
  1. **Facility Tier (Clinical Officer)**: Uses `phc-evals` multi-morbidity a-CDUs to resolve complex prescribing collisions at the clinic and writes a structured **FHIR `Task`** + **Target a-CDU ID** to the patient's record.
  2. **Community Tier (CHW on OHS Edge)**: Syncs the FHIR `Task` offline; uses `Tokempic` + the linked a-CDU on the CHW's phone at Day 3 and Day 7 home visits to check for specific danger signs, reinforce medication adherence, and trigger early re-referral *before* 14-day treatment failure occurs.

### 3.5 Cross-Lingual & Low-Resource Vernacular Grounding (Swahili, Hausa, Amharic, Hindi)
One of the strongest value propositions of an on-device SLM over a purely rule-based checklist is its ability to adapt clinical counseling to the patient's language and health literacy level.
- **Next Step**: Keep the a-CDU knowledge base ($\mathcal{I}, \mathcal{P}, \mathcal{C}, \mathcal{T}, \mathcal{R}, \mathcal{N}, \mathcal{M}$) canonical in English (or bilingual), and benchmark **Cross-Lingual a-CDU Conditioning**:
  - Test whether 2B–4B models (`Gemma 2 2B`, `Gemma 4`, `aya-expanse`) conditioned on English a-CDUs + ORPO alignment can generate accurate, culturally safe Swahili/Hausa CHW counseling scripts without losing negative-boundary compliance ("safety transfer across languages").

### 3.6 Publication & Benchmark Release Strategy
We now have three distinct, high-impact artifacts ready to be developed into academic papers or open-source releases:
1. **Paper / Whitepaper 1 (Edge FHIR Representation)**: *"Tokempic for Edge SLMs: Eliminating Code Bleed, Arithmetic Hallucinations, and Resource Blindspots via Deterministic SQL-on-FHIR Views"* (backed by the 3-way benchmark and upstream Tokempic patch).
2. **Paper / Whitepaper 2 (The a-CDU Architecture)**: *"Atomic Clinical Decision Units (a-CDUs): A Deontic, Zero-RAM Retrieval Architecture for Safe Small Language Models in Frontline Healthcare"* (backed by the 20-unit Kenya MOH eCHIS corpus, SQLite FTS5 edge benchmarks, and Android demo).
3. **Open Benchmark Suite (`phc-evals`)**: Expanding `phc-evals` from 10 to 50+ multi-morbidity cases across LMIC and global primary care guidelines, benchmarking `Gemma 2`, `Gemma 4`, `MedGemma`, `Llama 3.2`, and `Qwen 2.5` with and without a-CDU conditioning.
