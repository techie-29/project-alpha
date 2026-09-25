const { addDays, daysBetween, isoDate } = require("../analytics/periods");

const average = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;
const dayOfWeek = (date) => new Date(`${date}T00:00:00Z`).getUTCDay();

function linearRegression(values) {
  const centerX = (values.length - 1) / 2;
  const centerY = average(values);
  let numerator = 0;
  let denominator = 0;
  values.forEach((value, index) => {
    numerator += (index - centerX) * (value - centerY);
    denominator += (index - centerX) ** 2;
  });
  const slope = denominator ? numerator / denominator : 0;
  return { slope, intercept: centerY - slope * centerX };
}

function normalizedSeries(series) {
  return [...series]
    .map((point) => ({ date: isoDate(point.date), value: Number(point.value ?? point.revenue) }))
    .filter((point) => point.date && Number.isFinite(point.value))
    .sort((a, b) => a.date.localeCompare(b.date));
}

function contiguous(series) {
  return series.every((point, index) => index === 0 || daysBetween(series[index - 1].date, point.date) === 1);
}

function forecastDaily(input, horizon = 14) {
  const series = normalizedSeries(input);
  if (series.length < 30) return { ok: false, reason: "Need at least 30 days of sales data" };
  if (!contiguous(series)) return { ok: false, reason: "Forecast requires contiguous daily sales data" };

  const values = series.map((point) => point.value);
  const mean = average(values);
  const sums = Array(7).fill(0);
  const counts = Array(7).fill(0);
  series.forEach((point) => {
    sums[dayOfWeek(point.date)] += point.value;
    counts[dayOfWeek(point.date)] += 1;
  });
  const weekdayIndexes = sums.map((sum, index) => counts[index] && mean ? sum / counts[index] / mean : 1).map((value) => value || 1);
  const deseasonalized = series.map((point) => point.value / weekdayIndexes[dayOfWeek(point.date)]);
  const { slope, intercept } = linearRegression(deseasonalized);
  const residuals = deseasonalized.map((value, index) => value - (intercept + slope * index));
  const residualStandardDeviation = Math.sqrt(average(residuals.map((value) => value ** 2)));
  const lastDate = series.at(-1).date;
  const points = Array.from({ length: horizon }, (_, offset) => {
    const date = addDays(lastDate, offset + 1);
    const base = intercept + slope * (series.length + offset);
    const weekdayIndex = weekdayIndexes[dayOfWeek(date)];
    return {
      date,
      value: Math.max(0, base * weekdayIndex),
      lower: Math.max(0, (base - 1.28 * residualStandardDeviation) * weekdayIndex),
      upper: Math.max(0, (base + 1.28 * residualStandardDeviation) * weekdayIndex)
    };
  });
  return {
    ok: true,
    label: "Statistical forecast",
    method: "linear trend + weekday index",
    points,
    dataDays: series.length,
    residualStandardDeviation
  };
}

function backtest(input, holdout = 14) {
  const series = normalizedSeries(input);
  if (series.length < 30 + holdout) return { ok: false, reason: "Not enough data to backtest" };
  const actual = series.slice(-holdout);
  const forecast = forecastDaily(series.slice(0, -holdout), holdout);
  if (!forecast.ok) return forecast;
  const errors = actual.map((point, index) => {
    const predicted = forecast.points[index].value;
    const denominator = (Math.abs(point.value) + Math.abs(predicted)) / 2;
    return denominator === 0 ? null : Math.abs(point.value - predicted) / denominator;
  }).filter((value) => value !== null);
  const smape = errors.length ? average(errors) : 0;
  return {
    ok: true,
    holdoutDays: holdout,
    smape,
    confidence: smape < 0.15 ? "high" : smape < 0.3 ? "medium" : "low"
  };
}

function forecastWithBacktest(series, horizon = 14, holdout = 14) {
  const forecast = forecastDaily(series, horizon);
  if (!forecast.ok) return { ...forecast, backtest: { ok: false, reason: forecast.reason } };
  return { ...forecast, backtest: backtest(series, holdout) };
}

module.exports = { forecastDaily, backtest, forecastWithBacktest, normalizedSeries, contiguous };
