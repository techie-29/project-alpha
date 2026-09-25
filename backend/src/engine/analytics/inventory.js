function snapshotTime(snapshot) {
  const date = snapshot.stock_as_of_date;
  if (!date) return Number.NEGATIVE_INFINITY;
  const time = Date.parse(`${String(date).slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(time) ? Number.NEGATIVE_INFINITY : time;
}

function latestStockSnapshots(snapshots) {
  const latest = new Map();
  snapshots.forEach((snapshot) => {
    if (!snapshot.product_key || snapshot.stock_qty === null || snapshot.stock_qty === undefined) return;
    const current = latest.get(snapshot.product_key);
    const isNewer = !current || snapshotTime(snapshot) > snapshotTime(current) ||
      (snapshotTime(snapshot) === snapshotTime(current) &&
        Number(snapshot.source_row_number || 0) > Number(current.source_row_number || 0));
    if (isNewer) latest.set(snapshot.product_key, snapshot);
  });
  return [...latest.values()];
}

function daysOfCover({ stock, unitsSoldInWindow, windowDays = 30 }) {
  if (stock === null || stock === undefined || !windowDays) return null;
  if (unitsSoldInWindow <= 0) return null;
  return stock / (unitsSoldInWindow / windowDays);
}

function computeInventoryKpi(snapshots) {
  const latest = latestStockSnapshots(snapshots);
  if (!latest.length) {
    return { available: false, reason: "Inventory unavailable — map stock_qty." };
  }
  const totalUnits = latest.reduce((sum, row) => sum + Number(row.stock_qty || 0), 0);
  const inventoryValueRows = latest.filter((row) => row.unit_price !== null && row.unit_price !== undefined);
  const value = inventoryValueRows.reduce(
    (sum, row) => sum + Number(row.stock_qty || 0) * Number(row.unit_price || 0),
    0
  );
  const counts = latest.reduce((summary, row) => {
    const status = row.stock_status || (
      Number(row.stock_qty) <= 0 ? "out_of_stock" :
        row.reorder_level !== null && row.reorder_level !== undefined && Number(row.stock_qty) <= Number(row.reorder_level)
          ? "low_stock" : "healthy"
    );
    summary[status] = (summary[status] || 0) + 1;
    return summary;
  }, {});
  return {
    available: true,
    products: latest.length,
    totalUnits,
    value: inventoryValueRows.length ? value : null,
    valueCoverage: latest.length ? inventoryValueRows.length / latest.length : 0,
    healthy: counts.healthy || 0,
    lowStock: counts.low_stock || 0,
    outOfStock: counts.out_of_stock || 0,
    snapshots: latest
  };
}

module.exports = { latestStockSnapshots, daysOfCover, computeInventoryKpi };
