"""Validate timestamped sensor CSV data and emit JSON, with an optional HTML report."""
import argparse,csv,json,math
from collections import defaultdict
from html import escape
from pathlib import Path

ISSUE_LABELS = {
    'missing_sensor': 'Missing sensor identifier',
    'invalid_number': 'Invalid or nonfinite number',
    'out_of_range': 'Value outside configured bounds',
    'duplicate_timestamp': 'Duplicate timestamp',
    'out_of_order': 'Out-of-order sample',
    'sampling_gap': 'Sampling gap',
}

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

def render_html(report, source='Sensor data', minimum=-40.0, maximum=125.0, max_gap=2.0):
    """Render an audit result as one portable HTML file, without scripts or assets.

    Sensor identifiers and source names are untrusted CSV/file content. Escape
    every dynamic text value rather than interpolating it as HTML.
    """
    def safe(value):
        return escape(str(value), quote=True)

    status = 'PASS' if report['passed'] else 'REVIEW'
    flagged_rows = len({item['line'] for item in report['issues']})
    counts = ''.join(
        '<tr><td>' + safe(label) + '</td><td class="number">'
        + safe(report['issue_counts'].get(kind, 0)) + '</td></tr>'
        for kind, label in ISSUE_LABELS.items()
    )
    records = []
    for item in report['issues']:
        detail = {key: value for key, value in item.items()
                  if key not in ('line', 'sensor', 'kind')}
        records.append(
            '<tr><td class="number">' + safe(item['line']) + '</td><td>'
            + safe(item['sensor'] or '(missing)') + '</td><td>'
            + safe(ISSUE_LABELS.get(item['kind'], item['kind'])) + '</td><td><code>'
            + safe(json.dumps(detail, sort_keys=True, ensure_ascii=False, allow_nan=False)
                   if detail else '—') + '</code></td></tr>'
        )
    if not records:
        records.append('<tr><td colspan="4" class="empty">No issues found within the configured checks.</td></tr>')

    return '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Telemetry Quality Gate — ''' + safe(source) + '''</title>
<style>
:root{color-scheme:light;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#162a35;background:#edf2f3}
*{box-sizing:border-box}body{margin:0;padding:48px 24px}main{max-width:1080px;margin:auto}
header{border-top:5px solid #177264;padding-top:24px;display:flex;gap:24px;justify-content:space-between;align-items:start}
.eyebrow{font-size:12px;letter-spacing:.16em;font-weight:700;color:#43616a;text-transform:uppercase}
h1{font-size:clamp(28px,4vw,46px);letter-spacing:-.045em;line-height:1.1;margin:14px 0}p{line-height:1.6}
.source{overflow-wrap:anywhere;color:#45616a;margin-top:0}.badge{font-size:12px;font-weight:800;letter-spacing:.08em;border:1px solid currentColor;border-radius:4px;padding:8px 12px;white-space:nowrap}
.PASS{color:#146a4c;background:#e0f2e8}.REVIEW{color:#8d4a10;background:#fff0d9}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#c9d6d9;border:1px solid #c9d6d9;margin:30px 0}
.metric{padding:22px;background:#fff}.metric strong{display:block;font-size:34px;font-weight:650;letter-spacing:-.04em}.metric span{font-size:13px;color:#45616a}
h2{font-size:20px;letter-spacing:-.025em;margin:30px 0 12px}.panel{background:white;border:1px solid #c9d6d9;padding:24px}
.settings{display:flex;flex-wrap:wrap;gap:12px 32px;font-size:14px;color:#45616a}.settings b{color:#162a35}
table{width:100%;border-collapse:collapse;font-size:14px;text-align:left}th{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#45616a;background:#f4f7f7}
th,td{padding:13px 14px;border-bottom:1px solid #e0e8e9;vertical-align:top;overflow-wrap:anywhere}tr:last-child td{border-bottom:0}.number{text-align:right;font-variant-numeric:tabular-nums}
.table-scroll{overflow:auto;border:1px solid #c9d6d9;background:#fff}code{font-size:12px;white-space:pre-wrap}.empty{padding:28px;color:#45616a}
.note{font-size:13px;color:#45616a;margin:14px 0 0}footer{font-size:12px;line-height:1.7;color:#45616a;border-top:1px solid #c9d6d9;padding-top:20px;margin-top:32px}
@media(max-width:650px){body{padding:24px 14px}.metrics{grid-template-columns:repeat(2,1fr)}.metric{padding:16px}.panel{padding:18px}th,td{padding:10px 8px}header{gap:12px}}
@media print{body{padding:0;background:#fff}.table-scroll{overflow:visible}header{break-inside:avoid}.metric{padding:14px}tr{break-inside:avoid}}
</style>
</head>
<body><main>
<header><div><div class="eyebrow">Offline sensor data / quality report</div><h1>Telemetry Quality Gate</h1><p class="source">''' + safe(source) + '''</p></div><span class="badge ''' + status + '''">''' + status + '''</span></header>
<section class="metrics" aria-label="Audit summary">
<div class="metric"><strong>''' + safe(report['rows']) + '''</strong><span>Rows checked</span></div>
<div class="metric"><strong>''' + safe(report['sensors']) + '''</strong><span>Sensors with numeric samples</span></div>
<div class="metric"><strong>''' + safe(flagged_rows) + '''</strong><span>Rows with issues</span></div>
<div class="metric"><strong>''' + safe(len(report['issues'])) + '''</strong><span>Total issues</span></div>
</section>
<section class="panel"><div class="eyebrow">Configured checks</div><div class="settings"><p>Value range <b>''' + safe(minimum) + ''' to ''' + safe(maximum) + '''</b> (inclusive)</p><p>Maximum gap <b>''' + safe(max_gap) + ''' seconds</b></p></div><p class="note">Ordering, gaps and duplicates are checked independently for each sensor. One row can produce more than one issue.</p></section>
<h2>Issue breakdown</h2><div class="table-scroll"><table><thead><tr><th scope="col">Category</th><th scope="col" class="number">Count</th></tr></thead><tbody>''' + counts + '''</tbody></table></div>
<h2>Issue details</h2><div class="table-scroll"><table><thead><tr><th scope="col" class="number">CSV line</th><th scope="col">Sensor</th><th scope="col">Category</th><th scope="col">Details</th></tr></thead><tbody>''' + ''.join(records) + '''</tbody></table></div>
<footer>Generated by Telemetry Quality Gate · Report schema ''' + safe(report['schema_version']) + '''<br>Offline checks do not establish hardware safety or data completeness. CSV line references assume one physical line per record. Empty inputs pass these checks; require a minimum sample count separately.</footer>
</main></body></html>
'''

def main(argv=None):
    """Keep JSON on stdout; report/file/configuration failures use exit status 2."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv',type=Path)
    parser.add_argument('--minimum',type=float,default=-40)
    parser.add_argument('--maximum',type=float,default=125)
    parser.add_argument('--max-gap',type=float,default=2)
    parser.add_argument('--html-report',type=Path,metavar='PATH',
                        help='also write a standalone HTML quality report to PATH')
    args=parser.parse_args(argv)
    try:
        report=audit(read_csv(args.csv),args.minimum,args.maximum,args.max_gap)
        if args.html_report:
            if args.html_report.resolve() == args.csv.resolve():
                raise ValueError('HTML report path must differ from the input CSV path')
            args.html_report.write_text(
                render_html(report,args.csv.name,args.minimum,args.maximum,args.max_gap),
                encoding='utf-8')
    except (ValueError,OSError) as error:
        parser.exit(2,str(error)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))
    return 0 if report['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())
