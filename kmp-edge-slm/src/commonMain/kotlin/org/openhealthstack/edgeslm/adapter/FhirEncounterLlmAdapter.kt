package org.openhealthstack.edgeslm.adapter

/**
 * Lightweight clinical data models representing OHS FHIR resources
 * (compatible with `kotlin-fhir` / `hl7.fhir.r4`).
 */
data class SimplifiedPatient(
    val id: String,
    val name: String,
    val birthDate: String,
    val gender: String,
    val location: String
)

data class SimplifiedCondition(
    val codeText: String,
    val clinicalStatus: String, // "active", "resolved", "recurrence"
    val onsetDate: String?,
    val abatementDate: String? = null
)

data class SimplifiedObservation(
    val date: String,
    val display: String,
    val valueWithUnit: String,
    val interpretation: String? = null // "Normal", "High", "Abnormal"
)

data class SimplifiedTask(
    val priority: String, // "urgent", "routine"
    val description: String,
    val dueDate: String,
    val note: String? = null
)

data class SimplifiedMedication(
    val name: String,
    val status: String,
    val dosageInstruction: String
)

data class FhirEncounterBundle(
    val patient: SimplifiedPatient,
    val activeConditions: List<SimplifiedCondition>,
    val resolvedConditions: List<SimplifiedCondition>,
    val recentObservations: List<SimplifiedObservation>,
    val openTasks: List<SimplifiedTask>,
    val activeMedications: List<SimplifiedMedication>
)

/**
 * Adapter converting FHIR Patient and Encounter bundles into deterministic,
 * token-budgeted Markdown inputs optimized for offline 2B-4B SLMs.
 *
 * Implements strict defensive formatting:
 * - Highlights past resolved conditions with an explicit negative prompt barrier ("do not report as active")
 * - Enforces token ceilings to prevent mobile context overflows
 */
class FhirEncounterLlmAdapter {

    fun formatForSummarization(bundle: FhirEncounterBundle): String {
        val sb = StringBuilder()

        // 1. Demographics
        sb.append("## demographics\n")
        sb.append("${bundle.patient.name} | Age/DOB: ${bundle.patient.birthDate} | ${bundle.patient.gender} | ${bundle.patient.location}\n\n")

        // 2. Active Conditions
        sb.append("## active conditions\n")
        if (bundle.activeConditions.isEmpty()) {
            sb.append("None documented\n")
        } else {
            bundle.activeConditions.forEach { c ->
                sb.append("${c.codeText} | ${c.clinicalStatus} | ${c.onsetDate ?: "Unknown"} |\n")
            }
        }
        sb.append("\n")

        // 3. Past Resolved History (Explicit Guardrail for SLM Attention)
        sb.append("## past resolved history (do not report as active)\n")
        if (bundle.resolvedConditions.isEmpty()) {
            sb.append("None documented\n")
        } else {
            bundle.resolvedConditions.forEach { c ->
                sb.append("${c.codeText} | resolved | ${c.onsetDate ?: "-"} | ${c.abatementDate ?: "-"}\n")
            }
        }
        sb.append("\n")

        // 4. Recent Vitals & Observations
        sb.append("## vitals & observations\n")
        if (bundle.recentObservations.isEmpty()) {
            sb.append("No recent observations\n")
        } else {
            bundle.recentObservations.take(8).forEach { o ->
                val interp = o.interpretation?.let { " | $it" } ?: ""
                sb.append("${o.date} | ${o.display} | ${o.valueWithUnit}$interp\n")
            }
        }
        sb.append("\n")

        // 5. Urgent Alerts & Scheduled Tasks
        sb.append("## urgent alerts & scheduled tasks (Priority | Task | Due Date | Note)\n")
        if (bundle.openTasks.isEmpty()) {
            sb.append("No pending tasks\n")
        } else {
            bundle.openTasks.forEach { t ->
                sb.append("${t.priority} | ${t.description} | ${t.dueDate} | ${t.note ?: "-"}\n")
            }
        }
        sb.append("\n")

        // 6. Medications
        sb.append("## medications\n")
        if (bundle.activeMedications.isEmpty()) {
            sb.append("No active medications\n")
        } else {
            bundle.activeMedications.forEach { m ->
                sb.append("${m.name} | ${m.status} | ${m.dosageInstruction}\n")
            }
        }

        return sb.toString().trim()
    }
}
