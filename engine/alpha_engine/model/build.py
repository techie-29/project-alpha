"""Assemble the business model for all uploaded files."""
from __future__ import annotations
from .infer import infer_table, unify_links
from .concepts import CONCEPTS


def build_model(tables: dict, links: list, confirmations: dict | None = None, memory: dict | None = None) -> dict:
    confirmations = confirmations or {}
    owner: dict[str, dict] = {}
    for k, v in (confirmations.get("concepts") or {}).items():
        f, _, col = k.partition("::")
        owner.setdefault(f, {})[col] = v
    models = {name: (infer_table(p, memory, owner.get(name)) if p.kind != 'summary' else {'columns': {}, 'file': {'role': 'summary', 'entity': None, 'reason': 'a few summary rows'}, 'identities': []}) for name, p in tables.items()}
    unify_links(models, links)
    for name, p in tables.items():
        p.concepts = {c: v["concept"] for c, v in models[name]["columns"].items()}   # type: ignore[attr-defined]
        p.file_role = models[name]["file"]                                          # type: ignore[attr-defined]
        p.identities = models[name]["identities"]                                   # type: ignore[attr-defined]
    entities = {}
    for name, m in models.items():
        for c, v in m["columns"].items():
            e = CONCEPTS[v["concept"]].entity
            if e:
                entities.setdefault(e, []).append(f"{name}.{c}")
    return {"files": models, "entities": entities}


def view_concepts(view, tables: dict) -> dict[str, str]:
    """Concepts for a linked view: its own columns plus the columns it borrowed from parent files."""
    out = dict(getattr(tables.get(view.name), "concepts", {}) or {})
    for src in view.sources[1:] if view.sources else []:
        for c, k in (getattr(tables.get(src), "concepts", {}) or {}).items():
            if c in view.df.columns and c not in out:
                out[c] = k
    return out
