"""Stage 1d: connect files that belong together, safely.

A link is only used when (a) one side has unique keys, (b) nearly every key on the other side is found there,
and (c) the name/size evidence makes a chance match unlikely. Weaker candidates are proposed to the owner and
are NOT used until confirmed. Joins are always many-to-one lookups, so rows can never multiply.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, asdict, field
import pandas as pd
from ..understand.prepare import Prepared, prepare

AUTO_USE = 0.85
PROPOSE = 0.5


@dataclass
class Link:
    child: str
    child_col: str
    parent: str
    parent_col: str
    coverage: float            # share of child keys found in parent
    confidence: float
    reasons: list[str] = field(default_factory=list)
    use: bool = False          # will be used for building views
    needs_confirmation: bool = False

    @property
    def key(self) -> str:
        return f"{self.child}.{self.child_col}|{self.parent}.{self.parent_col}"

    def public(self) -> dict:
        d = asdict(self); d["key"] = self.key
        return d


def _norm(c: str) -> str:
    return re.sub(r"[^a-z0-9]", "", c.lower())


def _name_score(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return 1.0
    ta, tb = re.split(r"[_\s\-]+", a.lower()), re.split(r"[_\s\-]+", b.lower())
    if ta and tb and ta[-1] == tb[-1] and ta[-1] in ("id", "code", "key", "no", "number") and (ta[0].startswith(tb[0][:3]) or tb[0].startswith(ta[0][:3])):
        return 0.7
    return 0.0


def _keys(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col].dropna().astype(str).str.strip()


def find_links(tables: dict[str, Prepared]) -> list[Link]:
    out: list[Link] = []
    names = list(tables)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = tables[a], tables[b]
            if A.kind == "summary" or B.kind == "summary":
                continue
            for ca, ia in A.roles.items():
                if ia["role"] not in ("id", "category") or ia.get("unique", 0) < 20:
                    continue
                for cb, ib in B.roles.items():
                    if ib["role"] not in ("id", "category") or ib.get("unique", 0) < 20:
                        continue
                    ns = _name_score(ca, cb)
                    if ia["role"] == "category" and ns < 1.0:
                        continue
                    ka, kb = _keys(A.df, ca), _keys(B.df, cb)
                    ua, ub = ka.nunique(), kb.nunique()
                    a_unique, b_unique = ua == len(ka), ub == len(kb)
                    if not (a_unique or b_unique):
                        continue
                    # parent = the side with unique keys (if both unique, the smaller / the one with fewer rows)
                    if a_unique and b_unique:
                        parent_is_a = len(ka) <= len(kb)
                    else:
                        parent_is_a = a_unique
                    (pn, pc, pk), (cn, cc, ck) = ((a, ca, ka), (b, cb, kb)) if parent_is_a else ((b, cb, kb), (a, ca, ka))
                    cov = float(ck.drop_duplicates().isin(set(pk)).mean())
                    if cov < 0.5:
                        continue
                    size = 1.0 if pk.nunique() >= 100 else 0.5
                    numeric_small = pk.str.fullmatch(r"\d{1,4}").mean() > 0.9
                    conf = 0.5 * cov + 0.3 * ns + 0.2 * size
                    reasons = [f"{cov:.0%} of keys in {cn}.{cc} exist in {pn}.{pc}", f"{pn}.{pc} has unique keys"]
                    if ns == 1.0:
                        reasons.append("same column name")
                    elif ns > 0:
                        reasons.append("similar column names")
                    if numeric_small and ns < 1.0:
                        conf = min(conf, 0.45)
                        reasons.append("small plain numbers can match by chance")
                    if conf >= PROPOSE:
                        L = Link(cn, cc, pn, pc, round(cov, 4), round(conf, 3), reasons)
                        L.use, L.needs_confirmation = conf >= AUTO_USE, conf < AUTO_USE
                        out.append(L)
    out.sort(key=lambda l: -l.confidence)
    return out


def apply_link_confirmations(links: list[Link], confirmed: dict[str, bool]) -> list[Link]:
    for l in links:
        if l.key in confirmed:
            l.use, l.needs_confirmation = bool(confirmed[l.key]), False
    return links


# ---------- building analysis views ----------
def _dim_columns(P: Prepared) -> list[str]:
    cols = []
    for c, i in P.roles.items():
        if c.startswith("__") or c == "_t":
            continue
        if i["role"] in ("category", "flag") and not i.get("presence") and 2 <= i.get("unique", 0) <= 500 and not i.get("period_part"):
            cols.append(c)
    return cols


def _enrich(name: str, tables: dict[str, Prepared], links: list[Link], trail: tuple, notes: list[str], warns: list[str]) -> pd.DataFrame:
    """Return table `name` with columns looked up from its parents (many-to-one), recursively."""
    T = tables[name]
    df = T.df.copy()
    have_time = T.time_col is not None and "_t" in df.columns
    if have_time and T.time_col in df.columns:
        df[T.time_col] = df["_t"]                      # pass parsed dates upward/downward, not raw text
    df[f"__ok_{name}"] = T.ok.values if T.ok is not None else True
    for L in [l for l in links if l.use and l.child == name and l.parent not in trail]:
        P = tables[L.parent]
        pdf = _enrich(L.parent, tables, links, trail + (name,), notes, warns)
        pk = pdf[L.parent_col].astype(str).str.strip()
        dup = int(pk.duplicated().sum())
        if dup:
            warns.append(f"{L.parent}.{L.parent_col} has {dup:,} repeated key(s); the first record was used so rows are never multiplied.")
        lookup = pdf.assign(_k=pk).drop_duplicates("_k").set_index("_k")
        ck = df[L.child_col].astype(str).str.strip()
        miss = float(1 - ck.isin(lookup.index).mean())
        if miss > 0.05:
            warns.append(f"{miss:.0%} of {name} rows have no matching record in {L.parent}; their {L.parent} details are blank.")
        take = [c for c in lookup.columns if c.startswith("__ok_")]
        take += [c for c in _dim_columns_of(lookup, P) if c not in df.columns]
        if not have_time and P.time_col and P.time_col in lookup.columns and not P.synthetic_time:
            take.append(P.time_col)
            have_time = True
            notes.append(f"'{name}' has no dates of its own; dates are looked up from '{L.parent}' through {L.child_col}.")
        for c in dict.fromkeys(take):
            if c in df.columns:
                continue
            m = ck.map(lookup[c])
            df[c] = m.fillna(True).astype(bool) if c.startswith("__ok_") else m
    return df


def _dim_columns_of(lookup: pd.DataFrame, P: Prepared) -> list[str]:
    own = set(_dim_columns(P))
    extra = [c for c in lookup.columns if c not in P.roles and not c.startswith("__") and (pd.api.types.is_object_dtype(lookup[c]) or pd.api.types.is_string_dtype(lookup[c])) and lookup[c].nunique() <= 500]
    return [c for c in lookup.columns if c in own] + extra


def build_views(tables: dict[str, Prepared], links: list[Link], confirmed: dict | None = None) -> tuple[list[Prepared], list[str], list[str]]:
    confirmed = confirmed or {}
    notes: list[str] = []
    warns: list[str] = []
    used = [l for l in links if l.use]
    parents_only = {l.parent for l in used} - {l.child for l in used}
    views: list[Prepared] = []
    for name, T in tables.items():
        if T.kind == "summary":
            views.append(T); continue
        has_time_route = T.time_col is not None or any(
            tables[l.parent].time_col is not None for l in used if l.child == name)
        if T.kind in ("reference", "no_time") and name in parents_only and T.time_col is None:
            T.notes.append("Used as detail for the files that link to it (not scanned on its own).")
            T.kind = "dimension"
            views.append(T); continue
        if not any(l.child == name for l in used):
            views.append(T); continue                           # independent file: analysed on its own
        df = _enrich(name, tables, links, (), notes, warns)
        df = df.drop(columns=[c for c in df.columns if c == f"__ok_{name}"])
        conf = {k: v for k, v in confirmed.items() if not str(k).startswith("link:")}
        V = prepare(df, name, conf)
        V.sources = [name] + sorted({l.parent for l in used if l.child == name})
        V.notes = T.notes[:0] + V.notes
        views.append(V)
    # cross-level totals check (informational)
    for l in used:
        C, P = tables[l.child], tables[l.parent]
        if C.money_col and P.money_col and C.money_col == P.money_col and C.df[C.money_col].notna().any():
            try:
                cs = C.df.assign(_k=C.df[l.child_col].astype(str)).groupby("_k")[C.money_col].sum()
                ps = P.df.assign(_k=P.df[l.parent_col].astype(str)).set_index("_k")[P.money_col]
                j = pd.concat([cs, ps[~ps.index.duplicated()]], axis=1, keys=["c", "p"]).dropna()
                if len(j):
                    ok = float(((j.c - j.p).abs() <= 0.01 * j.p.abs().clip(lower=1)).mean())
                    msg = f"{l.child}.{C.money_col} adds up to {l.parent}.{P.money_col} for {ok:.0%} of {l.parent} records."
                    (notes if ok > 0.95 else warns).append(msg + ("" if ok > 0.95 else " They differ, so each file is analysed as it is and not mixed."))
            except Exception:
                pass
    return views, notes, warns
