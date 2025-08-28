#!/usr/bin/env python3
import argparse
import json
import os
import csv
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
import time as _time
import signal

DEFAULT_DATA_FILE = os.path.expanduser("~/.timelog.json")
ENV_DATA_FILE = "TT_TIME_FILE"


def data_file_path() -> str:
    # 1) Explicit env override wins
    env = os.environ.get(ENV_DATA_FILE)
    if env:
        return os.path.expanduser(env)
    # 2) Fallback to home file
    return DEFAULT_DATA_FILE


def load_data() -> List[Dict]:
    path = data_file_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # Corrupt file fallback
            backup = path + ".bak"
            try:
                os.replace(path, backup)
            except Exception:
                pass
            return []
    return []


essential_keys = {"project", "start", "end"}


def save_data(data: List[Dict]) -> None:
    path = data_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # prune unexpected fields lightly and ensure order
    cleaned: List[Dict] = []
    for e in data:
        cleaned.append({
            "project": e.get("project"),
            "start": e.get("start"),
            "end": e.get("end"),
            **{k: v for k, v in e.items() if k not in essential_keys},
        })
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cleaned, f, indent=2)
    os.replace(tmp, path)


def parse_duration(s: str) -> timedelta:
    s = s.strip().lower()
    total = 0
    num = ""
    had_unit = False
    for ch in s:
        if ch.isdigit():
            num += ch
        elif ch in ("h", "m"):
            if not num:
                raise ValueError("Missing number before unit")
            if ch == "h":
                total += int(num) * 60
            else:
                total += int(num)
            num = ""
            had_unit = True
        elif ch in (":",):
            # Support HH:MM format
            pass
        else:
            raise ValueError(f"Unsupported character in duration: {ch}")
    if num and not had_unit:
        # plain minutes (e.g., "90")
        total += int(num)
    if total <= 0:
        raise ValueError("Duration must be > 0")
    return timedelta(minutes=total)


def iso_now() -> str:
    return datetime.now().isoformat()


def _secs_to_hms(total_seconds: int) -> str:
    if total_seconds < 0:
        total_seconds = 0
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _osc8_link(text: str, url: str) -> str:
    # OSC 8 hyperlink sequence (supported by many modern terminals and VS Code terminal)
    # format: ESC ] 8 ; ; URL ESC \ TEXT ESC ] 8 ; ; ESC \
    return f"\x1b]8;;{url}\x1b\\{text}\x1b]8;;\x1b\\"


def _render_analog_clock_loop(start_dt: datetime, project_name: str) -> None:
    # Large ASCII digital clock (HH:MM:SS) using light shading (░) instead of solid blocks
    DIGITS = {
        '0': [
            " ░░░ ",
            "░   ░",
            "░   ░",
            "░   ░",
            " ░░░ ",
        ],
        '1': [
            "  ░  ",
            " ░░  ",
            "  ░  ",
            "  ░  ",
            " ░░░ ",
        ],
        '2': [
            " ░░░ ",
            "    ░",
            " ░░░ ",
            "░    ",
            "░░░░░",
        ],
        '3': [
            "░░░░ ",
            "    ░",
            " ░░░ ",
            "    ░",
            "░░░░ ",
        ],
        '4': [
            "░  ░ ",
            "░  ░ ",
            "░░░░░",
            "   ░ ",
            "   ░ ",
        ],
        '5': [
            "░░░░░",
            "░    ",
            "░░░░ ",
            "    ░",
            "░░░░ ",
        ],
        '6': [
            " ░░░ ",
            "░    ",
            "░░░░ ",
            "░   ░",
            " ░░░ ",
        ],
        '7': [
            "░░░░░",
            "   ░ ",
            "  ░  ",
            " ░   ",
            " ░   ",
        ],
        '8': [
            " ░░░ ",
            "░   ░",
            " ░░░ ",
            "░   ░",
            " ░░░ ",
        ],
        '9': [
            " ░░░ ",
            "░   ░",
            " ░░░░",
            "    ░",
            " ░░░ ",
        ],
        ':': [
            "     ",
            "  ░  ",
            "     ",
            "  ░  ",
            "     ",
        ],
    }

    while True:
        now = datetime.now()
        elapsed = now - start_dt
        hhmmss = now.strftime("%H:%M:%S")
        # Build 5 rows
        rows = [""] * 5
        for ch in hhmmss:
            glyph = DIGITS.get(ch, DIGITS['0'])
            for i in range(5):
                rows[i] += glyph[i] + "  "

        # Clear screen and move cursor to top-left
        print("\x1b[2J\x1b[H", end="")
        for r in rows:
            print(r)

        total = int(elapsed.total_seconds())
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        print("")
        # lowercase status lines
        print(f"currently working on: {str(project_name).lower()}")
        print(now.strftime("time: %Y-%m-%d %H:%M:%S").lower())
        print(f"elapsed: {h}h{m:02d}m{s:02d}s")
        _time.sleep(1)


def cmd_start(args: argparse.Namespace) -> None:
    data = load_data()
    if data and data[-1].get("end") is None:
        active = data[-1]
        started = datetime.fromisoformat(active["start"]).strftime("%Y-%m-%d %H:%M")
        print(f"Already tracking '{active['project']}' since {started}. Use 'tt time stop' first.")
        return
    now_iso = iso_now()
    # Support multi-word project names: args.project may be a list when nargs='+'
    project_name = " ".join(args.project) if isinstance(args.project, list) else args.project
    entry = {"project": project_name, "start": now_iso, "end": None}
    data.append(entry)
    save_data(data)
    print(f"Started tracking: {project_name}")
    # Show clock by default unless user opts out
    if not getattr(args, "no_clock", False):
        # Install signal handlers to finalize on terminal/session close
        def _finalize_active_from_signal(signum, _frame):
            try:
                end_dt = datetime.now()
                data_sig = load_data()
                if data_sig and data_sig[-1].get("end") is None:
                    data_sig[-1]["end"] = end_dt.isoformat()
                    try:
                        start_dt = datetime.fromisoformat(data_sig[-1]["start"])
                        secs = int((end_dt - start_dt).total_seconds())
                        data_sig[-1]["duration_seconds"] = secs
                        data_sig[-1]["duration"] = _secs_to_hms(secs)
                    except Exception:
                        pass
                    save_data(data_sig)
                    sig_name = {getattr(signal, n): n for n in dir(signal) if n.startswith("SIG")}.get(signum, str(signum))
                    print(f"\nStopped (via {sig_name}):", data_sig[-1]["project"]) 
            finally:
                os._exit(0)

        try:
            # Register SIGHUP/SIGTERM; they may not exist on some platforms
            if hasattr(signal, "SIGHUP"):
                signal.signal(signal.SIGHUP, _finalize_active_from_signal)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, _finalize_active_from_signal)
            _render_analog_clock_loop(datetime.fromisoformat(now_iso), project_name)
        except KeyboardInterrupt:
            # On Ctrl-C, also stop the timer and persist duration
            end_dt = datetime.now()
            data = load_data()
            if data and data[-1].get("end") is None:
                data[-1]["end"] = end_dt.isoformat()
                try:
                    start_dt = datetime.fromisoformat(data[-1]["start"])
                    secs = int((end_dt - start_dt).total_seconds())
                    data[-1]["duration_seconds"] = secs
                    data[-1]["duration"] = _secs_to_hms(secs)
                except Exception:
                    pass
                save_data(data)
                print("\nStopped (via Ctrl-C):", data[-1]["project"]) 
            return


def cmd_stop(_: argparse.Namespace) -> None:
    data = load_data()
    if not data or data[-1].get("end") is not None:
        print("No active timer.")
        return
    end_iso = iso_now()
    data[-1]["end"] = end_iso
    # compute duration_seconds
    try:
        start_dt = datetime.fromisoformat(data[-1]["start"])
        end_dt = datetime.fromisoformat(end_iso)
        secs = int((end_dt - start_dt).total_seconds())
        data[-1]["duration_seconds"] = secs
        data[-1]["duration"] = _secs_to_hms(secs)
    except Exception:
        pass
    save_data(data)
    print(f"Stopped: {data[-1]['project']}")


def cmd_log(args: argparse.Namespace) -> None:
    # Accept plain numeric hours (e.g., 3 or 3.5) OR the old formats (1h30m, 45m, 90)
    # Plain number is interpreted as hours
    dur: timedelta
    txt = args.duration.strip()
    try:
        if txt.replace(".", "", 1).isdigit():
            hours = float(txt)
            if hours <= 0:
                raise ValueError("Duration must be > 0")
            dur = timedelta(hours=hours)
        else:
            dur = parse_duration(txt)
    except ValueError as e:
        print(f"Invalid duration: {e}")
        return
    end_time = datetime.now()
    start_time = end_time - dur
    data = load_data()
    secs = int(dur.total_seconds())
    data.append({
        "project": args.project,
        "start": start_time.isoformat(),
        "end": end_time.isoformat(),
        "duration_seconds": secs,
        "duration": _secs_to_hms(secs),
        "manual": True,
    })
    save_data(data)
    mins = int(dur.total_seconds() // 60)
    print(f"Logged {mins}m to: {args.project}")


def cmd_clear(_: argparse.Namespace) -> None:
    # Delete the default home log and an optional local project log
    home_target = DEFAULT_DATA_FILE
    local_target = os.path.abspath(os.path.join(os.getcwd(), "timelog.json"))

    for target in (home_target, local_target):
        try:
            if os.path.exists(target):
                os.remove(target)
                print(f"Deleted log file: {target}")
            else:
                print(f"No log file to delete: {target}")
        except Exception as e:
            print(f"Failed to delete {target}: {e}")


def human_td(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    neg = total_seconds < 0
    total_seconds = abs(total_seconds)
    h, rem = divmod(total_seconds, 3600)
    m, _ = divmod(rem, 60)
    s = ("-" if neg else "")
    if h:
        return f"{s}{h}h{m:02d}m"
    return f"{s}{m}m"


def start_of_month(d: date) -> datetime:
    return datetime(d.year, d.month, 1)


def end_of_month(d: date) -> datetime:
    # First day of next month at 00:00, then subtract 1 second to get inclusive end-of-month display
    if d.month == 12:
        next_month = datetime(d.year + 1, 1, 1)
    else:
        next_month = datetime(d.year, d.month + 1, 1)
    return next_month


def day_span(dt: datetime) -> datetime:
    # next midnight from dt
    next_day = (dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return next_day


def clamp_interval(a: datetime, b: datetime, lo: datetime, hi: datetime) -> Optional[tuple]:
    start = max(a, lo)
    end = min(b, hi)
    if end <= start:
        return None
    return (start, end)


def cmd_report(args: argparse.Namespace) -> None:
    data = load_data()
    if not data:
        print("No entries yet. Start with: tt time start 'project'")
        return

    now = datetime.now()
    today = now.date()
    month_start = start_of_month(today)
    month_end = end_of_month(today)  # exclusive upper bound

    # Aggregations
    # per_day_totals[YYYY-MM-DD][project] = timedelta
    per_day_totals: Dict[str, Dict[str, timedelta]] = {}
    monthly_project_totals: Dict[str, timedelta] = {}

    for e in data:
        proj = e.get("project", "(unknown)")
        start_s = e.get("start")
        end_s = e.get("end")
        if not start_s:
            continue
        start = datetime.fromisoformat(start_s)
        end = datetime.fromisoformat(end_s) if end_s else now

        # Consider only overlap with this month window [month_start, month_end)
        interval = clamp_interval(start, end, month_start, month_end)
        if not interval:
            continue
        cur_start, cur_end = interval

        # Split across days
        while cur_start < cur_end:
            next_midnight = day_span(cur_start)
            seg_end = min(cur_end, next_midnight)
            dur = seg_end - cur_start
            day_key = cur_start.date().isoformat()
            per_day_totals.setdefault(day_key, {})
            per_day_totals[day_key][proj] = per_day_totals[day_key].get(proj, timedelta()) + dur
            monthly_project_totals[proj] = monthly_project_totals.get(proj, timedelta()) + dur
            cur_start = seg_end

    # Prepare weekly grouping within the month
    # Build ordered list of days in the month
    days: List[date] = []
    dcur = month_start.date()
    while datetime.combine(dcur, datetime.min.time()) < month_end:
        days.append(dcur)
        dcur = dcur + timedelta(days=1)

    # Group by ISO week
    from collections import OrderedDict

    weeks: "OrderedDict[tuple, List[date]]" = OrderedDict()
    for dday in days:
        iso = dday.isocalendar()  # (year, week, weekday)
        key = (iso[0], iso[1])
        if key not in weeks:
            weeks[key] = []
        weeks[key].append(dday)

    # Printing
    month_label = month_start.strftime("%B %Y")
    print(f"Report for {month_label} (from {month_start.strftime('%Y-%m-%d')} to {(month_end - timedelta(days=1)).strftime('%Y-%m-%d')})")
    print("")

    # For each week, show days that have any time (or all days? keep concise: only days with data)
    for (wyear, wnum), wdays in weeks.items():
        # Determine range within month for label
        label_start = wdays[0]
        label_end = wdays[-1]
        print(f"Week {wyear}-W{wnum:02d} ({label_start.strftime('%b %d')} - {label_end.strftime('%b %d')})")
        week_had_output = False
        for dday in wdays:
            day_key = dday.isoformat()
            if day_key not in per_day_totals:
                continue
            week_had_output = True
            projects = per_day_totals[day_key]
            day_total = sum((td for td in projects.values()), timedelta())
            print(f"  {dday.strftime('%Y-%m-%d (%a)')}: {human_td(day_total)}")
            for proj, dur in sorted(projects.items(), key=lambda x: x[0].lower()):
                print(f"    - {proj}: {human_td(dur)}")
        if not week_had_output:
            print("  (no time)")
        print("")

    # Monthly totals
    print("Monthly totals:")
    if monthly_project_totals:
        for proj, dur in sorted(monthly_project_totals.items(), key=lambda x: x[0].lower()):
            print(f"- {proj}: {human_td(dur)}")
        overall = sum((td for td in monthly_project_totals.values()), timedelta())
        print(f"- Overall: {human_td(overall)}")
    else:
        print("(no time this month)")

    # Export CSV to ~/Documents/Time Sheet Reports/<Month-YYYY>/<Time Sheet - <Month YYYY>>.csv
    # Build folder and filename
    docs = os.path.expanduser("~/Documents")
    month_folder = month_start.strftime("%B-%Y")  # e.g., August-2025
    export_dir = os.path.join(docs, "Time Sheet Reports", month_folder)
    os.makedirs(export_dir, exist_ok=True)
    export_name = f"Time Sheet - {month_label}.csv"  # e.g., Time Sheet - August 2025.csv
    export_path = os.path.join(export_dir, export_name)

    # Write CSV: Date, Weekday, Project, Duration (HH:MM)
    def td_to_hm(td: timedelta) -> str:
        total = int(td.total_seconds())
        h, rem = divmod(total, 3600)
        m, _ = divmod(rem, 60)
        return f"{h:02d}:{m:02d}"

    with open(export_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([f"Report for {month_label}"])
        writer.writerow([f"From {month_start.strftime('%Y-%m-%d')} to {(month_end - timedelta(days=1)).strftime('%Y-%m-%d')}"])
        writer.writerow([])
        writer.writerow(["Date", "Weekday", "Project", "Duration (HH:MM)"])

        # Iterate days in order, writing only days with data
        for dday in days:
            day_key = dday.isoformat()
            if day_key not in per_day_totals:
                continue
            projects = per_day_totals[day_key]
            for proj, dur in sorted(projects.items(), key=lambda x: x[0].lower()):
                writer.writerow([
                    dday.strftime('%Y-%m-%d'),
                    dday.strftime('%a'),
                    proj,
                    td_to_hm(dur),
                ])

        # Monthly totals
        writer.writerow([])
        writer.writerow(["Monthly totals"])
        if monthly_project_totals:
            for proj, dur in sorted(monthly_project_totals.items(), key=lambda x: x[0].lower()):
                writer.writerow([proj, td_to_hm(dur)])
            overall = sum((td for td in monthly_project_totals.values()), timedelta())
            writer.writerow(["Overall", td_to_hm(overall)])
        else:
            writer.writerow(["(no time this month)"])

    print("")
    try:
        url = Path(export_path).as_uri()
        clickable = _osc8_link(export_path, url)
        print(f"Exported report to: {clickable}")
    except Exception:
        # Fallback: plain path
        print(f"Exported report to: {export_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tt", description="Tiny terminal time tracker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # `tt time ...`
    p_time = subparsers.add_parser("time", help="Time tracking commands")
    sp = p_time.add_subparsers(dest="time_cmd", required=True)

    p_start = sp.add_parser("start", help="Start tracking a project")
    p_start.add_argument("project", nargs="+", help="Project name (can be multiple words)")
    p_start.add_argument("--no-clock", dest="no_clock", action="store_true", help="Do not show the ASCII clock after starting")
    p_start.set_defaults(func=cmd_start)

    p_stop = sp.add_parser("stop", help="Stop active timer")
    p_stop.set_defaults(func=cmd_stop)

    p_log = sp.add_parser("log", help="Log time: plain hours or duration (e.g., 3, 3.5, 1h30m, 45m)")
    p_log.add_argument("project", help="Project name")
    p_log.add_argument("duration", help="Hours (e.g., 3 or 3.5) or duration like 1h30m/45m")
    p_log.set_defaults(func=cmd_log)

    p_report = sp.add_parser("report", help="Show sessions and totals")
    p_report.set_defaults(func=cmd_report)

    p_clear = sp.add_parser("clear", help="Delete ~/.timelog.json and ./timelog.json")
    p_clear.set_defaults(func=cmd_clear)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return
    func(args)


if __name__ == "__main__":
    main()
