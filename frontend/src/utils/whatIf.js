/** What-if arithmetic. Plain sums on the owner's own totals: not a forecast. */
export const REACTION = { same: 0, little: -0.5, lot: -1.5 };   // % change in units bought per 1% price change

/** Revenue and profit from the overview figures; null when the report has no revenue. */
export function baseline(tiles = []) {
  const get = (label) => (tiles.find((t) => t.label === label) || {}).value;
  const revenue = get("Revenue"), profit = get("Profit");
  if (!(revenue > 0)) return null;
  return { revenue, profit: profit == null ? null : profit, cost: profit == null ? null : revenue - profit, orders: get("Orders") ?? null };
}

/** s: price, units, cost, discount in percent; reaction: key of REACTION. */
export function simulate(b, s) {
  const price = (s.price || 0) / 100, units = (s.units || 0) / 100, cost = (s.cost || 0) / 100, disc = (s.discount || 0) / 100;
  const react = REACTION[s.reaction] ?? 0;
  const volume = Math.max(0, (1 + units) * (1 + react * price));
  const revenue = b.revenue * (1 + price) * (1 - disc) * volume;
  if (b.cost == null) return { revenue, profit: null, margin: null, volume, orders: b.orders == null ? null : b.orders * volume };
  const spend = b.cost * (1 + cost) * volume;
  const profit = revenue - spend;
  return { revenue, profit, margin: revenue > 0 ? profit / revenue : null, volume, orders: b.orders == null ? null : b.orders * volume };
}
