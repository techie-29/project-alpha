import { describe, expect, it } from "vitest";
import qualityModule from "../../engine/quality/qualityScore.js";

const { calculateQualityScore } = qualityModule;

describe("dataset quality score", () => {
  it("uses the documented weighted formula and exposes its breakdown", () => {
    const result = calculateQualityScore({
      validationSuccessRate: 0.98,
      mappingCoverage: 0.86,
      duplicateRate: 0.02,
      criticalFieldCompleteness: 0.9
    });
    expect(result.score).toBe(93.6);
    expect(result.breakdown.mappingCoverage).toBe(0.86);
  });

  it("clamps invalid rates instead of producing impossible scores", () => {
    const result = calculateQualityScore({
      validationSuccessRate: 2,
      mappingCoverage: -1,
      duplicateRate: 0,
      criticalFieldCompleteness: 1
    });
    expect(result.score).toBe(70);
  });
});
