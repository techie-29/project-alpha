import { describe, expect, it } from "vitest";
import periodModule from "../../engine/analytics/periods.js";
import productModule from "../../engine/analytics/products.js";
import customerModule from "../../engine/analytics/customers.js";
import anomalyModule from "../../engine/analytics/anomalies.js";
import forecastModule from "../../engine/forecast/forecastDaily.js";

const { normalizePeriod, previousPeriod, filterByPeriod } = periodModule;
const { classifyProductsAbc } = productModule;
const { segmentCustomersRfm } = customerModule;
const { detectRevenueAnomalies } = anomalyModule;
const { forecastDaily, backtest, forecastWithBacktest } = forecastModule;

function series(length, valueForDay = (index) => 100 + index * 2) {
  return Array.from({ length }, (_, index) => {
    const date = new Date("2026-01-01T00:00:00Z");
    date.setUTCDate(date.getUTCDate() + index);
    return { date: date.toISOString().slice(0, 10), value: valueForDay(index) };
  });
}

describe("analytics periods", () => {
  it("builds current and exactly adjacent previous periods", () => {
    const current = normalizePeriod({ preset: "custom", from: "2026-09-01", to: "2026-09-30" });
    expect(previousPeriod(current)).toEqual({ from: "2026-08-02", to: "2026-08-31" });
    expect(filterByPeriod([{ order_date: "2026-09-01" }, { order_date: "2026-10-01" }], current)).toHaveLength(1);
  });
});

describe("product ABC classification", () => {
  it("classifies products by the revenue share before each item", () => {
    const products = classifyProductsAbc([
      { product_key: "a", revenue: 80 },
      { product_key: "b", revenue: 15 },
      { product_key: "c", revenue: 5 }
    ]);
    expect(products.map((item) => item.abcClass)).toEqual(["A", "B", "C"]);
    expect(products.at(-1).cumulativeShare).toBe(1);
  });
});

describe("customer RFM", () => {
  it("scores customers and assigns deterministic segments", () => {
    const records = [
      { customer_key: "champion", order_id: "1", order_date: "2026-09-30", revenue: 500 },
      { customer_key: "champion", order_id: "2", order_date: "2026-09-29", revenue: 500 },
      { customer_key: "champion", order_id: "3", order_date: "2026-09-28", revenue: 500 },
      { customer_key: "lost", order_id: "4", order_date: "2026-01-01", revenue: 5 },
      { customer_key: "risk", order_id: "5", order_date: "2026-02-01", revenue: 400 },
      { customer_key: "risk", order_id: "6", order_date: "2026-02-02", revenue: 400 },
      { customer_key: "middle", order_id: "7", order_date: "2026-08-01", revenue: 100 }
    ];
    const result = segmentCustomersRfm(records, { asOf: "2026-09-30" });
    expect(result.available).toBe(true);
    expect(result.customers.find((row) => row.customerKey === "champion").segment).toBe("Champions");
    expect(result.customers.find((row) => row.customerKey === "lost").segment).toBe("Lost");
    expect(result.customers.find((row) => row.customerKey === "risk").segment).toBe("At risk");
  });

  it("returns an unavailable state when customer/date evidence is missing", () => {
    expect(segmentCustomersRfm([{ revenue: 20 }]).available).toBe(false);
  });
});

describe("revenue anomaly detection", () => {
  it("guards short series and flags extreme days with evidence", () => {
    expect(detectRevenueAnomalies(series(13)).available).toBe(false);
    const result = detectRevenueAnomalies(series(30, (index) => index === 29 ? 1000 : 100));
    expect(result.anomalies).toHaveLength(1);
    expect(result.anomalies[0]).toMatchObject({ direction: "above", date: "2026-01-30" });
  });
});

describe("statistical forecast", () => {
  it("guards short and non-contiguous series", () => {
    expect(forecastDaily(series(20)).ok).toBe(false);
    const gapped = series(30);
    gapped[15].date = "2026-03-01";
    expect(forecastDaily(gapped).reason).toMatch(/contiguous/);
  });

  it("forecasts a linear series and reports a high-confidence backtest", () => {
    const data = series(60);
    const forecast = forecastWithBacktest(data, 14);
    expect(forecast.ok).toBe(true);
    expect(forecast.points).toHaveLength(14);
    expect(forecast.backtest).toMatchObject({ ok: true, confidence: "high" });
    expect(forecast.backtest.smape).toBeLessThan(0.02);
    expect(backtest(series(40)).ok).toBe(false);
  });
});
