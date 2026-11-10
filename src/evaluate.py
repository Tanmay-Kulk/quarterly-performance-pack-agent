"""Automatic checks on AI-written commentary against the validated table. Returns pass/fail per check."""
import re

FORBIDDEN = ["recommend", "should ", "expect", "forecast", "outlook", "likely to", "we believe", "buy ", "sell "]

def allowed_percentages(table_q, cfg):
    """Every figure a commentary may quote, as raw percentages (not yet rounded)."""
    vals = list(table_q["returns"].values()) + [table_q[k] for k in ("policy", "actual", "diff")] + list(table_q["alloc"].values()) + list(table_q["contrib"].values())
    out = [abs(v) * 100 for v in vals]
    for grp in ("policy", "actual"): out += [cfg[grp][a] * 100 for a in cfg[grp]]
    out += [abs(cfg["actual"][a] - cfg["policy"][a]) * 100 for a in cfg["policy"]]  # active weights (actual minus policy) are derived directly from the table
    return out

def extract_numbers(text):
    """Return (percent_strings, bps_strings) as written, e.g. '2.0' or '17'."""
    pct = re.findall(r"(\d+(?:\.\d+)?)\s*(?:%|percent|percentage points?|points?|pts)", text, re.I)
    bps = re.findall(r"(\d+(?:\.\d+)?)\s*(?:bps|basis points)", text, re.I)
    pct += [d for d in re.findall(r"(?<![\d.-])(\d+\.\d+)(?![\d%])", text) if d not in pct]  # decimals written without a unit are checked too
    return pct, bps

def _supported(num_str, raws, scale=1):
    d = len(num_str.split(".")[1]) if "." in num_str else 0
    n = float(num_str)
    return any(round(r * scale, d) == n for r in raws)

def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]

def evaluate(text, table_q, cfg, quarter_label):
    raws = allowed_percentages(table_q, cfg)
    pct, bps = extract_numbers(text)
    unsupported = [float(x) for x in pct if not _supported(x, raws)] + [float(x) for x in bps if not _supported(x, raws, scale=100)]
    low = text.lower()
    checks = {
        "numbers_supported": not unsupported and (len(pct) + len(bps)) > 0,
        "price_only_caveat": ("price" in low and ("dividend" in low or "price-only" in low or "price only" in low or "price index" in low)),
        "no_forecast_or_advice": not any(w in low for w in FORBIDDEN),
        "names_period": any(k in low for k in (quarter_label.lower(), "third quarter", "q3")),
        "three_or_four_sentences": 3 <= len(sentences(text)) <= 4,
    }
    return dict(checks=checks, unsupported=unsupported, passed=all(checks.values()), n_numbers=len(pct) + len(bps))
