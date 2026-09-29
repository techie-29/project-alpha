const config = require("../config");
const { insight } = require("../helpers");

module.exports = function cancelledRateHigh(context) {
  const orders = context.kpis?.orders;
  if (!orders?.available || !orders.value) return [];
  const rate = orders.cancelled / orders.value;
  if (rate < config.cancelledRate) return [];
  return [insight("cancelled_rate_high", context, {
    type: "alert", category: "sales", severity: rate >= 0.3 ? "high" : "medium", title: `${(rate * 100).toFixed(1)}% of orders were cancelled`,
    explanation: `${orders.cancelled} of ${orders.value} orders were cancelled in the selected period.`,
    evidence: { metric: "cancelled_order_rate", value: rate, cancelled: orders.cancelled, orders: orders.value },
    action: "Investigate cancellation reasons and affected products.", link: "/analytics/sales?status=cancelled"
  })];
};
