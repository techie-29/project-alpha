const config = require("../config");
const { insight } = require("../helpers");

module.exports = function revenueDecline(context) {
  const comparison = context.kpis?.revenue?.previousPeriod;
  if (!comparison?.available || comparison.percentage > config.revenueDeclineRate) return [];
  return [insight("revenue_decline", context, {
    type: "alert", category: "sales", severity: comparison.percentage <= -0.25 ? "high" : "medium",
    title: `Revenue declined by ${Math.abs(comparison.percentage * 100).toFixed(1)}%`,
    explanation: `Revenue changed from ${comparison.previous} to ${comparison.current} versus the previous period.`,
    evidence: { metric: "revenue_change", value: comparison.percentage, current: comparison.current, previous: comparison.previous },
    action: "Review product, category and customer drivers.", link: "/analytics/sales"
  })];
};
