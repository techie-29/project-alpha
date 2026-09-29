function number(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function classifyProductsAbc(records) {
  const products = new Map();
  records.forEach((record) => {
    if (!record.product_key) return;
    const revenue = number(record.revenue);
    if (revenue === null) return;
    const current = products.get(record.product_key) || {
      productKey: record.product_key,
      productName: record.product_name || record.product_key,
      category: record.category || null,
      revenue: 0,
      units: 0,
      profit: 0,
      profitAvailable: false
    };
    current.revenue += revenue;
    current.units += number(record.quantity) || 0;
    const profit = number(record.profit);
    if (profit !== null) {
      current.profit += profit;
      current.profitAvailable = true;
    }
    products.set(record.product_key, current);
  });
  const sorted = [...products.values()].sort((a, b) => b.revenue - a.revenue || a.productKey.localeCompare(b.productKey));
  const totalRevenue = sorted.reduce((total, item) => total + item.revenue, 0);
  let cumulativeRevenue = 0;
  return sorted.map((item) => {
    const shareBefore = totalRevenue ? cumulativeRevenue / totalRevenue : 0;
    cumulativeRevenue += item.revenue;
    const revenueShare = totalRevenue ? item.revenue / totalRevenue : 0;
    return {
      ...item,
      profit: item.profitAvailable ? item.profit : null,
      margin: item.profitAvailable && item.revenue ? item.profit / item.revenue : null,
      revenueShare,
      cumulativeShare: totalRevenue ? cumulativeRevenue / totalRevenue : 0,
      abcClass: shareBefore < 0.8 ? "A" : shareBefore < 0.95 ? "B" : "C"
    };
  });
}

module.exports = { classifyProductsAbc };
