# Verified simulator mathematics and pending PINN-ODE equations

## Scope
Derived from readable MATLAB source: physiology/interpolate_scenario_targets.m, initialize_physiological_state.m, generate_correlated_physiology.m; sensor/apply_configured_sensor_effects.m and apply_sensor_fault_scenarios.m. The batch generator and 15-day extension could not be read, so their equations are not established here.

## Layer A: engineering physiology
For each vital v in HR, RR (MATLAB RESP), SpO2 and temperature, let the scenario contain ordered knots (t_i, a_i). Between knots:

`target_v(t) = a_i + (a_(i+1)-a_i)*(t-t_i)/(t_(i+1)-t_i)`.

Endpoint values are held outside the knot range. Units: seconds, beats/min, breaths/min, percentage points and degrees Celsius. `interp1(...,'linear')` implements this exactly. These are engineered scenario curves, not observed physiological laws.

At each tick, `variation_v[k] = rho_v * variation_v[k-1] + sqrt(1-rho_v^2)*sigma_v*epsilon_v[k]`, with epsilon standard normal. Then `true_v[k] = target_v(t_k)+variation_v[k]`. SpO2 truth is clipped to [0,100]. Rho is dimensionless; sigma has the vital's units. This is temporal autocorrelation for each channel, not demonstrated cross-vital stochastic covariance or coupled mechanistic dynamics. `sampleIntervalSec` is validated but rho is not rescaled in the readable generator; changing dt changes the effective physical autocorrelation. For a different dt, review rho(dt)=rho_ref^(dt/dt_ref) as a proposed engineering change, not an implemented fact.

Independent random streams: physiology seed = globalSeed + patientIndex*1000, sensor seed = globalSeed + patientIndex*1000 + 500, MT19937. For repeated batch runs use documented distinct per-run seeds and verify independence. Do not assume different filenames imply distinct trajectories.

## Approved V1.1 configuration reference
The following numbers are engineering inputs from 02_patient_data/patient_physiological_configuration_v1_1.json, not a verified execution of the unreadable archive config.

| Vital | AR(1) rho | sensor noise SD | units |
|---|---:|---:|---|
| HR | 0.95 | 0.5 | bpm |
| RR | 0.95 | 0.3 | breaths/min |
| SpO2 | 0.98 | 0.2 | percentage points |
| Temperature | 0.999 | 0.02 | deg C |

1s tick, global seed 42, default missing probability 0, 900s configured calibration duration. Per-patient sigma and initial targets remain in authoritative V1.1; do not treat them as learned clinical baselines. Older simulator_config.m has different demo defaults (seed 20261112, 300s, HR noise 1.5 etc.); do not mix settings silently.

## Layer B: sensor measurements
`observed_v = true_v + sensor_noise_SD_v * eta_v`, eta standard normal independent of physiology stream. Random missingness uses independent uniform draws per channel, sets NaN. Configured probe fault sets selected channel to NaN or specified value; configured connectivity sets all values NaN. A separate fault scheduler implements deterministic synthetic motion `A*sin(2*pi*0.8*(t-start)) + 0.35*A*sin(2*pi*1.7*(t-start))`, held flatline at first active sample, null probe removal, all-NaN connectivity and periodic missingness. Fault metadata remains offline. Motion frequencies exceed Nyquist for 1Hz sampling; treat as sampled artifact construction, not validated waveform simulation. For joint removal hold last valid pre-event HR and set SpO2 null or explicit zero according to scenario; this is required revision/test, not verified current integration.

## Mechanistic model boundary
Final hybrid V4.1: dx/dt = f_phys(x,p,u) + f_theta(x,z,u), x=[HR,RR,SpO2,T]. The current readable simulator provides targets and AR(1) variation, not f_phys. Do not use AR(1) coefficients as physiological coupling constants or claim interpolation is a governing physiological ODE. The AI/MATLAB/clinical teams must approve actual four RHS equations, parameter units and bounds, plausible state ranges, initial-state prior, applicability, external inputs and solver assumptions. Clinical oxygen target is not a physical state constraint. Avoid hidden future scenario control at inference. If no mechanistic simulator exists, use the existing synthetic curves for engineering training and define justified simplified physiological equations independently; report limitations. Separate physiology loss from the ODE identity already integrated by solver.

## Required handoff table (fill actual, no invented values)
| Model item | MATLAB team | AI/clinical team |
|---|---|---|
| Current four signal generation formulas and code version | confirm batch and 15-day logic, exact parameter values | distinguish targets vs mechanistic RHS |
| Initial state, variability, time constants, units | actual config/export | approve model priors and identifiability |
| HR–temperature, SpO2–RR, HR–RR, activity coupling | confirm whether implemented or only correlated scenario knots | approve signed relationships and applicability, not universal laws |
| Medication and oxygen effects | identify what is genuinely simulated and known at runtime | no unconfirmed adherence or future interventions |
| State/parameter bounds and derivative units | export engineering limits | justify and review physical constraints separately from alert thresholds |
| Future external input | export actual offline control only | forecast using known-at-origin inputs/assumptions, never hidden future truth |

See 06_ai_digital_twin/03_physiological_equations.md for model approval gate. This file does not invent final coefficients.
