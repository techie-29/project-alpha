"""Business concepts a column can carry. A concept says what a column MEANS for the business
(revenue, stock on hand, customer, delivery days...), not just its data type.

Each concept lists: the data kind it needs, how it is aggregated, whether it is money, whether a rise is good,
name synonyms (used only as one piece of fuzzy evidence) and a value check (evidence from the values themselves)."""
from __future__ import annotations
from dataclasses import dataclass, field
import re

# kinds: number | key | group | date
# agg:   sum (a flow: add up over time) | mean (average) | level (a stock level: take the latest per item, never add over time) | None


@dataclass(frozen=True)
class Concept:
    id: str
    label: str
    kind: str
    agg: str | None = None
    money: bool = False
    polarity: int = 0          # +1 rise is good, -1 rise is bad, 0 neutral
    synonyms: tuple = ()
    area: str = "general"      # sales | customers | products | stock | costs | operations | service | people | general
    entity: str | None = None  # for keys: which entity they identify


def _c(*a, **k):
    return Concept(*a, **k)


CONCEPTS: dict[str, Concept] = {c.id: c for c in [
    # ---- money flows ----
    _c("revenue", "Revenue", "number", "sum", True, +1, ("sales", "revenue", "net sales", "net revenue", "turnover", "amount", "total amount", "sale amount", "sales amount",
       "order value", "order total", "gmv", "income", "billing", "invoice amount", "bill amount", "receipts", "total", "line total", "net amount", "ventas", "umsatz", "ingresos", "chiffre affaires", "bikri", "fee", "fees", "consultation fee", "charges", "billing amount", "amount paid", "paid amount", "takings"), "sales"),
    _c("gross_revenue", "Gross sales", "number", "sum", True, +1, ("gross sales", "gross revenue", "gross amount", "subtotal", "sub total", "mrp total", "list amount"), "sales"),
    _c("cost", "Cost of goods", "number", "sum", True, -1, ("cost", "cogs", "product cost", "cost of goods", "cost of sales", "purchase cost", "landed cost", "total cost", "item cost", "kosten", "costo", "cout"), "costs"),
    _c("expense", "Expense", "number", "sum", True, -1, ("expense", "expenses", "spend", "shipping cost", "freight", "delivery charge", "commission", "overhead", "rent", "salary", "wages",
       "marketing spend", "ad spend", "utilities", "payroll", "opex", "expense amount", "cost amount", "fees paid", "bank charges"), "costs"),
    _c("profit", "Profit", "number", "sum", True, +1, ("profit", "gross profit", "net profit", "earnings", "margin amount", "gain", "contribution", "ganancia", "gewinn", "benefice", "munafa"), "sales"),
    _c("discount", "Discount", "number", "sum", True, -1, ("discount", "discount amount", "rebate", "markdown", "promo amount", "coupon amount", "descuento", "rabatt", "remise"), "sales"),
    _c("tax", "Tax", "number", "sum", True, 0, ("tax", "tax amount", "vat", "gst", "sales tax", "iva", "mwst", "tva", "cess"), "sales"),
    _c("unit_price", "Unit price", "number", "mean", True, 0, ("price", "unit price", "selling price", "sale price", "mrp", "rate", "list price", "price per unit", "precio", "preis", "prix", "unit rate"), "products"),
    _c("unit_cost", "Unit cost", "number", "mean", True, 0, ("unit cost", "cost price", "purchase price", "buy price", "cost per unit", "standard cost"), "products"),
    _c("money_other", "Other amount", "number", "sum", True, 0, ("value", "balance", "payment", "paid", "charge", "credit", "debit", "lifetime value", "clv", "ltv"), "general"),
    # ---- quantities, levels ----
    _c("quantity", "Units", "number", "sum", False, +1, ("qty", "quantity", "units", "units sold", "pieces", "pcs", "volume", "items", "cantidad", "menge", "quantite", "nos", "sold qty"), "sales"),
    _c("stock_level", "Stock on hand", "number", "level", False, 0, ("stock", "on hand", "qty on hand", "quantity on hand", "inventory", "stock level", "closing stock", "available", "in stock",
       "available qty", "balance qty", "current stock", "soh", "stock qty", "qty oh", "qoh", "existencias", "bestand", "lager", "inventory level"), "stock"),
    _c("reorder_level", "Reorder level", "number", "level", False, 0, ("reorder level", "reorder point", "min stock", "minimum stock", "safety stock", "par level", "rop"), "stock"),
    _c("margin_pct", "Margin %", "number", "mean", False, +1, ("margin", "margin pct", "margin percentage", "profit margin", "markup", "gross margin", "margin percent"), "sales"),
    _c("rating", "Rating", "number", "mean", False, +1, ("rating", "stars", "review score", "satisfaction", "csat", "score", "customer rating", "feedback score"), "service"),
    _c("duration", "Time taken", "number", "mean", False, -1, ("delivery days", "lead time", "days to ship", "handling time", "duration", "resolution time", "wait time", "tat", "turnaround",
       "time taken", "processing time", "days", "hours", "delay", "transit time", "wait", "waiting time", "wait time", "minutes", "mins", "handle time", "call duration", "service time"), "operations"),
    _c("promised_duration", "Promised time", "number", "mean", False, 0, ("estimated delivery", "estimated delivery days", "expected days", "sla", "promised days", "target days", "eta days", "planned days"), "operations"),
    _c("age", "Age", "number", "mean", False, 0, ("age", "customer age", "years old"), "customers"),
    _c("points", "Points", "number", "sum", False, 0, ("points", "loyalty points", "reward points", "points earned", "points redeemed"), "customers"),
    _c("activity_count", "Activity count", "number", "sum", False, +1, ("visits", "sessions", "clicks", "views", "calls", "tickets", "impressions", "leads", "signups", "admissions",
       "appointments", "footfall", "orders count", "transactions", "bookings", "order count"), "general"),
    _c("discount_pct", "Discount %", "number", "mean", False, -1, ("discount percentage", "discount pct", "discount rate", "discount percent", "disc pct"), "sales"),
    _c("percent", "Percentage", "number", "mean", False, 0, ("percent", "pct", "ratio", "share", "percentage", "rate pct"), "general"),
    _c("number", "Number", "number", "mean", False, 0, (), "general"),
    # ---- keys (identify an entity) ----
    _c("order_id", "Order / transaction", "key", synonyms=("order id", "order no", "order number", "invoice no", "invoice id", "invoice number", "transaction id", "bill no", "receipt no", "booking id", "txn id", "sale id", "ticket id", "bestellung", "pedido", "commande", "rechnung", "factura"), area="sales", entity="order"),
    _c("customer_id", "Customer", "key", synonyms=("customer id", "client id", "cust id", "member id", "patient id", "account id", "buyer id", "user id", "customer code", "customer no", "customer", "patient no", "patient", "patient number", "member no", "client no", "account no", "customer number", "subscriber", "guest", "kunde", "kunden", "cliente", "client", "klant", "kundennummer"), area="customers", entity="customer"),
    _c("product_id", "Product", "key", synonyms=("product id", "sku", "item id", "item code", "product code", "article", "part number", "material", "item no", "product", "item", "barcode", "upc", "ean", "artikel", "produkt", "producto", "produit", "articulo"), area="products", entity="product"),
    _c("employee_id", "Employee", "key", synonyms=("employee id", "employee", "staff id", "staff", "agent", "salesperson", "sales rep", "rep", "cashier", "doctor", "technician", "waiter", "server", "stylist", "therapist", "driver", "teller", "attendant", "consultant", "physician", "nurse", "barista", "assigned to", "owner"), area="people", entity="employee"),
    _c("supplier_id", "Supplier", "key", synonyms=("supplier id", "supplier", "vendor id", "vendor", "manufacturer"), area="stock", entity="supplier"),
    _c("entity_id", "Identifier", "key", synonyms=(), area="general", entity="record"),
    _c("site_id", "Store / site", "key", synonyms=("store id", "store", "branch", "outlet", "shop", "warehouse", "location id", "site", "depot", "plant", "clinic", "hub"), area="operations", entity="site"),
    # ---- groups ----
    _c("location", "Location", "group", synonyms=("region", "city", "state", "country", "zone", "area", "territory", "district", "province", "market", "location", "geo", "postal code", "zip", "zip code", "pincode", "pin code"), area="general"),
    _c("channel", "Channel", "group", synonyms=("channel", "source", "medium", "platform", "sales channel", "marketing channel", "order source", "lead source", "utm source"), area="sales"),
    _c("status", "Status / outcome", "group", synonyms=("status", "order status", "outcome", "result", "stage", "delivery status", "payment status", "return status", "state of order"), area="operations"),
    _c("payment_method", "Payment method", "group", synonyms=("payment method", "payment mode", "payment type", "tender", "pay mode"), area="sales"),
    _c("product_group", "Product group", "group", synonyms=("category", "subcategory", "sub category", "department", "dept", "product type", "service type", "speciality", "specialty", "class", "family", "brand", "line", "product category", "collection", "genre"), area="products"),
    _c("segment", "Segment", "group", synonyms=("segment", "tier", "customer type", "membership", "plan", "customer segment", "type", "class of customer", "loyalty tier"), area="customers"),
    _c("campaign", "Campaign / promotion", "group", synonyms=("campaign", "promo", "promotion", "coupon", "coupon code", "offer", "voucher", "campaign name"), area="sales"),
    _c("delivery_method", "Delivery method", "group", synonyms=("shipping method", "delivery method", "shipping mode", "ship mode", "carrier", "courier", "delivery type", "shipping type"), area="operations"),
    _c("sentiment", "Sentiment", "group", synonyms=("sentiment", "review sentiment", "mood", "tone"), area="service"),
    _c("yes_no", "Yes / no", "group", synonyms=("is", "has", "flag", "repeat"), area="general"),
    _c("name_label", "Name", "group", synonyms=("product name", "item name", "campaign name", "store name", "service name", "title", "name", "description", "desc", "item description", "product description", "item"), area="general"),
    _c("gender", "Gender", "group", synonyms=("gender", "sex"), area="customers"),
    _c("currency", "Currency", "group", synonyms=("currency", "currency code", "curr", "ccy"), area="general"),
    _c("reason", "Reason", "group", synonyms=("reason", "return reason", "cancel reason", "cause", "complaint type", "issue type"), area="service"),
    _c("group", "Group", "group", (), area="general"),
    # ---- dates ----
    _c("event_date", "Date", "date", synonyms=("date", "order date", "sale date", "transaction date", "invoice date", "created", "timestamp", "datetime", "day", "datum", "fecha"), area="general"),
    _c("snapshot_date", "Snapshot date", "date", synonyms=("snapshot date", "as of", "as on", "stock date", "count date", "report date"), area="stock"),
    _c("signup_date", "Start date", "date", synonyms=("signup date", "join date", "joined", "registration date", "first purchase", "start date", "created at", "member since"), area="customers"),
    # ---- not for analysis ----
    _c("personal", "Personal detail", "text", synonyms=("customer name", "email", "phone", "mobile", "address", "street", "contact", "full name", "first name", "last name", "client name", "patient name", "employee name"), area="general"),
    _c("free_text", "Free text", "text", synonyms=("review", "comment", "notes", "remarks", "feedback text", "message", "long description"), area="general"),
]}

NUMBER_CONCEPTS = [c for c in CONCEPTS.values() if c.kind == "number"]
KEY_CONCEPTS = [c for c in CONCEPTS.values() if c.kind == "key"]
GROUP_CONCEPTS = [c for c in CONCEPTS.values() if c.kind == "group"]
DATE_CONCEPTS = [c for c in CONCEPTS.values() if c.kind == "date"]

STATUS_WORDS = re.compile(r"complet|deliver|cancel|return|refund|pending|ship|fail|success|paid|unpaid|process|open|closed|resolved|approved|reject|declin|active|inactive|void|attend|no.?show|missed|book|schedul|confirm|churn|expired|won|lost|overdue", re.I)
CHANNEL_WORDS = re.compile(r"online|offline|store|web|app|mobile|marketplace|social|email|direct|retail|wholesale|phone|referral|organic|paid|instore|in-store|ecom|amazon|website|partner", re.I)
PAYMENT_WORDS = re.compile(r"card|cash|upi|wallet|paypal|bank|transfer|cod|credit|debit|net ?banking|emi|cheque|check", re.I)
GENDER_VALUES = {"m", "f", "male", "female", "other", "non-binary", "nonbinary", "unknown", "prefer not to say", "man", "woman", "o", "u"}
CURRENCIES = {"USD", "EUR", "GBP", "INR", "JPY", "CNY", "AUD", "CAD", "CHF", "SGD", "AED", "SAR", "HKD", "NZD", "ZAR", "SEK", "NOK", "DKK", "BRL", "MXN", "RUB", "KRW",
              "THB", "MYR", "IDR", "PHP", "PKR", "BDT", "LKR", "NPR", "EGP", "NGN", "KES", "TRY", "PLN", "CZK", "HUF", "ILS", "QAR", "KWD", "OMR", "BHD", "VND", "TWD", "ARS", "CLP", "COP", "PEN"}
REGION_WORDS = re.compile(r"^(north|south|east|west|central|northeast|northwest|southeast|southwest|mid ?west|apac|emea|latam|na|eu|asia|europe|africa|americas?)\b", re.I)

SENTIMENT_WORDS = re.compile(r"^(very )?(positive|negative|neutral|mixed|happy|unhappy|satisfied|dissatisfied|good|bad)$", re.I)
YES_NO_VALUES = {"yes", "no", "y", "n", "true", "false", "1", "0", "t", "f"}
ID_HEAD = re.compile(r"(^|[_\s\-])(id|code|no|num|number|key|ref|sku|uid|uuid)($|[_\s\-])|[a-z]Id$|^sku$|^upc$|^ean$|barcode", re.I)
PERSON_NAME = re.compile(r"^(name|full_?name|first_?name|last_?name|(customer|client|patient|user|member|contact|employee|owner|buyer|person)[_\s]?name)$", re.I)
ALWAYS_PII = re.compile(r"(e_?mail|phone|mobile|address|street|ssn|aadhaar|passport|dob|birth)", re.I)
ID_VALUE = re.compile(r"^[A-Za-z]{1,8}[-_ /]?\d{2,}$|^\d{4,}$")
