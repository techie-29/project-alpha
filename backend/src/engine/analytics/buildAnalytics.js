const { computeKpis, dailyRevenue } = require("./kpis");
const { latestStockSnapshots, daysOfCover } = require("./inventory");
const { classifyProductsAbc } = require("./products");
const { segmentCustomersRfm } = require("./customers");
const { detectRevenueAnomalies } = require("./anomalies");
const { addDays, daysBetween, filterByPeriod, isoDate } = require("./periods");
const { forecastWithBacktest } = require("../forecast/forecastDaily");
const { generateInsights } = require("../insights/generateInsights");

function numeric(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function matchesFilters(record, filters = {}) {
  if (filters.datasetId && Number(record.ingestion_id) !== Number(filters.datasetId)) return false;
  if (filters.product && record.product_key !== filters.product) return false;
  if (filters.category && record.category !== filters.category) return false;
  if (filters.customer && record.customer_key !== filters.customer) return false;
  if (filters.status && record.status !== filters.status) return false;
  return true;
}

function denseRevenueSeries(records, from, to) {
  if (!from || !to || from > to) return [];
  const byDate = new Map(dailyRevenue(records).map((point) => [point.date, point.revenue]));
  const length = daysBetween(from, to) + 1;
  return Array.from({ length }, (_, index) => {
    const date = addDays(from, index);
    return { date, value: byDate.get(date) || 0 };
  });
}

function categoryAnalytics(sales) {
  const groups = new Map();
  sales.forEach((row) => {
    const revenue = numeric(row.revenue);
    if (!row.category || revenue === null) return;
    const current = groups.get(row.category) || { name: row.category, revenue: 0, profit: 0, profitAvailable: false };
    current.revenue += revenue;
    const profit = numeric(row.profit);
    if (profit !== null) {
      current.profit += profit;
      current.profitAvailable = true;
    }
    groups.set(row.category, current);
  });
  const total = [...groups.values()].reduce((sum, group) => sum + group.revenue, 0);
  return [...groups.values()].map((group) => ({
    ...group,
    profit: group.profitAvailable ? group.profit : null,
    revenueShare: total ? group.revenue / total : 0
  })).sort((a, b) => b.revenue - a.revenue);
}

function customerConcentration(sales) {
  const customers = new Map();
  sales.forEach((row) => {
    const revenue = numeric(row.revenue);
    if (!row.customer_key || revenue === null) return;
    customers.set(row.customer_key, (customers.get(row.customer_key) || 0) + revenue);
  });
  const revenues = [...customers.values()].sort((a, b) => b - a);
  if (!revenues.length) return null;
  const topCount = Math.max(1, Math.ceil(revenues.length * 0.1));
  const total = revenues.reduce((sum, value) => sum + value, 0);
  return { customerCount: revenues.length, topCustomerCount: topCount, topTenPercentShare: total ? revenues.slice(0, topCount).reduce((sum, value) => sum + value, 0) / total : 0 };
}

function inventoryAnalytics(stock, sales, productRecords, period, windowDays = 30) {
  const prices = new Map();
  [...productRecords, ...sales].forEach((row) => {
    const unitPrice = numeric(row.unit_price);
    if (row.product_key && unitPrice !== null) prices.set(row.product_key, unitPrice);
  });
  const latest = latestStockSnapshots(stock).map((row) => ({ ...row, unit_price: prices.get(row.product_key) ?? null }));
  const windowFrom = addDays(period.to, -(windowDays - 1));
  return latest.map((snapshot) => {
    const productSales = sales.filter((row) => row.product_key === snapshot.product_key && isoDate(row.order_date) <= period.to);
    const recentSales = productSales.filter((row) => isoDate(row.order_date) >= windowFrom);
    const units = recentSales.reduce((sum, row) => sum + (Number(row.quantity) || 0), 0);
    const velocity = units > 0 ? units / windowDays : 0;
    const lastSaleDate = productSales.map((row) => isoDate(row.order_date)).filter(Boolean).sort().at(-1) || null;
    return {
      ...snapshot,
      productKey: snapshot.product_key,
      productName: snapshot.product_name || snapshot.product_key,
      stock: Number(snapshot.stock_qty),
      reorderLevel: snapshot.reorder_level === null || snapshot.reorder_level === undefined ? null : Number(snapshot.reorder_level),
      unitPrice: snapshot.unit_price,
      inventoryValue: snapshot.unit_price === null ? null : Number(snapshot.stock_qty) * snapshot.unit_price,
      unitsSoldInWindow: units,
      velocity,
      windowDays,
      daysOfCover: daysOfCover({ stock: Number(snapshot.stock_qty), unitsSoldInWindow: units, windowDays }),
      lastSaleDate,
      daysSinceLastSale: lastSaleDate ? daysBetween(lastSaleDate, period.to) : null
    };
  }).sort((a, b) => (a.daysOfCover ?? Number.POSITIVE_INFINITY) - (b.daysOfCover ?? Number.POSITIVE_INFINITY));
}

function buildAnalytics({ sales = [], stock = [], products: productRecords = [], datasets = [], period, previous, filters = {} }) {
  const filteredAllSales = sales.filter((row) => matchesFilters(row, filters));
  const currentSales = filterByPeriod(filteredAllSales, period);
  const previousSales = filterByPeriod(filteredAllSales, previous);
  const relevantStock = stock.filter((row) => !filters.datasetId || Number(row.ingestion_id) === Number(filters.datasetId));
  const inventory = inventoryAnalytics(relevantStock, filteredAllSales, productRecords, period);
  const inventoryKpiRows = inventory.map((row) => ({
    ...row,
    product_key: row.productKey,
    stock_qty: row.stock,
    reorder_level: row.reorderLevel,
    unit_price: row.unitPrice
  }));
  const kpis = computeKpis({ sales: currentSales, previousSales, stock: inventoryKpiRows });
  const products = classifyProductsAbc(currentSales);
  const categories = categoryAnalytics(currentSales);
  const rfm = segmentCustomersRfm(filteredAllSales.filter((row) => isoDate(row.order_date) <= period.to), { asOf: period.to });
  const daily = denseRevenueSeries(currentSales, period.from, period.to);
  const anomalies = detectRevenueAnomalies(daily);
  const earliest = filteredAllSales.map((row) => isoDate(row.order_date)).filter(Boolean).sort()[0];
  const forecastSeries = earliest ? denseRevenueSeries(filteredAllSales.filter((row) => isoDate(row.order_date) <= period.to), earliest, period.to) : [];
  const forecast = forecastWithBacktest(forecastSeries);
  const concentration = customerConcentration(currentSales);
  const marginComparison = kpis.grossProfit?.marginPreviousPeriod;
  const context = {
    period, kpis, products, categories, inventory, rfm, anomalies,
    customerConcentration: concentration,
    marginChangePoints: marginComparison?.available ? marginComparison.absolute * 100 : null,
    datasets
  };
  return {
    period,
    previousPeriod: previous,
    filters,
    provenance: datasets,
    kpis,
    charts: { dailyRevenue: daily, categories },
    products,
    inventory,
    customers: { rfm, concentration },
    intelligence: { anomalies, forecast, insights: generateInsights(context) },
    recordCounts: { currentSales: currentSales.length, previousSales: previousSales.length, stockSnapshots: relevantStock.length }
  };
}

module.exports = { buildAnalytics, matchesFilters, denseRevenueSeries, categoryAnalytics, customerConcentration, inventoryAnalytics };
