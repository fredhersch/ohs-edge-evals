package org.openhealthstack.edgeslm

/**
 * Hardware execution delegates supported across mobile and desktop runtimes.
 */
enum class ExecutionProvider {
    /** CPU fallback - works universally across all Android devices and dev machines */
    CPU,
    /** GPU delegate (OpenCL / Vulkan / Metal) - high throughput on mid/high-tier chipsets */
    GPU,
    /** Dedicated NPU (Qualcomm Hexagon / MediaTek APU / Google Tensor TPU) */
    NPU
}

/**
 * Model quantization scheme supported for offline edge deployment.
 */
enum class QuantizationType {
    INT4,
    INT8,
    FP16
}

/**
 * Runtime telemetry metrics returned after each edge LLM inference call.
 */
data class ModelMetrics(
    val timeToFirstTokenMs: Long,
    val totalInferenceTimeMs: Long,
    val promptTokens: Int,
    val completionTokens: Int,
    val tokensPerSecond: Double,
    val peakMemoryMb: Double,
    val executionProvider: ExecutionProvider
)

/**
 * Inference parameters tuned for deterministic clinical summarization.
 */
data class GenerationConfig(
    val maxTokens: Int = 256,
    val temperature: Float = 0.0f,
    val topK: Int = 40,
    val randomSeed: Int = 42,
    val stopSequences: List<String> = listOf("<end_of_turn>", "<eos>", "\n\n\n")
)

/**
 * Result of a model generation call with output text and telemetry metrics.
 */
data class CompletionResult(
    val text: String,
    val metrics: ModelMetrics
)
