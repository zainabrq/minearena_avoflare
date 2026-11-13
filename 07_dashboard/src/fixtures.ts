export const metrics = [
  { label: 'Heart rate', unit: 'bpm', range: [55, 140], noise: 3, shift: 36 },
  { label: 'Respiratory rate', unit: '/min', range: [10, 35], noise: 1, shift: 12 },
  { label: 'Oxygen saturation', unit: '%', range: [85, 100], noise: 0.6, shift: -8 },
  { label: 'Temperature', unit: '°C', range: [35, 40], noise: 0.15, shift: 1.2 },
] as const;

export type Values = readonly [number, number, number, number];
export type Patient = { id: string; context: string; baseline: Values };
export type Sample = { time: number; values: (number | null)[] };
export type Priority = 'Watch' | 'Review' | 'Urgent';
export type AlertCategory = 'clinical' | 'technical';
export type Alert = {
  category: AlertCategory;
  time: number;
  title: string;
  priority?: Priority;
  reading: string;
  rule: string;
  fact: string;
};
export const scenarios = {
  stable: 'Stable recovery',
  slow: 'Slow deterioration',
  probe: 'Probe removal',
} as const;
export type Scenario = keyof typeof scenarios;
export type Run = {
  patientId: string;
  scenario: Scenario;
  step: number;
  status: 'Running' | 'Paused' | 'Complete';
  samples: Sample[];
  alerts: Alert[];
  probeOff: boolean;
};
export const totalSteps = 30;
export const patients: Patient[] = [
  { id: 'DEMO-001', context: 'Respiratory recovery', baseline: [83, 17, 97, 37.1] },
  { id: 'DEMO-002', context: 'Post-discharge follow-up', baseline: [76, 16, 98, 36.7] },
  { id: 'DEMO-003', context: 'Cardiac follow-up', baseline: [91, 18, 97, 36.9] },
  { id: 'DEMO-004', context: 'General recovery', baseline: [72, 15, 99, 36.6] },
  { id: 'DEMO-005', context: 'Respiratory follow-up', baseline: [86, 18, 96, 37] },
];

function reading(patient: Patient, step: number, shift = 0, probeOff = false): Sample {
  const patientNumber = Number(patient.id.split('-').at(-1));
  return {
    time: step * 30,
    values: metrics.map((metric, index) => {
      if (probeOff && index === 2) return null;
      const noise = Math.sin(step * 2.713 + patientNumber * 7.13 + index * 12.25);
      const value = patient.baseline[index] + shift * metric.shift + noise * metric.noise;
      return index === 3 ? Number(value.toFixed(1)) : Math.round(value);
    }),
  };
}

export function history(patient: Patient): Sample[] {
  return Array.from({ length: 61 }, (_, index) => reading(patient, index - 60));
}

export function startRun(patient: Patient, scenario: Scenario, samples = history(patient)): Run {
  return { patientId: patient.id, scenario, samples, step: 0, status: 'Running', alerts: [], probeOff: false };
}

export function advanceRun(run: Run): Run {
  if (run.status !== 'Running') return run;
  const patient = patients.find(item => item.id === run.patientId);
  if (!patient) return run;
  const step = run.step + 1;
  const probeOff = run.scenario === 'probe' && step >= 8 && step < 22;
  const shift = run.scenario === 'slow' ? Math.max(0, (step - 3) / 27) : 0;
  const sample = reading(patient, step, shift, probeOff);
  let alerts = run.alerts;
  if (run.scenario === 'slow' && (step === 12 || step === 24)) {
    const priority = step === 12 ? 'Review' : 'Urgent';
    alerts = [...alerts, {
      category: 'clinical', time: sample.time, priority,
      title: step === 12 ? 'Change across multiple demo vitals' : 'Continued deterioration in demo readings',
      reading: 'SpO₂ ' + sample.values[2] + '%, RR ' + sample.values[1] + ' /min',
      rule: 'The demo script sets ' + priority + ' at this replay checkpoint.',
      fact: patient.context + ' · demo SpO₂ baseline ' + patient.baseline[2] + '%',
    }];
  }
  if (run.scenario === 'probe' && (step === 8 || step === 22)) {
    alerts = [...alerts, {
      category: 'technical', time: sample.time,
      title: probeOff ? 'Simulated probe removed' : 'Simulated probe reattached',
      reading: probeOff ? 'SpO₂ unavailable' : 'SpO₂ ' + sample.values[2] + '%',
      rule: 'The demo script changes the probe state.',
      fact: 'Virtual pulse oximeter assigned to ' + patient.id,
    }];
  }
  return { ...run, step, alerts, probeOff, samples: [...run.samples, sample], status: step === totalSteps ? 'Complete' : 'Running' };
}

export function sourceTime(seconds: number): string {
  const absolute = Math.abs(seconds);
  return (seconds < 0 ? '−' : '') + String(Math.floor(absolute / 60)).padStart(2, '0') + ':' + String(absolute % 60).padStart(2, '0');
}
