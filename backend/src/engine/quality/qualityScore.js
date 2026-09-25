function clampRate(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(1, number));
}

function calculateQualityScore({
  validationSuccessRate,
  mappingCoverage,
  duplicateRate,
  criticalFieldCompleteness
}) {
  const breakdown = {
    validationSuccessRate: clampRate(validationSuccessRate),
    mappingCoverage: clampRate(mappingCoverage),
    duplicateRate: clampRate(duplicateRate),
    criticalFieldCompleteness: clampRate(criticalFieldCompleteness)
  };
  const score = 100 * (
    0.40 * breakdown.validationSuccessRate +
    0.30 * breakdown.mappingCoverage +
    0.20 * (1 - breakdown.duplicateRate) +
    0.10 * breakdown.criticalFieldCompleteness
  );
  return { score: Number(score.toFixed(1)), breakdown };
}

module.exports = { calculateQualityScore, clampRate };
