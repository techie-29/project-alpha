/** Builds the presentation from a finished analysis. Pure: the same report always gives the same slides. No AI, no network.
 *  Every slide carries its own speaker notes, written from templates around the real numbers. */
import { allSections, allTiles } from "../components/alpha/AreaPage";
import { healthOf } from "../context/AnalysisContext";
import { businessHealth } from "./businessHealth";
import { change, fmtValue } from "./alphaFormat";

const KEY = ["revenue", "profit", "orders", "customers", "margin"];
const tileBy = (tiles, m) => tiles.find((t) => t.metric === m);
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
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
  const slides = [];
  const add = (s) => slides.push(s);

  // 1. title
  const files = (report.files || []).length;
  const when = report.generated_at ? new Date(report.generated_at).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" }) : "";
  add({ id: "title", kind: "title", label: "Title", title: title || `${business}: business review`, subtitle: when ? `Prepared ${when}` : "", presenter,
    notes: `Welcome. This review is built from ${plural(files, "file")} of your own business data${when ? `, analysed on ${when}` : ""}. Everything here comes from the numbers, and each slide says where to look next. It should take about ${Math.max(5, slides.length * 2 + 8)} minutes.` });

  // 2. snapshot
  const rev = tileBy(tiles, "revenue");
  const figs = KEY.map((m) => tileBy(tiles, m)).filter(Boolean).map((t) => {
    const c = t.last_period?.change;
    const up = c > 0, flat = Math.abs(c) < 1e-9;
    return { label: t.label, value: fmtValue(t.value, t.fmt, t.unit), change: Number.isFinite(c) ? change(c, t.fmt) : null, tone: flat || !Number.isFinite(c) || !t.polarity ? "flat" : (t.polarity > 0) === up ? "good" : "bad", since: t.last_period ? `${t.last_period.label} vs ${t.last_period.previous_label}` : "" };
  });
  if (figs.length >= 2) {
    const c = rev?.last_period?.change;
    const head = risks.length ? `${plural(risks.length, "thing")} ${risks.length === 1 ? "needs" : "need"} your attention` : "Nothing urgent to report";
    add({ id: "snapshot", kind: "snapshot", label: "Snapshot", title: head, figures: figs, business: bh ? { score: bh.score, label: bh.label } : null, data: dataHealth,
      notes: `Start with the big picture.${Number.isFinite(c) ? ` Revenue is ${c >= 0 ? "up" : "down"} ${Math.abs(c * 100).toFixed(1)}% on the month before.` : ""} ${bh ? `The business health score is ${bh.score} out of 100, which we call ${bh.label.toLowerCase()}. ` : ""}${dataHealth != null ? `Separately, the data itself scores ${dataHealth}, so we can trust what follows.` : ""} ${risks.length ? `We found ${plural(risks.length, "risk")}; the next slides cover the biggest.` : ""}`.trim() });
  }

  // 3. sales over time
  const rs = revenueSeries(report, tiles);
  if (rs && rs.x.length >= 4) {
    const i = rs.y.indexOf(Math.max(...rs.y)), j = rs.y.indexOf(Math.min(...rs.y));
    add({ id: "sales", kind: "sales", label: "Sales over time", title: "How sales have moved", line: { x: rs.x, y: rs.y, fmt: rs.fmt, unit: rs.unit },
      caption: `Best month: ${rs.x[i]} (${fmtValue(rs.y[i], rs.fmt, rs.unit)}). Weakest: ${rs.x[j]} (${fmtValue(rs.y[j], rs.fmt, rs.unit)}).`,
      notes: `This is revenue month by month. The best month was ${rs.x[i]} and the weakest was ${rs.x[j]}. Ask the room what happened in those two months: a promotion, a season, a stock-out. The answer usually explains most of the shape.` });
  }

  // 4-6. problems
  risks.slice(0, 3).forEach((c, n) => {
    const cd = c.chart_data && c.chart_data.type === "bar" && (c.chart_data.rows || []).length > 1 ? c.chart_data : null;
    const act = suggestion(c) || "Open the rows behind this in the Data Explorer, find what they share, and give one person the job of fixing it.";
    const tb = c.chart_data && c.chart_data.type === "table" && (c.chart_data.rows || []).length ? c.chart_data : null;
    add({ id: `risk${n + 1}`, kind: "risk", label: `Problem ${n + 1}`, n: n + 1, title: c.headline, point: first(c.points?.[0]), money: c.money?.amount ? money(c.money.amount) : null,
      chart: cd ? { title: cd.title, fmt: cd.fmt, unit: cd.unit || "", rows: cd.rows.slice(0, 8), focus: cd.focus || c.look_at?.value || c.tags?.[1] || (cd.rows.find((r) => String(r.group).length > 2 && c.headline.includes(String(r.group))) || {}).group || null } : null, action: act, area: c.area,
      table: tb ? (() => { const keys = Object.keys(tb.rows[0]).filter((k) => k !== "key").slice(0, 4); return { title: tb.title, columns: keys, rows: tb.rows.slice(0, 6).map((r) => keys.map((k) => (r[k] == null ? "" : typeof r[k] === "number" ? fmtValue(r[k], tb.fmt || "number", "") : String(r[k])))) }; })() : null,
      notes: `${n === 0 ? "This is the most expensive problem we found. " : ""}${c.headline}. ${first(c.points?.[0])} ${c.money?.amount ? `That is roughly ${money(c.money.amount)} involved. ` : ""}${act ? `What to do: ${act}` : "Open the rows behind it to look for a shared cause."}` });
  });

  // 7. going well
  if (strengths.length) {
    add({ id: "good", kind: "good", label: "Going well", title: "What is going well",
      items: strengths.slice(0, 3).map((c) => ({ headline: c.headline, point: first(c.points?.[0]) })),
      notes: `It is not all problems. ${strengths.slice(0, 3).map((c) => c.headline).join("; ")}. These are worth protecting and, where possible, repeating in the parts of the business that lag.` });
  }

  // 8. forecast
  const fc = rs?.forecast;
  if (fc?.status === "ok") {
    const bt = fc.backtest;
    add({ id: "forecast", kind: "forecast", label: "Forecast", title: "The next three months", line: { x: rs.x.slice(-12), y: rs.y.slice(-12), fmt: rs.fmt, unit: rs.unit }, forecast: { x: fc.x, mid: fc.mid, low: fc.low, high: fc.high, last: fc.last_actual },
      total: { mid: fmtValue(fc.total.mid, rs.fmt, rs.unit), low: fmtValue(fc.total.low, rs.fmt, rs.unit), high: fmtValue(fc.total.high, rs.fmt, rs.unit) },
      trust: bt ? { error: Math.round(bt.error * 100), grade: bt.grade } : null, untested: fc.untested || null,
      notes: `This is an estimate, not a promise. Over the next three months revenue is most likely about ${fmtValue(fc.total.mid, rs.fmt, rs.unit)}, within a range of ${fmtValue(fc.total.low, rs.fmt, rs.unit)} to ${fmtValue(fc.total.high, rs.fmt, rs.unit)}. ${bt ? `To check how far to trust it we hid the last three months, predicted them, and compared: it was off by about ${Math.round(bt.error * 100)}% a month, which is ${bt.grade === "good" ? "close" : bt.grade === "fair" ? "reasonably close" : "rough, so treat the range as wide"}.` : fc.untested}` });
  }

  // 9. actions
  const acts = actionsRaw.length ? actionsRaw.map((a) => ({ title: a.title, action: a.action, impact: a.impact ? money(a.impact) : null }))
    : risks.slice(0, 3).map((c) => ({ title: c.headline, action: suggestion(c) || "Look at the rows behind this finding.", impact: c.money?.amount ? money(c.money.amount) : null }));
  if (acts.length) {
    add({ id: "actions", kind: "actions", label: "Action plan", title: "Do this first", items: acts.slice(0, 4),
      notes: `If you only do three things after this meeting, do these, in this order. They are ranked by the money involved and how strong the evidence is. ${acts[0] ? `Start with: ${acts[0].title}.` : ""}` });
  }

  // 10. data quality
  const r = report.data_check?.rows;
  if (r) {
    const tot = (r.ok || 0) + (r.fixed || 0) + (r.flagged || 0) + (r.left_out || 0);
    add({ id: "quality", kind: "quality", label: "Data quality", title: "Can we trust the numbers?", health: dataHealth, rows: r, total: tot, headline: report.data_check.headline || "",
      notes: `Every number here is only as good as the data behind it. We checked ${tot.toLocaleString()} rows: ${(r.ok || 0).toLocaleString()} were fine, ${(r.fixed || 0).toLocaleString()} were cleaned automatically, ${(r.flagged || 0).toLocaleString()} are flagged and ${(r.left_out || 0).toLocaleString()} were left out of the totals. ${dataHealth != null ? `That gives a data health of ${dataHealth}.` : ""}` });
  }

  // 11. close
  const todo = acts.slice(0, 3).map((a) => a.title);
  add({ id: "close", kind: "close", label: "Next steps", title: "What happens next", bullets: todo.length ? todo : ["Upload fresh data next week and compare."], presenter, business,
    notes: `To close: agree an owner for each of these. Then upload fresh data next week and check whether the problems shrank. Thank you.` });
  return slides;
}

export const slideIds = (slides) => slides.map((s) => s.id);
