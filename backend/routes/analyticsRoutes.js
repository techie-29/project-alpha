const express = require("express");
const { getAnalytics: defaultGetAnalytics } = require("../src/services/analyticsService");

function createAnalyticsRouter({ getAnalytics = defaultGetAnalytics } = {}) {
  const router = express.Router();

  async function analytics(req) {
    return getAnalytics({ businessAccountId: req.user.id, query: req.query });
  }

  router.get("/overview", async (req, res, next) => {
    try { return res.json({ success: true, data: await analytics(req) }); } catch (error) { next(error); }
  });
  router.get("/sales", async (req, res, next) => {
    try {
      const data = await analytics(req);
      return res.json({ success: true, data: { period: data.period, previousPeriod: data.previousPeriod, filters: data.filters, kpis: data.kpis, charts: data.charts, anomalies: data.intelligence.anomalies, forecast: data.intelligence.forecast } });
    } catch (error) { next(error); }
  });
  router.get("/products", async (req, res, next) => {
    try {
      const data = await analytics(req);
      return res.json({ success: true, data: { period: data.period, products: data.products } });
    } catch (error) { next(error); }
  });
  router.get("/inventory", async (req, res, next) => {
    try {
      const data = await analytics(req);
      return res.json({ success: true, data: { period: data.period, kpi: data.kpis.inventory, inventory: data.inventory } });
    } catch (error) { next(error); }
  });
  router.get("/customers", async (req, res, next) => {
    try {
      const data = await analytics(req);
      return res.json({ success: true, data: { period: data.period, kpi: data.kpis.customers, customers: data.customers } });
    } catch (error) { next(error); }
  });
  router.get("/insights", async (req, res, next) => {
    try {
      const data = await analytics(req);
      return res.json({ success: true, data: { period: data.period, ...data.intelligence } });
    } catch (error) { next(error); }
  });
  return router;
}

module.exports = createAnalyticsRouter();
module.exports.createAnalyticsRouter = createAnalyticsRouter;
