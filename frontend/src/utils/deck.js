/** Builds the presentation from a finished analysis. Pure: the same report always gives the same slides. No AI, no network.
 *  Every slide carries its own speaker notes, written from templates around the real numbers. */
import { allSections, allTiles } from "../components/alpha/AreaPage";
import { healthOf } from "../context/AnalysisContext";
import { businessHealth } from "./businessHealth";
import { change, fmtValue } from "./alphaFormat";

const KEY = ["revenue", "profit", "orders", "customers", "margin"];
const tileBy = (tiles, m) => tiles.find((t) => t.metric === m);
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
/** Turns engine wording into how a person would say it to partners. */
export function plain(h) {
  let t = String(h || "");
  const m = t.match(/^(.+?) rate \((.+?)\) is (.+?) (higher|lower) for (.+?) \((.+?)\)$/i);
  if (m) {
    const [, what, , size, dir, who, col] = m;
    const noun = { cancelled: "cancellations", returned: "returns", refunded: "refunds", damaged: "damaged orders", late: "late deliveries" }[what.toLowerCase()] || `${what.toLowerCase()} rate`;
    return `${who} (${col}) has ${size} ${dir} ${noun} than the rest`;
  }
  return t.replace(/\s*\((status|branch|staff|category|supplier|order type|delivery mode|offer code|channel)\)/gi, "").replace(/\s+/g, " ").trim();
}
const first = (s) => String(s || "").split(/(?<=[.!?])\s/)[0];

export const THEMES = {
  ink: { name: "Ink", bg: "10202E", panel: "1A3042", text: "FFFFFF", dim: "9FB2C4", accent: "3DDC9A", warn: "F2BF4D", bad: "FF9C8A", line: "2A6F97" },
  daylight: { name: "Daylight", bg: "FFFFFF", panel: "F3F5F7", text: "18202A", dim: "5D6773", accent: "12976A", warn: "C98500", bad: "C62828", line: "2A6F97" },
  emerald: { name: "Emerald", bg: "0B3B2E", panel: "12503F", text: "FFFFFF", dim: "A9CFC0", accent: "7EF0C0", warn: "F2D06B", bad: "FFB09E", line: "7EF0C0" },
};

function revenueSeries(report, tiles) {
  const chart = allSections(report.overview).flatMap((s) => s.charts).find((c) => c.type === "line" && c.metric === "revenue" && c.grains?.month);
  if (!chart) return null;
  const g = chart.grains.month;
  let x = g.x, y = g.series[0].values;
  const partial = /not complete/i.test(tileBy(tiles, "revenue")?.note || "");
  if (partial && x.length > 3) { x = x.slice(0, -1); y = y.slice(0, -1); }
  return { x, y, fmt: chart.fmt, unit: chart.unit, forecast: chart.forecast, metric: chart.metric };
}

export function buildDeck(report, view, { business = "Your business", presenter = "", title = "" } = {}) {
  const tiles = allTiles(report.overview);
  const currency = view.currency;
  const money = (v) => fmtValue(Math.abs(v), "money", currency);
  const cards = view.cards || [];
  const dataHealth = healthOf(report);
  const bh = businessHealth(tiles, cards);
  const risks = cards.filter((c) => c.tone === "risk").sort((a, b) => (b.money?.amount || 0) - (a.money?.amount || 0));
  const strengths = cards.filter((c) => c.tone === "strength");
  const actionsRaw = (report.briefing?.first_actions || []).slice(0, 5);
  const suggestion = (c) => c.look_into || (report.suggestions ? Object.values(report.suggestions).flat().find((s) => s.insight_id === c.insight_id)?.action : "") || "";
  const rev0 = tileBy(tiles, "revenue");
  const slides = [];
  const add = (s) => slides.push(s);

  const period = rev0?.last_period ? `${rev0.last_period.label}` : "";
  const prevPeriod = rev0?.last_period?.previous_label || "";
  const atRisk = risks.slice(0, 3).reduce((a, c) => a + (c.money?.amount || 0), 0);
  // 1. title
  const files = (report.files || []).length;
  const when = report.generated_at ? new Date(report.generated_at).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" }) : "";
  add({ id: "title", kind: "title", label: "Title", title: title || `${business}: performance review`, subtitle: [period && `${period} review`, when && `Prepared ${when}`].filter(Boolean).join("  ·  "), presenter,
    notes: `Welcome, everyone. This is our performance review${period ? ` for ${period}` : ""}. It is built from ${plural(files, "file")} of our own data, so every number you see is ours. I will cover how we did, what drove it, where we are losing money, and then ask you for a few decisions. About ten minutes, and please interrupt with questions.` });

  // 1b. the verdict: the whole story in one line
  const rc = rev0?.last_period?.change;
  if (Number.isFinite(rc) || risks.length) {
    const up = rc > 0, dir = Math.abs(rc) < 0.005 ? "flat" : up ? "up" : "down";
    const lead = Number.isFinite(rc) ? `Revenue is ${dir === "flat" ? "flat" : `${dir} ${Math.abs(rc * 100).toFixed(0)}%`} on ${prevPeriod || "last period"}` : "Here is where the business stands";
    const tail = risks.length ? (atRisk ? `, but about ${money(atRisk)} is leaking through ${plural(Math.min(risks.length, 3), "fixable problem")}` : `, with ${plural(risks.length, "problem")} to fix`) : ", and nothing urgent needs fixing";
    const bullets = [Number.isFinite(rc) && rev0 ? `${rev0.label}: ${fmtValue(rev0.value, rev0.fmt, rev0.unit)} (${change(rc, rev0.fmt)} vs ${prevPeriod})` : null,
      bh ? `Business health ${bh.score} out of 100: ${bh.label.toLowerCase()}` : null,
      risks.length ? `${plural(risks.length, "thing")} to fix, biggest first` : null, strengths.length ? `${plural(strengths.length, "thing")} working well to protect` : null].filter(Boolean);
    add({ id: "verdict", kind: "verdict", label: "The headline", title: lead + tail + ".", bullets,
      notes: `If you remember one slide, remember this one. ${lead}${tail}. The rest of the meeting is the detail behind that sentence and what I need from you.` });
  }


  // 2. snapshot
  const rev = tileBy(tiles, "revenue");
  const figs = KEY.map((m) => tileBy(tiles, m)).filter(Boolean).map((t) => {
    const c = t.last_period?.change;
    const up = c > 0, flat = Math.abs(c) < 1e-9;
    return { label: t.label, value: fmtValue(t.value, t.fmt, t.unit), change: Number.isFinite(c) ? change(c, t.fmt) : null, tone: flat || !Number.isFinite(c) || !t.polarity ? "flat" : (t.polarity > 0) === up ? "good" : "bad", since: t.last_period ? `${t.last_period.label} vs ${t.last_period.previous_label}` : "" };
  });
  if (figs.length >= 2) {
    const c = rev?.last_period?.change;
    const head = period ? `How we did in ${period}${prevPeriod ? `, against ${prevPeriod}` : ""}` : "How we did";
    add({ id: "snapshot", kind: "snapshot", label: "Snapshot", title: head, figures: figs, business: bh ? { score: bh.score, label: bh.label } : null, data: dataHealth,
      notes: `Here is the scorecard.${Number.isFinite(c) ? ` Revenue is ${c >= 0 ? "up" : "down"} ${Math.abs(c * 100).toFixed(1)}% on ${prevPeriod || "the period before"}.` : ""} Green means moving the right way, red the wrong way. Look at profit and margin as well as revenue, because growth that costs margin is not free. ${bh ? `The business health score is ${bh.score} out of 100, which we call ${bh.label.toLowerCase()}. ` : ""}${dataHealth != null ? `Separately, the data itself scores ${dataHealth}, so we can trust what follows.` : ""} ${risks.length ? `We found ${plural(risks.length, "risk")}; the next slides cover the biggest.` : ""}`.trim() });
  }

  // 3. sales over time
  const rs = revenueSeries(report, tiles);
  if (rs && rs.x.length >= 4) {
    const i = rs.y.indexOf(Math.max(...rs.y)), j = rs.y.indexOf(Math.min(...rs.y));
    add({ id: "sales", kind: "sales", label: "Sales over time", title: "How sales have moved", line: { x: rs.x, y: rs.y, fmt: rs.fmt, unit: rs.unit },
      caption: `Best month: ${rs.x[i]} (${fmtValue(rs.y[i], rs.fmt, rs.unit)}). Weakest: ${rs.x[j]} (${fmtValue(rs.y[j], rs.fmt, rs.unit)}).`,
      notes: `This is revenue month by month. The best month was ${rs.x[i]} and the weakest was ${rs.x[j]}. Ask the room what happened in those two months: a promotion, a season, a stock-out. The answer usually explains most of the shape.` });
  }

  // 3b. what drove it: where the revenue comes from
  const bars = allSections(report.overview).flatMap((x) => x.charts).filter((c) => c.type === "bar" && c.metric === "revenue" && (c.rows || c.items || c.data || []).length >= 3);
  const dv = bars[0];
  if (dv) {
    const raw = (dv.rows || dv.items || dv.data).map((r) => ({ group: r.group ?? r.name ?? r.label ?? r.x, value: r.value ?? r.y })).filter((r) => Number.isFinite(r.value) && r.group != null).sort((a, b) => b.value - a.value);
    const tot = raw.reduce((a, r) => a + r.value, 0), top = raw.slice(0, 5);
    if (tot > 0 && top.length >= 3) {
      const share = top[0].value / tot, by = String(dv.title).replace(/^.*\bby\s+/i, "");
      add({ id: "drivers", kind: "drivers", label: "What drove it", title: `Where our revenue comes from, by ${by}`, chart: { title: dv.title, fmt: dv.fmt || "money", unit: dv.unit || "", rows: top, focus: top[0].group }, share: Math.round(share * 100), top: String(top[0].group),
        caption: `${top[0].group} brings in ${Math.round(share * 100)}% of revenue${share >= 0.4 ? ". That is a lot to depend on one source." : "."}`,
        notes: `This is where the money comes from, by ${by}. ${top[0].group} is the biggest at ${Math.round(share * 100)}% of revenue${top[1] ? `, then ${top[1].group} at ${Math.round((top[1].value / tot) * 100)}%` : ""}. ${share >= 0.4 ? "That concentration is a risk worth discussing: what happens if we lose it? " : ""}Ask the team whether this split matches what they feel on the ground.` });
    }
  }

  // 4-6. problems
  risks.slice(0, 3).forEach((c, n) => {
    const cd = c.chart_data && c.chart_data.type === "bar" && (c.chart_data.rows || []).length > 1 ? c.chart_data : null;
    const act = suggestion(c) || "Open the rows behind this in the Data Explorer, find what they share, and give one person the job of fixing it.";
    const tb = c.chart_data && c.chart_data.type === "table" && (c.chart_data.rows || []).length ? c.chart_data : null;
    add({ id: `risk${n + 1}`, kind: "risk", label: `Problem ${n + 1}`, n: n + 1, title: plain(c.headline), kicker: n === 0 ? "Where we are losing money: the biggest" : "Where we are losing money", point: first(c.points?.[0]), money: c.money?.amount ? money(c.money.amount) : null,
      chart: cd ? { title: cd.title, fmt: cd.fmt, unit: cd.unit || "", rows: cd.rows.slice(0, 8), focus: cd.focus || c.look_at?.value || c.tags?.[1] || (cd.rows.find((r) => String(r.group).length > 2 && c.headline.includes(String(r.group))) || {}).group || null } : null, action: act, area: c.area,
      table: tb ? (() => { const keys = Object.keys(tb.rows[0]).filter((k) => k !== "key").slice(0, 4); return { title: tb.title, columns: keys, rows: tb.rows.slice(0, 6).map((r) => keys.map((k) => (r[k] == null ? "" : typeof r[k] === "number" ? fmtValue(r[k], tb.fmt || "number", "") : String(r[k])))) }; })() : null,
      notes: `${n === 0 ? "This is the most expensive problem we found. " : "Next problem. "}${plain(c.headline)}. ${first(c.points?.[0])} ${c.money?.amount ? `That is roughly ${money(c.money.amount)} we are not keeping. ` : ""}${act ? `Proposed fix: ${act} ` : ""}Pause here and ask who on the team owns this.` });
  });

  // 7. going well
  if (strengths.length) {
    add({ id: "good", kind: "good", label: "Going well", title: "What worked, and is worth repeating",
      items: strengths.slice(0, 3).map((c) => ({ headline: plain(c.headline), point: first(c.points?.[0]) })),
      notes: `Credit where it is due. ${strengths.slice(0, 3).map((c) => plain(c.headline)).join("; ")}. Thank the people behind these, and ask how we copy them in the parts of the business that lag.` });
  }

  // 8. forecast
  const fc = rs?.forecast;
  if (fc?.status === "ok") {
    const bt = fc.backtest;
    add({ id: "forecast", kind: "forecast", label: "Forecast", title: "Where we are heading: the next three months", line: { x: rs.x.slice(-12), y: rs.y.slice(-12), fmt: rs.fmt, unit: rs.unit }, forecast: { x: fc.x, mid: fc.mid, low: fc.low, high: fc.high, last: fc.last_actual },
      total: { mid: fmtValue(fc.total.mid, rs.fmt, rs.unit), low: fmtValue(fc.total.low, rs.fmt, rs.unit), high: fmtValue(fc.total.high, rs.fmt, rs.unit) },
      trust: bt ? { error: Math.round(bt.error * 100), grade: bt.grade } : null, untested: fc.untested || null,
      notes: `Now the outlook. This is an estimate, not a promise. Over the next three months revenue is most likely about ${fmtValue(fc.total.mid, rs.fmt, rs.unit)}, within a range of ${fmtValue(fc.total.low, rs.fmt, rs.unit)} to ${fmtValue(fc.total.high, rs.fmt, rs.unit)}. ${bt ? `To check how far to trust it we hid the last three months, predicted them, and compared: it was off by about ${Math.round(bt.error * 100)}% a month, which is ${bt.grade === "good" ? "close" : bt.grade === "fair" ? "reasonably close" : "rough, so treat the range as wide"}.` : fc.untested}` });
  }

  // 9. actions
  const acts = actionsRaw.length ? actionsRaw.map((a) => ({ title: plain(a.title), action: plain(a.action), impact: a.impact ? money(a.impact) : null }))
    : risks.slice(0, 3).map((c) => ({ title: plain(c.headline), action: plain(suggestion(c)) || "Look at the rows behind this finding.", impact: c.money?.amount ? money(c.money.amount) : null }));
  if (acts.length) {
    add({ id: "actions", kind: "actions", label: "Action plan", title: "The next 30 days: who does what", items: acts.slice(0, 4).map((a, k) => ({ ...a, when: ["This week", "Week 2", "Week 3", "Week 4"][k] })),
      notes: `This is the plan. If we only do these, in this order, we fix the biggest leaks first. For each one I want a name next to it before we leave the room. ${acts[0] ? `The first, this week: ${plain(acts[0].title)}.` : ""}` });
  }

  // 11. close
  const todo = [...risks.slice(0, 3).map((c) => `Decide who owns: ${plain(c.headline)}`), "Agree a date to look at fresh numbers again"];
  add({ id: "close", kind: "close", label: "Next steps", title: "What I need from you today", bullets: risks.length ? todo : ["Agree what to protect and repeat", "Agree a date to look at fresh numbers again"], presenter, business,
    notes: `To close. I am asking for decisions, not opinions: an owner for each problem, and a date when we look at fresh numbers again to see whether the leaks shrank. Questions?` });

  // 10. data quality
  const r = report.data_check?.rows;
  if (r) {
    const tot = (r.ok || 0) + (r.fixed || 0) + (r.flagged || 0) + (r.left_out || 0);
    add({ id: "quality", kind: "quality", label: "Data quality", title: "Can we trust the numbers?", appendix: true, health: dataHealth, rows: r, total: tot, headline: report.data_check.headline || "",
      notes: `If anyone asks whether the numbers can be trusted, this is the answer. Every number here is only as good as the data behind it. We checked ${tot.toLocaleString()} rows: ${(r.ok || 0).toLocaleString()} were fine, ${(r.fixed || 0).toLocaleString()} were cleaned automatically, ${(r.flagged || 0).toLocaleString()} are flagged and ${(r.left_out || 0).toLocaleString()} were left out of the totals. ${dataHealth != null ? `That gives a data health of ${dataHealth}.` : ""}` });
  }

  return slides;
}

export const slideIds = (slides) => slides.map((s) => s.id);
