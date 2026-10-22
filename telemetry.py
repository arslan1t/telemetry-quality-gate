"""Validate timestamped sensor CSV data and emit a machine-readable quality report."""
import argparse,csv,json,math
from collections import defaultdict
from pathlib import Path

def audit(rows,minimum=-40.0,maximum=125.0,max_gap=2.0):
    if not all(math.isfinite(v) for v in (minimum,maximum,max_gap)) or minimum>maximum or max_gap<=0:
        raise ValueError('Require finite bounds, minimum <= maximum, max_gap > 0')
    issues=[]; previous={}; seen=defaultdict(set); total=0
    def issue(line,sensor,kind,**detail):
        issues.append(dict(line=line,sensor=sensor,kind=kind,**detail))
    for line,row in enumerate(rows,start=2):
        total+=1;sensor=(row.get('sensor') or '').strip()
        if not sensor:
            issue(line,sensor,'missing_sensor');continue
        try:
            timestamp=float(row['timestamp']);value=float(row['value'])
            if not math.isfinite(timestamp) or not math.isfinite(value):raise ValueError()
        except (KeyError,TypeError,ValueError):
            issue(line,sensor,'invalid_number');continue
        if not minimum<=value<=maximum:
            issue(line,sensor,'out_of_range',value=value)
        if timestamp in seen[sensor]:issue(line,sensor,'duplicate_timestamp',timestamp=timestamp)
        seen[sensor].add(timestamp)
        if sensor in previous:
            delta=timestamp-previous[sensor]
            if delta<0:issue(line,sensor,'out_of_order',timestamp=timestamp)
            elif delta>max_gap:issue(line,sensor,'sampling_gap',seconds=delta)
        # Keep a high-water mark: late arrivals must not create false future gaps.
        previous[sensor]=max(timestamp,previous.get(sensor,timestamp))
    counts=defaultdict(int)
    for item in issues:counts[item['kind']]+=1
    return dict(schema_version=1,rows=total,sensors=len(seen),passed=not issues,
                issue_counts=dict(sorted(counts.items())),issues=issues)

def read_csv(path):
    with Path(path).open(newline='') as stream:
        reader=csv.DictReader(stream)
        if not {'timestamp','sensor','value'} <= set(reader.fieldnames or []):
            raise ValueError('Required CSV headers: timestamp,sensor,value')
        return list(reader)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv',type=Path)
    parser.add_argument('--minimum',type=float,default=-40)
    parser.add_argument('--maximum',type=float,default=125)
    parser.add_argument('--max-gap',type=float,default=2)
    args=parser.parse_args()
    try:report=audit(read_csv(args.csv),args.minimum,args.maximum,args.max_gap)
    except (ValueError,OSError) as error:parser.exit(2,str(error)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))
    raise SystemExit(0 if report['passed'] else 1)
