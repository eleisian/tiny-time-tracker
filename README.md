# tt-time

Tiny terminal time tracker you can run as `tt`.

- Tiny time tracker for freelancers who need a fast, distraction-free way to log billable hours by project. Start a session, do the work, press Ctrl-C to save—or just close the terminal and it auto-stops. Generate clear weekly/monthly summaries and export a CSV for invoicing.

Key points:
- Multi-word project names without quotes: `tt time start project name`
- Stop with Ctrl-C (or by closing the terminal); optional `tt time stop` from another shell
- Multiple log formats: `1h30m`, `45m`, `2h`, `1:30`, `90` (minutes), `3.5` (hours)
- Clean CLI reports + automatic CSV export to `~/Documents/Time Sheet Reports/...`
- Plain JSON storage; easy to back up or sync

- Data file (default): `~/.timelog.json`
- Override data file: set env `TT_TIME_FILE=/path/to/file.json`

## Install (recommended)

Using pipx (isolated, global CLI):

```bash
pipx install .
# for local dev, auto-reload code
pipx install --editable .
```

Alternative (user install):

```bash
pip install --user .
# ensure ~/.local/bin is on PATH (macOS/Linux)
```

## Usage

```bash
# start tracking a project (multi-word names don't need quotes)
tt time start project name

# stop active timer
# in the case that somehow your timer breaks, you can stop it from another terminal
tt time stop

# manually log a duration
# supported formats: 1h30m, 2h, 45m, 1:30 (HH:MM), 90 (minutes), 3.5 (hours)
# note: use quotes if the project name has spaces
tt time log "project name" 1h30m

# show a report
tt time report
```

## Report output
Shows entries and per-project totals for all completed sessions in the log.

## Uninstall

```bash
pipx uninstall tt-time
# or
pip uninstall tt-time
```
