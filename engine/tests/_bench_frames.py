import functools
from bench_business import make
from alpha_engine.understand.prepare import prepare
from alpha_engine.link.linker import find_links, build_views
from alpha_engine.model.build import build_model
from alpha_engine.metrics.frame import build_frame
from alpha_engine.overview.build import pick_frames


@functools.lru_cache(maxsize=2)
def bench(seed=7, plant=True):
    files, truth = make(seed, plant=plant)
    tables = {}
    for n, df in files.items():
        df = df.copy(); df.insert(0, "_row", range(2, len(df) + 2))
        tables[n] = prepare(df, n)
    links = find_links(tables)
    model = build_model(tables, links)
    views, _, _ = build_views(tables, links)
    frames = {v.name: build_frame(v, model["files"][v.name]["columns"], model["files"][v.name]["file"], tables, links, model["files"]) for v in views if v.kind != "summary"}
    return files, truth, model, frames, links, pick_frames(frames, links), tables, views
