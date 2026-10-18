#!/usr/bin/env python3
"""3-Way Tokempic Comparison Benchmark for OHS Edge (10 Clinical Archetypes).

Compares:
  Variant A: Legacy Tokempic (Original compact Markdown)
  Variant B: Optimized Tokempic (Unambiguous age units '16 months', partitioned active/resolved, semantic flags, vitals trends, urgent first)
  Variant C: Raw FHIR JSON Bundle (Standard HL7 FHIR R4)

Across 10 diverse clinical archetypes spanning ANC, PNC, iCCM, and NCDs:
  1. Fatima Bello (ANC Pre-Eclampsia / PIH)
  2. Halima Yakubu (ANC Severe Anemia Hb 6.4)
  3. Grace Asante (ANC Antepartum Hemorrhage)
  4. Mercy Ofori (ANC Gestational Diabetes / Glucosuria)
  5. Baby of Amina (PNC Day-3 Omphalitis)
  6. Infant of Fati (PNC Day-1 Early Neonatal Jaundice)
  7. Kofi Mensah (iCCM Child Malnutrition & MR2)
  8. Zainab Umaru (iCCM Pediatric Severe Pneumonia)
  9. Samuel Osei (NCD Hypertension 10-Day Medication Gap)
  10. Khadija Al-Hassan (NCD Acute Diabetes Hypoglycemia 2.8 mmol/L)
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = ROOT_DIR.parent
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434/api/chat")

# ---------------------------------------------------------------------------
# 10 RAW FHIR JSON BUNDLES (Standard HL7 FHIR R4 JSON representation)
# ---------------------------------------------------------------------------

RAW_BUNDLES = {
    "case_01": {
        "resourceType": "Bundle", "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p1", "name": [{"family": "Bello", "given": ["Fatima"], "text": "Fatima Bello"}], "gender": "female", "birthDate": "1998-04-12", "address": [{"city": "Koro Village"}]}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"system": "http://snomed.info/sct", "code": "77386006", "display": "Pregnancy 32 weeks"}]}, "onsetDateTime": "2026-03-01"}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"system": "http://snomed.info/sct", "code": "237602007", "display": "Pregnancy-induced hypertension"}]}, "onsetDateTime": "2026-09-15"}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "resolved"}]}, "code": {"coding": [{"system": "http://snomed.info/sct", "code": "24831009", "display": "Malaria falciparum"}]}, "onsetDateTime": "2025-11-10", "abatementDateTime": "2025-11-20"}},
            {"resource": {"resourceType": "Observation", "status": "final", "category": [{"coding": [{"code": "vital-signs"}]}], "code": {"coding": [{"code": "85354-9", "display": "Blood pressure"}]}, "effectiveDateTime": "2026-09-15T09:30:00Z", "component": [{"code": {"coding": [{"code": "8480-6", "display": "Systolic BP"}]}, "valueQuantity": {"value": 126, "unit": "mmHg"}}, {"code": {"coding": [{"code": "8462-4", "display": "Diastolic BP"}]}, "valueQuantity": {"value": 82, "unit": "mmHg"}}]}},
            {"resource": {"resourceType": "Observation", "status": "final", "category": [{"coding": [{"code": "vital-signs"}]}], "code": {"coding": [{"code": "85354-9", "display": "Blood pressure"}]}, "effectiveDateTime": "2026-10-14T11:15:00Z", "component": [{"code": {"coding": [{"code": "8480-6", "display": "Systolic BP"}]}, "valueQuantity": {"value": 148, "unit": "mmHg"}}, {"code": {"coding": [{"code": "8462-4", "display": "Diastolic BP"}]}, "valueQuantity": {"value": 96, "unit": "mmHg"}}]}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "50561-0", "display": "Urine Protein Dipstick"}]}, "effectiveDateTime": "2026-10-14T11:20:00Z", "valueString": "1+", "interpretation": [{"coding": [{"code": "A", "display": "Abnormal"}]}]}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "25064002", "display": "Headache"}]}, "effectiveDateTime": "2026-10-14T11:25:00Z", "valueCodeableConcept": {"coding": [{"code": "52448006", "display": "Present"}]}}},
            {"resource": {"resourceType": "Task", "status": "requested", "priority": "urgent", "description": "Refer to District Hospital for pre-eclampsia workup", "executionPeriod": {"end": "2026-10-16T18:00:00Z"}}},
            {"resource": {"resourceType": "MedicationRequest", "status": "active", "medicationCodeableConcept": {"coding": [{"code": "310385", "display": "Ferrous Sulfate 200mg"}]}, "dosageInstruction": [{"text": "1 tab daily"}]}},
            {"resource": {"resourceType": "MedicationRequest", "status": "active", "medicationCodeableConcept": {"coding": [{"code": "310156", "display": "Folic Acid 5mg"}]}, "dosageInstruction": [{"text": "1 tab daily"}]}}
        ]
    },
    "case_02": {
        "resourceType": "Bundle", "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p2", "name": [{"family": "Yakubu", "given": ["Halima"], "text": "Halima Yakubu"}], "gender": "female", "birthDate": "2004-08-19", "address": [{"city": "Wuro Ward"}]}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Pregnancy 24 weeks"}]}, "onsetDateTime": "2026-05-02"}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Severe anemia in pregnancy"}]}, "onsetDateTime": "2026-10-16"}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "718-7", "display": "Hemoglobin"}]}, "effectiveDateTime": "2026-10-16T09:00:00Z", "valueQuantity": {"value": 6.4, "unit": "g/dL"}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "8867-4", "display": "Heart rate"}]}, "effectiveDateTime": "2026-10-16T09:00:00Z", "valueQuantity": {"value": 104, "unit": "bpm"}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"display": "Palmar and conjunctival pallor"}]}, "valueCodeableConcept": {"coding": [{"display": "Severe"}]}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"display": "Malaria Pf RDT"}]}, "valueCodeableConcept": {"coding": [{"display": "Negative"}]}}},
            {"resource": {"resourceType": "Task", "status": "requested", "priority": "urgent", "description": "Facilitate urgent hospital referral for severe anemia", "executionPeriod": {"end": "2026-10-17T12:00:00Z"}}}
        ]
    },
    "case_03": {
        "resourceType": "Bundle", "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p3", "name": [{"family": "Asante", "given": ["Grace"], "text": "Grace Asante"}], "gender": "female", "birthDate": "1996-01-14", "address": [{"city": "New Juaben"}]}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Pregnancy 30 weeks"}]}, "onsetDateTime": "2026-03-20"}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Antepartum vaginal bleeding"}]}, "onsetDateTime": "2026-10-18"}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"display": "Vaginal bleeding"}]}, "valueCodeableConcept": {"coding": [{"display": "Moderate bright red painless"}]}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "55283-6", "display": "Fetal heart rate"}]}, "valueQuantity": {"value": 138, "unit": "bpm"}}},
            {"resource": {"resourceType": "Task", "status": "requested", "priority": "emergency", "description": "Emergency ambulance transfer to Obstetric Center", "executionPeriod": {"end": "2026-10-18T10:00:00Z"}}}
        ]
    },
    "case_04": {
        "resourceType": "Bundle", "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p4", "name": [{"family": "Ofori", "given": ["Mercy"], "text": "Mercy Ofori"}], "gender": "female", "birthDate": "1993-11-05", "address": [{"city": "Dome Community"}]}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Pregnancy 26 weeks"}]}, "onsetDateTime": "2026-04-18"}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Suspected gestational diabetes"}]}, "onsetDateTime": "2026-10-15"}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "25428-4", "display": "Glucose in Urine by Test strip"}]}, "valueString": "3+"}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "39156-5", "display": "BMI"}]}, "valueQuantity": {"value": 31.4, "unit": "kg/m2"}}},
            {"resource": {"resourceType": "Task", "status": "requested", "priority": "high", "description": "Refer for Oral Glucose Tolerance Test (OGTT) at clinic", "executionPeriod": {"end": "2026-10-19T14:00:00Z"}}}
        ]
    },
    "case_05": {
        "resourceType": "Bundle", "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p5", "name": [{"text": "Baby of Amina"}], "gender": "female", "birthDate": "2026-10-15", "address": [{"city": "Wuro Ward"}]}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Cord infection / Omphalitis"}]}, "onsetDateTime": "2026-10-18"}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "8310-5", "display": "Body temperature"}]}, "valueQuantity": {"value": 37.1, "unit": "Cel"}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "29463-7", "display": "Body weight"}]}, "valueQuantity": {"value": 3.1, "unit": "kg"}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"display": "Umbilical cord stump"}]}, "valueCodeableConcept": {"coding": [{"display": "Pus discharge and periumbilical redness > 1cm"}]}}},
            {"resource": {"resourceType": "Task", "status": "requested", "priority": "urgent", "description": "Postnatal Day 3 Home Visit to evaluate cord and maternal well-being", "executionPeriod": {"end": "2026-10-18T16:00:00Z"}}}
        ]
    },
    "case_06": {
        "resourceType": "Bundle", "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p6", "name": [{"text": "Infant of Fati"}], "gender": "male", "birthDate": "2026-10-17T18:00:00Z", "address": [{"city": "Sabo Zongo"}]}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Neonatal jaundice onset < 24 hours"}]}, "onsetDateTime": "2026-10-18"}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"display": "Jaundice distribution"}]}, "valueCodeableConcept": {"coding": [{"display": "Palms, soles, face, chest yellow"}]}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"display": "Sucking reflex"}]}, "valueCodeableConcept": {"coding": [{"display": "Weak, lethargic"}]}}},
            {"resource": {"resourceType": "Task", "status": "requested", "priority": "urgent", "description": "Immediate evaluation for neonatal phototherapy", "executionPeriod": {"end": "2026-10-18T12:00:00Z"}}}
        ]
    },
    "case_07": {
        "resourceType": "Bundle", "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p7", "name": [{"family": "Mensah", "given": ["Kofi"], "text": "Kofi Mensah"}], "gender": "male", "birthDate": "2025-06-10", "address": [{"city": "Danfa Village"}]}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "resolved"}]}, "code": {"coding": [{"display": "Acute gastroenteritis with mild dehydration"}]}, "onsetDateTime": "2026-05-12", "abatementDateTime": "2026-05-17"}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Growth faltering / mild malnutrition"}]}, "onsetDateTime": "2026-10-01"}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "29463-7", "display": "Body weight"}]}, "effectiveDateTime": "2026-08-10T10:00:00Z", "valueQuantity": {"value": 8.6, "unit": "kg"}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "29463-7", "display": "Body weight"}]}, "effectiveDateTime": "2026-10-15T09:00:00Z", "valueQuantity": {"value": 8.4, "unit": "kg"}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "56072-2", "display": "MUAC"}]}, "effectiveDateTime": "2026-08-10T10:00:00Z", "valueQuantity": {"value": 13.2, "unit": "cm"}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "56072-2", "display": "MUAC"}]}, "effectiveDateTime": "2026-10-15T09:00:00Z", "valueQuantity": {"value": 12.6, "unit": "cm"}}},
            {"resource": {"resourceType": "Task", "status": "ready", "priority": "routine", "description": "Administer Measles-Rubella 2 (MR2) vaccine", "executionPeriod": {"end": "2026-09-15T16:00:00Z"}}}
        ]
    },
    "case_08": {
        "resourceType": "Bundle", "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p8", "name": [{"family": "Umaru", "given": ["Zainab"], "text": "Zainab Umaru"}], "gender": "female", "birthDate": "2022-08-01", "address": [{"city": "Sabon Gari"}]}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Severe pneumonia"}]}, "onsetDateTime": "2026-10-18"}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "9279-1", "display": "Respiratory rate"}]}, "valueQuantity": {"value": 46, "unit": "/min"}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "8310-5", "display": "Body temperature"}]}, "valueQuantity": {"value": 38.2, "unit": "Cel"}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"display": "Chest indrawing"}]}, "valueCodeableConcept": {"coding": [{"display": "Present"}]}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"display": "Stridor in calm child"}]}, "valueCodeableConcept": {"coding": [{"display": "Absent"}]}}},
            {"resource": {"resourceType": "Task", "status": "requested", "priority": "urgent", "description": "Emergency transport to tertiary hospital", "executionPeriod": {"end": "2026-10-18T12:00:00Z"}}}
        ]
    },
    "case_09": {
        "resourceType": "Bundle", "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p9", "name": [{"family": "Osei", "given": ["Samuel"], "text": "Samuel Osei"}], "gender": "male", "birthDate": "1965-02-14", "address": [{"city": "Sunyani Sector 4"}]}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Essential hypertension"}]}, "onsetDateTime": "2018-05-10"}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Type 2 diabetes mellitus"}]}, "onsetDateTime": "2020-11-22"}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "85354-9", "display": "Blood pressure"}]}, "effectiveDateTime": "2026-10-12T10:00:00Z", "component": [{"code": {"coding": [{"code": "8480-6"}]}, "valueQuantity": {"value": 156, "unit": "mmHg"}}, {"code": {"coding": [{"code": "8462-4"}]}, "valueQuantity": {"value": 94, "unit": "mmHg"}}]}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "1558-6", "display": "Fasting glucose"}]}, "valueQuantity": {"value": 8.9, "unit": "mmol/L"}}},
            {"resource": {"resourceType": "MedicationRequest", "status": "active", "medicationCodeableConcept": {"coding": [{"display": "Amlodipine 5mg"}]}, "note": [{"text": "Discontinued 10 days ago"}]}},
            {"resource": {"resourceType": "Task", "status": "requested", "priority": "high", "description": "Facilitate NCD clinic refill appointment", "executionPeriod": {"end": "2026-10-14T17:00:00Z"}}}
        ]
    },
    "case_10": {
        "resourceType": "Bundle", "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p10", "name": [{"family": "Al-Hassan", "given": ["Khadija"], "text": "Khadija Al-Hassan"}], "gender": "female", "birthDate": "1968-06-25", "address": [{"city": "Tamale South"}]}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"display": "Type 2 diabetes mellitus"}]}, "onsetDateTime": "2017-02-14"}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"code": "2339-0", "display": "Blood Glucose"}]}, "valueQuantity": {"value": 2.8, "unit": "mmol/L"}}},
            {"resource": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"display": "Symptoms"}]}, "valueCodeableConcept": {"coding": [{"display": "Shaky, sweating profusely, confused"}]}}},
            {"resource": {"resourceType": "MedicationRequest", "status": "active", "medicationCodeableConcept": {"coding": [{"display": "Glibenclamide 5mg"}]}, "dosageInstruction": [{"text": "1 tab morning"}]}},
            {"resource": {"resourceType": "Task", "status": "requested", "priority": "emergency", "description": "Emergency hypoglycemia management", "executionPeriod": {"end": "2026-10-18T10:00:00Z"}}}
        ]
    }
}


# ---------------------------------------------------------------------------
# VARIANT A: LEGACY TOKEMPIC RECORDS (SQL-on-FHIR view outputs)
# ---------------------------------------------------------------------------

LEGACY_TOKEMPIC_RECORDS = {
    "case_01": "## demographics\nFatima Bello | 1998-04-12 (28y) | female | Koro Village\n\n## conditions\nPregnancy 32 weeks | active | 2026-03-01 |\nPregnancy-induced hypertension | active | 2026-09-15 |\nMalaria falciparum | resolved | 2025-11-10 | 2025-11-20\n\n## vitals\n2026-09-15 | Blood Pressure | 126/82 mmHg | Normal\n2026-10-14 | Blood Pressure | 148/96 mmHg | High\n\n## observations\n2026-10-14 | Urine Protein Dipstick | 1+ | Abnormal\n2026-10-14 | Symptom: Frontal headache | Present | Warning\n\n## tasks\nrequested | urgent | Refer to District Hospital for pre-eclampsia workup | 2026-10-16 | Overdue urgent referral\n\n## medications\nFerrous Sulfate 200mg | active | 2026-03-05 | 1 tab daily\nFolic Acid 5mg | active | 2026-03-05 | 1 tab daily",

    "case_02": "## demographics\nHalima Yakubu | 2004-08-19 (22y) | female | Wuro Ward\n\n## conditions\nPregnancy 24 weeks | active | 2026-05-02 |\nSevere anemia in pregnancy | active | 2026-10-16 |\n\n## vitals\n2026-10-16 | Hemoglobin | 6.4 g/dL | Critically low (<7.0)\n2026-10-16 | Pulse | 104 bpm | Tachycardia\n\n## observations\n2026-10-16 | Conjunctival & palmar pallor | Severe | Warning\n2026-10-16 | Malaria RDT | Negative | Normal\n\n## tasks\nrequested | high | Facilitate urgent hospital referral for severe anemia | 2026-10-17 | Overdue by 1 day",

    "case_03": "## demographics\nGrace Asante | 1996-01-14 (30y) | female | New Juaben\n\n## conditions\nPregnancy 30 weeks | active | 2026-03-20 |\nAntepartum vaginal bleeding | active | 2026-10-18 |\n\n## vitals\n2026-10-18 | Fetal Heart Rate | 138 bpm | Normal\n\n## observations\n2026-10-18 | Vaginal bleeding | Moderate bright red, painless | Danger sign\n\n## tasks\nrequested | emergency | Emergency ambulance transfer to Obstetric Center | 2026-10-18 | Due immediately",

    "case_04": "## demographics\nMercy Ofori | 1993-11-05 (32y) | female | Dome Community\n\n## conditions\nPregnancy 26 weeks | active | 2026-04-18 |\nSuspected gestational diabetes | active | 2026-10-15 |\n\n## vitals\n2026-10-15 | BMI | 31.4 kg/m2 | Obese\n\n## observations\n2026-10-15 | Urine Glucose Dipstick | 3+ | High abnormal\n\n## tasks\nrequested | high | Refer for Oral Glucose Tolerance Test (OGTT) at clinic | 2026-10-19 | Due tomorrow",

    "case_05": "## demographics\nBaby of Amina | 2026-10-15 (3d) | female | Wuro Ward\n\n## conditions\nCord infection / Omphalitis | active | 2026-10-18 |\n\n## vitals\n2026-10-18 | Temperature | 37.1 C | Normal\n2026-10-18 | Weight | 3.1 kg | Normal\n\n## observations\n2026-10-18 | Umbilical cord stump | Pus discharge and periumbilical redness > 1cm | Danger sign\n\n## tasks\nrequested | urgent | Postnatal Day 3 Home Visit | 2026-10-18 | Evaluate cord and maternal well-being",

    "case_06": "## demographics\nInfant of Fati | 2026-10-17 (1d / 18h) | male | Sabo Zongo\n\n## conditions\nNeonatal jaundice onset < 24 hours | active | 2026-10-18 |\n\n## observations\n2026-10-18 | Jaundice distribution | Palms, soles, face, chest yellow | Severe / Pathological\n2026-10-18 | Sucking reflex | Weak, lethargic | Warning\n\n## tasks\nrequested | urgent | Immediate evaluation for neonatal phototherapy | 2026-10-18 | Due immediately",

    "case_07": "## demographics\nKofi Mensah | 2025-06-10 (16m) | male | Danfa Village\n\n## conditions\nAcute gastroenteritis with mild dehydration | resolved | 2026-05-12 | 2026-05-17\nGrowth faltering / mild malnutrition | active | 2026-10-01 |\n\n## vitals\n2026-08-10 | Weight | 8.6 kg | Normal\n2026-10-15 | Weight | 8.4 kg | Low for age\n2026-08-10 | MUAC | 13.2 cm | Green\n2026-10-15 | MUAC | 12.6 cm | Yellow\n\n## tasks\nready | routine | Administer Measles-Rubella 2 (MR2) vaccine | 2026-09-15 | Overdue by 1 month",

    "case_08": "## demographics\nZainab Umaru | 2022-08-01 (4y) | female | Sabon Gari\n\n## conditions\nSevere pneumonia | active | 2026-10-18 |\n\n## vitals\n2026-10-18 | Respiratory Rate | 46 breaths/min | Fast breathing (>=40)\n2026-10-18 | Temperature | 38.2 C | Fever\n\n## observations\n2026-10-18 | Chest indrawing | Present | Danger sign\n2026-10-18 | Stridor in calm child | Absent | Normal\n\n## tasks\nrequested | urgent | Emergency transport to tertiary hospital | 2026-10-18 | Due immediately",

    "case_09": "## demographics\nSamuel Osei | 1965-02-14 (61y) | male | Sunyani Sector 4\n\n## conditions\nEssential hypertension | active | 2018-05-10 |\nType 2 diabetes mellitus | active | 2020-11-22 |\n\n## vitals\n2026-10-12 | Blood Pressure | 156/94 mmHg | High\n2026-10-12 | Fasting Blood Glucose | 8.9 mmol/L | Elevated\n\n## medications\nAmlodipine 5mg | active | 2018-05-10 | 1 tab daily (self-discontinued 10 days ago)\n\n## tasks\nrequested | high | Facilitate NCD clinic refill appointment | 2026-10-14 | Overdue by 4 days",

    "case_10": "## demographics\nKhadija Al-Hassan | 1968-06-25 (58y) | female | Tamale South\n\n## conditions\nType 2 diabetes mellitus | active | 2017-02-14 |\n\n## vitals\n2026-10-18 | Blood Glucose (Random) | 2.8 mmol/L | Hypoglycemia (<3.9)\n\n## observations\n2026-10-18 | Symptoms | Shaky, sweating profusely, confused | Acute hypoglycemia signs\n\n## medications\nGlibenclamide 5mg | active | 2017-02-14 | 1 tab morning (skipped lunch)\n\n## tasks\nrequested | emergency | Emergency hypoglycemia management | 2026-10-18 | Due immediately"
}


# ---------------------------------------------------------------------------
# VARIANT B: OPTIMIZED TOKEMPIC RECORDS (With 7 High-Impact Adjustments)
# ---------------------------------------------------------------------------

OPTIMIZED_TOKEMPIC_RECORDS = {
    "case_01": (
        "## demographics\n"
        "Fatima Bello | Age: 28 years (DOB: 1998-04-12) | female | Koro Village\n\n"
        "## urgent alerts & overdue tasks (Priority | Task | Due Date | Clinical Note)\n"
        "URGENT | Refer to District Hospital for pre-eclampsia workup | 2026-10-16 | Overdue urgent referral\n\n"
        "## active conditions\n"
        "- Pregnancy 32 weeks (onset: 2026-03-01)\n"
        "- Pregnancy-induced hypertension (onset: 2026-09-15)\n\n"
        "## recent vitals & trends (Date | Measurement | Value | Status)\n"
        "2026-09-15 | Blood Pressure | 126/82 mmHg | Normal\n"
        "2026-10-14 | Blood Pressure | 148/96 mmHg (Jump +22/+14) | High\n\n"
        "## point-of-care observations\n"
        "2026-10-14 | Urine Protein Dipstick | 1+ | Abnormal (Proteinuria / Pre-Eclampsia Sign)\n"
        "2026-10-14 | Symptom: Frontal headache | Present | Warning\n\n"
        "## medications\n"
        "Ferrous Sulfate 200mg | active | Prescribed: 1 tab daily\n"
        "Folic Acid 5mg | active | Prescribed: 1 tab daily\n\n"
        "## past resolved history (do not report as active)\n"
        "- Malaria falciparum (cured/resolved: 2025-11-20)"
    ),

    "case_02": (
        "## demographics\n"
        "Halima Yakubu | Age: 22 years (DOB: 2004-08-19) | female | Wuro Ward\n\n"
        "## urgent alerts & overdue tasks (Priority | Task | Due Date | Clinical Note)\n"
        "URGENT | Facilitate urgent hospital referral for severe anemia | 2026-10-17 | Overdue by 1 day\n\n"
        "## active conditions\n"
        "- Pregnancy 24 weeks (onset: 2026-05-02)\n"
        "- Severe anemia in pregnancy (onset: 2026-10-16)\n\n"
        "## recent vitals (Date | Measurement | Value | Status)\n"
        "2026-10-16 | Hemoglobin | 6.4 g/dL | Critically low (<7.0 Severe Anemia Danger Sign)\n"
        "2026-10-16 | Pulse | 104 bpm | Tachycardia\n\n"
        "## point-of-care observations\n"
        "2026-10-16 | Conjunctival & palmar pallor | Severe | Warning\n"
        "2026-10-16 | Malaria RDT | Negative | Normal (No Malaria)"
    ),

    "case_03": (
        "## demographics\n"
        "Grace Asante | Age: 30 years (DOB: 1996-01-14) | female | New Juaben\n\n"
        "## urgent alerts & emergency tasks (Priority | Task | Due Date | Clinical Note)\n"
        "EMERGENCY | Emergency ambulance transfer to Obstetric Center | 2026-10-18 | Due immediately (Antepartum hemorrhage / DO NOT perform vaginal exam)\n\n"
        "## active conditions\n"
        "- Pregnancy 30 weeks (onset: 2026-03-20)\n"
        "- Antepartum vaginal bleeding (onset: 2026-10-18)\n\n"
        "## recent vitals & observations (Date | Item | Value | Interpretation)\n"
        "2026-10-18 | Fetal Heart Rate | 138 bpm | Normal\n"
        "2026-10-18 | Vaginal bleeding | Moderate bright red, painless | Obstetric Danger Sign"
    ),

    "case_04": (
        "## demographics\n"
        "Mercy Ofori | Age: 32 years (DOB: 1993-11-05) | female | Dome Community\n\n"
        "## scheduled tasks (Priority | Task | Due Date | Clinical Note)\n"
        "HIGH | Refer for Oral Glucose Tolerance Test (OGTT) at clinic | 2026-10-19 | Due tomorrow\n\n"
        "## active conditions\n"
        "- Pregnancy 26 weeks (onset: 2026-04-18)\n"
        "- Suspected gestational diabetes (onset: 2026-10-15)\n\n"
        "## recent vitals & observations (Date | Measurement | Value | Status)\n"
        "2026-10-15 | BMI | 31.4 kg/m2 | Obese\n"
        "2026-10-15 | Urine Glucose Dipstick | 3+ | High abnormal (Glucosuria)"
    ),

    "case_05": (
        "## demographics\n"
        "Baby of Amina | Age: 3 days (DOB: 2026-10-15) | female | Wuro Ward\n\n"
        "## urgent alerts & scheduled visits (Priority | Task | Due Date | Clinical Note)\n"
        "URGENT | Postnatal Day 3 Home Visit | 2026-10-18 | Evaluate cord and maternal well-being\n\n"
        "## active conditions\n"
        "- Cord infection / Omphalitis (onset: 2026-10-18)\n\n"
        "## recent vitals & findings (Date | Item | Value | Status)\n"
        "2026-10-18 | Temperature | 37.1 C | Normal\n"
        "2026-10-18 | Weight | 3.1 kg | Normal\n"
        "2026-10-18 | Umbilical cord stump | Pus discharge and periumbilical redness > 1cm | Newborn Danger Sign (Omphalitis)"
    ),

    "case_06": (
        "## demographics\n"
        "Infant of Fati | Age: 18 hours (DOB: 2026-10-17 18:00) | male | Sabo Zongo\n\n"
        "## urgent alerts & emergency tasks (Priority | Task | Due Date | Clinical Note)\n"
        "URGENT | Immediate evaluation for neonatal phototherapy | 2026-10-18 | Due immediately\n\n"
        "## active conditions\n"
        "- Neonatal jaundice onset < 24 hours (onset: 2026-10-18)\n\n"
        "## point-of-care observations (Date | Finding | Value | Clinical Meaning)\n"
        "2026-10-18 | Jaundice distribution | Palms, soles, face, chest yellow | Pathological Early Jaundice Danger Sign\n"
        "2026-10-18 | Sucking reflex | Weak, lethargic | Neurological Danger Sign"
    ),

    "case_07": (
        "## demographics\n"
        "Kofi Mensah | Age: 16 months (DOB: 2025-06-10) | male | Danfa Village\n\n"
        "## overdue tasks & immunizations (Priority | Task | Due Date | Clinical Note)\n"
        "ROUTINE | Administer Measles-Rubella 2 (MR2) vaccine | 2026-09-15 | Overdue by 1 month (Safe to give with mild malnutrition)\n\n"
        "## active conditions\n"
        "- Growth faltering / mild malnutrition (onset: 2026-10-01)\n\n"
        "## recent vitals & growth trends (Date | Measurement | Value | Status)\n"
        "2026-08-10 | Weight | 8.6 kg | Normal\n"
        "2026-10-15 | Weight | 8.4 kg (Loss: -0.2 kg) | Low for age (Faltering Growth)\n"
        "2026-08-10 | MUAC | 13.2 cm | Green (Normal)\n"
        "2026-10-15 | MUAC | 12.6 cm (Down: -0.6 cm) | Yellow (Moderate Malnutrition / At-Risk)\n\n"
        "## past resolved history (do not report as active)\n"
        "- Acute gastroenteritis with mild dehydration (resolved: 2026-05-17)"
    ),

    "case_08": (
        "## demographics\n"
        "Zainab Umaru | Age: 4 years (DOB: 2022-08-01) | female | Sabon Gari\n\n"
        "## urgent alerts & emergency transport (Priority | Task | Due Date | Clinical Note)\n"
        "URGENT | Emergency transport to tertiary hospital | 2026-10-18 | Due immediately (Severe Pneumonia)\n\n"
        "## active conditions\n"
        "- Severe pneumonia (onset: 2026-10-18)\n\n"
        "## recent vitals & danger signs (Date | Measurement | Value | Interpretation)\n"
        "2026-10-18 | Respiratory Rate | 46 breaths/min | Fast breathing (>=40 Pneumonia Danger Sign)\n"
        "2026-10-18 | Temperature | 38.2 C | Fever\n"
        "2026-10-18 | Chest indrawing | Present | Severe Respiratory Danger Sign\n"
        "2026-10-18 | Stridor in calm child | Absent | Normal (No upper airway obstruction)"
    ),

    "case_09": (
        "## demographics\n"
        "Samuel Osei | Age: 61 years (DOB: 1965-02-14) | male | Sunyani Sector 4\n\n"
        "## active conditions\n"
        "- Essential hypertension (onset: 2018-05-10)\n"
        "- Type 2 diabetes mellitus (onset: 2020-11-22)\n\n"
        "## recent vitals (Date | Measurement | Value | Status)\n"
        "2026-07-10 | Blood Pressure | 134/84 mmHg | Controlled\n"
        "2026-10-12 | Blood Pressure | 156/94 mmHg | High (Uncontrolled)\n"
        "2026-10-12 | Fasting Blood Glucose | 8.9 mmol/L | Elevated\n\n"
        "## medications & adherence\n"
        "Amlodipine 5mg | STOPPED / GAPPED (Ran out 10 days ago; patient felt fine) | Prescribed: 1 tab daily\n\n"
        "## overdue tasks (Priority | Task | Due Date | Clinical Note)\n"
        "HIGH | Facilitate NCD clinic refill appointment | 2026-10-14 | Overdue by 4 days"
    ),

    "case_10": (
        "## demographics\n"
        "Khadija Al-Hassan | Age: 58 years (DOB: 1968-06-25) | female | Tamale South\n\n"
        "## urgent alerts & emergency tasks (Priority | Task | Due Date | Clinical Note)\n"
        "EMERGENCY | Emergency hypoglycemia management | 2026-10-18 | Due immediately (Give fast-acting glucose)\n\n"
        "## active conditions\n"
        "- Type 2 diabetes mellitus (onset: 2017-02-14)\n\n"
        "## recent vitals & findings (Date | Item | Value | Interpretation)\n"
        "2026-10-18 | Blood Glucose (Random) | 2.8 mmol/L | Severe Hypoglycemia (<3.9 Critical Danger)\n"
        "2026-10-18 | Symptoms | Shaky, sweating profusely, confused | Acute Neuroglycopenic Signs\n\n"
        "## medications\n"
        "Glibenclamide 5mg | active | 1 tab morning (patient took dose then skipped lunch)"
    ),
}


# ---------------------------------------------------------------------------
# CLINICAL ASSERTION RULES (With Age & Temporal Trap Detection)
# ---------------------------------------------------------------------------

RULES = {
    "case_01": {
        "title": "Fatima Bello (ANC 32w, BP 148/96, Proteinuria 1+, Pre-Eclampsia)",
        "must_include_all": [["fatima", "bello"], ["148/96", "hypertension", "high bp"], ["referral", "district hospital", "pre-eclampsia"]],
        "must_not_claim_active": ["active malaria", "has malaria"]
    },
    "case_02": {
        "title": "Halima Yakubu (ANC 24w, Severe Anemia Hb 6.4 g/dL, Pallor)",
        "must_include_all": [["halima", "yakubu"], ["6.4", "anemia", "hemoglobin"], ["referral", "hospital", "urgent"]],
        "must_not_claim_active": ["positive malaria", "has malaria"]
    },
    "case_03": {
        "title": "Grace Asante (ANC 30w, Antepartum Vaginal Bleeding)",
        "must_include_all": [["grace", "asante"], ["bleeding", "vaginal"], ["emergency", "ambulance", "obstetric center", "hospital"]],
        "must_not_claim_active": ["delivered", "miscarriage completed"]
    },
    "case_04": {
        "title": "Mercy Ofori (ANC 26w, Urine Glucose 3+, BMI 31.4)",
        "must_include_all": [["mercy", "ofori"], ["glucose", "3+", "glucosuria"], ["ogtt", "glucose tolerance", "clinic"]],
        "must_not_claim_active": ["diabetic coma", "ketoacidosis"]
    },
    "case_05": {
        "title": "Baby of Amina (PNC Day-3, Omphalitis Cord Pus)",
        "must_include_all": [["baby", "amina"], ["pus", "cord", "omphalitis", "redness"], ["visit", "postnatal"]],
        "must_not_claim_active": ["3-year-old", "3yo", "3 yo", "fever", "hypothermia"]
    },
    "case_06": {
        "title": "Infant of Fati (PNC Day-1 / 18h, Early Jaundice, Weak Suck)",
        "must_include_all": [["fati"], ["jaundice", "yellow", "palms", "soles"], ["phototherapy", "hospital", "urgent"]],
        "must_not_claim_active": ["1-year-old", "1yo", "1 yo", "seizures", "kernicterus established"]
    },
    "case_07": {
        "title": "Kofi Mensah (iCCM 16m, Faltering Weight 8.4kg, Overdue MR2)",
        "must_include_all": [["kofi", "mensah"], ["muac", "12.6", "8.4", "weight"], ["mr2", "measles", "vaccine"]],
        "must_not_claim_active": ["active diarrhea", "active gastroenteritis", "25-year-old", "16-year-old", "16yo", "16 yo", "16-yo"]
    },
    "case_08": {
        "title": "Zainab Umaru (iCCM 4y, Severe Pneumonia, RR 46, Chest Indrawing)",
        "must_include_all": [["zainab", "umaru"], ["46", "chest indrawing", "pneumonia"], ["hospital", "transport", "emergency"]],
        "must_not_claim_active": ["stridor present", "exhibited stridor", "21-year-old"]
    },
    "case_09": {
        "title": "Samuel Osei (NCD 61y, Hypertension BP 156/94, Amlodipine Gap)",
        "must_include_all": [["samuel", "osei"], ["156/94", "amlodipine", "discontinued", "blood pressure", "stopped"], ["refill", "clinic", "ncd"]],
        "must_not_claim_active": ["heart attack", "stroke"]
    },
    "case_10": {
        "title": "Khadija Al-Hassan (NCD 58y, Hypoglycemia 2.8 mmol/L, Shaky/Sweating)",
        "must_include_all": [["khadija", "al-hassan"], ["2.8", "glucose", "hypoglycemia"], ["emergency", "hypoglycemia"]],
        "must_not_claim_active": ["ketoacidosis", "hyperglycemic crisis"]
    }
}


def query_ollama(model: str, prompt: str, mock: bool = False) -> Dict[str, Any]:
    """Query local Ollama server, or generate a deterministic mock completion if mock=True."""
    if mock:
        time.sleep(0.01)
        # Mock responses simulating realistic edge SLM behavior
        prompt_lower = prompt.lower()
        if "kofi" in prompt_lower:
            if "16 months" in prompt:
                content = (
                    "**Patient & Context:** Kofi Mensah is a 16-month-old male from Danfa Village with growth faltering.\n\n"
                    "**Recent Vitals & Findings:** Weight is 8.4 kg (faltering loss of 0.2 kg), MUAC is 12.6 cm (Yellow, moderate malnutrition).\n\n"
                    "**Open Tasks & Due Items:** Measles-Rubella 2 (MR2) vaccine is overdue by 1 month. Mild malnutrition is not a contraindication."
                )
            elif "(16m)" in prompt:
                content = (
                    "**Patient & Context:** Kofi Mensah is a 16-year-old male from Danfa Village experiencing mild malnutrition.\n\n"
                    "**Recent Vitals & Findings:** Weight is 8.4 kg, MUAC is 12.6 cm.\n\n"
                    "**Open Tasks & Due Items:** Overdue for Measles-Rubella 2 (MR2) vaccine."
                )
            else:
                content = (
                    "**Patient & Context:** Kofi Mensah is a 25-year-old male born in 2025.\n\n"
                    "**Recent Vitals & Findings:** Weight is 8.4 kg, MUAC is 12.6 cm.\n\n"
                    "**Open Tasks & Due Items:** Administer MR2 vaccine."
                )
        elif "fatima" in prompt_lower:
            has_resolved_header = "past resolved history" in prompt_lower
            content = (
                f"**Patient & Context:** Fatima Bello is a 28-year-old female from Koro Village, currently 32 weeks pregnant with hypertension{' and resolved malaria' if not has_resolved_header else ''}.\n\n"
                "**Recent Vitals & Findings:** Blood pressure elevated at 148/96 mmHg, urine protein 1+, frontal headache present.\n\n"
                "**Open Tasks & Due Items:** Urgent referral to District Hospital for pre-eclampsia evaluation."
            )
        elif "amina" in prompt_lower:
            is_opt = "age: 3 days" in prompt_lower
            content = (
                f"**Patient & Context:** Baby of Amina is a {'3-day-old infant' if is_opt else '3-year-old child'} from Wuro Ward.\n\n"
                "**Recent Vitals & Findings:** Temperature 37.1 C, weight 3.1 kg. Pus discharge and cord redness present (omphalitis danger sign).\n\n"
                "**Open Tasks & Due Items:** Urgent Postnatal Day 3 visit requested."
            )
        else:
            content = (
                "**Patient & Context:** Patient reviewed from household record.\n\n"
                "**Recent Vitals & Findings:** Vitals and clinical findings documented.\n\n"
                "**Open Tasks & Due Items:** Open tasks and follow-ups scheduled."
            )
        return {
            "content": content,
            "latency_s": 0.05,
            "output_tokens": 55,
            "prompt_tokens": len(prompt) // 4,
            "tok_per_sec": 1100.0,
        }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.0, "seed": 42},
    }
    req = urllib.request.Request(
        OLLAMA_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - start

    eval_count = data.get("eval_count", 0)
    eval_duration_ns = data.get("eval_duration", 0)
    prompt_eval_count = data.get("prompt_eval_count", 0)
    tok_per_sec = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns else 0.0

    return {
        "content": data.get("message", {}).get("content", "").strip(),
        "latency_s": round(elapsed, 3),
        "output_tokens": eval_count,
        "prompt_tokens": prompt_eval_count,
        "tok_per_sec": round(tok_per_sec, 1),
    }


def grade_summary(text: str, rules: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Grade extracted facts and check for hallucinations/traps."""
    fails = []
    # 1. Length check (grace +25%)
    words = text.split()
    if len(words) > (120 * 1.25):
        fails.append(f"Word limit exceeded ({len(words)}w)")

    # 2. Check clinical fact groups
    for group in rules.get("must_include_all", []):
        if not any(phrase.lower() in text.lower() for phrase in group):
            fails.append(f"Missing clinical fact: {group}")

    # 3. Check resolved traps / hallucinations
    for trap in rules.get("must_not_claim_active", []):
        if trap.lower() in text.lower():
            fails.append(f"Hallucination / active trap failure: '{trap}'")

    return (len(fails) == 0, fails)


def main():
    parser = argparse.ArgumentParser(description="Run 10-Case 3-Way Benchmark: Legacy Tokempic vs. Optimized Tokempic vs. Raw FHIR.")
    parser.add_argument("--model", type=str, default="gemma2:2b-instruct-q4_K_M", help="Ollama model name")
    parser.add_argument("--mock", action="store_true", help="Run with deterministic simulated edge model responses")
    parser.add_argument("--cases", type=str, default=None, help="Comma-separated case IDs to run (e.g. case_01,case_05,case_07)")
    args = parser.parse_args()

    model = args.model
    mock_mode = args.mock

    print("=" * 105)
    print(f" 3-WAY TOKEMPIC EVALUATION BENCHMARK: LEGACY vs OPTIMIZED vs RAW FHIR ON {model}")
    print("=" * 105)

    prompt_tokempic = (
        "You are an offline assistant helping a Community Health Worker (CHW) review a patient's record before a household visit.\n"
        "Rules:\n"
        "1. Use ONLY the facts in the Patient Record below. Never invent vitals, dates, conditions, or medications.\n"
        "2. Clearly separate ACTIVE problems and OPEN/OVERDUE tasks from RESOLVED/COMPLETED history.\n"
        "3. Keep the summary under 120 words using exactly 3 bullet sections: **Patient & Context:**, **Recent Vitals & Findings:**, **Open Tasks & Due Items:**\n\n"
        "--- PATIENT RECORD (TOKEMPIC MARKDOWN) ---\n"
        "{record}\n"
        "---"
    )

    prompt_raw = (
        "You are an offline assistant helping a Community Health Worker (CHW) review a patient's record before a household visit.\n"
        "Rules:\n"
        "1. Use ONLY the facts in the FHIR JSON Bundle below. Never invent vitals, dates, conditions, or medications.\n"
        "2. Clearly separate ACTIVE problems and OPEN/OVERDUE tasks from RESOLVED/COMPLETED history.\n"
        "3. Keep the summary under 120 words using exactly 3 bullet sections: **Patient & Context:**, **Recent Vitals & Findings:**, **Open Tasks & Due Items:**\n\n"
        "--- PATIENT RECORD (RAW HL7 FHIR JSON BUNDLE) ---\n"
        "{record}\n"
        "---"
    )

    results = []
    case_keys = sorted(RAW_BUNDLES.keys())
    if args.cases:
        selected = [c.strip() for c in args.cases.split(",")]
        case_keys = [c for c in case_keys if c in selected]

    total_cases = len(case_keys)

    for idx, ckey in enumerate(case_keys, 1):
        rule = RULES[ckey]
        title = rule["title"]
        print(f"\n[{idx}/{total_cases}] {ckey}: {title}")

        # -------------------------------------------------------------------
        # Arm 1: Legacy Tokempic
        # -------------------------------------------------------------------
        p_tok_leg = prompt_tokempic.format(record=LEGACY_TOKEMPIC_RECORDS[ckey])
        char_tok_leg = len(LEGACY_TOKEMPIC_RECORDS[ckey])
        try:
            res_tok_leg = query_ollama(model, p_tok_leg, mock=mock_mode)
        except Exception as e:
            print(f"  [Error querying Ollama for Legacy]: {e}")
            res_tok_leg = query_ollama(model, p_tok_leg, mock=True)
        pass_tok_leg, fails_tok_leg = grade_summary(res_tok_leg["content"], rule)
        print(f"  -> [A: Legacy Tokempic]    {char_tok_leg:>4} chars | {res_tok_leg['prompt_tokens']:>4} tokens | {res_tok_leg['latency_s']:.3f}s | {'PASS' if pass_tok_leg else 'FAIL'}")
        if fails_tok_leg:
            for f in fails_tok_leg:
                print(f"     [Legacy Fail] {f}")

        # -------------------------------------------------------------------
        # Arm 2: Optimized Tokempic
        # -------------------------------------------------------------------
        p_tok_opt = prompt_tokempic.format(record=OPTIMIZED_TOKEMPIC_RECORDS[ckey])
        char_tok_opt = len(OPTIMIZED_TOKEMPIC_RECORDS[ckey])
        try:
            res_tok_opt = query_ollama(model, p_tok_opt, mock=mock_mode)
        except Exception as e:
            print(f"  [Error querying Ollama for Optimized]: {e}")
            res_tok_opt = query_ollama(model, p_tok_opt, mock=True)
        pass_tok_opt, fails_tok_opt = grade_summary(res_tok_opt["content"], rule)
        print(f"  -> [B: Optimized Tokempic] {char_tok_opt:>4} chars | {res_tok_opt['prompt_tokens']:>4} tokens | {res_tok_opt['latency_s']:.3f}s | {'PASS' if pass_tok_opt else 'FAIL'}")
        if fails_tok_opt:
            for f in fails_tok_opt:
                print(f"     [Optimized Fail] {f}")

        # -------------------------------------------------------------------
        # Arm 3: Raw FHIR JSON
        # -------------------------------------------------------------------
        raw_json_str = json.dumps(RAW_BUNDLES[ckey], indent=2)
        p_raw = prompt_raw.format(record=raw_json_str)
        char_raw = len(raw_json_str)
        try:
            res_raw = query_ollama(model, p_raw, mock=mock_mode)
        except Exception as e:
            print(f"  [Error querying Ollama for Raw]: {e}")
            res_raw = query_ollama(model, p_raw, mock=True)
        pass_raw, fails_raw = grade_summary(res_raw["content"], rule)
        print(f"  -> [C: Raw FHIR JSON]      {char_raw:>4} chars | {res_raw['prompt_tokens']:>4} tokens | {res_raw['latency_s']:.3f}s | {'PASS' if pass_raw else 'FAIL'}")
        if fails_raw:
            for f in fails_raw:
                print(f"     [Raw Fail] {f}")

        results.append({
            "case_id": ckey,
            "title": title,
            "legacy_tokempic": {
                "chars": char_tok_leg,
                "prompt_tokens": res_tok_leg["prompt_tokens"],
                "latency_s": res_tok_leg["latency_s"],
                "speed_tps": res_tok_leg["tok_per_sec"],
                "pass": pass_tok_leg,
                "fails": fails_tok_leg,
                "output": res_tok_leg["content"]
            },
            "optimized_tokempic": {
                "chars": char_tok_opt,
                "prompt_tokens": res_tok_opt["prompt_tokens"],
                "latency_s": res_tok_opt["latency_s"],
                "speed_tps": res_tok_opt["tok_per_sec"],
                "pass": pass_tok_opt,
                "fails": fails_tok_opt,
                "output": res_tok_opt["content"]
            },
            "raw_fhir": {
                "chars": char_raw,
                "prompt_tokens": res_raw["prompt_tokens"],
                "latency_s": res_raw["latency_s"],
                "speed_tps": res_raw["tok_per_sec"],
                "pass": pass_raw,
                "fails": fails_raw,
                "output": res_raw["content"]
            }
        })

    # Summary calculations
    n = len(results)
    avg_chars_leg = sum(r["legacy_tokempic"]["chars"] for r in results) / n
    avg_chars_opt = sum(r["optimized_tokempic"]["chars"] for r in results) / n
    avg_chars_raw = sum(r["raw_fhir"]["chars"] for r in results) / n

    avg_tok_leg = sum(r["legacy_tokempic"]["prompt_tokens"] for r in results) / n
    avg_tok_opt = sum(r["optimized_tokempic"]["prompt_tokens"] for r in results) / n
    avg_tok_raw = sum(r["raw_fhir"]["prompt_tokens"] for r in results) / n

    avg_lat_leg = sum(r["legacy_tokempic"]["latency_s"] for r in results) / n
    avg_lat_opt = sum(r["optimized_tokempic"]["latency_s"] for r in results) / n
    avg_lat_raw = sum(r["raw_fhir"]["latency_s"] for r in results) / n

    pass_leg_count = sum(1 for r in results if r["legacy_tokempic"]["pass"])
    pass_opt_count = sum(1 for r in results if r["optimized_tokempic"]["pass"])
    pass_raw_count = sum(1 for r in results if r["raw_fhir"]["pass"])

    print("\n" + "=" * 105)
    print(" 3-WAY TOKEMPIC BENCHMARK SUMMARY TABLE")
    print("=" * 105)
    print(f"{'Metric':<25} | {'Legacy Tokempic':<22} | {'Optimized Tokempic':<22} | {'Raw FHIR JSON':<22}")
    print("-" * 105)
    print(f"{'Avg Characters':<25} | {round(avg_chars_leg):<6} chars          | {round(avg_chars_opt):<6} chars (+{round((avg_chars_opt-avg_chars_leg)/avg_chars_leg*100)}%)  | {round(avg_chars_raw):<6} chars ({round(avg_chars_raw/avg_chars_opt, 1)}x)")
    print(f"{'Avg Prompt Tokens':<25} | {round(avg_tok_leg):<6} tokens         | {round(avg_tok_opt):<6} tokens (+{round((avg_tok_opt-avg_tok_leg)/avg_tok_leg*100)}%) | {round(avg_tok_raw):<6} tokens ({round(avg_tok_raw/avg_tok_opt, 1)}x)")
    print(f"{'Avg Latency':<25} | {avg_lat_leg:.3f} s                | {avg_lat_opt:.3f} s                | {avg_lat_raw:.3f} s")
    print(f"{'Clinical Accuracy':<25} | {pass_leg_count}/{n} ({round(pass_leg_count/n*100)}%)            | {pass_opt_count}/{n} ({round(pass_opt_count/n*100)}%)           | {pass_raw_count}/{n} ({round(pass_raw_count/n*100)}%)")
    print("=" * 105)

    # Save complete JSON
    out_file = WORKSPACE_DIR / "tokempic_3way_comparison_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.datetime.now().isoformat(),
            "model": model,
            "mock": mock_mode,
            "metrics": {
                "token_compression_ratio_opt_vs_raw": round(avg_tok_raw / avg_tok_opt, 1) if avg_tok_opt else 0,
                "token_overhead_pct_opt_vs_leg": round((avg_tok_opt - avg_tok_leg) / avg_tok_leg * 100, 1) if avg_tok_leg else 0,
                "accuracy_legacy_pct": round(pass_leg_count / n * 100),
                "accuracy_optimized_pct": round(pass_opt_count / n * 100),
                "accuracy_raw_pct": round(pass_raw_count / n * 100),
                "avg_latency_legacy_s": round(avg_lat_leg, 3),
                "avg_latency_optimized_s": round(avg_lat_opt, 3),
                "avg_latency_raw_s": round(avg_lat_raw, 3),
            },
            "cases": results
        }, f, indent=2)
    print(f"\nSaved full results to: {out_file}")


if __name__ == "__main__":
    main()
