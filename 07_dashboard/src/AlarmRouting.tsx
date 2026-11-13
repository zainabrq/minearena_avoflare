import { useEffect, useMemo, useRef, useState } from 'react';
import type { Run } from './fixtures';

type Recipient = 'Doctor' | 'Nurse' | 'Substitute doctor' | 'Management office';
type Alarm = { id: string; patientId: string; title: string; reading: string; sourceTime: number; recipientIndex: number; acknowledged: boolean; drill: boolean };
const recipients: Recipient[] = ['Doctor', 'Nurse', 'Substitute doctor', 'Management office'];
const intervalMs = 12_000;

function messageFor(recipient: Recipient, alarm: Alarm) {
  const handoff = `Critical review requested for ${alarm.patientId}: ${alarm.title}. ${alarm.reading}.`;
  if (recipient === 'Doctor') return `Urgent clinician assessment: ${handoff}`;
  if (recipient === 'Nurse') return `Doctor did not acknowledge. Please assess ${alarm.patientId} and contact the on-call clinician. ${alarm.reading}.`;
  if (recipient === 'Substitute doctor') return `Primary team did not acknowledge. Please take urgent clinical handoff for ${alarm.patientId}. ${alarm.reading}.`;
  return `Unacknowledged critical alarm for ${alarm.patientId}; arrange immediate clinical coverage. ${alarm.reading}.`;
}

export function AlarmRouting({ run }: { run: Run | null }) {
  const [alarm, setAlarm] = useState<Alarm | null>(null);
  const [available, setAvailable] = useState<Record<Recipient, boolean>>({
    Doctor: true, Nurse: true, 'Substitute doctor': true, 'Management office': true,
  });
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [noticePermission, setNoticePermission] = useState<NotificationPermission | 'unsupported'>(
    typeof Notification === 'undefined' ? 'unsupported' : Notification.permission,
  );
  const lastSeen = useRef('');
  const audio = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (run?.step === 0) { lastSeen.current = ''; return; }
    const critical = run?.alerts.findLast(item => item.category === 'clinical' && item.priority === 'Urgent');
    if (!critical || !run) return;
    const id = `${run.patientId}:${run.scenario}:${critical.time}:${critical.title}`;
    if (id === lastSeen.current) return;
    lastSeen.current = id;
    const firstAvailable = recipients.findIndex(role => available[role]);
    setAlarm({ id, patientId: run.patientId, title: critical.title, reading: critical.reading, sourceTime: critical.time, recipientIndex: firstAvailable === -1 ? recipients.length - 1 : firstAvailable, acknowledged: false, drill: false });
  }, [run]);

  useEffect(() => {
    if (!alarm || alarm.acknowledged || alarm.recipientIndex >= recipients.length - 1) return;
    const timer = window.setTimeout(() => {
      setAlarm(current => {
        if (!current || current.acknowledged || current.id !== alarm.id) return current;
        const next = recipients.findIndex((role, index) => index > current.recipientIndex && available[role]);
        return { ...current, recipientIndex: next === -1 ? recipients.length - 1 : next };
      });
    }, intervalMs);
    return () => window.clearTimeout(timer);
  }, [alarm, available]);

  useEffect(() => {
    if (!alarm || alarm.acknowledged || !soundEnabled) return;
    let stopped = false;
    const ctx = audio.current;
    if (!ctx) return;
    const buzz = () => {
      if (stopped || ctx.state !== 'running') return;
      const oscillator = ctx.createOscillator();
      const gain = ctx.createGain();
      oscillator.type = 'square';
      oscillator.frequency.value = 880;
      gain.gain.value = 0.035;
      oscillator.connect(gain);
      gain.connect(ctx.destination);
      oscillator.start();
      oscillator.stop(ctx.currentTime + 0.18);
      window.setTimeout(() => {
        if (stopped) return;
        oscillator.frequency.value = 660;
        const second = ctx.createOscillator();
        second.type = 'square';
        second.frequency.value = 660;
        second.connect(gain);
        second.start();
        second.stop(ctx.currentTime + 0.18);
      }, 260);
    };
    buzz();
    const timer = window.setInterval(buzz, 1_700);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [alarm, soundEnabled]);

  const recipient = alarm ? recipients[alarm.recipientIndex] : null;
  const message = useMemo(() => alarm && recipient ? messageFor(recipient, alarm) : '', [alarm, recipient]);

  async function enableNotifications() {
    if (typeof Notification === 'undefined') { setNoticePermission('unsupported'); return; }
    const permission = await Notification.requestPermission();
    setNoticePermission(permission);
  }

  async function enableSound() {
    try {
      const AudioContextClass = window.AudioContext;
      audio.current ??= new AudioContextClass();
      await audio.current.resume();
      setSoundEnabled(true);
    } catch {
      setSoundEnabled(false);
    }
  }

  useEffect(() => {
    if (!alarm || alarm.acknowledged || noticePermission !== 'granted') return;
    new Notification(`Critical alarm · ${alarm.patientId}`, { body: `${recipient}: ${message}` });
  }, [alarm?.id, alarm?.recipientIndex, alarm?.acknowledged, noticePermission, message, recipient]);

  function setRoleAvailability(role: Recipient, isAvailable: boolean) {
    setAvailable(current => ({ ...current, [role]: isAvailable }));
    if (!isAvailable && alarm && !alarm.acknowledged && recipients[alarm.recipientIndex] === role) {
      const next = recipients.findIndex((candidate, index) => index > alarm.recipientIndex && candidate !== role && available[candidate]);
      setAlarm({ ...alarm, recipientIndex: next === -1 ? recipients.length - 1 : next });
    }
  }

  function startDrill() {
    const id = `drill:${Date.now()}`;
    lastSeen.current = id;
    const firstAvailable = recipients.findIndex(role => available[role]);
    setAlarm({ id, patientId: 'DRILL', title: 'Critical alarm routing drill', reading: 'Test event · no patient data', sourceTime: 0, recipientIndex: firstAvailable === -1 ? recipients.length - 1 : firstAvailable, acknowledged: false, drill: true });
  }

  return <section className="panel alarm-routing" aria-live="assertive">
    <div className="alarm-head"><div><h2>Critical alarm routing</h2><p className="small muted">Local demo only · no message is sent to a real care team</p></div>
      <div className="actions"><button type="button" onClick={enableSound}>{soundEnabled ? 'Alarm sound enabled' : 'Enable alarm sound'}</button>
        <button type="button" onClick={enableNotifications}>{noticePermission === 'granted' ? 'Browser alerts enabled' : 'Enable browser alerts'}</button>
        <button type="button" className="primary" onClick={startDrill}>Start routing drill</button></div>
    </div>
    <div className="route-settings"><strong>Escalation order</strong>{recipients.map(role => <label key={role}><input type="checkbox" checked={available[role]} onChange={event => setRoleAvailability(role, event.target.checked)} />{role} available</label>)}</div>
    {alarm ? <div className={'active-alarm' + (alarm.acknowledged ? ' acknowledged' : '')}>
      <div><span className="alarm-tag">{alarm.drill ? 'DRILL' : 'CRITICAL'}</span><strong>{alarm.title}</strong><span>{alarm.patientId} · source {String(Math.floor(alarm.sourceTime / 60)).padStart(2, '0')}:{String(alarm.sourceTime % 60).padStart(2, '0')}</span></div>
      <div><strong>{alarm.acknowledged ? 'Acknowledged locally' : `Current recipient: ${recipient}`}</strong><p>{message}</p>
        {!alarm.acknowledged && <button type="button" className="primary" onClick={() => setAlarm(current => current ? { ...current, acknowledged: true } : current)}>Acknowledge demo alarm</button>}
        {alarm.acknowledged && <button type="button" onClick={() => setAlarm(null)}>Clear demo alarm</button>}
      </div>
      {!alarm.acknowledged && <p className="small muted">Unacknowledged alarms advance every 12 seconds in this demo. Acknowledgement stops the local buzzer; it does not resolve a clinical episode.</p>}
    </div> : <p className="small muted">No active critical alarm. Urgent scripted replay events appear here automatically.</p>}
  </section>;
}
