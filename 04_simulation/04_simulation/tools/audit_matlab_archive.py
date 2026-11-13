#!/usr/bin/env python3
"""Read every ZIP file entry and verify its CRC; never extract or execute it."""
import argparse, hashlib, json, sys, zipfile
from pathlib import Path

def audit(path):
    entries=[]
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir(): continue
            row={'path':info.filename,'uncompressed_bytes':info.file_size,'crc32':f'{info.CRC:08x}'}
            try:
                h=hashlib.sha256()
                with z.open(info) as f:
                    for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
                row.update(status='readable_crc_verified',sha256=h.hexdigest())
            except Exception as e: row.update(status='unreadable',error=f'{type(e).__name__}: {e}')
            entries.append(row)
    bad=sum(e['status']=='unreadable' for e in entries)
    return {'archive':str(path),'file_count':len(entries),'readable':len(entries)-bad,'unreadable':bad,'entries':entries}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    try: report=audit(a.archive)
    except Exception as e: print(f'Archive open failed: {e}',file=sys.stderr);return 2
    s=json.dumps(report,indent=2); print(s)
    if a.output: a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(s+'\n',encoding='utf-8')
    return 1 if report['unreadable'] else 0
if __name__=='__main__': sys.exit(main())
