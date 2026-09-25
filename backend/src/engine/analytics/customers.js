const { isoDate, daysBetween } = require("./periods");

function scoreRank(value, sorted, higherIsBetter = true) {
  if (!sorted.length) return null;
  if (sorted.length === 1) return 5;
  const index = sorted.findIndex((candidate) => candidate >= value);
  const percentile = (index < 0 ? sorted.length - 1 : index) / (sorted.length - 1);
  const ascendingScore = Math.min(5, Math.floor(percentile * 5) + 1);
  return higherIsBetter ? ascendingScore : 6 - ascendingScore;
}

function segmentFor({ recencyScore, frequencyScore, monetaryScore }) {
  if (recencyScore >= 4 && frequencyScore >= 4 && monetaryScore >= 4) return "Champions";
  if (recencyScore >= 3 && frequencyScore >= 4) return "Loyal";
  if (recencyScore <= 2 && frequencyScore <= 2) return "Lost";
  if (recencyScore <= 2 && (frequencyScore >= 3 || monetaryScore >= 3)) return "At risk";
  return "Promising";
}

function segmentCustomersRfm(records, { asOf } = {}) {
  const dated = records.filter((record) => record.customer_key && isoDate(record.order_date));
  if (!dated.length) return { available: false, reason: "RFM requires customer identifiers and order dates.", customers: [] };
  const latestDate = dated.map((record) => isoDate(record.order_date)).sort().at(-1);
  const referenceDate = isoDate(asOf) || latestDate;
  const customers = new Map();
  dated.forEach((record) => {
    const current = customers.get(record.customer_key) || {
      customerKey: record.customer_key,
      customerName: record.customer_name || record.customer_key,
      lastPurchaseDate: null,
      orderIds: new Set(),
      monetary: 0
    };
    const date = isoDate(record.order_date);
    if (!current.lastPurchaseDate || date > current.lastPurchaseDate) current.lastPurchaseDate = date;
    if (record.order_id) current.orderIds.add(record.order_id);
    const revenue = Number(record.revenue);
    if (Number.isFinite(revenue)) current.monetary += revenue;
    customers.set(record.customer_key, current);
  });
  const metrics = [...customers.values()].map((customer) => ({
    ...customer,
    recency: Math.max(0, daysBetween(customer.lastPurchaseDate, referenceDate)),
    frequency: customer.orderIds.size
  }));
  const recencies = metrics.map((row) => row.recency).sort((a, b) => a - b);
  const frequencies = metrics.map((row) => row.frequency).sort((a, b) => a - b);
  const monetaryValues = metrics.map((row) => row.monetary).sort((a, b) => a - b);
  const segmented = metrics.map((customer) => {
    const scores = {
      recencyScore: scoreRank(customer.recency, recencies, false),
      frequencyScore: scoreRank(customer.frequency, frequencies, true),
      monetaryScore: scoreRank(customer.monetary, monetaryValues, true)
    };
    return {
      customerKey: customer.customerKey,
      customerName: customer.customerName,
      lastPurchaseDate: customer.lastPurchaseDate,
      recency: customer.recency,
      frequency: customer.frequency,
      monetary: customer.monetary,
      ...scores,
      segment: segmentFor(scores)
    };
  }).sort((a, b) => b.monetary - a.monetary || a.customerKey.localeCompare(b.customerKey));
  const counts = segmented.reduce((result, customer) => {
    result[customer.segment] = (result[customer.segment] || 0) + 1;
    return result;
  }, {});
  return { available: true, asOf: referenceDate, customers: segmented, segmentCounts: counts };
}

module.exports = { scoreRank, segmentFor, segmentCustomersRfm };
