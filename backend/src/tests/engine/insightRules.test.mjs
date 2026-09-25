import { describe, expect, it } from "vitest";
import lowStock from "../../engine/insights/rules/lowStock.js";
import stockoutRisk from "../../engine/insights/rules/stockoutRisk.js";
import excessStock from "../../engine/insights/rules/excessStock.js";
import slowMoving from "../../engine/insights/rules/slowMoving.js";
import revenueDecline from "../../engine/insights/rules/revenueDecline.js";
import salesAnomaly from "../../engine/insights/rules/salesAnomaly.js";
import categoryConcentration from "../../engine/insights/rules/categoryConcentration.js";
import productConcentration from "../../engine/insights/rules/productConcentration.js";
import customerConcentration from "../../engine/insights/rules/customerConcentration.js";
import marginDrop from "../../engine/insights/rules/marginDrop.js";
import cancelledRateHigh from "../../engine/insights/rules/cancelledRateHigh.js";
import atRiskCustomers from "../../engine/insights/rules/atRiskCustomers.js";
import dataQualityLow from "../../engine/insights/rules/dataQualityLow.js";
import insightModule from "../../engine/insights/generateInsights.js";

const { generateInsights } = insightModule;
const period = { from: "2026-09-01", to: "2026-09-30" };
const inventoryItem = {
  productKey: "helmet", productName: "Trail Helmet", stock: 8, reorderLevel: 12,
  daysOfCover: 6.2, velocity: 1.29, windowDays: 30, daysSinceLastSale: 2
};

const cases = [
  ["low stock", lowStock, { inventory: [inventoryItem] }, 1],
  ["stock-out risk", stockoutRisk, { inventory: [inventoryItem] }, 2],
  ["excess stock", excessStock, { inventory: [{ ...inventoryItem, daysOfCover: 100 }] }, 1],
  ["slow moving", slowMoving, { inventory: [{ ...inventoryItem, daysSinceLastSale: 35 }] }, 1],
  ["revenue decline", revenueDecline, { kpis: { revenue: { previousPeriod: { available: true, current: 80, previous: 100, percentage: -0.2 } } } }, 1],
  ["sales anomaly", salesAnomaly, { anomalies: { expectedRange: { lower: 50, upper: 150 }, anomalies: [{ date: "2026-09-10", value: 300, zScore: 3, explanation: "unusually high" }] } }, 1],
  ["category concentration", categoryConcentration, { categories: [{ name: "Accessories", revenue: 400, revenueShare: 0.4 }] }, 1],
  ["product concentration", productConcentration, { products: [{ productKey: "helmet", productName: "Helmet", revenue: 500, revenueShare: 0.5 }] }, 1],
  ["customer concentration", customerConcentration, { customerConcentration: { topTenPercentShare: 0.65, customerCount: 20 } }, 1],
  ["margin drop", marginDrop, { marginChangePoints: -6, kpis: { grossProfit: { margin: 0.2 } } }, 1],
  ["cancelled rate", cancelledRateHigh, { kpis: { orders: { available: true, value: 10, cancelled: 2 } } }, 1],
  ["at-risk customers", atRiskCustomers, { rfm: { customers: [{ segment: "At risk", monetary: 200 }] } }, 1],
  ["low data quality", dataQualityLow, { datasets: [{ id: 7, filename: "messy.csv", qualityScore: 65 }] }, 1]
];

describe.each(cases)("%s rule", (_name, rule, triggerContext, count) => {
  it("triggers with complete supporting evidence", () => {
    const results = rule({ period, ...triggerContext });
    expect(results).toHaveLength(count);
    results.forEach((result) => {
      expect(result).toMatchObject({ period, severity: expect.any(String), evidence: expect.any(Object), link: expect.any(String) });
      expect(result.id).toContain(":");
    });
  });

  it("does not trigger when its input is missing", () => {
    expect(rule({ period })).toEqual([]);
  });
});

describe("insight registry", () => {
  it("runs every rule and sorts critical outputs first", () => {
    const results = generateInsights({
      period,
      inventory: [{ ...inventoryItem, stock: 0, daysOfCover: 0 }],
      datasets: [{ id: 7, filename: "messy.csv", qualityScore: 65 }]
    });
    expect(results.length).toBeGreaterThan(2);
    expect(results[0].severity).toBe("critical");
  });

  it("does not treat an unavailable quality score as zero", () => {
    expect(dataQualityLow({ period, datasets: [{ id: 8, filename: "pending.csv", qualityScore: null }] })).toEqual([]);
  });
});
