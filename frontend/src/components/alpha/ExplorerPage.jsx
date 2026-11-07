import { useMemo, useState } from "react";
import { FindingCard } from "./report/Report";

const TONES = [["all", "All"], ["risk", "Risks"], ["strength", "Strengths"], ["neutral", "Worth knowing"], ["data", "Data issues"]];
const SORTS = [["importance", "Most important"], ["money", "Biggest money"], ["area", "By area"]];
const IMP = { high: 0, medium: 1, low: 2 };
const text = (c) => [c.headline, ...(c.points || []), c.why_it_matters, c.look_into, c.area].filter(Boolean).join(" ").toLowerCase();

/** Every finding in one searchable list: filter by kind and area, search the words, sort by what matters. */
export default function ExplorerPage({ view }) {
  const [q, setQ] = useState("");
  const [tone, setTone] = useState("all");
  const [area, setArea] = useState("all");
  const [sort, setSort] = useState("importance");
  const areas = useMemo(() => [...new Set(view.cards.map((c) => c.area || "general"))].sort(), [view.cards]);
  const list = useMemo(() => {
    const w = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const out = view.cards.filter((c) => (tone === "all" || c.tone === tone) && (area === "all" || (c.area || "general") === area) && w.every((x) => text(c).includes(x)));
    const money = (c) => Math.abs(c.money?.amount || 0);
    if (sort === "money") out.sort((a, b) => money(b) - money(a));
    else if (sort === "area") out.sort((a, b) => (a.area || "").localeCompare(b.area || ""));
    else out.sort((a, b) => (IMP[a.importance] ?? 3) - (IMP[b.importance] ?? 3) || money(b) - money(a));
    return out;
  }, [view.cards, q, tone, area, sort]);
  const clear = () => { setQ(""); setTone("all"); setArea("all"); };
  const filtered = q || tone !== "all" || area !== "all";

  if (!view.cards.length) return <div className="al-panel al-empty-page"><p>There are no findings to explore in this analysis yet.</p></div>;
  return <div className="al-stack ex">
    <div className="ex-bar">
      <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search findings (e.g. returns, West, stock)" aria-label="Search findings"/>
      <select value={area} onChange={(e) => setArea(e.target.value)} aria-label="Area"><option value="all">All areas</option>{areas.map((a) => <option key={a} value={a}>{a[0].toUpperCase() + a.slice(1)}</option>)}</select>
      <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort by">{SORTS.map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select>
    </div>
    <div className="al-filters" role="tablist" aria-label="Kind of finding">
      {TONES.map(([k, t]) => <button key={k} type="button" role="tab" aria-selected={tone === k} className={tone === k ? "on" : ""} onClick={() => setTone(k)}>{t} <b>{k === "all" ? view.cards.length : view.cards.filter((c) => c.tone === k).length}</b></button>)}
    </div>
    <p className="al-muted">{list.length} of {view.cards.length} finding{view.cards.length === 1 ? "" : "s"}{filtered && <> · <button type="button" className="al-link-button" onClick={clear}>Clear filters</button></>}</p>
    {list.length === 0 ? <div className="al-panel al-empty-page"><p>Nothing matches. Try fewer words or clear the filters.</p></div>
      : <div className="ar-list">{list.map((c) => <FindingCard key={c.id} card={c} currency={view.currency}/>)}</div>}
  </div>;
}
