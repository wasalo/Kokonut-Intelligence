# delphi

`services.delphi` — Real-time Delphi service package.

## CLI Usage

```bash
python3 -m services.delphi
```
```bash
python3 -m services.delphi.cli --help
```

## Modules

- `cli` — CLI for the Real-time Delphi service.
- `consensus` — Consensus math for Real-time Delphi.
- `facilitator` — Facilitator for Real-time Delphi.
- `minority` — Governed minority reports for Delphi studies.
- `models` — Pydantic models for the Real-time Delphi service: study, panel member, item,
- `panel` — Panel management for Real-time Delphi.

## Files

7 Python modules

## Access boundary

The legacy `Facilitator`, `PanelManager`, and `MinorityReportManager`
database-backed methods are compatibility facades and raise before using a
connection or cursor. Use the authenticated, location-scoped Gateway for the
study and participant workflows it implements. Direct panel administration,
diversity assessment, minority-report operations, and panel calibration are
not available until their authorization, privacy, and review contracts exist.
`ConsensusCalculator` remains available for pure, in-memory consensus math.
