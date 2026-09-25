const CANONICAL_FIELDS = [
  "product_name",
  "sku",
  "category",
  "unit_price",
  "cost_price",
  "supplier_name",
  "order_id",
  "order_date",
  "quantity",
  "discount",
  "revenue",
  "profit",
  "status",
  "notes",
  "customer_id",
  "customer_name",
  "customer_email",
  "customer_phone",
  "region",
  "stock_qty",
  "reorder_level",
  "stock_as_of_date"
];

const HEADER_ALIASES = {
  product_name: ["product name", "product", "item name", "item"],
  sku: ["sku", "product sku", "stock keeping unit", "stock code"],
  category: ["category", "product category", "item category"],
  unit_price: ["unit price", "price", "selling price", "sale price"],
  cost_price: ["cost price", "cost", "unit cost", "purchase cost"],
  supplier_name: ["supplier name", "supplier", "vendor", "vendor name"],
  order_id: ["order id", "orderid", "transaction id", "sale id"],
  order_date: ["order date", "order dt", "date", "sale date", "sales date"],
  quantity: ["quantity", "qty", "quantity sold", "qty sold", "units", "units sold"],
  discount: ["discount", "discount amount", "discount percentage", "discount percent"],
  revenue: ["revenue", "sales amount", "sale amount", "amount", "total amount"],
  profit: ["profit", "gross profit"],
  status: ["status", "order status", "record status", "payment status", "delivery status"],
  notes: ["notes", "note", "remarks", "comments"],
  customer_id: ["customer id", "customerid", "cust id", "client id"],
  customer_name: ["customer name", "customer", "cust name", "client name"],
  customer_email: ["customer email", "email", "email address", "client email"],
  customer_phone: ["customer phone", "phone", "phone number", "mobile"],
  region: ["region", "customer region", "customer city", "city", "location"],
  stock_qty: ["stock qty", "stock quantity", "stock level", "inventory level", "current stock"],
  reorder_level: ["reorder level", "reorder point", "minimum stock", "minimum inventory"],
  stock_as_of_date: ["stock as of date", "stock date", "inventory date", "snapshot date"]
};

function normalizeHeader(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[_\-]+/g, " ")
    .replace(/[^a-z0-9 ]+/g, "")
    .replace(/\s+/g, " ");
}

module.exports = { CANONICAL_FIELDS, HEADER_ALIASES, normalizeHeader };
