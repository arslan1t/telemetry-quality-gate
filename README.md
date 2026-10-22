# Telemetry Quality Gate

[![CI](https://github.com/arslan1t/telemetry-quality-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/arslan1t/telemetry-quality-gate/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![license](https://img.shields.io/badge/license-MIT-blue)

A dependency-free Python CLI that checks timestamped sensor CSV files before
analysis. Reports duplicate timestamps, out-of-order samples, sampling gaps,
invalid numbers, missing sensor identifiers, and values outside configured bounds.

Python 3.10+. Intended for offline engineering datasets and CI checks.

## Run

```sh
python3 telemetry.py example.csv --minimum -40 --maximum 125 --max-gap 2
python3 -m unittest -v
```

The supplied example deliberately contains anomalies, so the first command exits
with status **1**. Exit 0 means all rows passed; 2 means a file/configuration error.
The report is valid JSON and can be redirected to a file.

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
nonfinite values, invalid configuration, CSV schema and late-arrival handling.
No inferred sample rate, clock-drift correction, unit conversion or automatic data
repair. Thresholds must be selected for the actual sensor. Empty datasets pass
vacuously and report zero rows; downstream checks should require their own minimum
sample count.

## Development

No production deployment or hardware integration is claimed. MIT licensed.
