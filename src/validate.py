"""Data validation checks. Each check returns a list of issues: {check, severity, detail}. 'error' stops the pipeline."""
import datetime as dt, statistics as st

def _d(s): return dt.date.fromisoformat(s)

def check_schema(rows, name):
    out = []
    if not rows: return [dict(check="schema", severity="error", detail=f"{name}: no rows")]
    for d, v in rows:
        try: _d(d)
        except Exception: out.append(dict(check="schema", severity="error", detail=f"{name}: bad date {d!r}")); break
    return out

def check_sorted_unique(rows, name):
    out, seen, prev = [], set(), None
    for d, v in rows:
        if d in seen: out.append(dict(check="duplicate_date", severity="error", detail=f"{name}: duplicate date {d}"))
        seen.add(d)
        if prev and d < prev: out.append(dict(check="order", severity="error", detail=f"{name}: dates out of order at {d}"))
        prev = d
    return out

def check_gaps(rows, name, max_gap_days):
    ds = [_d(d) for d, v in rows if v is not None]
    out = []
    for a, b in zip(ds, ds[1:]):
        if (b - a).days > max_gap_days:
            out.append(dict(check="gap", severity="error", detail=f"{name}: no data from {a} to {b} ({(b - a).days} days)"))
    return out

def check_staleness(rows, name, as_of, max_stale_days):
    ds = [_d(d) for d, v in rows if v is not None]
    if not ds: return []
    age = (_d(as_of) - max(ds)).days
    return [dict(check="stale", severity="error", detail=f"{name}: latest value is {max(ds)}, {age} days before {as_of}")] if age > max_stale_days else []

def check_range(rows, name, lo, hi):
    bad = [(d, v) for d, v in rows if v is not None and not (lo <= v <= hi)]
    return [dict(check="range", severity="error", detail=f"{name}: {len(bad)} value(s) outside {lo} to {hi}, first {bad[0][0]} = {bad[0][1]}")] if bad else []

def check_outliers(rows, name, max_daily_move):
    out, prev = [], None
    for d, v in rows:
        if v is None: continue
        if prev not in (None, 0) and abs(v / prev - 1) > max_daily_move:
            out.append(dict(check="outlier", severity="warning", detail=f"{name}: move of {v / prev - 1:+.1%} on {d}"))
        prev = v
    return out

def check_units(rows, name, kind, yield_median_min):
    vals = [v for d, v in rows if v is not None]
    if kind == "yield" and vals and st.median(vals) < yield_median_min:
        return [dict(check="units", severity="error", detail=f"{name}: median {st.median(vals):.4f} looks like decimals, not percent")]
    return []

def validate_series(rows, spec, cfg, name):
    th = cfg["thresholds"]; issues = []
    issues += check_schema(rows, name)
    if any(i["severity"] == "error" and i["check"] == "schema" for i in issues): return issues
    issues += check_sorted_unique(rows, name)
    issues += check_gaps(rows, name, th["max_gap_days"])
    issues += check_staleness(rows, name, cfg["as_of"], th["max_stale_days"])
    issues += check_range(rows, name, spec["min"], spec["max"])
    issues += check_outliers(rows, name, th["max_daily_move"])
    issues += check_units(rows, name, spec["kind"], th["yield_median_min"])
    return issues
