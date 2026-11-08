import { useEffect, useMemo, useState } from "react";
import { FindingCard } from "./report/Report";
import { fmtValue } from "../../utils/alphaFormat";
import { plain } from "../../utils/deck";

const GROUPS = [
  ["fix", "Do these first", "Problems that cost you money, biggest first."],
  ["keep", "Protect and repeat", "What is working. Keep it going and copy it elsewhere."],
  ["plan", "Plan ahead", "Patterns you can get ready for."],
  ["watch", "Keep an eye on", "Early signs. Check again with next month's data."],
];
const SURE = { Calculated: "Calculated from your rows", "Supported by evidence": "Holds up against chance", "Possible (early sign)": "Early sign" };
const FALLBACK = { fix: "Open the rows behind this and find what they share, then give one person the job of fixing it.", keep: "Find out what you do differently here and repeat it elsewhere.", plan: "Plan stock, staff and promotions around this pattern.", watch: "Check this again when you upload fresh data." };
const key = (id) => `alphaDone:${id}`;

function load(id) { try { return JSON.parse(localStorage.getItem(key(id)) || "{}"); } catch { return {}; } }

/** Builds the to-do list: what to do, why, how much money is behind it. */
export function itemsOf(report, view) {
  const byId = new Map((view.cards || []).map((c) => [c.insight_id, c]));
  const sg = report.suggestions;
  if (sg && ["fix", "keep", "plan", "watch"].some((b) => (sg[b] || []).length)) {
    return ["fix", "keep", "plan", "watch"].flatMap((b) => (sg[b] || []).map((s) => ({ id: s.insight_id, bucket: b, action: plain(s.action || FALLBACK[b]), why: plain(s.title), impact: s.impact, unit: s.impact_unit, claim: s.claim, card: byId.get(s.insight_id) })));
  }
  const bucket = (c) => (c.tone === "risk" ? "fix" : c.tone === "strength" ? "keep" : "watch");
  return (view.cards || []).filter((c) => c.tone !== "data").map((c) => ({ id: c.id, bucket: bucket(c), action: c.look_into || FALLBACK[bucket(c)], why: plain(c.headline), impact: c.money?.amount, unit: view.currency, claim: c.strength, card: c }));
}

export default function SuggestionsPage({ id, report, view }) {
  const [state, setState] = useState(() => load(id));
  useEffect(() => { setState(load(id)); }, [id]);
  const set = (iid, v) => setState((s) => { const n = { ...s }; if (!v || n[iid] === v) delete n[iid]; else n[iid] = v; try { localStorage.setItem(key(id), JSON.stringify(n)); } catch { /* storage blocked */ } return n; });
  const items = useMemo(() => itemsOf(report, view), [report, view]);
  const open = items.filter((i) => state[i.id] !== "done");
  const done = items.filter((i) => state[i.id] === "done");
  const todoFix = open.filter((i) => i.bucket === "fix");
  const atStake = todoFix.reduce((a, i) => a + (i.impact || 0), 0);
  if (!items.length) return <div className="al-panel">Nothing to suggest yet. Alpha found no problem, strength or pattern that passed its checks.</div>;
  return <div className="sg">
    <div className="sg-sum">
      <div><b>{todoFix.length}</b><span>{todoFix.length === 1 ? "thing" : "things"} to fix</span></div>
      {atStake > 0 && <div><b>{fmtValue(atStake, "money", view.currency)}</b><span>involved in them</span></div>}
      <div><b>{done.length}</b><span>done so far</span></div>
    </div>
    {GROUPS.map(([b, title, sub]) => {
      const list = open.filter((i) => i.bucket === b);
      if (!list.length) return null;
      return <section key={b} className="sg-group"><header><h3>{title}</h3><p>{sub}</p></header>
        <ol>{list.map((i, n) => <SuggestionItem key={i.id} n={n + 1} item={i} state={state[i.id]} set={set} currency={view.currency}/>)}</ol></section>;
    })}
    {done.length > 0 && <details className="sg-done"><summary>{done.length} done</summary><ol>{done.map((i, n) => <SuggestionItem key={i.id} n={n + 1} item={i} state="done" set={set} currency={view.currency}/>)}</ol></details>}
  </div>;
}

function SuggestionItem({ n, item, state, set, currency }) {
  const [more, setMore] = useState(false);
  return <li className={`sg-item sg-${item.bucket}${state === "done" ? " is-done" : ""}`} id={`sg-${item.id}`}>
    <i className="sg-n">{n}</i>
    <div className="sg-body">
      <span className="sg-label">{item.bucket === "fix" ? "Do this" : item.bucket === "keep" ? "Keep doing" : item.bucket === "plan" ? "Get ready" : "Watch"}</span>
      <p className="sg-action">{item.action}</p>
      <p className="sg-why"><b>Why:</b> {item.why}</p>
      <div className="sg-meta">
        {item.impact ? <span className="sg-chip sg-money">{fmtValue(Math.abs(item.impact), "money", item.unit || currency)} involved</span> : null}
        {item.claim && <span className="sg-chip">{SURE[item.claim] || item.claim}</span>}
        <span className="sg-track" role="group" aria-label="Progress">
          {[["doing", "Doing"], ["done", "Done"]].map(([k, t]) => <button key={k} type="button" className={state === k ? "on" : ""} aria-pressed={state === k} onClick={() => set(item.id, k)}>{t}</button>)}
        </span>
        {item.card && <button type="button" className="sg-more" aria-expanded={more} onClick={() => setMore(!more)}>{more ? "Hide the numbers" : "See the numbers"}</button>}
      </div>
      {more && item.card && <div className="sg-detail"><FindingCard card={item.card} currency={currency}/></div>}
    </div>
  </li>;
}
