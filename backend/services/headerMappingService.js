// Version 1 canonical Alpha fields
const alphaFieldsV1 = [
  // Product
  "product_id",
  "product_name",
  "product_description",
  "product_code",
  "sku",
  "category",

  // Customer
  "customer_id",
  "customer_name",
  "customer_email",
  "customer_phone",
  "customer_city",

  // Supplier
  "supplier_id",
  "supplier_name",

  // Sales / Orders
  "order_id",
  "order_date",
  "quantity",
  "unit_price",
  "discount",
  "revenue",

  // Inventory
  "inventory_level",
  "reorder_level",
  "stock_status",

  // Common / useful
"cost_price",
"profit",
"payment_status",
"delivery_status",
"status",
"notes"
];


// Aliases that may appear in uploaded datasets
const headerAliasesV1 = {
  product_id: [
    "product id",
    "productid",
    "prod id",
    "prodid",
    "item id"
  ],

  product_name: [
    "product name",
    "product",
    "prod name",
    "item name",
    "item"
  ],

  product_description: [
    "product description",
    "description",
    "product desc",
    "prod desc",
    "item description"
  ],

  product_code: [
    "product code",
    "prod code",
    "item code"
  ],

  sku: [
      "sku",
  "product sku",
  "product_sku",
  "stock keeping unit",
  "stock code"
  ],

  category: [
    "category",
    "product category",
    "item category"
  ],

  customer_id: [
    "customer id",
    "customerid",
    "cust id",
    "custid"
  ],

  customer_name: [
    "customer name",
    "customer",
    "cust name",
    "client name"
  ],

  customer_email: [
    "customer email",
    "email",
    "email address",
    "customer email address"
  ],

  customer_phone: [
    "customer phone",
    "phone",
    "phone number",
    "mobile",
    "customer mobile"
  ],

  customer_city: [
    "customer city",
    "city",
    "customer location"
  ],

  supplier_id: [
    "supplier id",
    "supplierid",
    "vendor id",
    "vendorid"
  ],

  supplier_name: [
    "supplier name",
    "supplier",
    "vendor",
    "vendor name"
  ],

  order_id: [
    "order id",
    "orderid",
    "transaction id",
    "sale id"
  ],

  order_date: [
    "order date",
    "order dt",
    "date",
    "sale date",
    "sales date"
  ],

  quantity: [
    "quantity",
    "qty",
    "quantity sold",
    "qty sold",
    "units",
    "units sold"
  ],

  unit_price: [
    "unit price",
    "price",
    "selling price",
    "sale price"
  ],

  discount: [
     "discount",
  "discount amount",
  "discount percentage",
  "discount percent",
  "discount pct",
  "discount_pct"
  ],

  revenue: [
    "revenue",
    "sales amount",
    "sale amount",
    "amount",
    "total amount",
    "sales revenue"
  ],

  inventory_level: [
    "inventory level",
    "stock level",
    "current stock",
    "stock quantity",
    "inventory quantity"
  ],

  reorder_level: [
    "reorder level",
    "reorder point",
    "minimum stock",
    "minimum inventory"
  ],

  stock_status: [
    "stock status",
    "inventory status",
    "availability status"
  ],

  cost_price: [
    "cost price",
    "cost",
    "unit cost",
    "purchase cost"
  ],

  profit: [
    "profit",
    "gross profit",
    "net profit"
  ],

  status: [
    "status",
    "order status",
    "record status"
  ],
  payment_status: [
  "payment status",
  "payment_status",
  "payment state"
],

delivery_status: [
  "delivery status",
  "delivery_status",
  "shipping status",
  "shipment status"
],

notes: [
  "notes",
  "note",
  "remarks",
  "comments",
  "customer note",
  "customer_note"
]
};


// making different header styles comparable
function normalizeHeader(header) {
  return String(header)
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ");
}


// mapping one uploaded header
function mapHeader(header) {
  const normalizedHeader = normalizeHeader(header);

  for (const alphaField of alphaFieldsV1) {
    // allow the canonical name itself
    if (normalizedHeader === normalizeHeader(alphaField)) {
      return {
        originalHeader: header,
        mappedHeader: alphaField,
        mappingStatus: "mapped"
      };
    }

    const aliases = headerAliasesV1[alphaField] || [];

    if (aliases.includes(normalizedHeader)) {
      return {
        originalHeader: header,
        mappedHeader: alphaField,
        mappingStatus: "mapped"
      };
    }
  }

  return {
    originalHeader: header,
    mappedHeader: null,
    mappingStatus: "unmapped"
  };
}


// mapping every header from one ingestion
function mapHeaders(headers) {
  return headers.map((header) => mapHeader(header));
}


module.exports = {
  alphaFieldsV1,
  normalizeHeader,
  mapHeader,
  mapHeaders
};