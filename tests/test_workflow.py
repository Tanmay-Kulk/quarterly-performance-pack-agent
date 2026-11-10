import copy, datetime as dt, json, os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, "src"))
from validate import validate_series
from transform import quarter_end, asset_return, prev_quarter, build_table
from evaluate import evaluate, extract_numbers, sentences
from fetch import parse_csv

CFG = json.load(open(os.path.join(ROOT, "config.json")))

def business_days(start, n):
    d, out = dt.date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5: out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out

def clean_series(level0=1000.0, n=300):
    days = business_days("2026-01-05", n); v, rows = level0, []
    for i, d in enumerate(days):
        v *= 1.0005 if i % 2 else 0.9998; rows.append((d, round(v, 4)))
    return rows

SPEC = {"min": 100, "max": 20000, "kind": "price"}
CFG_T = dict(CFG, as_of=business_days("2026-01-05", 300)[-1])
checks = lambda rows, spec=SPEC: {i["check"] for i in validate_series(rows, spec, CFG_T, "TEST")}

class SeededDefects(unittest.TestCase):
    """Five defects are injected into a clean series. Each must be caught by name; the clean series must raise nothing."""
    def test_clean_series_passes(self):
        self.assertEqual(validate_series(clean_series(), SPEC, CFG_T, "TEST"), [])
    def test_missing_days_gap(self):
        r = clean_series(); del r[100:112]; self.assertIn("gap", checks(r))
    def test_duplicate_row(self):
        r = clean_series(); r.insert(50, r[50]); self.assertIn("duplicate_date", checks(r))
    def test_stale_series(self):
        r = clean_series()[:-20]; self.assertIn("stale", checks(r))
    def test_ten_times_value(self):
        r = clean_series(); r[150] = (r[150][0], r[150][1] * 10); self.assertTrue({"outlier", "range"} & checks(r) or True); self.assertIn("outlier", checks(r))
    def test_percent_vs_decimal_units(self):
        r = [(d, 0.04) for d, v in clean_series()]; self.assertIn("units", checks(r, {"min": 0, "max": 25, "kind": "yield"}))

class Transform(unittest.TestCase):
    def test_quarter_end_and_prev(self):
        self.assertEqual(quarter_end("2026Q3"), dt.date(2026, 9, 30)); self.assertEqual(quarter_end("2025Q4"), dt.date(2025, 12, 31)); self.assertEqual(prev_quarter("2026Q1"), "2025Q4")
    def test_index_return(self):
        rows = [("2026-06-30", 100.0), ("2026-09-30", 110.0)]; self.assertAlmostEqual(asset_return(rows, "price", "2026Q3"), 0.10)
    def test_yield_return_uses_prior_quarter_end(self):
        rows = [("2026-06-30", 4.0), ("2026-09-30", 9.0)]; self.assertAlmostEqual(asset_return(rows, "yield", "2026Q3"), 0.01)
    def test_allocation_effects_sum_to_difference(self):
        rows = {a: [("2026-06-30", 100.0), ("2026-09-30", 100.0 * (1 + r))] for a, r in {"equity": .04, "ig": -.02, "hy": .01, "cash": .0}.items()}
        rows["cash"] = [("2026-06-30", 4.0), ("2026-09-30", 4.0)]
        t = build_table(rows, dict(CFG, quarters=["2026Q3"]))["2026Q3"]
        self.assertAlmostEqual(sum(t["alloc"].values()), t["diff"], places=10)

class Evaluator(unittest.TestCase):
    T = {"returns": {"equity": 0.020, "ig": -0.038, "hy": -0.018, "cash": 0.010}, "policy": 0.001, "actual": 0.003, "diff": 0.0017, "alloc": {"equity": .0005, "ig": .0004, "hy": 0, "cash": 0}, "contrib": {"equity": .012, "ig": -.0095, "hy": -.0018, "cash": .0005}}
    GOOD = "In 2026Q3 the equity index, a price index that excludes dividends, returned 2.0%. Investment grade bonds fell 3.8%. The actual portfolio returned 0.3% against 0.1% for the policy portfolio."
    def test_good_passes(self): self.assertTrue(evaluate(self.GOOD, self.T, CFG, "2026Q3")["passed"])
    def test_invented_number_caught(self):
        r = evaluate(self.GOOD.replace("0.3%", "0.7%"), self.T, CFG, "2026Q3"); self.assertFalse(r["checks"]["numbers_supported"]); self.assertEqual(r["unsupported"], [0.7])
    def test_forecast_caught(self):
        r = evaluate(self.GOOD + " We expect equities to keep rising.", self.T, CFG, "2026Q3"); self.assertFalse(r["checks"]["no_forecast_or_advice"])
    def test_missing_caveat_caught(self):
        r = evaluate("In 2026Q3 equities returned 2.0%. Bonds fell 3.8%. The plan returned 0.3%.", self.T, CFG, "2026Q3"); self.assertFalse(r["checks"]["price_only_caveat"])
    def test_points_without_the_word_percentage_are_checked(self):
        r = evaluate(self.GOOD.replace("0.3%", "0.3%") + " The equity overweight added about 0.8 points.", self.T, CFG, "2026Q3"); self.assertIn(0.8, r["unsupported"])
    def test_active_weight_is_allowed(self):
        r = evaluate(self.GOOD + " Equity was 3 points overweight.", self.T, CFG, "2026Q3"); self.assertNotIn(3.0, r["unsupported"])
    def test_sentence_count(self): self.assertEqual(len(sentences("One. Two. Three.")), 3)
    def test_number_extraction(self): self.assertEqual(extract_numbers("up 2.0% and 17 bps"), (["2.0"], ["17"]))

class Fetch(unittest.TestCase):
    def test_missing_dot_becomes_none(self): self.assertEqual(parse_csv("observation_date,X\n2026-01-01,.\n2026-01-02,5.5\n"), [("2026-01-01", None), ("2026-01-02", 5.5)])

if __name__ == "__main__":
    unittest.main(verbosity=2)
