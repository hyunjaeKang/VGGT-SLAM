"""Summarize measured V4 worker timings without treating targets as passes."""
import argparse
import json
from pathlib import Path
import numpy as np


def report(folder):
    events=[]
    for path in folder.rglob('timings.jsonl'):
        for line in path.read_text().splitlines():
            try:events.append(json.loads(line))
            except json.JSONDecodeError:pass
    groups={}
    for event in events:
        for key,value in event.items():
            if isinstance(value,(int,float)) and not isinstance(value,bool) and ('seconds' in key or key.endswith('_s')):
                groups.setdefault(f'{event.get("stage","unknown")}.{key}',[]).append(value)
    return {'folder':str(folder),'event_count':len(events),'metrics':{key:{'n':len(values),'p50':float(np.percentile(values,50)),'p95':float(np.percentile(values,95)),'max':max(values)} for key,values in groups.items()},
            'qualification':'Measured samples only. No independent GT or realtime acceptance implied.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=json.dumps(report(args.folder),indent=2)
    if args.output:args.output.write_text(result+'\n')
    print(result)
