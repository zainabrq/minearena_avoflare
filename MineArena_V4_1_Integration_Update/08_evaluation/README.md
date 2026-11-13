# MineArena PS03 — Evaluation package v1.0
Architecture V4.1, frozen. This folder specifies tests, not implemented code or measured results. Clinical decision support only; not diagnosis. All clinical heuristics are prototype settings, not validated clinical practice.

## Claude implementation order
1. Read the original PS03 requirements, final Architecture_V4_1.md, and all eight clinical intelligence specifications. File 07 section 6 is authoritative for the clinical comparator and episode policy. Reconcile final V4.1 contracts before implementation.
2. Implement an offline replay harness that feeds the same observed data to both monitoring systems, with identical source clocks and independent state. Reuse the real ingestion/clinical path where practical; distinguish offline from end-to-end results.
3. Implement the fixed comparator and metrics as defined in 01 and 03. Never load labels into the operational monitoring process.
4. Use the scenario plan in 02; ask the MATLAB owner for exported independent runs. Run the existing 81 clinical test fixtures separately; they are acceptance tests, not population-level performance evidence.
5. Run mandatory integration checks (04); fill the report template (05) only from actual outputs. Save raw logs, configuration hashes, run IDs and test reports under results/<run_id>/.

## Files
- 01_evaluation_protocol.md: comparison, data isolation, execution and fairness.
- 02_scenario_plan.json: required scenario requests, not generated observations or ground truth.
- 03_metrics_and_report_contract.md: exact metrics and expected output schema.
- 04_mandatory_acceptance_tests.md: end-to-end requirement and demo gate.
- 05_performance_report_template.md: blank results for actual measurement.

## Dependencies
MATLAB live streaming, joint probe-removal/HR-flatline, motion artifacts, independent scenario exports, FHIR API/HAPI server, final contracts and clinical implementation are not verified here. PINN-ODE optional for mandatory benchmark; record whether enabled. No results may be invented. Keep ground_truth.csv and run_manifest.json accessible only to offline evaluator, never runtime. Do not replace original source datasets. Confirm hackathon AI coding policy and code provenance.


## V4.1 integration revision (Backend V1.1)
V1.1 adds 06_security_and_resilience_test_plan.md and engineering scenarios; original clinical comparator unchanged. Separate clinical outcome report from infrastructure report. No claims without actual outputs.
