const config = require("../config");
const { insight } = require("../helpers");

module.exports = function dataQualityLow(context) {
  return (context.datasets || []).filter((dataset) => dataset.qualityScore !== null && dataset.qualityScore !== undefined && Number(dataset.qualityScore) < config.dataQualityScore).map((dataset) => insight("data_quality_low", context, {
    type: "alert", category: "data_quality", severity: Number(dataset.qualityScore) < 50 ? "high" : "medium",
    title: `${dataset.filename} has a low data-quality score`, explanation: `The dataset scored ${dataset.qualityScore} out of 100.`,
    evidence: { metric: "data_quality_score", value: Number(dataset.qualityScore), ingestion_id: dataset.id },
    entity: { kind: "dataset", key: String(dataset.id), name: dataset.filename }, action: "Review mapping and validation issues.",
    link: `/datasets/${dataset.id}`
  }));
};
