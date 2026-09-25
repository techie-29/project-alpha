const { insight } = require("../helpers");

module.exports = function salesAnomaly(context) {
  return (context.anomalies?.anomalies || []).map((item) => insight("sales_anomaly", context, {
    type: "insight", category: "sales", severity: Math.abs(item.zScore) >= 3.5 ? "high" : "medium",
    title: `Unusual revenue on ${item.date}`, explanation: item.explanation,
    evidence: { metric: "daily_revenue_z_score", value: item.zScore, revenue: item.value, expected_range: context.anomalies.expectedRange },
    entity: { kind: "date", key: item.date, name: item.date }, link: `/analytics/sales?date=${item.date}`
  }));
};
