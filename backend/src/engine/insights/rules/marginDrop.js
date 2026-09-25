const config = require("../config");
const { insight } = require("../helpers");

module.exports = function marginDrop(context) {
  if (context.marginChangePoints === null || context.marginChangePoints === undefined || context.marginChangePoints > config.marginDropPoints) return [];
  return [insight("margin_drop", context, {
    type: "alert", category: "sales", severity: "high", title: `Gross margin fell ${Math.abs(context.marginChangePoints).toFixed(1)} points`,
    explanation: "Gross margin is at least five percentage points below the previous period.",
    evidence: { metric: "margin_change_points", value: context.marginChangePoints, current_margin: context.kpis?.grossProfit?.margin },
    action: "Review price, discount and cost changes.", link: "/analytics/sales"
  })];
};
