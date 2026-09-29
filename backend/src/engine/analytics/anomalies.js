function detectRevenueAnomalies(series, threshold = 2.5) {
  if (series.length < 14) {
    return { available: false, reason: "Need at least 14 days of sales data for anomaly detection.", anomalies: [] };
  }
  const values = series.map((point) => Number(point.value ?? point.revenue)).filter(Number.isFinite);
  if (values.length < 14) {
    return { available: false, reason: "Need at least 14 valid daily revenue values for anomaly detection.", anomalies: [] };
  }
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
  const standardDeviation = Math.sqrt(variance);
  const expectedRange = {
    lower: Math.max(0, mean - threshold * standardDeviation),
    upper: mean + threshold * standardDeviation
  };
  if (!standardDeviation) return { available: true, mean, standardDeviation, expectedRange, anomalies: [] };
  const anomalies = series.flatMap((point) => {
    const value = Number(point.value ?? point.revenue);
    if (!Number.isFinite(value)) return [];
    const zScore = (value - mean) / standardDeviation;
    if (Math.abs(zScore) < threshold) return [];
    return [{
      date: point.date,
      value,
      zScore,
      direction: zScore > 0 ? "above" : "below",
      explanation: `${point.date} revenue was ${zScore > 0 ? "above" : "below"} the expected range of ${expectedRange.lower.toFixed(2)}–${expectedRange.upper.toFixed(2)}.`
    }];
  });
  return { available: true, mean, standardDeviation, expectedRange, threshold, anomalies };
}

module.exports = { detectRevenueAnomalies };
