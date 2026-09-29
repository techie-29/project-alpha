/** Parse messy numeric input. Returns a finite number or null, never NaN. */
function parseNumber(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;

  let text = String(value).trim();
  if (!text || /^(n\/?a|null|none|-)$/i.test(text)) return null;

  const negative = text.startsWith("-") || /^\(.*\)$/.test(text);
  text = text.replace(/[^\d.,]/g, "");
  if (!/\d/.test(text)) return null;

  const lastDot = text.lastIndexOf(".");
  const lastComma = text.lastIndexOf(",");
  let decimalSeparator = null;

  if (lastDot > -1 && lastComma > -1) {
    decimalSeparator = lastDot > lastComma ? "." : ",";
  } else if (lastComma > -1) {
    decimalSeparator = /^\d+,\d{1,2}$/.test(text) ? "," : null;
  } else if (lastDot > -1) {
    decimalSeparator = (text.match(/\./g) || []).length === 1 ? "." : null;
  }

  const cleaned = decimalSeparator
    ? text
      .split(decimalSeparator === "." ? "," : ".").join("")
      .replace(decimalSeparator, ".")
    : text.replace(/[.,]/g, "");
  const number = Number(cleaned);
  if (!Number.isFinite(number)) return null;
  return negative ? -number : number;
}

function normalizeText(value) {
  if (value === null || value === undefined) return null;
  const text = String(value).trim().replace(/\s+/g, " ");
  return text || null;
}

function normalizeStatus(value) {
  const text = normalizeText(value)?.toLowerCase();
  if (!text) return null;
  const aliases = {
    complete: "completed",
    completed: "completed",
    paid: "completed",
    pending: "pending",
    processing: "pending",
    cancelled: "cancelled",
    canceled: "cancelled",
    refunded: "cancelled"
  };
  return aliases[text] || text;
}

function productKey({ sku, product_name: productName }) {
  return normalizeText(sku)?.toLowerCase() || normalizeText(productName)?.toLowerCase() || null;
}

module.exports = { parseNumber, normalizeText, normalizeStatus, productKey };
