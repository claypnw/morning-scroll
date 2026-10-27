#!/usr/bin/env python3
"""weather_pull.py — BATCH JOB, Scroll step 1a: pull the day's weather ONCE,
in a fixed shape, so the same values feed the paper identically every run
(no worker re-typing numbers from a search result).

Pulls Open-Meteo hourly + daily for the Hearth's exact coordinates
(34.2362, -111.3149, America/Phoenix):
  - the four "By the Hours" blocks at fixed hours 09 / 12 / 17 / 21 with
    The admin's exact labels: Morning, Noon, Late Afternoon, Evening;
  - the weather-box fields (high, low, conditions, rain chance, sunrise,
    sunset, tomorrow line) in the paper JSON's existing shape.
Each block also carries an ART KEY naming one of the six fixed engraved sky
pictures in ~/workspace/morning-post/images/sky/ (sunny, partly, cloudy,
drizzle, lightrain, hardrain) — picked here, by condition code, never daily.
Each block ALSO carries the hour's wind (wind_speed_10m in mph and
wind_direction_10m in degrees, Open-Meteo hourly) and a WINDSOCK key naming
one of the three fixed engraved windsock pictures in
~/workspace/morning-post/images/windsock/ (limp, half, straight) — picked
here, by wind speed, never daily. The bands (the admin, 2026-10-23):
under 5 mph limp, 5-12 mph half, 13 mph and up straight. The paper prints
the windsock picture in the hour block with the mph number under it.
The weather box ALSO carries four more fields (2026-10-26, for the
quarter-size weather area the admin approved): "wind" — the day's
strongest hourly wind, in mph; "feels" — the day's feels-like high
(Open-Meteo daily apparent_temperature_max); "uv" — the day's highest
UV index with its band word (uv_band below); and "call" — a one-line
plain-words call on the day, made by the fixed rule in call_sentence
below from the day's condition word, high, strongest wind, and rain
chance. No field is ever guessed: if the forecast answer lacks any of
them, the run takes the standing FAIL path with the rest.

Usage:  weather_pull.py [YYYY-MM-DD]     (default: today, America/Phoenix)
Writes: batch/weather-YYYY-MM-DD.json and prints the same values.
Exit 0 on success; exit 1 with a plain reason on any failure.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
LAT, LON = 34.2362, -111.3149
TZ = ZoneInfo("America/Phoenix")
BLOCKS = [("Morning", 9), ("Noon", 12), ("Late Afternoon", 17), ("Evening", 21)]


# --- Shared error program (standards wiring step B, 2026-10-21) -------------
# The one shared error program is ~/workspace/batch/shared_error.py.
# An error in this program goes there, and the standard processing —
# write the error down in full in the dated error record, open an
# ERROR line in the completion pile, append the problem entry to the
# quality record, hand back STOP — happens in that one program, never
# in code copied here. This block is only the call. If the shared
# error program cannot be loaded or cannot record, the report prints
# a loud line on stderr and this program's own output and exit
# behavior are unchanged.
from pathlib import Path as _Path


def _load_shared_error():
    for parent in _Path(__file__).resolve().parents:
        for candidate in (parent / "shared_error.py",
                          parent / "batch" / "shared_error.py"):
            if candidate.is_file():
                try:
                    if str(candidate.parent) not in sys.path:
                        sys.path.insert(0, str(candidate.parent))
                    from shared_error import report_error
                    return report_error
                except Exception:
                    # A shared error program that is present but
                    # fails to load is treated the same as one
                    # that cannot be found: fall back, never
                    # raise at startup.
                    continue
    return None


_shared_report_error = _load_shared_error()


def _report_to_shared_error(step, error, kind="foreseen"):
    """Send one error to the one shared error program. Never raises."""
    if _shared_report_error is None:
        print(f"SHARED ERROR PROGRAM UNAVAILABLE — error not recorded: {error}",
              file=sys.stderr)
        return None
    try:
        return _shared_report_error(
            program=_Path(__file__).name, step=step, error=error, kind=kind,
            error_type="FailedVerdict" if kind == "check_failed" else None)
    except Exception as exc:
        print(f"SHARED ERROR PROGRAM FAILED — error not recorded: {exc}",
              file=sys.stderr)
        return None


# --- Start and finish records (standards wiring step B, 2026-10-21) --------
# This program writes a start line when it begins and a finish line
# when it ends well, both through the one shared finish-line writer,
# ~/workspace/work-launcher/write_finish_line.py — the same writer the
# morning jobs write their finish lines through, called the same way.
# A run that fails writes no finish line: its error goes to the one
# shared error program (the block above), and the pile carries the
# ERROR line instead. These calls are records only: they never change
# this program's own output or exit code, and a failed record write
# prints a loud line on stderr.
import subprocess as _subprocess
from datetime import datetime as _datetime
from zoneinfo import ZoneInfo as _ZoneInfo


def _finish_writer_path():
    for parent in _Path(__file__).resolve().parents:
        candidate = parent / "work-launcher" / "write_finish_line.py"
        if candidate.is_file():
            return candidate
    return None


_FINISH_WRITER = _finish_writer_path()


def _write_pile_line(mode, result, rests_on):
    """Write one start or finish line through the shared writer."""
    if _FINISH_WRITER is None:
        print("FINISH-LINE WRITER UNAVAILABLE — record line not written",
              file=sys.stderr)
        return
    try:
        proc = _subprocess.run(
            [sys.executable, str(_FINISH_WRITER), mode,
             _Path(__file__).name,
             _datetime.now(_ZoneInfo("America/Phoenix")).strftime("%Y-%m-%d"),
             result, rests_on],
            check=False, capture_output=True, text=True)
    except Exception as exc:
        print(f"FINISH-LINE WRITER FAILED — record line not written: {exc}",
              file=sys.stderr)
        return
    if proc.returncode != 0:
        detail = (proc.stdout or "").strip() or (proc.stderr or "").strip()
        print(f"FINISH-LINE WRITER STOPPED — record line not written: {detail}",
              file=sys.stderr)


def _write_start_line():
    _write_pile_line("start", "run started", "this run's own output")


def _write_finish_line(result, rests_on):
    _write_pile_line("finish", result, rests_on)


def wmo(code, hour=None):
    """WMO weather code -> (condition word, sky-art key). Total mapping:
    every code lands somewhere; the art key is always one of the six."""
    if code == 0:
        return ("Clear", "sunny") if (hour is not None and hour >= 19) else ("Sunny", "sunny")
    if code == 1:
        return ("Mostly sunny", "sunny")
    if code == 2:
        return ("Partly cloudy", "partly")
    if code == 3:
        return ("Overcast", "cloudy")
    if code in (45, 48):
        return ("Foggy", "cloudy")
    if 51 <= code <= 57:
        return ("Drizzle", "drizzle")
    if code == 61:
        return ("Light rain", "lightrain")
    if code == 65:
        return ("Hard rain", "hardrain")
    if 60 <= code <= 67:
        return ("Rain", "lightrain")
    if 71 <= code <= 77 or code in (85, 86):
        return ("Snow", "cloudy")
    if code in (80, 81):
        return ("Showers", "lightrain")
    if code == 82:
        return ("Hard rain", "hardrain")
    if 95 <= code <= 99:
        return ("Thunderstorms", "hardrain")
    return ("Cloudy", "cloudy")


def sock_key(speed_mph):
    """Wind speed (mph, already rounded) -> windsock art key. The bands
    (the admin, 2026-10-23): under 5 mph the sock hangs limp, 5-12 mph
    it stands half-raised, 13 mph and up it flies straight out. The key
    is always one of the three fixed pictures in images/windsock/."""
    if speed_mph < 5:
        return "limp"
    if speed_mph < 13:
        return "half"
    return "straight"


def uv_band(uv):
    """A day's highest UV index (already rounded) -> its band word, on
    the standard scale: 0-2 Low, 3-5 Moderate, 6-7 High, 8-10 Very
    high, 11 and up Extreme."""
    if uv <= 2:
        return "Low"
    if uv <= 5:
        return "Moderate"
    if uv <= 7:
        return "High"
    if uv <= 10:
        return "Very high"
    return "Extreme"


# The plain-words call on the day (2026-10-26) is made by ONE fixed
# rule from facts this pull already holds — the day's condition word,
# high, strongest wind, and rain chance — never written freehand:
#   "A {sky word}, {warmth word} day — {skies}, {wind}, and {rain}."
# The sky words key off the condition word wmo() returns, so every
# condition the pull can name has a call.
_CALL_SKY = {
    "Sunny": ("bright", "sunny skies"),
    "Clear": ("bright", "clear skies"),
    "Mostly sunny": ("bright", "mostly sunny skies"),
    "Partly cloudy": ("fair", "partly cloudy skies"),
    "Cloudy": ("grey", "cloudy skies"),
    "Overcast": ("grey", "overcast skies"),
    "Foggy": ("grey", "foggy skies"),
    "Drizzle": ("grey", "drizzle through the day"),
    "Light rain": ("wet", "light rain"),
    "Rain": ("wet", "rain through the day"),
    "Hard rain": ("wet", "hard rain"),
    "Showers": ("wet", "showers passing through"),
    "Thunderstorms": ("grey", "thunderstorms"),
    "Snow": ("white", "snow falling"),
}


def _call_warmth(high):
    if high >= 90:
        return "hot"
    if high >= 80:
        return "warm"
    if high >= 65:
        return "mild"
    if high >= 50:
        return "cool"
    if high >= 35:
        return "cold"
    return "bitter cold"


def _call_wind(mph):
    if mph < 8:
        return "light winds"
    if mph < 16:
        return "a steady breeze"
    if mph < 25:
        return "strong winds"
    return "high winds"


def _call_rain(pct):
    if pct <= 0:
        return "no rain in it"
    if pct <= 40:
        return "a chance of rain"
    if pct <= 70:
        return "rain likely"
    return "rain through the day"


def call_sentence(conditions, high, wind_mph, rain_pct):
    """The day's plain-words call, by the fixed rule above."""
    adj, skies = _CALL_SKY.get(conditions, ("fair", "changing skies"))
    return "A %s, %s day — %s, %s, and %s." % (
        adj, _call_warmth(high), skies, _call_wind(wind_mph),
        _call_rain(rain_pct))


def fmt_time(iso):
    """'2026-10-18T06:24' -> '6:24 AM'"""
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%-I:%M %p")


def main():
    _write_start_line()
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now(TZ).strftime("%Y-%m-%d")
    try:
        day = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        print("WEATHER PULL FAIL: %r is not a date (want YYYY-MM-DD)" % date)
        _report_to_shared_error(
            "read arguments", f"{date!r} is not a date (want YYYY-MM-DD)",
            kind="foreseen")
        return 1
    nxt = (day + timedelta(days=1)).isoformat()
    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
        "&hourly=temperature_2m,weather_code,precipitation_probability,"
        "wind_speed_10m,wind_direction_10m"
        "&daily=temperature_2m_max,temperature_2m_min,weather_code,sunrise,sunset,"
        "apparent_temperature_max,uv_index_max"
        "&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=America%%2FPhoenix"
        "&start_date=%s&end_date=%s" % (LAT, LON, date, nxt)
    )
    # The fetch climbs a step-down ladder (2026-10-26): up to 3 tries,
    # each allowed more time than the one before — 60, then 90, then
    # 120 seconds — with a wait before try 2 (15 seconds) and try 3
    # (30 seconds). A failed try is printed as it happens, flushed so
    # the line reaches the log at once even if the run is stopped
    # later. An answer of JSON null counts as a failed try, with the
    # empty answer named as its reason — before this was named, a
    # null answer ended the ladder after one try while the FAIL line
    # below claimed 3 tries and gave "None" as the reason. Only the
    # last try's failure takes the standing FAIL path below, with the
    # last error, exactly as the single try did before.
    # Time bound: the ladder's worst case is 60+15+90+30+120 = 315
    # seconds. The invoking record — step 5 of the morning briefing
    # job (daily, 03:30), which runs this program as a step and reads
    # its output — names no outer time limit or kill for the step, so
    # nothing ends the program before the ladder and its FAIL path
    # have run.
    data = None
    last_exc = None
    for try_no, timeout in ((1, 60), (2, 90), (3, 120)):
        if try_no > 1:
            wait = 15 if try_no == 2 else 30
            print("weather fetch try %d failed (%s); waiting %d seconds "
                  "before try %d" % (try_no - 1, last_exc, wait, try_no),
                  flush=True)
            time.sleep(wait)
        try:
            with urllib.request.urlopen(url, timeout=timeout) as fh:
                data = json.load(fh)
            if data is None:
                last_exc = ValueError(
                    "the forecast answer was empty (JSON null)")
                continue
            break
        except Exception as exc:
            data = None
            last_exc = exc
    if data is None:
        print("WEATHER PULL FAIL: could not fetch Open-Meteo forecast "
              "in 3 tries: %s" % last_exc, flush=True)
        _report_to_shared_error(
            "fetch forecast", f"could not fetch Open-Meteo forecast: {last_exc}",
            kind="foreseen")
        return 1

    try:
        hourly = data["hourly"]
        hidx = {t: i for i, t in enumerate(hourly["time"])}
        blocks = []
        for label, hour in BLOCKS:
            key = "%sT%02d:00" % (date, hour)
            i = hidx[key]
            word, art = wmo(int(hourly["weather_code"][i]), hour)
            wspeed = int(round(hourly["wind_speed_10m"][i]))
            blocks.append({
                "label": label, "hour": hour,
                "temp": int(round(hourly["temperature_2m"][i])),
                "condition": word, "art": art,
                "wind_speed": wspeed,
                "wind_direction": int(round(hourly["wind_direction_10m"][i])),
                "sock": sock_key(wspeed),
            })
        daily = data["daily"]
        didx = {t: i for i, t in enumerate(daily["time"])}
        d0, d1 = didx[date], didx[nxt]
        probs = [hourly["precipitation_probability"][hidx["%sT%02d:00" % (date, h)]]
                 for h in range(24) if hourly["precipitation_probability"][hidx["%sT%02d:00" % (date, h)]] is not None]
        rain_pct = int(max(probs)) if probs else 0
        speeds = [hourly["wind_speed_10m"][hidx["%sT%02d:00" % (date, h)]]
                  for h in range(24)
                  if hourly["wind_speed_10m"][hidx["%sT%02d:00" % (date, h)]] is not None]
        if not speeds:
            raise ValueError("forecast answer carried no wind speeds for %s" % date)
        wind_max = int(round(max(speeds)))
        feels = int(round(daily["apparent_temperature_max"][d0]))
        uv = int(round(daily["uv_index_max"][d0]))
        tword, _ = wmo(int(daily["weather_code"][d1]))
        _high = int(round(daily["temperature_2m_max"][d0]))
        _conditions = wmo(int(daily["weather_code"][d0]))[0]
        weather = {
            "high": _high,
            "low": int(round(daily["temperature_2m_min"][d0])),
            "conditions": _conditions,
            "rain": "%d%%" % rain_pct,
            "sunrise": fmt_time(daily["sunrise"][d0]),
            "sunset": fmt_time(daily["sunset"][d0]),
            "tomorrow": "%s, %d/%d" % (tword, int(round(daily["temperature_2m_max"][d1])),
                                       int(round(daily["temperature_2m_min"][d1]))),
            "wind": "%d mph" % wind_max,
            "feels": feels,
            "uv": "%d (%s)" % (uv, uv_band(uv)),
            "call": call_sentence(_conditions, _high, wind_max, rain_pct),
        }
    except Exception as exc:
        print("WEATHER PULL FAIL: forecast response missing expected fields: %r" % exc)
        _report_to_shared_error(
            "read forecast", f"forecast response missing expected fields: {exc!r}",
            kind="foreseen")
        return 1

    out = {
        "date": date,
        "pulled_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "source": "Open-Meteo api.open-meteo.com (hourly + daily)",
        "lat": LAT, "lon": LON,
        "weather": weather,
        "blocks": blocks,
    }
    path = os.path.join(HERE, "weather-%s.json" % date)
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2)
        fh.write("\n")
    print("WEATHER PULL OK for %s -> %s" % (date, path))
    print("weather: high %s / low %s, %s, rain %s, sunrise %s, sunset %s, tomorrow %s"
          % (weather["high"], weather["low"], weather["conditions"], weather["rain"],
             weather["sunrise"], weather["sunset"], weather["tomorrow"]))
    print("weather box extras: wind %s, feels like %s, uv %s"
          % (weather["wind"], weather["feels"], weather["uv"]))
    print("call: %s" % weather["call"])
    for b in blocks:
        print("block: %-14s %2d:00  %s°  %-14s art %s  wind %s mph from %s°  sock %s"
              % (b["label"], b["hour"], b["temp"], b["condition"], b["art"],
                 b["wind_speed"], b["wind_direction"], b["sock"]))
    _write_finish_line(f"WEATHER PULL OK for {date}", path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        # Catch-all: an error this program did not foresee goes to the
        # one shared error program, then the program stops as it would
        # have — the traceback still prints.
        _report_to_shared_error("main", exc, kind="unforeseen")
        raise
