"""Fetch a public time series from FRED as CSV (a simple API integration) with retries and a local cache."""
import csv, io, os, time, urllib.request

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"

def fetch_series(series_id, cache_dir, retries=3, use_cache=True):
    """Return (rows, source) where rows is a list of (date_str, value_or_None). Missing observations come through as None."""
    path = os.path.join(cache_dir, f"{series_id}.csv")
    text, source = None, None
    if use_cache and os.path.exists(path):
        text, source = open(path, encoding="utf-8").read(), "cache"
    if text is None:
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                with urllib.request.urlopen(URL.format(series_id), timeout=30) as r:
                    text = r.read().decode("utf-8")
                os.makedirs(cache_dir, exist_ok=True)
                open(path, "w", encoding="utf-8").write(text)
                source = "live"
                break
            except Exception as e:  # network errors are retried, then raised with context
                last_err = e
                time.sleep(attempt)
        if text is None:
            raise RuntimeError(f"could not fetch {series_id} after {retries} tries: {last_err}")
    return parse_csv(text), source

def parse_csv(text):
    rows = []
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    if len(header) < 2:
        raise ValueError("unexpected CSV header: " + repr(header))
    for rec in reader:
        if len(rec) < 2:
            continue
        d, v = rec[0].strip(), rec[1].strip()
        rows.append((d, None if v in ("", ".") else float(v)))
    return rows
