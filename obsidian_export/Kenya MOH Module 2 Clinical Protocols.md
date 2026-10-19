---
type: clinical-protocols
topic: Kenya MOH Module 2 Maternal and Newborn Health Decision Units
created: 2026-10-18
last_processed: 2026-10-18
status: active
tags:
  - health-tech/ohs
  - health-tech/fhir
  - ai/edge-llm
  - ai/mini-rag
  - global-health/chw
  - kenya-moh/echis
---

# Kenya MOH Module 2: Maternal and Newborn Health (MNH)
## Certified Clinical Decision Units for Edge Mini-RAG

> [!ABSTRACT] Executive Summary
> Complete reference dataset of **20 certified Clinical Decision Units (CDUs)** derived from the [[Kenya MOH]] Community Health Promoter (CHP) Technical Training Manual (Module 2: Maternal & Newborn Health) and eCHIS (MoH 514 / MoH 515). Optimized for offline [[SQLite]] FTS5 retrieval and [[Gemma]] 2 2B closed-book prompt injection on [[OHS Edge]].

## Document Index & Relations
- **Master Index:** [[00_Index_OHS_Edge_Mini_RAG]]
- **Product Requirements:** [[OHS Edge Mini-RAG PRD]]
- **Pipeline Architecture:** [[Clinical Mini-RAG Pipeline Specification]]
- **Evals & Alignment Spec:** [[Clinical Protocol Metadata Extraction and Evals Specification]]
- **Dataset JSON:** `chw-edge-evals/dataset/kenya_moh_mnh_protocols.json`

---

## Protocol Overview Table

| ID | Domain | Topic | Target Cohort | Key Safety / Negative Boundary |
| :--- | :--- | :--- | :--- | :--- |
| `MNH-01` | ANC | ANC Booking & 8-Contact Schedule | Pregnant (All) | No planned home delivery or TBA referral |
| `MNH-02` | ANC | Hypertension & Pre-Eclampsia | GA $\ge 20$w | **Strictly no home antihypertensives or MgSO4** |
| `MNH-03` | ANC | Antepartum Hemorrhage (APH) | GA $\ge 20$w | **NEVER perform digital vaginal exam** |
| `MNH-04` | ANC | Maternal Anemia & IFAS | Pregnant (All) | No tea/coffee/milk with iron; refer severe pallor |
| `MNH-05` | ANC | Malaria in Pregnancy (IPTp-SP) | Pregnant (All) | **NEVER give SP in 1st trimester or with Bactrim** |
| `MNH-06` | ANC | Premature Rupture of Membranes (PROM) | GA $\ge 20$w | **No vaginal exams; no home antibiotics** |
| `MNH-07` | Labor | Individual Birth Plan (BPCR) | GA $\ge 20$w | No unverified transport or home delivery plan |
| `MNH-08` | Labor | Labor Signs vs. False Labor & Escort | GA $\ge 37$w | **Never give traditional labor herbs ('kaloba')** |
| `MNH-09` | Labor | Imminent / Unavoidable Home Delivery | In Labor | **NEVER pull cord to deliver placenta; delayed clamp** |
| `MNH-10` | PNC | Postnatal Care (PNC) Schedule | Postpartum | Never delay Visit 1 beyond 48 hours |
| `MNH-11` | PNC | Postpartum Hemorrhage (PPH) | Postpartum | **Fundal massage + breastfeed; NEVER pack vagina** |
| `MNH-12` | PNC | Puerperal Sepsis (Infection) | Postpartum | **No paracetamol alone; NEVER douche or insert herbs** |
| `MNH-13` | PNC | Maternal Postpartum Mental Health | Postpartum | No dismissals as spiritual weakness; supervise infant |
| `MNH-14` | Newborn | Immediate Thermal Care & Hypothermia | Neonate (0-28d) | **Do NOT bathe $< 24\text{h}$; no hot stones/jikos** |
| `MNH-15` | Newborn | Cord Care with 7.1% Chlorhexidine | Neonate (0-28d) | **ABSOLUTE PROHIBITION: no cow dung, ash, or herbs** |
| `MNH-16` | Newborn | Kangaroo Mother Care (Low Birth Weight) | Weight $< 2.5\text{kg}$ | Continuous KMC; no separation; no hot water bottles |
| `MNH-17` | Newborn | Severe Neonatal Sepsis (Danger Signs) | Neonate (0-28d) | **Emergency transfer; no home antibiotics** |
| `MNH-18` | Newborn | Omphalitis (Cord Infection with Pus) | Neonate (0-28d) | Immediate referral; 7.1% chlorhexidine; no cow dung |
| `MNH-19` | Newborn | Pathological Neonatal Jaundice | Neonate (0-28d) | **Do NOT place in burning sun; refer phototherapy** |
| `MNH-20` | Newborn | Exclusive Breastfeeding & Latch | Infant (0-6m) | **NO prelacteal feeds (no water, sugar, honey, tea)** |

---

## Detailed Clinical Decision Units

### Cluster 1: Antenatal Care & Danger Signs

#### `KENYA-MOH-MNH-01`: ANC Booking & 8-Contact Schedule
> [!NOTE] Source Authority
> Kenya MOH CHP Technical Manual - Module 2 (MoH 514 / eCHIS ANC-01)  
> *"Every pregnant woman in the community must be registered in MoH 514 and supported to attend at least 8 ANC contacts at a health facility. Contact 1 should occur within the first 12 weeks of pregnancy."*

- **Criteria:** All pregnant women residing in the community unit.
- **Danger Signs:** Missed booking past 16 weeks; $>6$ weeks overdue for scheduled contact.
- **Mandated Actions:** Register in MoH 514; counsel on 8-contact schedule (<12w, 20w, 26w, 30w, 34w, 36w, 38w, 40w); promote skilled facility delivery.
- **Negative Boundaries:** Do not endorse planned home delivery or unregistered traditional birth attendants (TBAs).

#### `KENYA-MOH-MNH-02`: Hypertension & Suspected Pre-Eclampsia
> [!NOTE] Source Authority
> Kenya MOH CHP Technical Manual - Module 2 (MoH 514 / eCHIS ANC-04)  
> *"Elevated blood pressure (systolic >= 140 mmHg or diastolic >= 90 mmHg) after 20 weeks gestation is abnormal. If accompanied by severe headache, visual disturbances, epigastric pain, or proteinuria, it is pre-eclampsia and requires immediate hospital referral."*

> [!DANGER] Danger Signs (Red Flags)
> Severe frontal headache not relieved by simple analgesics, visual disturbances (flashes, blur, double vision), severe epigastric/upper abdominal pain, facial/hand edema, convulsions.

> [!CHECK] Mandated CHW Actions
> Immediate emergency referral to Level 4 Hospital / CEmoNC facility. Position patient comfortably on her left side during transport. Mobilize community transport fund.

> [!WARNING] Strict Negative Boundaries & Prohibitions
> **STRICTLY FORBIDDEN:** Do not prescribe or administer oral or injectable antihypertensives at home (no nifedipine, labetalol, hydralazine). Do not attempt parenteral magnesium sulfate injection. Prohibit home herbal sedatives or remedies.

#### `KENYA-MOH-MNH-03`: Antepartum Hemorrhage (Vaginal Bleeding)
> [!NOTE] Source Authority
> Kenya MOH CHP Technical Manual - Module 2 (MoH 514 / eCHIS ANC-05)  
> *"Any vaginal bleeding after 20 weeks gestation is an obstetric emergency. Digital vaginal examination must NEVER be performed by a community health worker or traditional attendant as it can precipitate torrential fatal hemorrhage from placenta previa."*

> [!DANGER] Danger Signs
> Painless bright red bleeding (placenta previa) or severe uterine pain with dark bleeding (abruption); rapid weak pulse, cold extremities, pallor (shock).

> [!WARNING] Absolute Prohibition
> **ABSOLUTE CONTRAINDICATION: NEVER perform a digital vaginal examination (PV exam) or allow anyone to examine the cervix.** Do not pack the vagina with cloth or cotton. Withhold oral food/drink in case urgent surgery/anesthesia is needed.

#### `KENYA-MOH-MNH-04`: Maternal Anemia & IFAS
> [!NOTE] Source Authority
> Kenya MOH CHP Technical Manual - Module 2 (MoH 514 / eCHIS ANC-02)
- **Criteria:** Pale conjunctiva/palms, fatigue, or breathlessness.
- **Mandated Actions:** Daily Iron and Folic Acid Supplementation (IFAS); dietary counseling with vitamin C; refer severe pallor for facility Hb testing.
- **Negative Boundaries:** Do not take iron with tea, coffee, or milk (inhibits absorption). Do not manage severe anemia at home.

#### `KENYA-MOH-MNH-05`: Fever & Malaria in Pregnancy (IPTp-SP)
> [!NOTE] Source Authority
> Kenya MOH CHP Technical Manual - Module 2 (MoH 514 / eCHIS ANC-06)
- **Criteria:** Fever (Temp $\ge 37.5^\circ\text{C}$) or malaria prevention.
- **Mandated Actions:** Verify daily LLIN use. Track monthly IPTp-SP doses starting at 13 weeks (minimum 3 doses 1 month apart). Refer fever for mRDT.
- **Negative Boundaries:** **NEVER administer IPTp-SP in the first trimester (<13 weeks). NEVER administer SP if taking Cotrimoxazole (Bactrim) prophylaxis.**

#### `KENYA-MOH-MNH-06`: Premature Rupture of Membranes (PROM)
> [!NOTE] Source Authority
> Kenya MOH CHP Technical Manual - Module 2 (MoH 514 / eCHIS ANC-07)
- **Criteria:** Gush or continuous trickling of fluid before labor contractions.
- **Mandated Actions:** Urgent facility transfer. Apply clean sanitary pad. Note time leakage began. Place in knee-chest position if cord prolapse is visible.
- **Negative Boundaries:** **FORBIDDEN: Do not perform vaginal examination. Do not insert anything into vagina.**

---

### Cluster 2: Birth Preparedness & Delivery Triage

#### `KENYA-MOH-MNH-07`: Individual Birth Plan (BPCR)
- **Criteria:** All pregnant women at $\ge 20$ weeks gestation (finalize by 28–32w).
- **Mandated Actions:** Complete 5-point birth plan in MoH 514: 1) Chosen facility; 2) Birth companion; 3) Emergency transport driver contact; 4) Savings fund; 5) Potential blood donor. Gather newborn warmth kit.
- **Negative Boundaries:** Do not endorse planned home births or unverified transport arrangements.

#### `KENYA-MOH-MNH-08`: Labor Signs vs. False Labor & Facility Escort
- **Criteria:** Gestation $\ge 37$ weeks with labor contractions.
- **Mandated Actions:** Differentiate true labor (regular, tightening, bloody show) from false labor. Immediately activate transport and escort woman to facility with MoH 216 card.
- **Negative Boundaries:** **STRICTLY FORBIDDEN: Do not administer traditional labor-accelerating herbs ('kaloba' / uterine stimulants).** Do not delay facility transfer.

#### `KENYA-MOH-MNH-09`: Imminent / Unavoidable Home Delivery
- **Criteria:** Head crowning visible; delivery unavoidable before transport.
- **Mandated Actions:** Clean hands. Support head gently without pulling. Dry baby immediately. Place skin-to-skin on mother's chest. Tie cord at 2cm and 5cm with clean ties; cut with sterile blade. Put baby to breast immediately. Escort dyad to facility.
- **Negative Boundaries:** **ABSOLUTELY FORBIDDEN: NEVER pull the cord to deliver placenta (uterine inversion risk). Never insert hands into birth canal.**

---

### Cluster 3: Maternal Postnatal Care (PNC)

#### `KENYA-MOH-MNH-10`: Postnatal Care (PNC) Schedule
- **Criteria:** All recently delivered mothers and newborns.
- **Mandated Actions:** Conduct 4 scheduled PNC visits: Visit 1 ($< 24\text{h}$), Visit 2 (Day 3 / 48–72h), Visit 3 (Day 7–14), Visit 4 (6 weeks).
- **Negative Boundaries:** Never delay the first PNC visit beyond 48 hours post-delivery.

#### `KENYA-MOH-MNH-11`: Postpartum Hemorrhage (PPH) Triage
> [!DANGER] Obstetric Emergency
> Soaking $>2$ large sanitary pads in 1 hour, continuous trickling, dizziness, pallor, rapid weak pulse, boggy soft uterus.

- **Mandated Actions:** EMERGENCY transfer to Level 4 Hospital. Vigorously massage uterine fundus until firm. Put baby to breast immediately (oxytocin release). Elevate legs 30 cm, keep warm.
- **Negative Boundaries:** **STRICTLY FORBIDDEN: NEVER pack the vagina with cloth or cotton (conceals internal bleeding). Never give herbal remedies.**

#### `KENYA-MOH-MNH-12`: Puerperal Sepsis (Postpartum Infection)
- **Criteria:** Postpartum fever (Temp $\ge 38.0^\circ\text{C}$) or foul vaginal discharge within 6 weeks.
- **Danger Signs:** Foul-smelling lochia, severe lower abdominal tenderness, chills/rigors, septic shock.
- **Mandated Actions:** Urgent referral to Level 4 Hospital for IV antibiotics. Encourage hydration. Strict hand hygiene.
- **Negative Boundaries:** Do not treat with simple analgesics alone. **NEVER douche or wash inside vagina.**

#### `KENYA-MOH-MNH-13`: Maternal Postpartum Mental Health
- **Criteria:** Persistent low mood, crying, extreme anxiety, or detachment from newborn within 1 year.
- **Danger Signs:** Thoughts of self-harm or harming baby, hallucinations, hearing voices, complete refusal to touch infant.
- **Mandated Actions:** Empathetic counseling. Mobilize family support for infant care. Immediate escorted referral for psychiatric evaluation if self-harm or psychosis suspected. Keep infant supervised.
- **Negative Boundaries:** Do not dismiss as spiritual weakness or laziness. Never leave infant unmonitored.

---

### Cluster 4: Essential Newborn Care & Newborn Red Flags

#### `KENYA-MOH-MNH-14`: Immediate Newborn Thermal Care & Hypothermia
- **Criteria:** All newborns (0–28 days).
- **Danger Signs:** Axillary temp $< 36.5^\circ\text{C}$, cold extremities, weak suckling, blue lips, temp $> 37.5^\circ\text{C}$.
- **Mandated Actions:** Immediate skin-to-skin contact on mother's bare chest. Warm hat, socks, blanket. Breastfeed every 2 hours. Refer if cold persists after 1 hour.
- **Negative Boundaries:** **ABSOLUTELY FORBIDDEN: Do NOT bathe within first 24 hours of life. NEVER use hot water bottles or charcoal jikos near baby (burns & carbon monoxide).**

#### `KENYA-MOH-MNH-15`: Cord Care with 7.1% Chlorhexidine
- **Criteria:** Daily cord care for all newborns until healed.
- **Mandated Actions:** Wash hands with soap. Apply 7.1% Chlorhexidine gel to cord stump and base once daily for 7 days. Keep exposed to air. Fold diaper below umbilicus.
- **Negative Boundaries:** **ABSOLUTE PROHIBITION: NEVER apply cow dung, ash, soot, cooking oil, breast milk, saliva, or traditional herbs to the cord. Do NOT bandage tightly or pull stump.**

#### `KENYA-MOH-MNH-16`: Kangaroo Mother Care (Low Birth Weight <2.5kg)
- **Criteria:** Stable infant with birth weight $< 2,500\text{g}$ or preterm.
- **Danger Signs:** Weight $< 2,000\text{g}$, breathing pauses $>20\text{s}$, inability to feed, persistent hypothermia.
- **Mandated Actions:** Continuous skin-to-skin KMC in upright frog position on chest. Warm cap and wrap. Feed expressed breast milk every 2 hours. Weekly weight tracking.
- **Negative Boundaries:** Do not isolate baby from mother. Never give non-breastmilk liquids.

#### `KENYA-MOH-MNH-17`: Severe Neonatal Sepsis (Systemic Danger Signs)
> [!DANGER] Neonatal Medical Emergency
> Inability to feed/suckle, convulsions/fits, fast breathing $\ge 60\text{/min}$, severe chest indrawing, grunting, lethargy/unconsciousness, hypothermia ($<36.5^\circ\text{C}$) or fever ($>37.5^\circ\text{C}$).

- **Mandated Actions:** MEDICAL EMERGENCY. Immediate transfer to hospital newborn unit. Keep skin-to-skin warm during transit. Sips of breast milk if swallowing.
- **Negative Boundaries:** **STRICTLY FORBIDDEN: Do NOT administer antibiotics at home. Never force-feed a convulsing or unconscious infant.**

#### `KENYA-MOH-MNH-18`: Omphalitis (Severe Cord Infection)
- **Criteria:** Umbilical redness spreading to abdominal skin, pus, or foul odor.
- **Danger Signs:** Redness $>1\text{cm}$ around cord base, pus discharge, tenderness, fever, lethargy.
- **Mandated Actions:** Refer IMMEDIATELY to hospital for systemic antibiotics. Clean gently with clean water and apply 7.1% chlorhexidine. Counsel family against harmful traditional concoctions.
- **Negative Boundaries:** Never apply cow dung, ash, or herbs. Do NOT squeeze or bandage.

#### `KENYA-MOH-MNH-19`: Neonatal Jaundice (Hyperbilirubinemia)
- **Criteria:** Yellow discoloration of skin or eyes in newborn.
- **Danger Signs:** Jaundice appearing within first 24 hours of life; yellow palms and soles; dark urine/pale stool; high-pitched cry/lethargy (kernicterus risk).
- **Mandated Actions:** Urgent hospital referral for phototherapy/bilirubin testing. Feed frequently (every 2 hours) to clear bilirubin.
- **Negative Boundaries:** **STRICTLY FORBIDDEN: Do NOT place in direct burning sunlight (severe sunburn & dehydration without curing jaundice). Never give glucose water or herbal tea.**

#### `KENYA-MOH-MNH-20`: Exclusive Breastfeeding (EBF) & Latch Support
- **Criteria:** All infants 0–6 months of age.
- **Mandated Actions:** Initiate within 1 hour of birth. Feed golden colostrum. Ensure good attachment (mouth wide open, lower lip curled outward, chin on breast). Feed on demand 8–12 times in 24 hours. Give ONLY breast milk for 6 months.
- **Negative Boundaries:** **STRICTLY FORBIDDEN: NO prelacteal feeds (no water, sugar, honey, tea, animal milk, butter) — introduces lethal pathogens and destroys infant gut flora. No bottles or artificial teats.**
