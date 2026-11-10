"""Quarterly returns, policy and actual portfolio returns, and the allocation effect."""
import datetime as dt

def quarter_end(q):
    y, n = int(q[:4]), int(q[5])
    m = n * 3
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return nxt - dt.timedelta(days=1)

def level_on_or_before(rows, day):
    best = None
    for d, v in rows:
        if v is None: continue
        if dt.date.fromisoformat(d) <= day: best = (d, v)
        else: break
    return best

def prev_quarter(q):
    y, n = int(q[:4]), int(q[5])
    return f"{y - 1}Q4" if n == 1 else f"{y}Q{n - 1}"

def asset_return(rows, kind, q):
    """Quarterly return for one asset. Index series: level at quarter end over level at previous quarter end. Yield series: previous quarter-end yield / 4."""
    end, start = level_on_or_before(rows, quarter_end(q)), level_on_or_before(rows, quarter_end(prev_quarter(q)))
    if end is None or start is None: return None
    if kind == "yield": return start[1] / 100 / 4
    return end[1] / start[1] - 1

def build_table(data, cfg):
    out = {}
    for q in cfg["quarters"]:
        r = {a: asset_return(data[a], cfg["series"][a]["kind"], q) for a in cfg["series"]}
        if any(v is None for v in r.values()): continue
        pol = sum(cfg["policy"][a] * r[a] for a in r); act = sum(cfg["actual"][a] * r[a] for a in r)
        alloc = {a: (cfg["actual"][a] - cfg["policy"][a]) * (r[a] - pol) for a in r}
        out[q] = dict(returns=r, policy=pol, actual=act, diff=act - pol, alloc=alloc, contrib={a: cfg["policy"][a] * r[a] for a in r})
    return out
