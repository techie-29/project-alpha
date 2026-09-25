const config = require("../config");
const { insight } = require("../helpers");

module.exports = function customerConcentration(context) {
  const concentration = context.customerConcentration;
  if (!concentration || concentration.topTenPercentShare < config.customerConcentrationShare) return [];
  return [insight("customer_concentration", context, {
    type: "alert", category: "customers", severity: "medium",
    title: `Top customers generate ${(concentration.topTenPercentShare * 100).toFixed(1)}% of revenue`,
    explanation: "The top 10% of customers account for at least 60% of revenue.",
    evidence: { metric: "top_10_percent_customer_share", value: concentration.topTenPercentShare, customer_count: concentration.customerCount },
    action: "Protect key relationships and reduce concentration risk.", link: "/analytics/customers"
  })];
};
