# Telemetry Quality Gate

[![Tests](https://github.com/arslan1t/telemetry-quality-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/arslan1t/telemetry-quality-gate/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![Standard library only](https://img.shields.io/badge/dependencies-standard%20library-green)
[![MIT license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

A dependency-free Python CLI that checks timestamped sensor CSV files before
analysis. Reports duplicate timestamps, out-of-order samples, sampling gaps,
invalid numbers, missing sensor identifiers, and values outside configured bounds.

Get structured JSON for automation and an optional standalone HTML report for
reviewing the same result in a browser. The HTML file has no external assets,
scripts, or dependencies.

Python 3.10+. Intended for offline engineering datasets and CI checks.

![Standalone HTML report generated from the synthetic anomaly fixture](report-preview.jpg)

## Run

```sh
python3 telemetry.py example.csv --minimum -40 --maximum 125 --max-gap 2
python3 telemetry.py example_anomalies.csv --html-report quality-report.html > report.json
python3 -m unittest -v
```

The supplied example deliberately contains anomalies, so the first command exits
with status **1**. Exit 0 means all rows passed; 2 means a file/configuration error.
The report is valid JSON and can be redirected to a file.

`--html-report PATH` additionally writes a UTF-8 HTML file. JSON remains on stdout,
and finding issues still returns 1. File or configuration errors return 2 without
JSON output. A report path matching the input CSV is rejected to prevent replacing
the dataset. Parent directories must already exist; an existing report is replaced.

## Try a complete example

Both fixtures are **synthetic** and make no claim about real hardware:

| Input | Rows | Sensors with numeric samples | Expected result |
| --- | ---: | ---: | --- |
| `example_valid.csv` | 8 | 2 | Pass, no issues, exit 0 |
| `example_anomalies.csv` | 8 | 2 | 6 issues across 5 rows, exit 1 |

```sh
python3 telemetry.py example_valid.csv --html-report clean-report.html
python3 telemetry.py example_anomalies.csv --html-report quality-report.html
```

Open the generated file in a browser, or inspect the checked-in
[sample HTML report](example-report.html), generated from `example_anomalies.csv`
with the default thresholds. It contains overall row/sensor counts, the count of
rows with issues, all six category counts (including zero counts), configured
thresholds, and per-issue CSV line references and details. A row can have more than
one issue, so the issue count can exceed the number of affected rows. All source
names and sensor identifiers are HTML-escaped before rendering.

## Input contract

Required headers: `timestamp,sensor,value`. Timestamps are finite numeric seconds
on a consistent clock. Values are finite numeric measurements in one common unit.
Rows may interleave sensors; ordering and gaps are evaluated independently per
sensor. Boundaries are inclusive; a gap is flagged only when strictly greater
than `--max-gap`. CSV line references assume one physical line per record.

## Example report

The sample produces one each of: `duplicate_timestamp`, `sampling_gap`,
`out_of_range`, `out_of_order`, and `invalid_number`. Each issue includes the
record line and sensor. A row can produce multiple issues.

## Design decisions

- Never silently coerce NaN or infinity into valid measurements.
- Keep a per-sensor timestamp high-water mark, so a late arrival does not create
  a spurious gap on the next valid sample.
- Preserve anomalies as structured records, suitable for scripts and CI.
- Keep the parser and validation core separate for direct unit testing.

Time complexity is O(N). Memory is O(N): the current CLI loads records, retains
seen timestamps for exact duplicate detection and collects the full issue report.
This is deliberately an offline validator, not a bounded-memory streaming service.

## Validation and limits

Tests cover interleaved sensors, every issue category, threshold boundaries,
nonfinite values, invalid configuration, CSV schema and late-arrival handling,
known synthetic fixture counts, HTML escaping, and CLI JSON/HTML consistency and
exit statuses.
No inferred sample rate, clock-drift correction, unit conversion or automatic data
repair. Thresholds must be selected for the actual sensor. Empty datasets pass
vacuously and report zero rows; downstream checks should require their own minimum
sample count.

## Development

The GitHub Actions workflow runs the test suite on Python 3.10, 3.12, and 3.13.
It also checks the clean/anomalous CLI fixtures and regenerates the sample HTML
report to check that the committed example matches the code.

No production deployment or hardware integration is claimed. MIT licensed.
