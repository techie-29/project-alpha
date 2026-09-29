const config = require("../config");
const { insight } = require("../helpers");

module.exports = function productConcentration(context) {
  const product = (context.products || []).find((item) => item.revenueShare >= config.productConcentrationShare);
  if (!product) return [];
  return [insight("product_concentration", context, {
    type: "alert", category: "products", severity: "medium", title: `${product.productName} represents ${(product.revenueShare * 100).toFixed(1)}% of revenue`,
    explanation: "Revenue is concentrated in one product, increasing dependency risk.",
    evidence: { metric: "product_revenue_share", value: product.revenueShare, revenue: product.revenue },
    entity: { kind: "product", key: product.productKey, name: product.productName }, action: "Review product diversification and demand risk.",
    link: `/analytics/products?product=${encodeURIComponent(product.productKey)}`
  })];
};
