package org.openhealthstack.edgeslm

import kotlinx.coroutines.flow.Flow

/**
 * Universal Kotlin Multiplatform abstraction layer for offline Edge Small Language Models (SLMs).
 *
 * Implemented on Android via Google MediaPipe GenAI / LiteRT (.task bundles),
 * and on JVM/Desktop via llama.cpp GGUF bindings or local proxy.
 */
interface EdgeLlmEngine {

    /**
     * Unique identifier for the currently loaded model (e.g. "gemma-2-2b-it-cpu-int4").
     */
    val modelId: String

    /**
     * Whether the weights are active in memory and ready for immediate inference.
     */
    val isLoaded: Boolean

    /**
     * Active hardware delegate being utilized.
     */
    val activeProvider: ExecutionProvider

    /**
     * Asynchronously loads the model into device memory with the specified delegate.
     *
     * @param modelPath Absolute filesystem path to the .task or .gguf model file
     * @param preferredProvider Desired hardware delegate (GPU, NPU, or CPU)
     * @throws IllegalStateException if device does not meet RAM requirements (>1.8GB free)
     */
    suspend fun loadModel(
        modelPath: String,
        preferredProvider: ExecutionProvider = ExecutionProvider.CPU
    )

    /**
     * Executes non-streaming completion. Ideal for clinical visit summarization and
     * structured patient record synthesis.
     *
     * @param prompt Fully constructed prompt including system instructions and encounter data
     * @param config Generation hyper-parameters (temperature, top_k, max_tokens)
     * @return Completed text along with runtime latency and token-speed telemetry
     */
    suspend fun generateCompletion(
        prompt: String,
        config: GenerationConfig = GenerationConfig()
    ): CompletionResult

    /**
     * Streams tokens as they are decoded by the edge engine. Ideal for live CHW chat/guideline QA.
     *
     * @param prompt Fully constructed prompt
     * @param config Generation hyper-parameters
     * @return Coroutine Flow emitting partial token strings as they arrive
     */
    fun streamCompletion(
        prompt: String,
        config: GenerationConfig = GenerationConfig()
    ): Flow<String>

    /**
     * Returns approximate token count for budgeting against edge context window (typically 2048-4096 tokens).
     */
    fun countTokens(text: String): Int

    /**
     * Explicitly unloads weights from RAM and releases GPU/NPU contexts.
     * Crucial on 3GB RAM Android devices to prevent Out-Of-Memory (OOM) kill.
     */
    suspend fun unloadModel()
}
