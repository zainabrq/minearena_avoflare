#!/usr/bin/env python3
"""Offline structural preflight for existing MATLAB CSV batches; not clinical validation.
Uses temporary SQLite to join large tables without loading them entirely into RAM.
Accepts documented column aliases; fail clearly if actual export needs a mapping.
"""
import argparse,csv,hashlib,json,math,sqlite3,sys,tempfile
from collections import Counter
from pathlib import Path

ALIASES={
 'run':('run_id','session_id'), 'patient':('patient_id','subject_id'),
 'time':('source_time_s','timestamp_seconds','elapsed_seconds','time_s'),
 'hr':('HR','hr','hr_bpm','heart_rate_bpm'), 'rr':('RESP','rr','rr_per_min','respiratory_rate_per_min'),
 'spo2':('SpO2','spo2','spo2_pct','spo2_percent'), 'temp':('TEMP','temp','temperature','temperature_c'),
 'true_hr':('true_HR','true_hr','true_hr_bpm'), 'true_rr':('true_RESP','true_rr','true_rr_per_min'),
 'true_spo2':('true_SpO2','true_spo2','true_spo2_pct'), 'true_temp':('true_TEMP','true_temp','true_temperature','true_temperature_c')}
MISSING={'','nan','na','null','none','missing','<missing>'}

def choose(cols,key):
    present=[c for c in ALIASES[key] if c in cols]
    if not present: raise ValueError(f'No column for {key}; expected one of {ALIASES[key]}')
    return present[0]

def parse_num(value,allow_missing):
    if value is None or value.strip().lower() in MISSING:
        if allow_missing:return None
        raise ValueError('missing required numeric value')
    v=float(value)
    if not math.isfinite(v): raise ValueError('nonfinite numeric value')
    return v

def forbidden(c):
    s=c.lower()
    return (s.startswith(('true_','target_','fault_','artifact_','future_','deterioration_','scenario_')) or s in {'scenario','severity','ground_truth','calibration_complete'})

def load_file(db,path,table,truth,errors,warnings):
    runs={}; missing=Counter(); count=0; examples=[]
    db.execute(f'CREATE TABLE {table} (run TEXT NOT NULL, t REAL NOT NULL, patient TEXT NOT NULL, PRIMARY KEY(run,t)) WITHOUT ROWID')
    with path.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f); cols=reader.fieldnames or []
        if len(cols)!=len(set(cols)): raise ValueError(f'{path.name}: duplicate column names')
        mapping={k:choose(cols,k) for k in ('run','patient','time')}
        keys=['true_hr','true_rr','true_spo2','true_temp'] if truth else ['hr','rr','spo2','temp']
        mapping.update({k:choose(cols,k) for k in keys})
        if not truth:
            leaked=[c for c in cols if forbidden(c)]
            if leaked: errors.append(f'{path.name}: offline/label columns present: {leaked}; exclude from runtime export/encoder')
        pending=[]; dup=0; bad_rows=0; nonmonotonic=0; identity_errors=0; physical_errors=0
        for line,row in enumerate(reader,2):
            count+=1
            try:
                run=row[mapping['run']].strip(); patient=row[mapping['patient']].strip(); t=parse_num(row[mapping['time']],False)
                if not run or not patient:raise ValueError('empty run/patient ID')
                vals=[parse_num(row[mapping[k]],not truth) for k in keys]
                if truth and (vals[0]<0 or vals[1]<0 or not 0<=vals[2]<=100):physical_errors+=1
                for k,v in zip(keys,vals):
                    if v is None:missing[k]+=1
                if run not in runs:
                    runs[run]={'patient_id':patient,'first':t,'last':t,'min':t,'max':t,'rows':0,'gaps':0,'hash':hashlib.sha256()}
                r=runs[run]
                if r['patient_id']!=patient:identity_errors+=1
                if r['rows'] and t<=r['last']:nonmonotonic+=1
                if r['rows'] and t-r['last']>1.000001:r['gaps']+=1
                r['last']=t;r['min']=min(t,r['min']);r['max']=max(t,r['max']);r['rows']+=1
                r['hash'].update(json.dumps([t-r['first'],vals],separators=(',',':')).encode()+b'\n')
                pending.append((run,t,patient))
                if len(pending)>=10000:
                    before=db.total_changes;db.executemany(f'INSERT OR IGNORE INTO {table} VALUES (?,?,?)',pending);dup+=len(pending)-(db.total_changes-before);pending=[]
            except (ValueError,AttributeError,TypeError,KeyError) as e:
                bad_rows+=1
                if len(examples)<10:examples.append({'line':line,'error':str(e)})
        if pending:
            before=db.total_changes;db.executemany(f'INSERT OR IGNORE INTO {table} VALUES (?,?,?)',pending);dup+=len(pending)-(db.total_changes-before)
        db.commit()
    for n,msg in [(bad_rows,'malformed rows'),(dup,'duplicate run/time keys'),(nonmonotonic,'non-increasing run timestamps'),(identity_errors,'run patient identity conflicts'),(physical_errors,'negative HR/RR or out-of-range true SpO2')]:
        if n:errors.append(f'{path.name}: {n} {msg}')
    if not count:errors.append(f'{path.name}: no data rows')
    output={}
    for run,r in runs.items():
        output[run]={'patient_id':r['patient_id'],'rows':r['rows'],'start_s':r['min'],'end_s':r['max'],'span_s':r['max']-r['min'],'gaps_gt_1s':r['gaps'],'trajectory_sha256':r['hash'].hexdigest()}
    return {'rows':count,'run_count':len(runs),'runs':output,'missing_counts':{k:missing[k] for k in keys},'column_mapping':mapping,'bad_row_examples':examples}

def validate(folder):
    errors=[];warnings=[];report={'status':'not_run','folder':str(folder),'errors':errors,'warnings':warnings,'limits':['Structural preflight only; no physiological/clinical validation, independent seed proof, context cutoff or event label verification.','Fingerprint assumes ordered run rows and compares exact values relative to first timestamp. Near-duplicates require additional review.','Gaps assume intended 1 Hz; non-1Hz exports need explicit cadence review.','Unmatched truth rows may be intentional dropout; require independent annotation before acceptance.']}
    for name in ['clinical_context.json','run_manifest.json']:
        path=folder/name
        if not path.exists() and name=='run_manifest.json':path=folder/'scenario_manifest.json'
        try:
            obj=json.loads(path.read_text(encoding='utf-8-sig'))
            report[name]={'path':str(path),'json_valid':True,'top_level_type':type(obj).__name__}
        except Exception as e:errors.append(f'{name}: {e}')
    if not (folder/'observations.csv').is_file() or not (folder/'ground_truth.csv').is_file():
        errors.append('Both observations.csv and ground_truth.csv required.');report['status']='blocked';return report
    try:
        with tempfile.TemporaryDirectory() as tmp:
            db=sqlite3.connect(Path(tmp)/'join.sqlite')
            try:
                report['observed']=load_file(db,folder/'observations.csv','obs',False,errors,warnings)
                report['ground_truth']=load_file(db,folder/'ground_truth.csv','gt',True,errors,warnings)
                q=lambda s:db.execute(s).fetchone()[0]
                report['join']={'observations_without_truth':q('SELECT count(*) FROM obs LEFT JOIN gt USING(run,t) WHERE gt.run IS NULL'), 'truth_without_observations':q('SELECT count(*) FROM gt LEFT JOIN obs USING(run,t) WHERE obs.run IS NULL'), 'patient_identity_mismatch':q('SELECT count(*) FROM obs JOIN gt USING(run,t) WHERE obs.patient!=gt.patient')}
                if report['join']['observations_without_truth']:errors.append('Observed rows without matched truth')
                if report['join']['patient_identity_mismatch']:errors.append('Observed/truth patient identity mismatch')
                if report['join']['truth_without_observations']:warnings.append('Truth rows without observed rows; verify explicit packet-drop annotations before training.')
            finally:db.close()
    except Exception as e:errors.append(str(e));report['status']='blocked';return report
    for label in ['observed','ground_truth']:
        groups={}
        for run,r in report[label]['runs'].items():groups.setdefault(r['trajectory_sha256'],[]).append(run)
        duplicate=[v for v in groups.values() if len(v)>1];report[label]['exact_duplicate_run_groups']=duplicate
        if duplicate:warnings.append(f'{label}: exact duplicate trajectory groups; investigate before splitting.')
    spans=[r['span_s'] for r in report['ground_truth']['runs'].values()];report['runs_with_600s_span']=sum(s>=600 for s in spans)
    if not report['runs_with_600s_span']:warnings.append('No run spans 600s (proposed 5min history + 5min target).')
    report['status']='failed' if errors else 'review_required' if warnings else 'structural_checks_passed'
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    report=validate(a.folder);s=json.dumps(report,indent=2);print(s)
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(s+'\n',encoding='utf-8')
    return 0 if report['status']=='structural_checks_passed' else 2 if report['status']=='blocked' else 1
if __name__=='__main__':sys.exit(main())
