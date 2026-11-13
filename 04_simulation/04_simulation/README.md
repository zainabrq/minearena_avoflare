# Avoflare V4.1 | Simulation handoff (V1.1)

## Authority and scope
Use the original PS03, frozen V4.1 architecture, approved backend integration addendum, and current clinical/AI/evaluation specifications. This is an integration and verification package, not a replacement MATLAB simulator. All simulation is engineering test data; not a validated clinical model.

## Read in this order
01 architecture; 02 audit; 03 verified mathematical logic; 04 source adapter; 05 offline training contract; 06 BIDMC; 07 tests; 08 team handoff; 09 scenario registry; V4_1_source_adapter_handoff.md. Tools are independent checks, not clinical code.

## Placement and preservation
Merge this folder into Desktop/mineareana/04_simulation. Do not delete existing MATLAB work or reassign patient IDs. Keep Abhi's entire original directory (including config, profiles, sensor, physiology, gateway, replay, batch, tests, evaluation and output) under matlab_source/Abhi_MATLAB_Virtual_Wearable_Simulator/ so relative paths continue to work. Do not rearrange original files inside it. Keep the 15-day extension inside that directory as received until its scope is reviewed. The original archive is not bundled here: its uploaded copy has 114 unreadable file entries out of 140. 26 entries passed CRC verification, but the batch CSVs and most validation exports cannot be read. Test the local copy before reusing it and request a split clean export if needed.

The project-level 02_patient_data/verified_clinical_registry_v1.json and patient_physiological_configuration_v1_1.json are authoritative. Abhi's original root config V1 and extension copy V1.1 are distinct; use an explicit config path and compare hashes/versions. Do not overwrite patient data with older copies. Original V1 may be used for reproducing earlier results only. Avoid adding P002-H to the original ten-patient list; run its approved hypothetical overlay separately.

Existing independently prepared BIDMC numeric extract and statistics are bundled in bidmc_analysis/ (not extracted from corrupt ZIP). Original PhysioNet source archive belongs in bidmc_source/ if available, with attribution and source version. The numerical extract is enough for the specified replay; raw waveforms are optional.

## First run after receiving a healthy handoff
1. Run `python tools/audit_matlab_archive.py <path-to-zip>`; confirm all file entries readable. Extract the whole project into matlab_source/.
2. Check MATLAB release/toolboxes, entry points, and remove machine-specific path assumptions through arguments, not uncontrolled source edits. Start from the project directory, use an explicit projectDir and selected config. `run_virtual_wearable_simulator` is legacy demo; distinguish integrated and batch scripts. Obtain exact commands from Abhi for the approved V1.1 integrated path.
3. Run `run_minearena_master_tests_v2(projectDir)` only after the expected files exist; this suite expects ten original patients and 40 runs, not a general validation for arbitrary batch sizes. Record console logs, commit/hash, MATLAB version and report. It does not test HAPI.
4. Run `python tools/validate_training_batch.py <batch-directory>` before importing the batch. Check run identities, time joins and missingness, then review the remaining semantic checks in 07.
5. Backend owner implements shared Python adapter using 04 and 05_backend/11_source_adapter_contract.md; test MATLAB and BIDMC with actual FHIR responses and retrieval before enabling live UI.
6. AI owner reconstructs clinical context, baselines, experts, manifest and encoder causally. Train only after 06_ai_digital_twin approval gates.

## Completion boundary
Source inspection, archive integrity inventory and BIDMC CSV structural check were performed. No MATLAB execution, network transmission, FHIR creation or neural training was performed in this review. Existing generated datasets must be verified after receiving a readable copy. `validation_outputs/` contains actual inspection results, not fabricated passing reports.
