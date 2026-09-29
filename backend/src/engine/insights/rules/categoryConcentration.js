const config = require("../config");
const { insight } = require("../helpers");

module.exports = function categoryConcentration(context) {
  const category = (context.categories || []).find((item) => item.revenueShare >= config.categoryConcentrationShare);
  if (!category) return [];
  return [insight("category_concentration", context, {
    type: "insight", category: "sales", severity: "info", title: `${category.name} drives ${(category.revenueShare * 100).toFixed(1)}% of revenue`,
    explanation: "A single category contributes at least 30% of period revenue.",
    evidence: { metric: "category_revenue_share", value: category.revenueShare, revenue: category.revenue },
    entity: { kind: "category", key: category.name, name: category.name }, link: `/analytics/sales?category=${encodeURIComponent(category.name)}`
  })];
};
