const { CANONICAL_FIELDS, HEADER_ALIASES, normalizeHeader } = require("./canonicalFields");
const { similarity } = require("./similarity");

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function looksLikeEmailColumn(values) {
  const present = values
    .filter((value) => value !== null && value !== undefined && String(value).trim() !== "")
    .map((value) => String(value).trim());

  if (present.length === 0) return false;
  return present.every((value) => EMAIL_PATTERN.test(value));
}

function exactSuggestion(header) {
  const normalized = normalizeHeader(header);

  for (const field of CANONICAL_FIELDS) {
    if (normalized === normalizeHeader(field)) {
      return { field, confidence: 1, reason: "canonical_name" };
    }

    const aliases = HEADER_ALIASES[field] || [];
    if (aliases.some((alias) => normalized === normalizeHeader(alias))) {
      return { field, confidence: 1, reason: "alias" };
    }
  }

  return null;
}

function fuzzySuggestion(header, minimum = 0.85) {
  const normalized = normalizeHeader(header);
  let best = null;

  for (const field of CANONICAL_FIELDS) {
    const candidates = [field, ...(HEADER_ALIASES[field] || [])];
    for (const candidate of candidates) {
      const score = similarity(normalized, normalizeHeader(candidate));
      if (!best || score > best.confidence) {
        best = { field, confidence: score, reason: "fuzzy" };
      }
    }
  }

  return best && best.confidence >= minimum ? best : null;
}

function suggestHeaderMapping(header, values = []) {
  const exact = exactSuggestion(header);
  if (exact) return exact;

  const fuzzy = fuzzySuggestion(header);
  if (fuzzy) return fuzzy;

  if (looksLikeEmailColumn(values)) {
    return { field: "customer_email", confidence: 0.8, reason: "value_sniff_email" };
  }

  return { field: null, confidence: 0, reason: "unmapped" };
}

function suggestMappings(headers, rows = []) {
  return headers.map((header) => ({
    originalHeader: header,
    ...suggestHeaderMapping(header, rows.map((row) => row?.[header]))
  }));
}

module.exports = {
  looksLikeEmailColumn,
  exactSuggestion,
  fuzzySuggestion,
  suggestHeaderMapping,
  suggestMappings
};
