package org.openhealthstack.edgeslm

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * JVM / Desktop implementation of [EdgeLlmEngine] for local workstation development,
 * developer emulators, and CI/CD evaluation test harnesses.
 *
 * Connects directly to local Ollama runtime (`http://127.0.0.1:11434`) or local llama.cpp server.
 */
class JvmLlamaCppEngine(
    override val modelId: String = "gemma2:2b-instruct-q4_K_M",
    private val apiBaseUrl: String = "http://127.0.0.1:11434"
) : EdgeLlmEngine {

    override var isLoaded: Boolean = true
        private set

    override var activeProvider: ExecutionProvider = ExecutionProvider.CPU
        private set

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .build()

    override suspend fun loadModel(
        modelPath: String,
        preferredProvider: ExecutionProvider
    ) = withContext(Dispatchers.IO) {
        activeProvider = preferredProvider
        isLoaded = true
    }

    override suspend fun generateCompletion(
        prompt: String,
        config: GenerationConfig
    ): CompletionResult = withContext(Dispatchers.IO) {
        val payload = JSONObject().apply {
            put("model", modelId)
            put("prompt", prompt)
            put("stream", false)
            put("options", JSONObject().apply {
                put("temperature", config.temperature)
                put("top_k", config.topK)
                put("seed", config.randomSeed)
                put("num_predict", config.maxTokens)
            })
        }

        val request = Request.Builder()
            .url("$apiBaseUrl/api/generate")
            .post(payload.toString().toRequestBody("application/json".toMediaType()))
            .build()

        val startTime = System.currentTimeMillis()
        httpClient.newCall(request).execute().use { response ->
            val elapsedMs = System.currentTimeMillis() - startTime
            if (!response.isSuccessful) {
                throw IllegalStateException("Ollama API failed with HTTP ${response.code}: ${response.body?.string()}")
            }
            val bodyStr = response.body?.string() ?: "{}"
            val json = JSONObject(bodyStr)
            val text = json.optString("response", "")

            val promptTokens = json.optInt("prompt_eval_count", countTokens(prompt))
            val evalTokens = json.optInt("eval_count", countTokens(text))
            val evalDurationNs = json.optLong("eval_duration", 0L)
            val tokensPerSec = if (evalDurationNs > 0) (evalTokens.toDouble() / (evalDurationNs / 1e9)) else 0.0

            val metrics = ModelMetrics(
                timeToFirstTokenMs = (json.optLong("prompt_eval_duration", 0L) / 1e6).toLong(),
                totalInferenceTimeMs = elapsedMs,
                promptTokens = promptTokens,
                completionTokens = evalTokens,
                tokensPerSecond = tokensPerSec,
                peakMemoryMb = 1800.0,
                executionProvider = activeProvider
            )

            CompletionResult(text = text, metrics = metrics)
        }
    }

    override fun streamCompletion(
        prompt: String,
        config: GenerationConfig
    ): Flow<String> = flow {
        val payload = JSONObject().apply {
            put("model", modelId)
            put("prompt", prompt)
            put("stream", true)
            put("options", JSONObject().apply {
                put("temperature", config.temperature)
                put("top_k", config.topK)
            })
        }

        val request = Request.Builder()
            .url("$apiBaseUrl/api/generate")
            .post(payload.toString().toRequestBody("application/json".toMediaType()))
            .build()

        httpClient.newCall(request).execute().use { response ->
            val source = response.body?.source() ?: return@use
            while (!source.exhausted()) {
                val line = source.readUtf8Line() ?: break
                if (line.isNotBlank()) {
                    val obj = JSONObject(line)
                    emit(obj.optString("response", ""))
                }
            }
        }
    }.flowOn(Dispatchers.IO)

    override fun countTokens(text: String): Int {
        return (text.length / 3.8).toInt().coerceAtLeast(1)
    }

    override suspend fun unloadModel() = withContext(Dispatchers.IO) {
        // No-op for local proxy
    }
}
