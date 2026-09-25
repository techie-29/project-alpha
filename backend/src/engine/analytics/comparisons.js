function compareValues(current, previous) {
  if (current === null || current === undefined || previous === null || previous === undefined) {
    return { available: false, absolute: null, percentage: null };
  }
  const absolute = current - previous;
  const percentage = previous === 0
    ? (current === 0 ? 0 : null)
    : absolute / Math.abs(previous);
  return {
    available: true,
    current,
    previous,
    absolute,
    percentage: percentage === null ? null : Number(percentage.toFixed(4))
  };
}

module.exports = { compareValues };
