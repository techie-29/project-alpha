const defaultRepository = require("../../services/analyticsPersistenceService");
const { buildAnalytics } = require("../engine/analytics/buildAnalytics");
const { normalizePeriod, previousPeriod, isoDate, filterByPeriod } = require("../engine/analytics/periods");
const { matchesFilters } = require("../engine/analytics/buildAnalytics");
const { latestStockSnapshots } = require("../engine/analytics/inventory");

const ALLOWED_PRESETS = new Set(["daily", "weekly", "monthly", "quarterly", "custom"]);

function normalizeFilters(query = {}) {
  const preset = query.preset || (query.from || query.to ? "custom" : "monthly");
  if (!ALLOWED_PRESETS.has(preset)) {
    const error = new Error("Period preset must be daily, weekly, monthly, quarterly or custom");
    error.status = 400;
    error.code = "INVALID_PERIOD_PRESET";
    throw error;
  }
  let datasetId = null;
  if (query.datasetId !== undefined && query.datasetId !== "") {
    datasetId = Number(query.datasetId);
    if (!Number.isInteger(datasetId) || datasetId <= 0) {
      const error = new Error("datasetId must be a positive integer");
      error.status = 400;
      error.code = "INVALID_DATASET";
      throw error;
    }
  }
  return {
    preset,
    from: query.from,
    to: query.to,
    datasetId,
    product: query.product || null,
    category: query.category || null,
    customer: query.customer || null,
    status: query.status || null
  };
}

function createAnalyticsService({ repository = defaultRepository } = {}) {
  async function loadRequest({ businessAccountId, query = {} }) {
    const filters = normalizeFilters(query);
    const data = await repository.loadAnalyticsData({ businessAccountId });
    const latestDataDate = data.sales.map((row) => isoDate(row.order_date)).filter(Boolean).sort().at(-1) || new Date();
    const period = normalizePeriod({
      preset: filters.preset,
      from: filters.from,
      to: filters.to,
      anchor: latestDataDate
    });
    return { filters, data, period, previous: previousPeriod(period) };
  }

  async function getAnalytics(request) {
    const { filters, data, period, previous } = await loadRequest(request);
    return buildAnalytics({
      ...data,
      period,
      previous,
      filters: {
        datasetId: filters.datasetId,
        product: filters.product,
        category: filters.category,
        customer: filters.customer,
        status: filters.status
      }
    });
  }

  function parseJson(value, fallback) {
    if (value === null || value === undefined) return fallback;
    if (typeof value !== "string") return value;
    try { return JSON.parse(value); } catch { return fallback; }
  }

  function traceRow(row, metric, valueField) {
    return {
      id: `${row.ingestion_id}:${row.source_row_number}`,
      metric,
      value: Number(row[valueField]),
      ingestionId: row.ingestion_id,
      sourceRowNumber: row.source_row_number,
      sourceFile: row.source_file_name,
      normalized: metric === "stock" ? {
        productKey: row.product_key, productName: row.product_name, stockQty: Number(row.stock_qty),
        reorderLevel: row.reorder_level === null ? null : Number(row.reorder_level), stockAsOfDate: row.stock_as_of_date
      } : {
        orderId: row.order_id, orderDate: row.order_date, productKey: row.product_key,
        productName: row.product_name, quantity: row.quantity === null ? null : Number(row.quantity),
        revenue: row.revenue === null ? null : Number(row.revenue), customerKey: row.customer_key
      },
      repairedFields: parseJson(row.repaired_fields, []),
      computedFields: parseJson(row.computed_fields, []),
      mapping: parseJson(row.source_mapping, []),
      rawValues: parseJson(row.raw_values, {})
    };
  }

  async function getTraceability(request) {
    const metric = request.metric;
    if (!["revenue", "units", "stock"].includes(metric)) {
      const error = new Error("Traceability is available for revenue, units and stock");
      error.status = 400;
      error.code = "UNSUPPORTED_TRACE_METRIC";
      throw error;
    }
    const { filters, data, period } = await loadRequest(request);
    let records;
    if (metric === "stock") {
      const filtered = data.stock.filter((row) => (!filters.datasetId || Number(row.ingestion_id) === filters.datasetId) && (!filters.product || row.product_key === filters.product));
      records = latestStockSnapshots(filtered).map((row) => traceRow(row, metric, "stock_qty"));
    } else {
      const valueField = metric === "revenue" ? "revenue" : "quantity";
      records = filterByPeriod(data.sales.filter((row) => matchesFilters(row, filters)), period)
        .filter((row) => row[valueField] !== null && row[valueField] !== undefined)
        .map((row) => traceRow(row, metric, valueField));
    }
    return {
      metric,
      period,
      recordCount: records.length,
      total: records.reduce((sum, record) => sum + record.value, 0),
      records
    };
  }

  return { getAnalytics, getTraceability };
}

const service = createAnalyticsService();
module.exports = { createAnalyticsService, normalizeFilters, getAnalytics: service.getAnalytics, getTraceability: service.getTraceability };
