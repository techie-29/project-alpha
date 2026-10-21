import { useState } from "react";
import Chart, { RowsTable } from "./viz/Chart";
import { CLAIM_CLASS, fmtValue } from "../../utils/alphaFormat";

const POL = { good: ["Helps", "pol-good", "▲"], bad: ["Hurts", "pol-bad", "▼"], neutral: ["Neutral", "pol-neutral", "•"] };
const TYPE = { group_difference: "Group difference", combination: "Hidden combination", trend: "Trend", change: "Change over time", share_shift: "Mix shift",
  seasonality: "Seasonal pattern", weekday: "Weekly rhythm", relationship: "Relationship", concentration: "Concentration", dependency: "Dependency",
  quiet_customers: "Customers", new_customers: "Customers", repeat: "Customers", stockout: "Stock", low_cover: "Stock", dead_stock: "Stock", overstock: "Stock",
  loss_makers: "Profit", extreme_values: "Data check", duplicates: "Data check", ai_question: "AI question" };

export function Claim({ claim }) {
  return <span className={`al-badge al-badge-${CLAIM_CLASS[claim] || "calc"}`}>{claim}</span>;
}

export default function InsightCard({ item, feedback, onFeedback, open: openInit = false }) {
  const [open, setOpen] = useState(openInit);
  const [label, cls, icon] = POL[item.polarity] || POL.neutral;
  return <article className={`al-finding ${cls}`} id={`ins-${item.id}`}>
    <button type="button" className="al-finding-head" aria-expanded={open} onClick={() => setOpen(!open)}>
      <div>
        <div className="al-finding-meta"><Claim claim={item.claim}/><span className="al-chip">{TYPE[item.type] || item.type}</span><span className={`al-chip ${cls}`}><b aria-hidden="true">{icon}</b> {label}</span>
          {item.impact ? <span className="al-chip">{fmtValue(Math.abs(item.impact), "money", item.impact_unit)} involved</span> : null}</div>
        <h3>{item.title}</h3>
        <p>{item.detail}</p>
      </div>
      <span className="al-chevron" aria-hidden="true">{open ? "−" : "+"}</span>
    </button>
    {open && <div className="al-finding-body">
      {item.suggestion && <div className="al-action"><strong>What to do</strong><span>{item.suggestion}</span></div>}
      {item.ai_note && <div className="al-ai"><strong>AI helper</strong><span>{item.ai_note}</span><small>Numbers checked against Alpha's own calculations.</small></div>}
      {item.chart && <Chart spec={item.chart}/>}
      {item.calculations?.length > 0 && <div className="al-block"><h4>How the AI helper worked this out</h4>
        {item.calculations.map((c, i) => <div key={i}><p className="al-muted">{c.why}</p><pre className="al-pre">{JSON.stringify(c.result, null, 1).slice(0, 1200)}</pre></div>)}</div>}
      {item.note && <p className="al-muted">{item.note}</p>}
      <RowsTable evidence={item.evidence}/>
      <p className="al-muted">{item.claim === "Calculated" ? "Plain arithmetic on your rows." : item.claim === "Supported by evidence" ? "Passed shuffle tests that allow for chance across everything Alpha checked." : "An early sign: worth watching, not yet solid."} It shows what lines up with what, not a cause.</p>
      {onFeedback && <div className="al-feedback"><span>Was this useful?</span>
        <button type="button" className={feedback === "useful" ? "is-on" : ""} onClick={() => onFeedback(item.id, "useful")}>Useful</button>
        <button type="button" className={feedback === "not_useful" ? "is-on" : ""} onClick={() => onFeedback(item.id, "not_useful")}>Not useful (show less like this)</button></div>}
    </div>}
  </article>;
}
