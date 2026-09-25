const defaultRepository = require("../../services/analyticsPersistenceService");
const { buildAnalytics } = require("../engine/analytics/buildAnalytics");
const { normalizePeriod, previousPeriod, isoDate } = require("../engine/analytics/periods");

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
  async function getAnalytics({ businessAccountId, query = {} }) {
    const filters = normalizeFilters(query);
    const data = await repository.loadAnalyticsData({ businessAccountId });
    const latestDataDate = data.sales.map((row) => isoDate(row.order_date)).filter(Boolean).sort().at(-1) || new Date();
    const period = normalizePeriod({
      preset: filters.preset,
      from: filters.from,
      to: filters.to,
      anchor: latestDataDate
    });
    return buildAnalytics({
      ...data,
      period,
      previous: previousPeriod(period),
      filters: {
        datasetId: filters.datasetId,
        product: filters.product,
        category: filters.category,
        customer: filters.customer,
        status: filters.status
      }
    });
  }

  return { getAnalytics };
}

const service = createAnalyticsService();
module.exports = { createAnalyticsService, normalizeFilters, getAnalytics: service.getAnalytics };
