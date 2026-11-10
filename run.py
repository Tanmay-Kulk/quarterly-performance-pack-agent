"""Quarterly performance pack workflow.
  python run.py prepare   fetch, validate, transform, write the table and the two prompts
  python run.py evaluate  score saved AI commentaries against the table
  python run.py pack      write the Excel pack and the run log
Stages stop on validation errors. Everything is logged to outputs/run_log.json."""
import json, os, sys, time, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "src"))
from fetch import fetch_series
from validate import validate_series
from transform import build_table
from evaluate import evaluate

CFG = json.load(open(os.path.join(HERE, "config.json")))
OUT = os.path.join(HERE, "outputs"); DATA = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)

def table_text(q, t, through):
    names = {"equity": "US equity (S&P 500 price index)", "ig": "US investment grade corporate bonds", "hy": "US high yield bonds", "cash": "Cash (3-month Treasury)"}
    lines = [f"Quarter: {q}", f"{'Asset':42}{'Policy wt':>10}{'Actual wt':>10}{'Return':>9}"]
    for a in t["returns"]:
        lines.append(f"{names[a]:42}{CFG['policy'][a] * 100:>9.0f}%{CFG['actual'][a] * 100:>9.0f}%{t['returns'][a] * 100:>8.1f}%")
    lines += [f"Policy portfolio return: {t['policy'] * 100:.1f}%", f"Actual portfolio return: {t['actual'] * 100:.1f}%", f"Difference (actual minus policy): {t['diff'] * 100:.2f} percentage points", f"Data through: {through}"]
    return "\n".join(lines)

def prepare():
    t0 = time.time(); log = dict(stage="prepare", series={}, issues=[])
    data = {}
    for a, spec in CFG["series"].items():
        rows, src = fetch_series(spec["id"], DATA)
        rows = [r for r in rows if r[0] >= CFG["start_date"]]
        issues = validate_series(rows, spec, CFG, spec["id"])
        log["series"][a] = dict(id=spec["id"], rows=len(rows), observations=sum(1 for r in rows if r[1] is not None), source=src, first=rows[0][0], last=rows[-1][0], issues=issues)
        log["issues"] += issues; data[a] = rows
    errors = [i for i in log["issues"] if i["severity"] == "error"]
    if errors:
        json.dump(log, open(os.path.join(OUT, "run_log.json"), "w"), indent=1); print("STOPPED: validation errors", errors); return 1
    table = build_table(data, CFG); q = CFG["report_quarter"]
    json.dump(table, open(os.path.join(OUT, "table.json"), "w"), indent=1)
    body = table_text(q, table[q], min(s["last"] for s in log["series"].values()))
    for v in ("v1", "v2"):
        open(os.path.join(OUT, f"prompt_{v}.txt"), "w").write(open(os.path.join(HERE, "prompts", f"{v}.txt")).read().strip() + "\n\n" + body + "\n")
    log.update(quarters=len(table), seconds=round(time.time() - t0, 2), warnings=len([i for i in log["issues"] if i["severity"] == "warning"]))
    json.dump(log, open(os.path.join(OUT, "run_log.json"), "w"), indent=1); print(body); print("prepare ok", log["seconds"], "s", log["warnings"], "warnings"); return 0

def do_evaluate():
    table = json.load(open(os.path.join(OUT, "table.json"))); q = CFG["report_quarter"]; res = {}
    for f in sorted(glob.glob(os.path.join(OUT, "commentary_v*_*.txt"))):
        name = os.path.basename(f)[:-4]; res[name] = evaluate(open(f).read(), table[q], CFG, q)
    json.dump(res, open(os.path.join(OUT, "eval_results.json"), "w"), indent=1)
    for v in ("v1", "v2"):
        runs = [r for k, r in res.items() if k.startswith(f"commentary_{v}_")]
        if runs: print(v, "all checks passed:", sum(r["passed"] for r in runs), "of", len(runs))
    return 0

def pack():
    try:
        from openpyxl import Workbook
    except ImportError:
        print("The Excel pack needs openpyxl: pip install openpyxl"); return 1
    table = json.load(open(os.path.join(OUT, "table.json"))); log = json.load(open(os.path.join(OUT, "run_log.json")))
    wb = Workbook(); ws = wb.active; ws.title = "Quarterly returns"
    ws.append(["Quarter"] + [CFG["series"][a]["name"] for a in CFG["series"]] + ["Policy return", "Actual return", "Difference (actual minus policy)"])
    for q, t in table.items(): ws.append([q] + [round(t["returns"][a], 6) for a in CFG["series"]] + [round(t["policy"], 6), round(t["actual"], 6), round(t["diff"], 6)])
    v = wb.create_sheet("Validation log"); v.append(["Series", "Rows", "Observations", "Source", "First", "Last", "Issues"])
    for a, s in log["series"].items(): v.append([s["id"], s["rows"], s["observations"], s["source"], s["first"], s["last"], len(s["issues"])])
    wb.save(os.path.join(OUT, "performance_pack.xlsx")); print("pack written"); return 0

if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    sys.exit({"prepare": prepare, "evaluate": do_evaluate, "pack": pack}[stage]())
