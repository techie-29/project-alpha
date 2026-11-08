/** Business health: one 0-100 score for how the business itself is doing (not the data), from parts the data can support.
 *  Plain arithmetic with fixed, documented thresholds. Parts the files cannot measure are left out, never guessed. */
const clamp = (v) => Math.max(0, Math.min(100, Math.round(v)));
const lerp = (x, pts) => {                       // piecewise-linear through [input, score] points
  if (x <= pts[0][0]) return pts[0][1];
  for (let i = 1; i < pts.length; i++) if (x <= pts[i][0]) { const [a, sa] = pts[i - 1], [b, sb] = pts[i]; return sa + ((x - a) / (b - a)) * (sb - sa); }
  return pts[pts.length - 1][1];
};
const pc = (v, d = 1) => `${(v * 100).toFixed(d)}%`;

export function businessHealth(tiles = [], cards = []) {
  const t = (m) => tiles.find((x) => x.metric === m);
  const parts = [];
  const rev = t("revenue");
  const g = rev?.vs_last_year ? { c: rev.vs_last_year.change, vs: `vs ${rev.vs_last_year.label}` } : rev?.last_period ? { c: rev.last_period.change, vs: `${rev.last_period.label} vs ${rev.last_period.previous_label}` } : null;
  if (g && Number.isFinite(g.c)) parts.push({ id: "growth", label: "Growth", weight: 25, score: clamp(50 + g.c * 250), value: `Revenue ${g.c >= 0 ? "up" : "down"} ${pc(Math.abs(g.c))} (${g.vs})`,
    how: "Flat sales score 50; +20% or more scores 100; -20% or worse scores 0.", page: "trends", fix: "Find what grew in your best periods and do more of it." });
  const m = t("margin");
  if (m && Number.isFinite(m.value)) parts.push({ id: "margin", label: "Profit margin", weight: 20, score: clamp(lerp(m.value, [[0, 0], [0.05, 40], [0.15, 70], [0.3, 100]])), value: `${pc(m.value)} of sales is profit`,
    how: "0% scores 0, 5% scores 40, 15% scores 70, 30% or more scores 100. Normal margins differ a lot between trades.", page: "sales", fix: "Check discounts, prices and the lowest-margin groups on the Sales page." });
  const rr = t("repeat_rate"), cust = t("customers"), quiet = t("quiet_customers");
  if (rr && Number.isFinite(rr.value)) {
    const gone = quiet && cust?.value ? quiet.value / cust.value : 0;
    parts.push({ id: "customers", label: "Customers coming back", weight: 15, score: clamp(lerp(rr.value, [[0, 0], [0.3, 50], [0.6, 100]]) - gone * 100),
      value: `${pc(rr.value, 0)} buy again${quiet ? `; ${Math.round(quiet.value).toLocaleString()} regulars have gone quiet` : ""}`,
      how: "Share of customers who buy more than once (60% or more scores 100), minus the share of regulars who stopped coming.", page: "customers", fix: "Win back the regular customers who have gone quiet." });
  }
  const rates = tiles.filter((x) => String(x.metric).startsWith("rate:") && Number.isFinite(x.value));
  if (rates.length) {
    const sum = rates.reduce((s, x) => s + x.value, 0);
    parts.push({ id: "problems", label: "Orders that go wrong", weight: 15, score: clamp(100 - sum * 400), value: `${pc(sum)} ${rates.map((x) => x.label.replace(/ \(.*\)$/, "").replace(/ rate$/i, "").toLowerCase()).join(" or ")}`,
      how: "Returned, cancelled and refunded orders together: 0% scores 100, 10% scores 60, 25% or more scores 0.", page: "alerts", fix: "Tackle the group with the highest return or cancellation rate first." });
  }
  const oos = t("out_of_stock"), sold = t("products_sold");
  if (oos && sold?.value) parts.push({ id: "stock", label: "Stock", weight: 10, score: clamp(100 - (oos.value / sold.value) * 300), value: `${oos.value} of ${sold.value} selling products out of stock`,
    how: "Share of selling products with nothing on the shelf: none scores 100, a third or more scores 0.", page: "products", fix: "Re-order the products that are out of stock but still selling." });
  const risks = cards.filter((c) => c.tone === "risk");
  if (tiles.length) parts.push({ id: "risks", label: "Open risks", weight: 15, score: clamp(100 - risks.length * 10), value: `${risks.length} risk${risks.length === 1 ? "" : "s"} found`,
    how: "Each risk Alpha found takes 10 points off.", page: "alerts", fix: "Work through the Alerts page, most serious first." });
  if (parts.length < 2) return null;
  const w = parts.reduce((s, p) => s + p.weight, 0);
  const score = clamp(parts.reduce((s, p) => s + p.score * p.weight, 0) / w);
  const gap = (p) => p.weight * (100 - p.score);
  const ranked = [...parts].sort((a, b) => gap(b) - gap(a));
  // "open risks" is the catch-all; a concrete part that is nearly as big is the more useful advice
  const raise = ranked[0]?.id === "risks" && ranked[1] && gap(ranked[1]) >= 0.7 * gap(ranked[0]) ? ranked[1] : ranked[0];
  const missing = ["growth", "margin", "customers", "problems", "stock"].filter((id) => !parts.some((p) => p.id === id));
  return { score, label: score >= 75 ? "Strong" : score >= 50 ? "Steady" : "Needs care", parts, raise: raise.score < 100 ? { ...raise, gain: Math.round((raise.weight * (100 - raise.score)) / w) } : null, missing };
}
