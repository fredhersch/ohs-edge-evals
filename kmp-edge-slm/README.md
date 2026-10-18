# OHS Edge SLM Kotlin Multiplatform (KMP) Architecture

Universal, offline Kotlin Multiplatform library for running Small Language Models (SLMs, 1B–4B parameters) directly inside Open Health Stack Android & desktop applications.

## Architecture Overview

```
                      +---------------------------------------+
                      |       OHS Android / CHW App           |
                      |   (e.g., ANC / iCCM Care Workflows)   |
                      +-------------------+-------------------+
                                          |
                      +-------------------v-------------------+
                      |       FhirEncounterLlmAdapter         |
                      |   (Converts FHIR resources into       |
                      |    token-budgeted clinical prompts)   |
                      +-------------------+-------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                           EdgeLlmEngine (KMP Common)                              |
|   suspend fun generateCompletion(prompt, config): CompletionResult               |
|   fun streamCompletion(prompt, config): Flow<String>                             |
+-----------------------------------------+-----------------------------------------+
                                          |
                  +-----------------------+-----------------------+
                  |                                               |
+-----------------v------------------+         +------------------v-----------------+
|   androidMain (AndroidLiteRt)      |         |     jvmMain (JvmLlamaCppEngine)    |
|   - Google MediaPipe Tasks GenAI   |         |   - Local llama.cpp / GGUF JNI     |
|   - LiteRT runtime (.bin / .task)  |         |   - Local Ollama dev proxy         |
|   - NPU / GPU / CPU INT4 delegates |         |   - Workstation & CI test harness  |
|   - RAM guardrails (<1.8GB cap)    |         +------------------------------------+
+------------------------------------+
```

## Key Modules

| Path | Target | Description |
|---|---|---|
| `commonMain/kotlin/.../EdgeLlmEngine.kt` | Common | Unified interface for non-streaming & streaming inference, hardware selection, and token counting. |
| `commonMain/kotlin/.../ExecutionProvider.kt` | Common | Hardware delegates (`CPU`, `GPU`, `NPU`) and telemetry metrics (`timeToFirstTokenMs`, `tokensPerSecond`, `peakMemoryMb`). |
| `commonMain/kotlin/.../FhirEncounterLlmAdapter.kt` | Common | Bridges OHS FHIR data (`Patient`, `Condition`, `Observation`, `Task`) into deterministic Markdown with explicit negative barriers. |
| `androidMain/kotlin/.../AndroidLiteRtLlmEngine.kt` | Android | Direct Google MediaPipe GenAI / LiteRT bindings for Gemma-2-2B INT4 `.task` models with GPU/NPU acceleration. |
| `jvmMain/kotlin/.../JvmLlamaCppEngine.kt` | JVM / Desktop | Workstation engine communicating with local Ollama (`http://localhost:11434`) or llama.cpp for rapid developer iteration. |

## Quickstart (Android)

```kotlin
// 1. Initialize Android LiteRT Engine
val engine: EdgeLlmEngine = AndroidLiteRtLlmEngine(context = applicationContext)
engine.loadModel("/data/user/0/org.ohs.chw/files/gemma-2-2b-it-int4.task")

// 2. Format FHIR Encounter into SLM Prompt
val adapter = FhirEncounterLlmAdapter()
val clinicalPrompt = adapter.formatForSummarization(encounterBundle)

// 3. Generate Offline Summary
val result = engine.generateCompletion(
    prompt = clinicalPrompt,
    config = GenerationConfig(temperature = 0.0f, maxTokens = 150)
)

println("Clinical Summary: ${result.text}")
println("Inference Speed: ${result.metrics.tokensPerSecond} tokens/sec")
println("TTFT: ${result.metrics.timeToFirstTokenMs} ms")
```

## Low-Bandwidth & Hardware Requirements

- **Minimum Android Version**: Android 8.0 (API 26)
- **RAM Threshold**: Minimum 3GB physical device RAM (INT4 quantized model occupies ~1.4GB in memory).
- **Execution Target**: Cortex-A53/A55 octa-core CPU fallback or Qualcomm Adreno / Hexagon NPU where available.
