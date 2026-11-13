import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import logo from '../assets/images/logo.png';
import {
  advanceRun, history, metrics, patients, scenarios, sourceTime, startRun, totalSteps,
} from './fixtures';
import type { Alert, AlertCategory, Patient, Priority, Run, Sample, Scenario } from './fixtures';
import { AlarmRouting } from './AlarmRouting';

const pages = {
  overview: 'Overview',
  monitoring: 'Patient monitoring',
  alerts: 'Clinical alerts',
  replay: 'Scenario replay',
  fhir: 'FHIR records',
  reports: 'Clinical reports',
} as const;
type Page = keyof typeof pages;

const baselineHistory = Object.fromEntries(patients.map(patient => [patient.id, history(patient)]));
const priorities = ['Watch', 'Review', 'Urgent'] as const;
const urgency = { Watch: 0, Review: 1, Urgent: 2 };

function priorityOf(run: Run | null): Priority {
  return run?.alerts.findLast(alert => alert.category === 'clinical')?.priority ?? 'Watch';
}

function readPage(): Page {
  const page = window.location.hash.slice(1);
  return Object.hasOwn(pages, page) ? page as Page : 'overview';
}

function Heading({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <header className="heading"><div><h1 tabIndex={-1}>{title}</h1><p className="muted">{description}</p></div>{action}</header>;
}

function Status({ value }: { value: Priority }) {
  return <span className={'status ' + value.toLowerCase()}>{value}</span>;
}

function Overview({ run, openPatient }: { run: Run | null; openPatient: (id: string) => void }) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const rows = patients.map(patient => {
    const session = run?.patientId === patient.id ? run : null;
    const samples = session?.samples ?? baselineHistory[patient.id];
    return { patient, priority: priorityOf(session), latest: samples.at(-1)!, interrupted: Boolean(session?.probeOff) };
  }).sort((a, b) => urgency[b.priority] - urgency[a.priority] || b.latest.time - a.latest.time || a.patient.id.localeCompare(b.patient.id));
  const visible = rows.filter(row =>
    (filter === 'all' || row.priority === filter) &&
    (row.patient.id + ' ' + row.patient.context).toLowerCase().includes(query.trim().toLowerCase()),
  );
  const summary = [
    { label: 'Demo patients', count: rows.length },
    ...priorities.map(label => ({ label, count: rows.filter(row => row.priority === label).length })),
    { label: 'Interrupted', count: rows.filter(row => row.interrupted).length },
  ];
  return <>
    <Heading title="Post-discharge monitoring" description="Clinician workspace"
      action={<a className="button primary" href="#replay">Open scenario replay</a>} />
    <div className="stats" aria-label="Cohort summary">
      {summary.map(item => <div key={item.label}><span className="small">{item.label}</span><b>{item.count}</b></div>)}
    </div>
    <section className="panel queue" aria-labelledby="queue-title">
      <h2 id="queue-title">Patient queue</h2>
      <div className="filters">
        <label>Search patients<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Patient ID or context" /></label>
        <label>Priority<select value={filter} onChange={event => setFilter(event.target.value)}>
          <option value="all">All priorities</option>{priorities.map(item => <option key={item}>{item}</option>)}
        </select></label>
      </div>
      <div className="table-wrap" role="region" aria-label="Patient readings" tabIndex={0}>
        <table>
          <thead><tr>{['Patient', 'Demo context', 'HR (bpm)', 'RR (/min)', 'SpO₂ (%)', 'Temp (°C)', 'Priority', 'Monitoring', 'Source time']
            .map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
          <tbody>
            {visible.map(row => <tr key={row.patient.id}>
              <td><button className="link" onClick={() => openPatient(row.patient.id)}>{row.patient.id}</button></td>
              <td>{row.patient.context}</td>
              {row.latest.values.map((value, index) => <td key={metrics[index].label}>{value ?? 'Unavailable'}</td>)}
              <td><Status value={row.priority} /></td>
              <td>{row.interrupted ? 'Signal interrupted' : 'Available'}</td><td>{sourceTime(row.latest.time)}</td>
            </tr>)}
            {visible.length === 0 && <tr><td colSpan={9}>No demo patients match these filters.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  </>;
}

function Chart({ samples, index, baseline, minutes }: { samples: Sample[]; index: number; baseline: number; minutes: number }) {
  const metric = metrics[index];
  const [low, high] = metric.range;
  const x = (point: number) => 30 + point * 232 / (samples.length - 1);
  const y = (value: number) => 75 - (value - low) * 61 / (high - low);
  const path = samples.map((sample, point) => {
    const value = sample.values[index];
    if (value === null) return '';
    const command = point === 0 || samples[point - 1].values[index] === null ? 'M' : 'L';
    return command + x(point).toFixed(1) + ',' + y(value).toFixed(1);
  }).join(' ');
  const last = samples.at(-1)!;
  const lastValue = last.values[index];
  return <svg viewBox="0 0 280 100" role="img" aria-label={metric.label + ', last ' + minutes + ' minutes of source time. Gaps indicate unavailable readings.'}>
    <path d="M30 14H262 M30 75H262" stroke="#dde3dd" />
    <path d={'M30 ' + y(baseline) + 'H262'} stroke="#78867d" strokeDasharray="4 4" />
    <path d={path} fill="none" stroke="#174b38" strokeWidth="2" />
    {lastValue !== null && <circle cx={262} cy={y(lastValue)} r={3} fill="#174b38" />}
    <text x="0" y="18" fontSize="11">{high}</text><text x="0" y="79" fontSize="11">{low}</text>
    <text x="30" y="94" fontSize="11">{sourceTime(samples[0].time)}</text>
    <text x="262" y="94" fontSize="11" textAnchor="end">{sourceTime(last.time)}</text>
  </svg>;
}

function Evidence({ alert }: { alert: Alert }) {
  return <dl>
    <dt>Triggering reading</dt><dd>{alert.reading} at {sourceTime(alert.time)} source time</dd>
    <dt>Applied demo rule</dt><dd>{alert.rule}</dd>
    <dt>Relevant demo fact</dt><dd>{alert.fact}</dd>
  </dl>;
}

function Monitoring({ patient, run, select }: { patient: Patient; run: Run | null; select: (id: string) => void }) {
  const [minutes, setMinutes] = useState(15);
  const [tab, setTab] = useState<'monitor' | 'profile' | 'twin' | 'intelligence'>('monitor');
  const samples = (run?.samples ?? baselineHistory[patient.id]).slice(-minutes * 2 - 1);
  const latest = samples.at(-1)!;
  const alert = run?.alerts.findLast(event => event.category === 'clinical');
  const details = {
    profile: ['Patient profile', patient.context + '. This synthetic profile includes reference values for the four demo vitals.'],
    twin: ['Digital twin', 'Manifest, model estimates and forecasts are pending the digital-twin service.'],
    intelligence: ['Intelligence', 'Expert and trust assessments are pending clinical-intelligence outputs.'],
  } as const;
  return <>
    <Heading title={patient.id} description={patient.context + ' · Synthetic profile'} action={
      <label>Select patient<select value={patient.id} onChange={event => select(event.target.value)}>
        {patients.map(item => <option key={item.id}>{item.id}</option>)}
      </select></label>
    } />
    <div className="tabs" aria-label="Patient views">
      {Object.entries({ monitor: 'Monitoring', profile: 'Profile', twin: 'Digital twin', intelligence: 'Intelligence' }).map(([key, label]) =>
        <button key={key} aria-pressed={tab === key} onClick={() => setTab(key as typeof tab)}>{label}</button>)}
    </div>
    {tab === 'monitor' ? <div className="detail">
      <section className="stack" aria-label="Vital trends">
        <div className="section-head"><div><h2>Vital trends</h2><p className="small muted">Latest source time {sourceTime(latest.time)}</p></div>
          <label>Trend range<select value={minutes} onChange={event => setMinutes(Number(event.target.value))}>
            {[5, 15, 30].map(value => <option value={value} key={value}>{value} minutes</option>)}
          </select></label>
        </div>
        <div className="vitals">
          {metrics.map((metric, index) => {
            const value = latest.values[index];
            const baseline = patient.baseline[index];
            const delta = value === null ? null : Number((value - baseline).toFixed(1));
            return <article className="vital" key={metric.label}>
              <h3>{metric.label}</h3>
              <p className={'value' + (value === null ? ' missing' : '')}>
                {value ?? 'Unavailable'}{value !== null && <small> {metric.unit}</small>}
              </p>
              <p className="small muted">Demo baseline {baseline} {metric.unit}
                {delta !== null && ' · Δ ' + (delta > 0 ? '+' : '') + delta + (index === 2 ? ' pp' : '')}
              </p>
              <Chart samples={samples} index={index} baseline={baseline} minutes={minutes} />
            </article>;
          })}
        </div>
        <p className="small muted">Time zero marks the start of replay. Dashed lines show demo baselines.</p>
      </section>
      <div className="stack assessment-stack">
        <section className="panel assessment" aria-live="polite">
          <h2>Assessment</h2><p><Status value={priorityOf(run)} /> · Scripted demo status</p>
          {alert ? <><p><strong>{alert.title}</strong></p><Evidence alert={alert} /></>
            : <p>No scripted clinical alert for this patient in the current replay.</p>}
        </section>
        <section className="panel"><h2>Signal quality</h2><p>{run?.probeOff
          ? 'Simulated probe removal. SpO₂ is unavailable and the chart shows a gap.'
          : 'All four simulated signals are available.'}</p></section>
        <section className="panel"><h2>Partial NEWS2-style subtotal</h2><p>Awaiting backend assessment output.</p></section>
      </div>
    </div> : <section className="panel"><h2>{details[tab][0]}</h2><p>{details[tab][1]}</p></section>}
  </>;
}

function AlertCenter({ run }: { run: Run | null }) {
  const [category, setCategory] = useState<AlertCategory>('clinical');
  const alerts = run?.alerts.filter(alert => alert.category === category).toReversed() ?? [];
  return <>
    <Heading title="Alert center" description="Scripted clinical and technical alerts from the current replay."
      action={<a className="button" href="#replay">Open scenario replay</a>} />
    <div className="stack">
      <div><label className="inline-label">Alert category<select value={category} onChange={event => setCategory(event.target.value as AlertCategory)}>
        <option value="clinical">Clinical alerts</option><option value="technical">Technical alerts</option>
      </select></label></div>
      <div className="stack" aria-live="polite">
        {alerts.length === 0 && <p className="panel muted">No {category} alerts in this replay.</p>}
        {alerts.map(alert => <article className="panel" key={alert.time}>
          <h3>{alert.title}</h3><p>{run?.patientId} · {alert.priority ? <Status value={alert.priority} /> : 'Technical'} · Scripted</p>
          <Evidence alert={alert} />
        </article>)}
      </div>
    </div>
  </>;
}

function Replay({ run, patientId, start, togglePause, reset, openPatient }: {
  run: Run | null; patientId: string; start: (id: string, scenario: Scenario) => void;
  togglePause: () => void; reset: () => void; openPatient: (id: string) => void;
}) {
  const [selectedId, setSelectedId] = useState(run?.patientId ?? patientId);
  const [scenario, setScenario] = useState<Scenario>(run?.scenario ?? 'slow');
  return <>
    <Heading title="Scenario replay" description="Replay 15 minutes of simulated readings in about 18 seconds." />
    <div className="replay">
      <div className="stack">
        <form className="panel stack" onSubmit={event => { event.preventDefault(); start(selectedId, scenario); }}>
          <h2>Replay setup</h2>
          <label>Demo patient<select value={selectedId} onChange={event => setSelectedId(event.target.value)}>
            {patients.map(patient => <option key={patient.id} value={patient.id}>{patient.id} · {patient.context}</option>)}
          </select></label>
          <label>Scenario<select value={scenario} onChange={event => setScenario(event.target.value as Scenario)}>
            {Object.entries(scenarios).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select></label>
          <div className="actions">
            <button className="primary" type="submit">Start replay</button>
            <button type="button" disabled={!run || run.status === 'Complete'} onClick={togglePause}>{run?.status === 'Paused' ? 'Resume' : 'Pause'}</button>
            <button type="button" disabled={!run} onClick={reset}>Reset</button>
          </div>
        </form>
        <section className="panel"><h2>Evaluation results</h2><p>Measured results are pending a backend evaluation run.</p></section>
      </div>
      <section className="panel stack">
        <div><h2>Replay timeline</h2><p className="muted" aria-live="polite">{run
          ? scenarios[run.scenario] + ' · ' + run.patientId + ' · ' + run.status
          : 'Ready to start'}</p></div>
        <div><progress value={run?.step ?? 0} max={totalSteps} aria-label="Replay progress" />
          <p className="small">{sourceTime((run?.step ?? 0) * 30)} / 15:00 source time</p></div>
        <ul className="events" aria-live="polite">
          {!run?.alerts.length && <li className="muted">Scripted events appear here as the replay runs.</li>}
          {run?.alerts.map(alert => <li key={alert.time}><time className="small muted">{sourceTime(alert.time)} source time</time><strong>{alert.title}</strong></li>)}
        </ul>
        <button type="button" onClick={() => openPatient(run?.patientId ?? selectedId)}>Open patient monitoring</button>
      </section>
    </div>
  </>;
}

export function App() {
  const [page, setPage] = useState(readPage);
  const [patientId, setPatientId] = useState(patients[0].id);
  const [run, setRun] = useState<Run | null>(null);
  const isRunning = run?.status === 'Running';

  useEffect(() => {
    const sync = () => {
      setPage(readPage());
      window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);

  useEffect(() => {
    if (!isRunning) return;
    const timer = window.setInterval(() => setRun(current => current && advanceRun(current)), 600);
    return () => window.clearInterval(timer);
  }, [isRunning]);

  const patient = patients.find(item => item.id === patientId) ?? patients[0];
  function openPatient(id: string) {
    setPatientId(id);
    window.location.hash = 'monitoring';
  }

  return <>
    <a className="skip" href="#main" onClick={event => {
      event.preventDefault();
      document.querySelector<HTMLElement>('#main')?.focus();
    }}>Skip to dashboard</a>
    <div className="shell">
      <aside>
        <img className="brand" src={logo} alt="Avoflare" />
        <nav aria-label="Dashboard navigation">
          {Object.entries(pages).map(([key, label]) => <a className="button" href={'#' + key} key={key}
            aria-current={page === key ? 'page' : undefined}>{label}</a>)}
        </nav>
        <p className="footnote">Clinical decision support only. Simulation data for demonstration.</p>
      </aside>
      <main id="main" tabIndex={-1}>
        <div className="banner"><strong>Simulation mode</strong> · Synthetic readings and scripted alerts · Backend disconnected</div>
        <AlarmRouting run={run} />
        {page === 'overview' && <Overview run={run} openPatient={openPatient} />}
        {page === 'monitoring' && <Monitoring key={patient.id} patient={patient} run={run?.patientId === patient.id ? run : null} select={setPatientId} />}
        {page === 'alerts' && <AlertCenter run={run} />}
        {page === 'replay' && <Replay run={run} patientId={patientId} openPatient={openPatient}
          start={(id, scenario) => {
            const selected = patients.find(item => item.id === id);
            if (selected) setRun(startRun(selected, scenario, baselineHistory[id]));
          }}
          togglePause={() => setRun(current => current && current.status !== 'Complete'
            ? { ...current, status: current.status === 'Paused' ? 'Running' : 'Paused' } : current)}
          reset={() => setRun(null)} />}
        {page === 'fhir' && <><Heading title="FHIR records" description="Observation retrieval and validation" />
          <section className="panel"><h2>FHIR connection pending</h2><p>Connect the backend FHIR retrieval API to inspect persisted Observations.</p></section></>}
        {page === 'reports' && <><Heading title="Clinical reports" description="Reports and evaluation evidence" />
          <section className="panel"><h2>Reports unavailable</h2><p>Reports will appear after the backend generates them.</p></section></>}
      </main>
    </div>
  </>;
}
