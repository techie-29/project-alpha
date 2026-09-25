const { compareValues } = require("./comparisons");
const { computeInventoryKpi } = require("./inventory");

function number(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function availableNumbers(records, field) {
  return records.map((record) => number(record[field])).filter((value) => value !== null);
}

function sum(values) {
  return values.reduce((total, value) => total + value, 0);
}

function groupSum(records, keyField, valueField) {
  const groups = new Map();
  records.forEach((record) => {
    const key = record[keyField];
    const value = number(record[valueField]);
    if (!key || value === null) return;
    groups.set(key, (groups.get(key) || 0) + value);
  });
  return [...groups.entries()].map(([key, value]) => ({ key, value }));
}

function extreme(groups, direction = "max") {
  if (!groups.length) return null;
  return groups.reduce((best, item) => (
    direction === "max" ? (item.value > best.value ? item : best) : (item.value < best.value ? item : best)
  ));
}

function dailyRevenue(records) {
  return groupSum(records, "order_date", "revenue")
    .map((item) => ({ date: String(item.key).slice(0, 10), revenue: item.value }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

function revenueValue(records) {
  const values = availableNumbers(records, "revenue");
  return values.length ? sum(values) : null;
}

function orderCount(records) {
  const ids = new Set(records.map((record) => record.order_id).filter(Boolean));
  return ids.size ? ids.size : null;
}

function unitsValue(records) {
  const values = availableNumbers(records, "quantity");
  return values.length ? sum(values) : null;
}

function computeRevenue(records, previousRecords) {
  const total = revenueValue(records);
  if (total === null) return { available: false, reason: "Revenue unavailable — map revenue or quantity and unit_price." };
  const daily = dailyRevenue(records);
  const products = groupSum(records, "product_key", "revenue");
  return {
    available: true,
    value: total,
    previousPeriod: compareValues(total, revenueValue(previousRecords)),
    dailyAverage: daily.length ? total / daily.length : null,
    bestDay: extreme(daily.map((row) => ({ key: row.date, value: row.revenue }))),
    topContributor: extreme(products),
    series: daily
  };
}

function computeOrders(records, previousRecords) {
  const total = orderCount(records);
  if (total === null) return { available: false, reason: "Orders unavailable — map order_id." };
  const orders = new Map();
  records.forEach((record) => {
    if (record.order_id && !orders.has(record.order_id)) orders.set(record.order_id, record.status);
  });
  const statuses = { completed: 0, pending: 0, cancelled: 0 };
  orders.forEach((status) => {
    if (statuses[status] !== undefined) statuses[status] += 1;
  });
  const days = new Set(records.map((record) => record.order_date).filter(Boolean)).size;
  return {
    available: true,
    value: total,
    ...statuses,
    dailyAverage: days ? total / days : null,
    previousPeriod: compareValues(total, orderCount(previousRecords))
  };
}

function computeUnits(records, previousRecords) {
  const total = unitsValue(records);
  if (total === null) return { available: false, reason: "Units unavailable — map quantity." };
  const byProduct = groupSum(records, "product_key", "quantity");
  const orders = orderCount(records);
  return {
    available: true,
    value: total,
    perOrder: orders ? total / orders : null,
    bestProduct: extreme(byProduct),
    weakestProduct: extreme(byProduct, "min"),
    previousPeriod: compareValues(total, unitsValue(previousRecords))
  };
}

function computeAov(records, previousRecords) {
  const revenue = revenueValue(records);
  const orders = orderCount(records);
  if (revenue === null || !orders) return { available: false, reason: "Average order value requires revenue and order_id." };
  const byOrder = groupSum(records, "order_id", "revenue");
  const value = revenue / orders;
  const previousRevenue = revenueValue(previousRecords);
  const previousOrders = orderCount(previousRecords);
  return {
    available: true,
    value,
    highestValueOrder: extreme(byOrder),
    previousPeriod: compareValues(value, previousRevenue !== null && previousOrders ? previousRevenue / previousOrders : null)
  };
}

function profitValue(records) {
  const values = availableNumbers(records, "profit");
  return values.length ? sum(values) : null;
}

function computeProfit(records, previousRecords) {
  const profitRows = records.filter((record) => number(record.profit) !== null);
  if (!profitRows.length) return { available: false, reason: "Gross profit unavailable — map cost_price." };
  const profit = sum(availableNumbers(profitRows, "profit"));
  const knownRevenue = sum(availableNumbers(profitRows, "revenue"));
  const totalCost = sum(profitRows.map((record) => {
    const cost = number(record.cost_price);
    const quantity = number(record.quantity);
    return cost !== null && quantity !== null ? cost * quantity : 0;
  }));
  const previousProfit = profitValue(previousRecords);
  const previousRevenue = previousRecords.filter((record) => number(record.profit) !== null);
  const previousKnownRevenue = sum(availableNumbers(previousRevenue, "revenue"));
  const previousMargin = previousProfit !== null && previousKnownRevenue ? previousProfit / previousKnownRevenue : null;
  const margin = knownRevenue ? profit / knownRevenue : null;
  const byProduct = groupSum(profitRows, "product_key", "profit");
  return {
    available: true,
    value: profit,
    totalCost,
    margin,
    marginPreviousPeriod: compareValues(margin, previousMargin),
    coverage: records.length ? profitRows.length / records.length : 0,
    topProfitProduct: extreme(byProduct),
    previousPeriod: compareValues(profit, previousProfit)
  };
}

function computeCustomers(records, previousRecords) {
  const customers = new Set(records.map((record) => record.customer_key).filter(Boolean));
  if (!customers.size) return { available: false, reason: "Customer analytics unavailable — map a customer identifier." };
  const previousCustomers = new Set(previousRecords.map((record) => record.customer_key).filter(Boolean));
  let returning = 0;
  customers.forEach((key) => { if (previousCustomers.has(key)) returning += 1; });
  const revenue = revenueValue(records);
  const orders = orderCount(records);
  return {
    available: true,
    value: customers.size,
    new: customers.size - returning,
    returning,
    averageSpend: revenue === null ? null : revenue / customers.size,
    ordersPerCustomer: orders === null ? null : orders / customers.size
  };
}

function computeKpis({ sales = [], stock = [], previousSales = [] }) {
  return {
    revenue: computeRevenue(sales, previousSales),
    orders: computeOrders(sales, previousSales),
    units: computeUnits(sales, previousSales),
    averageOrderValue: computeAov(sales, previousSales),
    grossProfit: computeProfit(sales, previousSales),
    customers: computeCustomers(sales, previousSales),
    inventory: computeInventoryKpi(stock)
  };
}

module.exports = {
  computeKpis,
  computeRevenue,
  computeOrders,
  computeUnits,
  computeAov,
  computeProfit,
  computeCustomers,
  dailyRevenue,
  groupSum
};
