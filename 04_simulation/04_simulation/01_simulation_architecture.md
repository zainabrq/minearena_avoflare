# Simulation architecture | V4.1

## Ownership
MATLAB generates engineering physiological trajectories and wearable measurements; backend validates/authenticates, assigns identity, computes quality and clinical decisions; AI team reconstructs virtual state and trains the hybrid PINN-ODE. No simulator scoring, priority assignment or autonomous clinical action. Patient Context Expert is sole patient KB access path for runtime/causal training snapshots.

## Two data paths
Runtime: selected original Synthea patient profile + versioned engineering configuration -> true physiology generator -> independent sensor noise/fault layer -> observed sample -> Python source adapter -> authenticated FHIR R4 API -> backend independent safety per accepted observation + adaptive 5/10/15s windows + independent HAPI persistence -> clinical intelligence/dashboard and fixed 15s encoder.

Offline: same generator -> observations and independently exported pre-sensor truth -> run metadata/parameters/event annotations -> validation -> grouped dataset split -> causal clinical features and manifests -> encoder -> PINN-ODE training/evaluation. Offline labels never enter runtime events or neural inputs. True physiology means simulator truth, not clinical truth. Simulator configured calibration flag is not the clinical rolling baseline.

BIDMC: independent recorded HR/RR/SpO2 -> shared source adapter -> same FHIR API and clinical pipeline in isolated replay session. No Synthea history or fabricated temperature; offline analytics may use P3. Source-time progression distinct from wall time. All accepted events independently persisted, P0 safety does not wait for windows/model/HAPI.

## Versions and legacy entry points
The readable README and `simulator_config.m` describe a starter 300s, 1 Hz demo with placeholder baselines and optional legacy raw JSON posting. `physiology/`, `profiles/`, `sensor/`, `evaluation/`, `batch/` represent the newer structured implementation; use the latter after verified entry point selection. `run_minearena_realtime_replay.m` reads an integrated observed CSV, validates exactly 10 patients per tick and continuous integer seconds, and supports a callback; without callback it is dry run. Its default 480 ticks do not necessarily contain deterioration or faults (e.g. P010 fault starts at 3000s in V1.1). Start from relevant interval only with explicit source-time preservation and baseline state treatment; for a full baseline demonstration replay from start, optionally accelerated.

## Simulation clock
Canonical engineering sample period 1s. Define duration convention: N ticks from t0 to t0+(N-1)*dt; report both row count and span. A 480-second duration with 480 ticks is not the same as BIDMC's 481 samples spanning 480s. Preserve original offsets; no cross-patient aggregation. Current `run_minearena_realtime_replay` uses deadline-based pacing, not a fixed sleep after each callback; maintain this behavior for live/accelerated pacing. A callback returning does not prove durable backend acceptance.

## Configuration authority
Use 02_patient_data V1.1 config, selected through explicit path. Initial targets and SD are engineering assumptions, never validated personal baselines. Historical medication prescriptions do not prove current use. P007 scenario is simulated fever, not verified postoperative state. Separate P002-H with hypothetical authorization, oxygen off for defined comparison, and its own session. Do not change original Synthea clinical history. 15-day extension is optional; do not require it for mandatory 1Hz replay or claim it is implemented until inspected.

## Performance
10 concurrent patients at 1Hz -> 10 multi-vital source rows/s, potentially 40 individual FHIR Observations/s. Accelerated replay multiplies wall arrival rate, not physiological rate. Throttle/backpressure via backend; no silent sample loss. Count transmitted, accepted, retried, rejected, pending and HAPI persisted separately. Preserve observation ordering and unique session identity.
