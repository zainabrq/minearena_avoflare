import test from 'node:test';
import assert from 'node:assert/strict';
import { advanceRun, patients, startRun } from '../src/fixtures.ts';

function advance(run, steps) {
  for (let i = 0; i < steps; i++) run = advanceRun(run);
  return run;
}

test('deterioration emits staged alerts for the selected demo patient', () => {
  let run = advance(startRun(patients[0], 'slow'), 12);
  assert.equal(run.alerts[0].priority, 'Review');
  run = advance(run, 18);
  assert.deepEqual(run.alerts.map(alert => alert.priority), ['Review', 'Urgent']);
  assert.equal(run.status, 'Complete');
  assert.equal(run.patientId, 'DEMO-001');
  assert.equal(run.samples.at(-1).time, 900);
  assert.equal(advanceRun(run), run);
});

test('probe removal records missing SpO₂ and emits only technical events', () => {
  let run = advance(startRun(patients[1], 'probe'), 8);
  assert.equal(run.probeOff, true);
  assert.equal(run.samples.at(-1).values[2], null);
  run = advance(run, 14);
  assert.equal(run.probeOff, false);
  assert.equal(typeof run.samples.at(-1).values[2], 'number');
  assert.equal(run.samples.find(sample => sample.time === 240).values[2], null);
  assert.deepEqual(run.alerts.map(alert => alert.category), ['technical', 'technical']);
});

test('pause preserves the current state and stable replay produces no alerts', () => {
  const paused = { ...startRun(patients[2], 'stable'), status: 'Paused' };
  assert.equal(advanceRun(paused), paused);
  const run = advance({ ...paused, status: 'Running' }, 30);
  assert.equal(run.status, 'Complete');
  assert.deepEqual(run.alerts, []);
});
