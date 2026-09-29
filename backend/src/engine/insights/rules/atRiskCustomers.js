const { insight } = require("../helpers");

module.exports = function atRiskCustomers(context) {
  const customers = (context.rfm?.customers || []).filter((customer) => customer.segment === "At risk");
  if (!customers.length) return [];
  const monetary = customers.reduce((sum, customer) => sum + customer.monetary, 0);
  return [insight("at_risk_customers", context, {
    type: "recommendation", category: "customers", severity: "medium", title: `${customers.length} customer${customers.length === 1 ? " is" : "s are"} at risk`,
    explanation: `These previously valuable or frequent customers have not purchased recently; their recorded spend is ${monetary.toFixed(2)}.`,
    evidence: { metric: "at_risk_customer_count", value: customers.length, monetary }, action: "Prioritize a targeted re-engagement campaign.",
    link: "/analytics/customers?segment=At%20risk"
  })];
};
