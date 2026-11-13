# MineArena 1.0 — Final Architecture V4.1

## Manifest-Driven, Context-Adaptive Physics-Informed Cognitive Patient Digital Twin

Problem Statement: Personalized Post-Discharge Deterioration Monitor

Objective: Build an intelligent, personalized patient monitoring and recovery platform that understands each patient's clinical context, continuously analyzes physiological behavior, reconstructs a virtual physiological state using a textual manifest, predicts future physiological changes using PINN-ODEs, verifies its intelligence through a trustworthy layer, and provides evidence-based recommendations to clinicians and patients.

The architecture has seven specialized experts, two knowledge bases, a manifest-driven PINN-ODE digital twin, trustworthy intelligence, and a human-supervised decision system.

# 1. Final complete architecture

## Complete System Architecture

Context-adaptive · Manifest-driven · Physics-informed · Trustworthy

#### LAYER 1 — DATA SOURCES

MATLAB Virtual Wearable

HR, RR, SpO₂, temperature, physiological scenarios

BIDMC Dataset

Real HR, RR and SpO₂ recordings

Synthea Clinical Registry

Patient records and clinical history

Patient Recovery Inputs

Activities, symptoms, medication reports and tasks

#### LAYER 2 — SECURE COMBINED GATEWAY

Patient identity verification

Authentication & authorization

FHIR validation

Integrity & replay protection

Signal quality monitoring

Patient-aware load balancing

Adaptive 5/10/15s windows

Missingness & artifact handling

#### HOT PATH

FastAPI

Real-time processing

Immediate safety checks

Anomaly detection

Priority notification

#### COLD PATH

HAPI FHIR R4

Patient clinical records

Original observations

Longitudinal history

Clinical reports

#### LAYER 3 — PATIENT CONTEXT INTELLIGENCE

Patient Knowledge Base

Patient ID as retrieval key

Medical history

Conditions & procedures

Prescriptions & allergies

Discharge & recovery plan

Shared Clinical Knowledge Base

Clinical context and rule-based retrieval

Clinical knowledge

Physiological relationships

Encoded tacit knowledge

Recovery & safety protocols

### Expert 1 — Patient Context Expert

Identifies the patient using Patient ID, retrieves the patient record, understands what the patient has undergone, and determines applicable clinical context.

Context Output

Condition · Procedure · Recovery phase · Relevant knowledge · Personalization · Unknown information

#### LAYER 4 — PHYSIOLOGICAL EXPERT INTELLIGENCE

Expert 2 — HR

Cardiovascular intelligenceSkills + applicable tacit knowledge

Expert 3 — RR

Respiratory intelligenceSkills + applicable tacit knowledge

Expert 4 — SpO₂

Oxygenation intelligenceSkills + applicable tacit knowledge

Expert 5 — Temperature

Thermoregulatory intelligenceSkills + applicable tacit knowledge

Shared Physiological Knowledge

Context-conditioned relationships, rules, mental models and physiological constraints

Clinical Scoring & Personalized Baseline

Partial NEWS2 · Baseline deviation · Persistence · Cross-vital evidence

#### LAYER 5 — VIRTUAL PHYSIOLOGICAL REPRESENTATION

### Textual Physiological State Manifest

Machine-readable virtual state — no images or anatomical models

Observed physiological state

Personalized baseline state

Physiological relationships

Expert evidence references

Applicable ODE configuration

Estimated model parameters

Missingness & uncertainty

State checkpoint & version

Only opaque patient/session identity and a context reference are retained. Full patient history remains in the Patient KB.

#### LAYER 6 — PHYSICS-INFORMED DIGITAL TWIN

Manifest

Virtual physiological state

Patient Context

Relevant numerical context features

Context-Adaptive Vector Encoder

264-dimensional feature representation with availability masks

Initial State Estimation

Reconstruct estimated current physiology

Parameter Estimation

Context-conditioned physiological parameters

### Hybrid PINN-ODE Core

Mechanistic Physiological ODEs

Applicable physiological relationships

Learned Neural Residual Dynamics

Learn dynamics not captured by simplified equations

Differentiable ODE Solver

Continuous physiological state evolution

State Reconciliation & Forecast Decoder

Observed state · Estimated state · Predicted trajectories · Uncertainty

5 min

Primary

15 min

Secondary

30 min

Experimental

Feedback loop: new observations → manifest update → state reconciliation → revised forecast.

#### LAYER 7 — TRUSTWORTHY INTELLIGENCE

Uncertainty Engine

Measurement, parameter and prediction uncertainty

Counterfactual Engine

Manifest branching and evidence robustness

Trust Engine

Source, knowledge and model reliability

Evidence Engine

Grounding, provenance and deduplication

Physiological Consistency

Equation applicability and plausible bounds

Model Validity Gate

OOD detection, eligibility and abstention

#### LAYER 8 — HYBRID DECISION INTELLIGENCE

Evidence-Constrained Decision System

Patient context + Clinical scoring + Expert evidence + Baseline deviation + Verified forecasts + Uncertainty + Counterfactual robustness

Independent Clinical Safety Supervisor

Direct hot-path input · Mandatory escalation floor · No neural dependency

Watch

Review

Urgent

Structured clinical recommendation, supporting evidence and required human action

#### LAYER 9 — ACTION & RECOVERY INTELLIGENCE

Expert 6 — Medication & Intervention

Prescribed care, clinical review options, preparation and clinician-controlled intervention

Expert 7 — Patient Recovery

Daily activities, approved exercises, symptoms, recovery milestones and progress

Both experts receive relevant patient context directly. Neither autonomously prescribes or authorizes treatment.

#### LAYER 10 — HUMAN INTERACTION & RECORDS

Clinician Command Center

Live vitals, twin, expert evidence, alerts, forecasts and clinical review

Patient Recovery Assistant

Daily recovery, approved care plan, reminders and symptom check-in

Hospital Record Interface

FHIR observations, clinical reports and longitudinal history

Evaluation & Security Console

Simulation, replay, benchmarking, data quality and security audit

CROSS-CUTTING GOVERNANCE

Privacy · Cybersecurity · Clinical safety · Patient isolation · Human oversight · Evidence provenance · Performance · Auditability

# 2. Patient Knowledge Base and Shared Clinical Knowledge Base

This is the final knowledge architecture.

We have two distinct knowledge bases because patient-specific facts and general clinical knowledge serve different purposes.

## 2.1 Patient Knowledge Base — Patient KB

The Patient KB stores or references all relevant information about an individual patient.

Primary lookup key: Patient ID

| Information category  | Contents                                                             |
| --------------------- | -------------------------------------------------------------------- |
| Patient identity      | Internal patient ID, FHIR identity mapping, demographics             |
| Clinical history      | Documented medical conditions and encounters                         |
| Procedures            | Verified surgeries and treatments undergone                          |
| Medication history    | Prescriptions, reported current usage and adherence                  |
| Discharge information | Discharge encounter, condition and date                              |
| Recovery context      | Approved recovery plan, restrictions and milestones                  |
| Historical physiology | Previous observations and clinical measurements                      |
| Personalization       | Authorized oxygen scale, individual targets and relevant constraints |
| Safety information    | Documented allergies, contraindications and restrictions             |
| Care team             | Assigned clinician and authorized backup                             |

The existing Clinical Registry V1 and HAPI FHIR records provide the authoritative patient information.

The Patient KB can maintain an indexed, runtime-safe representation of those records instead of duplicating the entire clinical database.

### Example Patient KB record

```
{
  "patient_id": "P001",
  "record_version": 3,
  "clinical_history": {
    "documented_conditions": [
      {
        "condition": "Pneumonia",
        "evidence_ref": "Condition/COND-001"
      }
    ],
    "verified_procedures": [],
    "allergy_status": "unknown"
  },
  "discharge_context": {
    "encounter_ref": "Encounter/ENC-001",
    "primary_condition": "Pneumonia",
    "recovery_phase": "early"
  },
  "medication_context": {
    "prescription_refs": [
      "MedicationRequest/MED-001"
    ],
    "current_adherence": "unknown"
  },
  "recovery_plan_ref": "CarePlan/CP-001",
  "personalization": {
    "oxygen_scale": 1,
    "baseline_profile_ref": "BASELINE-P001"
  },
  "care_team_ref": "CareTeam/TEAM-001"
}
```

This is an illustrative synthetic record, not an extracted patient record.

## 2.2 Shared Clinical Knowledge Base — Clinical KB

This contains general knowledge that can be reused across different patients.

| Knowledge category          | Examples                                                             |
| --------------------------- | -------------------------------------------------------------------- |
| Explicit clinical knowledge | NEWS2 components, measurement interpretation and clinical guidelines |
| Physiological knowledge     | Cardiorespiratory coupling, thermoregulation and recovery dynamics   |
| Encoded tacit knowledge     | Contextual reasoning heuristics and physiological mental models      |
| Medication knowledge        | Known medication effects, interactions and limitations               |
| Recovery knowledge          | Condition-specific recovery protocols and activity restrictions      |
| Physiological modeling      | ODE equations, parameter bounds and applicability                    |
| Safety knowledge            | Criticality rules, verification and escalation policies              |

Each knowledge entry should have a rule ID, version, applicability criteria, supporting references, exceptions and limitations.

The shared KB is not patient-specific. The Patient Context Expert determines which knowledge is applicable to a particular patient.

# 3. Expert 1 — Patient Context Expert

This is the context controller of the entire intelligence system.

Its responsibility is to identify the patient and understand what the patient has undergone so that every downstream component can work appropriately.

Authenticated Patient ID

Patient Context Expert

Patient KB retrieval

Find the patient record using Patient ID

Clinical KB retrieval

Find applicable clinical and physiological knowledge

Context Understanding

Condition, procedure, treatment, recovery phase, medication context, personalization and missing information

Versioned Patient Context Output

### Patient Context Expert workflow

1. Receive the authenticated Patient ID.
2. Retrieve the corresponding record from the Patient KB.
3. Identify documented conditions, verified procedures and treatments.
4. Determine the patient's recovery phase and approved care requirements.
5. Retrieve applicable knowledge from the Shared Clinical KB.
6. Produce a structured context for the downstream intelligence components.

### Example context output

```
{
  "context_id": "CTX-P001-V3",
  "patient_id": "P001",
  "patient_record_version": 3,

  "clinical_context": {
    "documented_condition": "Pneumonia",
    "clinical_domain": "respiratory",
    "recovery_phase": "early"
  },

  "applicable_knowledge_refs": [
    "RESPIRATORY_RECOVERY_V1",
    "CARDIORESP_COUPLING_V1",
    "OXYGENATION_INTERPRETATION_V1"
  ],

  "personalization": {
    "oxygen_scale": 1,
    "baseline_profile_ref": "BASELINE-P001"
  },

  "model_context": {
    "equation_set": "CARDIORESP_THERMAL_V1",
    "parameter_profile_ref": "PARAM-P001-V1"
  },

  "unknown_information": [
    "current_medication_adherence"
  ]
}
```

This context is provided to the four physiological experts, encoder, decision system, medication expert and recovery expert.

The manifest does not need to repeat this clinical history.

# 4. Experts 2–5 — Physiological Expert Intelligence

These four experts operate in parallel after receiving the Patient Context Expert's output.

They remain general physiological experts rather than separate disease-specific agents.

### Heart Rate Expert

Cardiovascular intelligence

HR trends and baseline deviations

Cardiovascular compensation

Medication-related influences

Activity and recovery response

Cross-vital relationships

### Respiratory Rate Expert

Respiratory intelligence

Respiratory trends

Sustained respiratory changes

Compensatory responses

Activity-related variation

Respiratory recovery behavior

### SpO₂ Expert

Oxygenation intelligence

Oxygen saturation trends

Personalized oxygen interpretation

Desaturation persistence

Probe artifact recognition

Cardiorespiratory evidence

### Temperature Expert

Thermoregulatory intelligence

Temperature trends

Thermal baseline deviations

Fever-related physiological changes

Recovery context

Thermal–cardiovascular relationships

## How context changes expert behavior

| Patient context                            | Expert adaptation                                                      |
| ------------------------------------------ | ---------------------------------------------------------------------- |
| Pneumonia recovery                         | Respiratory and oxygenation relationships become particularly relevant |
| Verified cardiac procedure                 | Cardiovascular recovery and applicable restrictions receive attention  |
| Historical beta-blocker prescription       | Consider possible blunted HR response, without assuming current use    |
| Authorized hypercapnic respiratory failure | Apply appropriate oxygen interpretation                                |
| Verified orthopedic procedure              | Consider approved mobility restrictions and activity response          |

All four experts remain active. Context determines applicable knowledge and interpretation, not which vital signs can be ignored.

## Expert outputs

Each expert produces structured findings containing:

| Output                     | Meaning                                      |
| -------------------------- | -------------------------------------------- |
| Clinical component score   | Applicable partial NEWS2 component           |
| Contextual concern         | None, mild, moderate or high                 |
| Baseline deviation         | Difference from previous eligible baseline   |
| Trend slope                | Rate of physiological change                 |
| Abnormal duration          | Observed persistence of an abnormality       |
| Cross-signal support       | Supporting evidence from other vital domains |
| Evidence reliability       | Reliability of the underlying evidence       |
| Interpretation uncertainty | Uncertainty in the expert's interpretation   |
| Evidence references        | Original measurements and clinical context   |
| Knowledge references       | Applied rules and versions                   |

The experts also identify relevant physiological relationships that can inform the virtual manifest and PINN-ODE.

These relationships are hypotheses or applicable modeling assumptions unless sufficiently supported by evidence.

# 5. Clinical scoring and personalized baseline intelligence

The scoring and baseline modules support the physiological experts and the final decision system.

They are deterministic clinical intelligence modules, not additional agents.

## Clinical scoring

The system computes component-level scores for HR, RR, SpO₂ and temperature using NEWS2-style rules.

Important correction to the earlier architecture: Standard NEWS2 temperature scoring includes 3 points for temperature at or below 35°C. Therefore, the maximum possible four-component subtotal is 12, not 11.

| Component               | Maximum score |
| ----------------------- | ------------- |
| Heart rate              | 3             |
| Respiratory rate        | 3             |
| SpO₂                    | 3             |
| Temperature             | 3             |
| Four-component subtotal | 12            |

The full NEWS2 system also includes systolic blood pressure, consciousness and supplemental oxygen scoring.

Our four-component subtotal must therefore be clearly identified as partial NEWS2, and full NEWS2 escalation thresholds must not be directly applied to it.

## Personalized baseline

The baseline engine maintains an independent physiological reference for each vital.

1. Historical reference

   Retrieve available historical observations from the Patient KB.
2. Calibration

   Establish an individual baseline from eligible, stable and reliable observations.
3. Established baseline

   Compare incoming observations against the previously established baseline.
4. Freeze

   Stop baseline adaptation during suspected deterioration or unreliable measurements.
5. Resume

   Resume adaptation only after the applicable stability and eligibility requirements are satisfied.

The baseline must not gradually adapt to a deteriorating physiological state and incorrectly classify that deterioration as the patient's new normal.

# 6. Textual Physiological State Manifest

This is the first part of our combined digital twin.

## What the manifest actually is

The manifest is a structured textual representation of the virtual physiological state of a patient.

It contains the information required to reconstruct, model, update and audit the patient's computational physiological state.

It is not a patient biography, clinical database, image or anatomical reconstruction.

### What belongs inside the manifest

| Component                       | Purpose                                                     |
| ------------------------------- | ----------------------------------------------------------- |
| Opaque patient/session identity | Associate the state with the correct patient and session    |
| Context reference               | Reference the Patient Context Expert's output               |
| Observed physiological state    | Current measured HR, RR, SpO₂ and temperature               |
| Baseline state                  | Individual physiological reference values and freeze status |
| Physiological relationships     | Applicable relationships and expert-supported findings      |
| Model configuration             | Applicable ODE equations and parameter definitions          |
| Estimated parameters            | Current patient-conditioned model parameters                |
| Quality and missingness         | Measurement reliability and unavailable information         |
| Expert evidence references      | Supporting physiological expert findings                    |
| State checkpoint                | Reconstructable computational state                         |
| Version and time                | Reproduce the state at a particular physiological time      |

### What does not belong inside the manifest

Full patient medical history, patient name, detailed diagnosis descriptions, complete surgical records, medication prescription history, personal demographic records, images, 3D anatomy or hidden simulator ground truth.

Those remain in their respective authoritative sources.

## Final manifest example

```
{
  "manifest_id": "MANIFEST-P001-0042",
  "schema_version": "1.0",
  "state_version": 42,

  "identity": {
    "patient_id": "P001",
    "session_id": "SESSION-001",
    "variant_id": "original"
  },

  "source_time_s": 630,

  "context_ref": "CTX-P001-V3",

  "observed_state": {
    "hr": {
      "value": 108,
      "unit": "bpm",
      "quality": "valid",
      "observation_ref": "OBS-HR-630"
    },
    "rr": {
      "value": 26,
      "unit": "breaths/min",
      "quality": "valid",
      "observation_ref": "OBS-RR-630"
    },
    "spo2": {
      "value": 92,
      "unit": "%",
      "quality": "valid",
      "observation_ref": "OBS-SPO2-630"
    },
    "temperature": {
      "value": 38.1,
      "unit": "Cel",
      "quality": "valid",
      "observation_ref": "OBS-TEMP-630"
    }
  },

  "baseline_state": {
    "hr": 78,
    "rr": 16,
    "spo2": 97,
    "temperature": 37.0,
    "adaptation_status": "frozen",
    "baseline_ref": "BASELINE-P001-V4"
  },

  "physiological_relationships": [
    {
      "relationship": "cardiorespiratory_coupling",
      "status": "supported",
      "evidence_ref": "EVIDENCE-42-A"
    },
    {
      "relationship": "thermal_cardiovascular_coupling",
      "status": "possible",
      "evidence_ref": "EVIDENCE-42-B"
    }
  ],

  "model_configuration": {
    "equation_set": "CARDIORESP_THERMAL_V1",
    "parameter_profile_ref": "PARAM-P001-V2",
    "parameter_status": "provisional"
  },

  "expert_evidence_refs": [
    "HR-E42",
    "RR-E42",
    "SPO2-E42",
    "TEMP-E42"
  ],

  "uncertainty": {
    "missing_vitals": [],
    "parameter_uncertainty": "moderate",
    "unobserved_physiology": "unknown"
  },

  "estimated_state_ref": "ESTIMATE-P001-42",
  "checkpoint_ref": "CHECKPOINT-P001-42",
  "parent_manifest_ref": "MANIFEST-P001-0041"
}
```

This is the proposed structure for an illustrative synthetic state.

The Patient Context Expert's output is referenced through `context_ref`. There is no duplication of the patient's entire clinical record.

# 7. Context-adaptive vector encoder

The encoder receives two distinct inputs:

Input A — Manifest

Physiological state, baseline, relationships, quality and expert evidence

Input B — Patient Context

Applicable clinical features and personalization from the Patient Context Expert

Context-Adaptive Encoder

Feature extraction · Normalization · Missingness masks · Context conditioning

# 264

Ordered numerical features

PINN-ODE State & Parameter Estimation

## Final encoder feature structure

| Feature group                    | Dimensions |
| -------------------------------- | ---------- |
| Physiological features           | 48         |
| Physiological availability masks | 48         |
| Signal quality features          | 24         |
| Expert-derived features          | 32         |
| Expert feature masks             | 32         |
| Patient context features         | 32         |
| Context availability masks       | 32         |
| Temporal and baseline features   | 16         |
| Total                            | 264        |

The encoder preserves missingness explicitly.

A missing temperature value must not become a real temperature measurement of zero.

The initial model uses a fixed 15-second source-time feature timeline, even when the gateway uses adaptive 5/10/15-second windows. Immediate safety evaluation remains event-driven.

# 8. Manifest + PINN-ODE Cognitive Digital Twin

This is the central innovation of the architecture.

Manifest = representation of the current virtual physiological state.

PINN-ODE = mathematical evolution of that state.

The combined system reconstructs an estimated patient state, models its dynamics, forecasts possible changes and continuously updates itself as new observations arrive.

## 8.1 Internal architecture

### Hybrid Physics-Informed Twin

Encoded Manifest + Context

State Estimator

Estimate the current four-vital physiological state

Parameter Estimator

Estimate constrained patient-specific parameters

### Coupled Physiological Dynamics

HR dynamics

Cardiovascular state evolution

RR dynamics

Respiratory state evolution

SpO₂ dynamics

Oxygenation state evolution

Temperature dynamics

Thermoregulatory state evolution

Shared Context-Conditioned Neural Residual

Learn additional physiological dynamics from training trajectories

Differentiable ODE Solver

Integrates the coupled state over continuous physiological time

Forecast Decoder & Uncertainty Estimation

Predicted Physiological Trajectories

HR · RR · SpO₂ · Temperature

## 8.2 Mathematical architecture

Let the Patient Context Expert produce:

\\[ C_t=ContextExpert(PatientID,KB) \\]

The four experts produce:

\\[ E_t=Experts(X_t,C_t,K) \\]

The textual manifest is constructed as:

\\[ M_t=Manifest(X_t,E_t,B_t,Q_t) \\]

Where \\(X_t\\) represents observations, \\(B_t\\) represents baseline state and \\(Q_t\\) represents quality and uncertainty.

The encoder combines the manifest and clinical context:

\\[ z_t=Encoder(M_t,C_t) \\]

The physiological state is:

\\[ x(t)= \begin{bmatrix} HR(t)\\\ RR(t)\\\ SpO_2(t)\\\ T(t) \end{bmatrix} \\]

The final hybrid PINN-ODE formulation is:

\\[ \boxed{ \frac{dx}{dt} = f\_{\mathrm{phys}}(x,p,u) + f\_{\theta}(x,z_t,u) } \\]

| Term                     | Meaning                                                  |
| ------------------------ | -------------------------------------------------------- |
| \\(f\_{\mathrm{phys}}\\) | Simplified mechanistic physiological dynamics            |
| \\(f\_\theta\\)          | Learned neural residual dynamics                         |
| \\(p\\)                  | Constrained patient-specific physiological parameters    |
| \\(u\\)                  | Available external influences, such as reported activity |
| \\(z_t\\)                | Context-conditioned encoded manifest                     |
| \\(x(t)\\)               | Current estimated physiological state                    |

## 8.3 Example physiological equation

An illustrative HR equation is:

\\[ \frac{dHR}{dt} = -\frac{HR-HR_b}{\tau\_{HR}} +\alpha_T(T-T_b) +\alpha_AA(t) +r\_\theta \\]

The equation represents baseline recovery dynamics, temperature influence, activity influence and learned residual behavior.

The exact physiological equations, coefficients, units and parameter bounds must be agreed upon by the MATLAB, clinical and AI teams.

This equation is an engineering example, not a clinically validated individual heart-rate prediction law.

## 8.4 Physics-informed training

\\[ \mathcal L\_{\mathrm{total}} = \lambda_d\mathcal L\_{\mathrm{data}} + \lambda_p\mathcal L\_{\mathrm{physics}} + \lambda_i\mathcal L\_{\mathrm{initial}} + \lambda_b\mathcal L\_{\mathrm{bounds}} + \lambda_r\mathcal L\_{\mathrm{residual}} \\]

The training objectives ensure that the model learns from available trajectories while respecting applicable physiological constraints and plausible parameter ranges.

Clinical targets are not automatically physical constraints. For example, a patient's authorized SpO₂ target must not force the predicted oxygenation state to remain within that target.

## 8.5 Continuous adaptation

Patient-specific state and parameters adapt to incoming evidence. Shared trained neural weights remain fixed during normal runtime.

The model does not require retraining for every new patient observation.

Personalization occurs through context, initial-state estimation, baseline state, constrained parameters and observation reconciliation.

# 9. Trustworthy Intelligence Layer

This layer verifies the intelligence generated by the physiological experts and digital twin before it contributes to the final decision.

## 9.1 Uncertainty Engine

Identifies and represents different types of uncertainty.

| Type                       | Example                                     |
| -------------------------- | ------------------------------------------- |
| Measurement uncertainty    | Unreliable oxygen sensor                    |
| Context uncertainty        | Unknown medication adherence                |
| Baseline uncertainty       | Insufficient calibration                    |
| Parameter uncertainty      | Poorly identifiable physiological parameter |
| Model uncertainty          | Unseen physiological behavior               |
| Forecast uncertainty       | Wide future prediction interval             |
| Interpretation uncertainty | Multiple plausible explanations             |

The system must be able to abstain from a forecast when evidence is insufficient.

## 9.2 Counterfactual Engine

The manifest enables isolated virtual experiments.

Original Manifest

Current physiological state and supporting evidence

Branch A

Original available observations

Branch B

Exclude unreliable observation

Branch C

Vary uncertain measurement within justified bounds

Branch D

Vary uncertain model parameters

Reconstruct affected state and run PINN-ODE

Compare forecast divergence and decision robustness

The original patient state remains unchanged.

These experiments test evidence and model sensitivity. They do not establish the causal effect of administering a medication or performing a treatment.

## 9.3 Trust Engine

Evaluates source authenticity, signal quality, knowledge applicability, model validity, patient-state integrity and forecast reliability.

## 9.4 Evidence Engine

Every recommendation must be traceable to actual observations, patient context, applicable knowledge, expert findings and relevant model outputs.

Overlapping expert findings must be deduplicated so that multiple interpretations of the same physiological evidence are not incorrectly treated as independent confirmations.

## 9.5 Physiological Consistency and Model Validity

Checks numerical stability, applicable physiological relationships, plausible output bounds, out-of-distribution conditions and forecast eligibility.

Experimental or unvalidated forecasts can be displayed for evaluation but cannot independently change clinical priority.

# 10. Hybrid Decision Intelligence

The decision system combines all verified evidence.

It is not dependent on a single neural risk score.

\\[ D_t=F(C_t,S_t,E_t,B_t,P_t,U_t,R_t) \\]

Where:

| Input     | Meaning                             |
| --------- | ----------------------------------- |
| \\(C_t\\) | Patient clinical context            |
| \\(S_t\\) | Clinical scoring                    |
| \\(E_t\\) | Physiological expert evidence       |
| \\(B_t\\) | Personalized baseline deviation     |
| \\(P_t\\) | Eligible PINN-ODE forecasts         |
| \\(U_t\\) | Uncertainty                         |
| \\(R_t\\) | Trust and counterfactual robustness |

## Decision hierarchy

1. Independent safety evaluation

   Determine whether the available evidence establishes a mandatory escalation requirement.
2. Current physiological assessment

   Analyze actual measurements, clinical scoring, baseline deviations and expert findings.
3. Predictive assessment

   Consider eligible PINN-ODE forecasts and associated uncertainty.
4. Evidence verification

   Resolve conflicts, evaluate reliability and preserve unknown information.
5. Clinical recommendation

   Determine Watch, Review or Urgent using the applicable decision policy.
6. Human action

   Generate an evidence report, notify the appropriate clinician and support approved care.

## Final decision output

| Dimension             | Output                                                    |
| --------------------- | --------------------------------------------------------- |
| Clinical priority     | Watch / Review / Urgent / Insufficient assessment         |
| Physiological concern | None / Mild / Moderate / High / Unknown                   |
| Evidence reliability  | Low / Moderate / High / Unknown                           |
| Monitoring status     | Normal / Degraded / Interrupted                           |
| Forecast status       | Validated / Experimental / Abstained / Failed             |
| Recommended action    | Continue monitoring / Verify / Review / Escalate          |
| Supporting evidence   | Observations, clinical rules, context and expert findings |
| Limitations           | Missing information, uncertainty and model limitations    |

Physiological concern and evidence reliability remain separate.

An unreliable measurement indicating potentially serious deterioration must not be automatically dismissed.

# 11. Independent clinical safety path

This is a mandatory parallel architecture, not simply the last step of the neural pipeline.

Incoming Physiological Observation

Immediate Safety Path

Criticality, verification, escalation floor and urgent notification

Intelligence Path

Experts, manifest, PINN-ODE and trustworthy assessment

Final Safety-Constrained Decision

Authorized Clinical Notification

The immediate safety path remains functional during missing data, baseline calibration, PINN-ODE failure, unreliable forecasts, gateway overload and HAPI persistence delays.

Urgent notifications must not wait for the neural model or detailed report.

The final decision cannot downgrade a mandatory safety requirement merely because the PINN-ODE predicts recovery.

# 12. Expert 6 — Medication & Clinical Intervention Expert

This expert receives the Patient Context Expert's output, medication knowledge, verified decision and relevant clinical evidence.

It can prepare contextual information in parallel, but intervention recommendations must wait for the verified clinical assessment.

| Patient situation                   | Expert response                                       |
| ----------------------------------- | ----------------------------------------------------- |
| Stable recovery                     | Continue existing approved care                       |
| Prescribed medication due           | Generate an appropriate reminder                      |
| Possible medication-related concern | Present supporting evidence for clinician review      |
| Potential intervention              | Provide evidence-backed options to the clinician      |
| Urgent deterioration                | Support immediate escalation and clinical preparation |
| New treatment instruction           | Require authorized clinician approval                 |

### Human-supervised workflow

Verified Clinical Decision

Medication & Intervention Expert

Patient context + medication knowledge + relevant safety information

Clinician Review

Approve, modify, reject or request further assessment

Authorized Patient Instructions

The expert does not autonomously prescribe new medication, change dosage or authorize procedures.

# 13. Expert 7 — Patient Recovery Expert

This expert continuously supports the patient's recovery journey.

It retrieves relevant patient context and approved care-plan information through the Patient Context Expert.

## Recovery intelligence inputs

| Input                      | Purpose                                    |
| -------------------------- | ------------------------------------------ |
| Approved recovery plan     | Establish applicable recovery goals        |
| Patient activities         | Understand activity tolerance and progress |
| Symptoms                   | Identify new or worsening concerns         |
| Reported medication usage  | Track reported adherence                   |
| Physiological trends       | Understand response during recovery        |
| Approved exercises         | Monitor task completion and tolerance      |
| Verified clinical decision | Adjust monitoring and escalation behavior  |

## Recovery timeline

1. 7 days — Immediate recovery

   Approved medication reminders, rest, symptom monitoring and early recovery tasks.
2. 15 days — Early recovery

   Activity tolerance, progress assessment and follow-up preparation.
3. 30 days — Functional recovery

   Approved activity progression and condition-specific milestones.
4. 90 days — Rehabilitation

   Longitudinal functional progress and approved rehabilitation goals.
5. 180 days — Long-term recovery

   Review of longer-term recovery goals and follow-up requirements.

These are possible care-plan durations, not mandatory monitoring periods for every patient.

The Recovery Expert provides daily summaries, approved tasks, symptom check-ins, medication reminders and progress monitoring.

It does not independently authorize exercise progression during unresolved clinical concerns.

# 14. Final dashboard architecture

The dashboard must expose the intelligence generated by the architecture in a meaningful way.

The clinician interface provides technical and clinical evidence. The patient interface provides understandable recovery support.

## A. Clinician Command Center

## Clinical Command Center

Illustrative interface

Demo data

Monitored

# 10

Review

# 2

Urgent

# 1

### Patient P001 — Live Digital Twin

Post-discharge monitoring · Synthetic example

Heart rate

# 108

bpm

Baseline: 78

Respiratory rate

# 26

/min

Baseline: 16

SpO₂

# 92

%

Baseline: 97

Temperature

# 38.1

°C

Baseline: 37.0

#### Physiological trajectory

Observed SpO₂PINN-ODE forecast

84%88%92%96%100%−15m−10m−5mNow+5m+10m+15m

Illustrative forecast, not a result from a trained or validated model.

#### Expert intelligence

| HR Expert          | Elevated relative to baseline  |
| ------------------ | ------------------------------ |
| RR Expert          | Sustained respiratory increase |
| SpO₂ Expert        | Declining oxygenation          |
| Temperature Expert | Increasing temperature         |

#### Trustworthy assessment

Physiological concern

High

Evidence reliability

High

Baseline adaptation

Frozen

Forecast status

Experimental

Clinical recommendation

Review the sustained physiological changes, original observations and applicable patient context. Obtain an authorized clinical assessment.

### Final clinician dashboard pages

| Page                     | Main functionality                                           |
| ------------------------ | ------------------------------------------------------------ |
| Overview                 | Patient queue, clinical priority and monitoring status       |
| Patient Profile          | Clinical information retrieved from Patient KB               |
| Live Monitoring          | Four vital signs, trends, baselines and signal quality       |
| Cognitive Digital Twin   | Textual manifest, estimated state, parameters and forecasts  |
| Expert Intelligence      | Four expert findings and supporting clinical knowledge       |
| Trustworthy Intelligence | Uncertainty, evidence, counterfactuals and model validity    |
| Alert Center             | Clinical and technical alerts, acknowledgment and escalation |
| Clinical Reports         | Evidence-grounded assessments and recommendations            |
| Medication Review        | Existing prescriptions and clinician-controlled intervention |
| Recovery Progress        | Daily activities, symptoms and recovery milestones           |
| Patient History          | FHIR records and longitudinal clinical timeline              |

The digital twin page can visualize numerical trends and forecasts. That does not mean the manifest itself contains images or anatomical representations.

## B. Patient Recovery Assistant

## My Recovery

Day 4 · Illustrative care plan

Today's recovery tasks

# 2 of 4

Daily progress

### Today's approved care plan

Morning prescribed medication

Approved walking activity

Daily symptom check-in

Evening prescribed medication

Recovery phase

Early recovery

Reported walking

## 8 min

Recovery guidance

Follow your approved care plan and report new or worsening symptoms to your care team.

Interactive mockup only. Task changes are not transmitted to a clinician.

## C. Evaluation and Security Console

This interface contains:

| Module              | Functionality                                           |
| ------------------- | ------------------------------------------------------- |
| Simulator controls  | Select patient, physiological scenario and replay speed |
| BIDMC replay        | Select independent real-data recording                  |
| Data quality        | Missingness, artifacts and timestamp gaps               |
| Model evaluation    | Forecast errors and uncertainty coverage                |
| Clinical evaluation | Detection lead time and false alerts                    |
| Manifest validation | State reconstruction and reproducibility                |
| Security monitoring | Authentication failures, replay and unauthorized access |
| System performance  | Latency, throughput and resource usage                  |
| FHIR monitoring     | Persistence, validation and reconciliation              |

# 15. Privacy, cybersecurity and patient isolation

The Patient ID is the primary Patient KB lookup key, but it is not sufficient by itself for authorization or runtime state isolation.

### Identity architecture

| Identity         | Purpose                                            |
| ---------------- | -------------------------------------------------- |
| Patient ID       | Retrieve the patient from Patient KB               |
| FHIR Patient ID  | Access authorized standardized clinical records    |
| Source namespace | Separate Synthea, BIDMC and other sources          |
| Variant ID       | Separate original and synthetic test variants      |
| Session ID       | Separate independent monitoring or replay sessions |
| Manifest ID      | Identify a particular physiological state version  |

The runtime state key should include:

```
Source Namespace
    + Patient/Subject ID
    + Variant ID
    + Session ID
```

This prevents independent recordings or simulation runs from sharing model state and personalized baselines.

### Security mechanisms

| Security area         | Implementation                                     |
| --------------------- | -------------------------------------------------- |
| Source authentication | Authenticated simulator and data producers         |
| Transport             | TLS                                                |
| Event integrity       | Authenticated events and replay protection         |
| Access control        | Role-based and patient-level authorization         |
| Data privacy          | Pseudonymization and minimum necessary information |
| Storage               | Encryption and controlled key management           |
| State isolation       | Independent patient/session state                  |
| Manifest integrity    | Versioned references and tamper-evident audit      |
| Clinical data         | Restricted HAPI FHIR access                        |
| Security audit        | Access logs and security event records             |

The manifest's lack of duplicated personal and clinical information reduces unnecessary exposure, but physiological measurements and opaque identifiers still require appropriate privacy protection.

# 16. Training and evaluation architecture

The training pipeline remains separate from the operational clinical system.

MATLAB Batch Simulation

Multiple patient configurations, stable recovery, deterioration, recovery transitions and sensor effects

Observed Data

Runtime-equivalent physiological observations

Hidden Ground Truth

Offline training targets and evaluation labels

Causal Context, Expert & Manifest Reconstruction

Grouped Train / Validation / Test Split

Independent trajectories and held-out patient configurations

Hybrid PINN-ODE Training

Observation consistency, physiological constraints and residual learning

Forecast, Clinical & System Evaluation

## Evaluation requirements

| Category                | Metrics                                                     |
| ----------------------- | ----------------------------------------------------------- |
| Deterioration detection | Lead time, detected events, missed events                   |
| Alert performance       | False alerts, alerts per patient-day                        |
| Forecasting             | MAE and RMSE per vital and horizon                          |
| Uncertainty             | Prediction interval coverage and width                      |
| Personalization         | Improvement over non-personalized monitoring                |
| Artifact handling       | Precision, recall and missed genuine abnormalities          |
| Missingness             | Detection latency and safe abstention                       |
| Manifest                | Reconstruction accuracy and reproducibility                 |
| PINN-ODE                | Solver stability, physiological consistency and latency     |
| Explainability          | Evidence completeness and rule traceability                 |
| Security                | Replay rejection, unauthorized access and patient isolation |
| System performance      | Throughput, p50/p95/p99 latency and resource usage          |
| FHIR                    | Resource validation and persistence                         |

### Baseline comparisons

For clinical monitoring, compare the proposed system against a naive fixed-threshold alerting system.

For physiological forecasting, compare persistence, linear trend, mechanistic ODE, unconstrained neural ODE and the hybrid PINN-ODE.

BIDMC is used for independent real-data replay and limited forecasting evaluation. It does not contain labelled post-discharge deterioration outcomes or temperature measurements.

Synthetic training performance must not be presented as clinical validation.

# 17. Final technology stack

| Component                    | Technology                                                |
| ---------------------------- | --------------------------------------------------------- |
| Virtual wearable             | MATLAB                                                    |
| Real physiological replay    | BIDMC PhysioNet                                           |
| Patient clinical profiles    | Synthea                                                   |
| Patient KB                   | Clinical Registry + HAPI FHIR + indexed context store     |
| Shared Clinical KB           | Versioned JSON/YAML and deterministic knowledge functions |
| Operational backend          | Python + FastAPI                                          |
| Healthcare interoperability  | HAPI FHIR R4                                              |
| Shared interfaces            | Pydantic + JSON Schema                                    |
| Textual manifest             | Structured JSON                                           |
| Feature processing           | NumPy + SciPy                                             |
| Neural modeling              | PyTorch                                                   |
| Differentiable ODE solver    | torchdiffeq                                               |
| Physics-informed training    | PyTorch automatic differentiation                         |
| Operational state store      | PostgreSQL or SQLite for prototype                        |
| Durable event processing     | Redis Streams or equivalent                               |
| Live dashboard communication | WebSockets                                                |
| Frontend                     | React + TypeScript                                        |
| Data visualization           | Recharts or Plotly                                        |
| Deployment                   | Docker Compose                                            |
| Testing                      | Pytest                                                    |
| Performance evaluation       | Replay benchmarks and load testing                        |

# 18. Final shared contracts

These contracts define how the components communicate without duplicating responsibility.

| Contract                  | Purpose                                       |
| ------------------------- | --------------------------------------------- |
| `ObservationEventV1`      | Individual incoming physiological observation |
| `ObservationWindowV1`     | Adaptive gateway evidence packet              |
| `PatientKBRecordV1`       | Runtime-safe patient record                   |
| `ClinicalContextV1`       | Patient Context Expert output                 |
| `KnowledgeRuleV1`         | Versioned clinical or physiological knowledge |
| `BaselineStateV1`         | Personalized baseline state                   |
| `ClinicalScoreV1`         | Partial NEWS2 scoring                         |
| `ExpertInputV1`           | Physiological expert input                    |
| `ExpertEvidenceV1`        | Structured physiological expert output        |
| `PhysiologicalManifestV1` | Textual virtual physiological representation  |
| `EncoderFrameV1`          | Ordered numerical features                    |
| `ODEParameterStateV1`     | Constrained physiological model parameters    |
| `PatientTwinStateV1`      | Observed, estimated and predicted states      |
| `NeuralForecastV1`        | Forecast and uncertainty                      |
| `TrustAssessmentV1`       | Evidence reliability and robustness           |
| `SafetyAssessmentV1`      | Independent clinical safety                   |
| `ClinicalDecisionV1`      | Evidence-constrained recommendation           |
| `ClinicalReportV1`        | Structured clinician report                   |
| `CarePlanV1`              | Approved recovery plan                        |

The previously drafted contracts need to be updated to incorporate the final textual manifest, separate Patient KB context and PINN-ODE state.

# 19. Final division of work

| Workstream                   | Responsibilities                                                                                                            |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| MATLAB & Data Team           | Virtual wearable, BIDMC replay, physiological scenarios, batch generation, offline ground truth                             |
| Clinical Intelligence Team   | Patient KB, Patient Context Expert, Shared Clinical KB, four physiological experts, scoring and baseline rules              |
| AI Architecture Team         | Manifest, encoder, PINN-ODE, state estimation, uncertainty, counterfactuals and decision intelligence                       |
| Integration & Dashboard Team | Secure gateway, FastAPI, HAPI FHIR, shared interfaces, clinician dashboard, patient dashboard, notifications and evaluation |

The MATLAB team's existing simulator remains usable. The clinical reasoning team's existing registry and physiological expert work also remain usable.

The main architectural update is the separation of patient context from the textual manifest and the implementation of the PINN-ODE core.

# 20. Final implementation priorities

### P0 — Mandatory working prototype

Complete the required problem statement before expanding the research features.

Patient KB with authenticated Patient ID lookup

Patient Context Expert and runtime-safe context output

MATLAB simulator and BIDMC replay

FHIR ingestion and HAPI FHIR storage

Four physiological experts and clinical knowledge

Partial NEWS2 and personalized baseline

Artifact and missing-data handling

Independent clinical safety supervisor

Clinician dashboard and explained alerts

Comparative clinical performance report

### P1 — Core innovation

Textual physiological manifest

264-dimensional context-adaptive encoder

Hybrid PINN-ODE five-minute forecasting

Uncertainty and trustworthy assessment

Evidence-constrained decision system

Authorized clinician notifications

Patient recovery assistant

### P2 — Advanced intelligence

Manifest counterfactual branching

15-minute and 30-minute forecasts

Advanced physiological parameter adaptation

Medication review and approval workflow

Longitudinal recovery intelligence

Comprehensive security and performance testing

Implementation checklist

0/23

Use this checklist to track verified completion, not simply documented design.

# 21. Final architecture identity and responsibilities

The complete architecture can be summarized through the responsibility of each intelligence component.

| Component                  | Responsibility                                              |
| -------------------------- | ----------------------------------------------------------- |
| Patient KB                 | Stores what is known about the patient                      |
| Shared Clinical KB         | Stores general clinical, physiological and tacit knowledge  |
| Patient Context Expert     | Understands who the patient is and what they have undergone |
| Four Physiological Experts | Understand the patient's current physiological behavior     |
| Textual Manifest           | Represents the patient's virtual physiological state        |
| Context-Adaptive Encoder   | Converts state and relevant context into numerical features |
| PINN-ODE                   | Models how the physiological state evolves                  |
| Trustworthy Intelligence   | Verifies evidence, uncertainty, trust and robustness        |
| Decision System            | Determines the appropriate clinical recommendation          |
| Safety Supervisor          | Enforces independent clinical safety requirements           |
| Medication Expert          | Supports clinician-controlled intervention                  |
| Recovery Expert            | Supports the patient's approved recovery journey            |
| Clinician                  | Reviews and authorizes clinical actions                     |
| HAPI FHIR                  | Preserves standardized clinical records                     |

## Final architecture principle

Patient ID retrieves the patient.

The Patient Context Expert understands the patient using the Patient KB and Shared Clinical KB.

The four physiological experts understand the patient's physiological behavior using their skills and applicable tacit knowledge.

The textual manifest reconstructs the virtual physiological state without duplicating the patient's medical history.

The PINN-ODE evolves that state and forecasts possible physiological changes.

The Trustworthy Intelligence layer verifies the resulting intelligence.

The Decision System generates evidence-constrained clinical recommendations.

The Medication and Recovery Experts support human-supervised care.

## Architecture freeze

This is the final V4.1 architecture, incorporating all the latest decisions:

- Patient ID-based Patient KB retrieval.
- Separate Patient KB and Shared Clinical KB.
- Patient Context Expert as the context controller.
- Four context-adaptive physiological experts.
- Textual-only physiological manifest, without duplicated medical history.
- Manifest combined with hybrid PINN-ODEs.
- Separate context and manifest inputs to the encoder.
- Trustworthy intelligence before the final decision.
- Independent safety path.
- Medication and recovery experts.
- Clinician and patient dashboards.

The architecture is finalized at the system-design level. The remaining implementation dependencies are the exact physiological ODE equations, parameter bounds, updated shared contracts, clinical decision policies and validated model performance.

We should now stop changing the architecture and concentrate on implementing and integrating the working prototype.

## Backend implementation addendum
Read V4_1_Backend_Integration_Addendum.md and V4_1_Shared_Contract_Amendments.md for adopted backend engineering and conflict resolutions. Original 40-page PDF remains authoritative for system structure; no change to V4.1.
