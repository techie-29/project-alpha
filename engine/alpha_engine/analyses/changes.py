"""What changed over time: the existing calibrated change scan (shift / window / trend / outlier tests with shuffles and BH),
wrapped into the common insight format. Run on the main activity file only (line items repeat the same activity)."""
from __future__ import annotations
from .common import insight
from ..scan.engine import scan_view
from ..discover.discover import discover
from ..report.build import evidence_sample


def run(view, limit: int = 25) -> tuple[list[dict], dict]:
    if view is None or view.kind not in ("events", "periodic"):
        return [], {}
    sr = scan_view(view)
    if sr is None:
        return [], {}
    d = discover(sr)
    out = []
    for f in d["findings"][:limit]:
        strength = "supported" if f["level"] == "confirmed" else "early"
        n = f["numbers"]
        unit = n.get("unit") or ""
        ins = insight("change", "sales" if f["kind"] in ("money", "count") else "operations", f["title"], f["detail"], strength=strength,
                      p=f["p"], polarity=f["polarity"], impact=n.get("impact"), impact_unit=unit, impact_share=n.get("impact_share"),
                      actionable=bool(f.get("drivers") or f.get("slice_col")),
                      look_at={"col": f["slice_col"], "value": f["slice_val"]} if f.get("slice_col") else None,
                      numbers={"before": n.get("before"), "after": n.get("after"), "relative": n.get("relative"), "fmt": "money" if f["kind"] == "money" else "number", "unit": unit},
                      chart={"type": "line", "title": f["label"] + (f" for {f['slice_val']}" if f.get("slice_val") else ""), "fmt": "money" if f["kind"] == "money" else "number",
                             "unit": unit, "x": f["chart"]["labels"], "values": f["chart"]["values"], "focus_range": f["chart"]["focus"]},
                      evidence=evidence_sample(sr, f), source=view.name, metric=f["measure"], metric_label=f["label"],
                      tags=[x for x in (f.get("slice_col"), f.get("slice_val"), f["family"], "change") if x], drivers=f.get("drivers"), when=f["when"])
        ins["q"] = f["q"]
        out.append(ins)
    return out, {"series": d["checked"]["series"], "tests": d["checked"]["tests"], "seasonal": d["seasonal"]}
