const fs = require("node:fs");
const path = require("node:path");
const XLSX = require("xlsx");

const fixtureDirectory = __dirname;
const products = Array.from({ length: 15 }, (_, index) => ({
  sku: `SKU-${String(index + 1).padStart(3, "0")}`,
  name: [
    "Trail Helmet", "Riding Gloves", "Rain Jacket", "Tank Bag", "Phone Mount",
    "Chain Cleaner", "Knee Guard", "Boot Cover", "Saddle Bag", "Visor Wipe",
    "Bungee Cord", "First Aid Kit", "Tool Roll", "Thermal Liner", "Hydration Pack"
  ][index],
  category: ["Safety", "Apparel", "Luggage", "Accessories"][index % 4]
}));

function csvValue(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function writeCsv(fileName, headers, rows) {
  const lines = [headers, ...rows].map((row) => row.map(csvValue).join(","));
  fs.writeFileSync(path.join(fixtureDirectory, fileName), `${lines.join("\n")}\n`, "utf8");
}

const cleanRows = Array.from({ length: 300 }, (_, index) => {
  const product = products[index % products.length];
  const day = new Date(Date.UTC(2026, 6, 1 + (index % 75))).toISOString().slice(0, 10);
  const quantity = (index % 4) + 1;
  const unitPrice = 250 + (index % products.length) * 75;
  const discount = index % 9 === 0 ? 50 : 0;
  return [
    `ORD-${String(index + 1).padStart(4, "0")}`,
    day,
    product.sku,
    product.name,
    product.category,
    quantity,
    unitPrice,
    discount,
    quantity * unitPrice - discount,
    `CUST-${String((index % 40) + 1).padStart(3, "0")}`,
    ["completed", "completed", "pending", "cancelled"][index % 4]
  ];
});

writeCsv("sales_clean.csv", [
  "Order ID", "Order Date", "SKU", "Item Name", "Category", "Qty Sold",
  "Selling Price", "Discount", "Sales Amount", "Customer ID", "Status"
], cleanRows);

fs.writeFileSync(path.join(fixtureDirectory, "sales_messy.csv"), [
  "\uFEFFOrder ID,Order Date,Item Name,Qty Sold,Selling Price,Client Email,Status,Status",
  "A-1001,2026-09-01,Trail Helmet,2,\"₹1,200.50\",priya@example.com,Complete,paid",
  "A-1002,01/09/2026,Riding Gloves,3,\"1.200,50\",bad-email,Pending,pending",
  "A-1003,Sep 1 26,Rain Jacket,-1,(200),arun@example.com,Cancelled,cancelled",
  "A-1003,Sep 1 26,Rain Jacket,-1,(200),arun@example.com,Cancelled,cancelled",
  "A-1004,31/02/2026,Tank Bag,text,N/A,,Complete,paid",
  "",
  "A-1005,2026-09-05,Phone Mount,1,450,dev@example.com,Complete,paid,unexpected"
].join("\n"), "utf8");

writeCsv("customers.csv", ["Customer ID", "Customer Name", "Client Email", "Region"],
  Array.from({ length: 40 }, (_, index) => [
    `CUST-${String(index + 1).padStart(3, "0")}`,
    `Customer ${index + 1}`,
    `customer${index + 1}@example.com`,
    ["North", "South", "East", "West"][index % 4]
  ]));

const inventoryWorkbook = XLSX.utils.book_new();
const inventorySheet = XLSX.utils.aoa_to_sheet([
  ["Product", null, "Stock", "Reorder", "Supplier"],
  ["SKU", "Name", "Qty", "Level", "Name"],
  ...products.map((product, index) => [
    product.sku,
    product.name,
    index % 5 === 0 ? 0 : index + 3,
    8,
    `Supplier ${(index % 4) + 1}`
  ])
]);
inventorySheet["!merges"] = [
  { s: { r: 0, c: 0 }, e: { r: 0, c: 1 } }
];
XLSX.utils.book_append_sheet(inventoryWorkbook, inventorySheet, "Current Stock");
XLSX.utils.book_append_sheet(
  inventoryWorkbook,
  XLSX.utils.aoa_to_sheet([["This sheet is intentionally ignored"]]),
  "Notes"
);
XLSX.writeFile(inventoryWorkbook, path.join(fixtureDirectory, "inventory.xlsx"));

const supplierWorkbook = XLSX.utils.book_new();
XLSX.utils.book_append_sheet(supplierWorkbook, XLSX.utils.aoa_to_sheet([
  ["Supplier Name", "Region", "Phone"],
  ["Supplier 1", "North", "9000000001"],
  ["Supplier 2", "South", "9000000002"],
  ["Supplier 3", "East", "9000000003"],
  ["Supplier 4", "West", "9000000004"]
]), "Suppliers");
XLSX.writeFile(supplierWorkbook, path.join(fixtureDirectory, "suppliers.xlsx"));

fs.writeFileSync(path.join(fixtureDirectory, "ingestion_expected.json"), JSON.stringify({
  sales_clean: { rows: 300, columns: 11, type: "sales" },
  inventory: { rows: 15, columns: 5, first_sheet: "Current Stock", ignored_sheets: 1 },
  customers: { rows: 40, columns: 4, type: "customers" },
  suppliers: { rows: 4, columns: 3, type: "suppliers" }
}, null, 2) + "\n");
