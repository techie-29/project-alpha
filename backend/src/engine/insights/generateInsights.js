const { severityRank } = require("./helpers");
const lowStock = require("./rules/lowStock");
const stockoutRisk = require("./rules/stockoutRisk");
const excessStock = require("./rules/excessStock");
const slowMoving = require("./rules/slowMoving");
const revenueDecline = require("./rules/revenueDecline");
const salesAnomaly = require("./rules/salesAnomaly");
const categoryConcentration = require("./rules/categoryConcentration");
const productConcentration = require("./rules/productConcentration");
const customerConcentration = require("./rules/customerConcentration");
const marginDrop = require("./rules/marginDrop");
const cancelledRateHigh = require("./rules/cancelledRateHigh");
const atRiskCustomers = require("./rules/atRiskCustomers");
const dataQualityLow = require("./rules/dataQualityLow");

const rules = [lowStock, stockoutRisk, excessStock, slowMoving, revenueDecline, salesAnomaly,
  categoryConcentration, productConcentration, customerConcentration, marginDrop,
  cancelledRateHigh, atRiskCustomers, dataQualityLow];

function generateInsights(context) {
  return rules.flatMap((rule) => rule(context)).sort((left, right) =>
    (severityRank[right.severity] || 0) - (severityRank[left.severity] || 0) || left.id.localeCompare(right.id)
  );
}

module.exports = { generateInsights, rules };
