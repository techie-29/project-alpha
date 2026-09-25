const severityRank = Object.freeze({ critical: 5, high: 4, medium: 3, low: 2, info: 1 });

function entityKey(entity) {
  return entity?.key || entity?.name || "all";
}

function insight(rule, context, details) {
  const entity = details.entity || null;
  const period = details.period || context.period || null;
  const periodKey = period ? `${period.from || "all"}:${period.to || "all"}` : "all";
  return {
    id: `${rule}:${entityKey(entity)}:${periodKey}`,
    type: details.type,
    category: details.category,
    severity: details.severity,
    period,
    title: details.title,
    explanation: details.explanation,
    evidence: details.evidence || {},
    entity,
    action: details.action || null,
    link: details.link
  };
}

module.exports = { insight, severityRank };
