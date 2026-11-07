import Tile from "./viz/Tile";
import Chart from "./viz/Chart";
import { FindingCard } from "./report/Report";

export const AREA_PAGES = {
  sales: { title: "Sales", areas: ["sales", "costs"], intro: "Revenue, orders, prices, discounts and costs: how much came in and what it took." },
  customers: { title: "Customers", areas: ["customers", "service"], intro: "Who buys, how often, how much they spend, and how they rate you." },
  products: { title: "Products", areas: ["products", "stock", "operations"], intro: "What sells, what earns, what sits in stock, and how orders get delivered." },
};

const WIDE = new Set(["line", "stacked", "stacked_count", "table"]);

/** Every overview section, also when unlinked files were summarised as separate parts. */
export function allSections(ov) {
  if (!ov) return [];
  if (ov.parts) return ov.parts.flatMap((p) => (p.overview.sections || []).map((s) => ({ ...s, part: p.name })));
  return ov.sections || [];
}
export function allTiles(ov) {
  if (!ov) return [];
  if (ov.parts) return ov.parts.flatMap((p) => p.overview.tiles || []);
  return ov.tiles || [];
}

function Charts({ charts }) {
  if (!charts.length) return null;
  return <div className="al-chartgrid">{charts.map((c) => <div key={c.id} className={WIDE.has(c.type) ? "al-wide" : ""}><Chart spec={c}/></div>)}</div>;
}

function Empty({ what }) {
  return <div className="al-panel al-empty-page"><h3 className="al-h3">No {what} data in these files</h3>
    <p className="al-muted">Upload a file that holds {what.toLowerCase()} (for example an orders list or a customer list) and this page fills in on its own.</p></div>;
}

export function AreaPage({ page, report, view }) {
  const cfg = AREA_PAGES[page];
  const ov = report.overview;
  const tiles = allTiles(ov).filter((t) => cfg.areas.includes(t.area));
  const sections = allSections(ov).filter((s) => cfg.areas.includes(s.area));
  const cards = view.cards.filter((c) => cfg.areas.includes(c.area));
  if (!tiles.length && !sections.length && !cards.length) return <><Head title={cfg.title} intro={cfg.intro}/><Empty what={cfg.title}/></>;
  return <div className="al-stack">
    <Head title={cfg.title} intro={cfg.intro}/>
    {tiles.length > 0 && <div className="al-tiles">{tiles.map((t) => <Tile key={`${t.metric}-${t.source}`} t={t}/>)}</div>}
    {cards.length > 0 && <section><h3 className="al-h3">What Alpha found</h3><div className="ar-list">{cards.map((c) => <FindingCard key={c.id} card={c} currency={view.currency}/>)}</div></section>}
    {sections.map((s) => <section key={`${s.part || ""}${s.area}`}><h3 className="al-h3">{s.title}{s.part ? <small className="al-muted"> · {s.part}</small> : null}</h3><Charts charts={s.charts}/></section>)}
  </div>;
}

export function TrendsPage({ report }) {
  const ov = report.overview;
  const lines = allSections(ov).flatMap((s) => s.charts.filter((c) => c.type === "line" || c.type === "stacked").map((c) => ({ ...c, _area: s.title })));
  const moving = allTiles(ov).filter((t) => t.last_period || t.vs_last_year || (t.spark || []).length > 2);
  const intro = "How your numbers move over time: month by month, and compared with the period before.";
  if (!lines.length && !moving.length) return <><Head title="Trends" intro={intro}/><div className="al-panel al-empty-page"><h3 className="al-h3">No dates to follow over time</h3>
    <p className="al-muted">Trends need a date on each row (an order date, a sale date). These files have none, or too few dates to show a trend.</p></div></>;
  return <div className="al-stack">
    <Head title="Trends" intro={intro}/>
    {moving.length > 0 && <div className="al-tiles">{moving.map((t) => <Tile key={`${t.metric}-${t.source}`} t={t}/>)}</div>}
    <Charts charts={lines}/>
  </div>;
}

export function Head({ title, intro, children }) {
  return <section className="pg-head"><div><h1>{title}</h1>{intro && <p>{intro}</p>}</div>{children}</section>;
}
