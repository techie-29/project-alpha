const BUCKETS = [
  ["fix", "Fix", "Confirmed changes that hurt. Start here.", "al-fix"],
  ["keep", "Keep", "Confirmed changes that help. Understand them so they last.", "al-keep"],
  ["watch", "Watch", "Early signs and changes that are not clearly good or bad.", "al-watch"]
];

export default function IntelligenceTab({ report, onOpenFinding }) {
  const intel = report.intelligence;
  const notExplained = report.not_explained || [];
  return <div className="al-stack">
    <p className="al-muted">A short list of what to do first. Each item points to where in your data to look; it does not claim a cause.</p>
    <div className="al-columns">
      {BUCKETS.map(([key, title, sub, cls]) => <section key={key} className={`al-bucket ${cls}`}>
        <header><h3>{title}</h3><span>{intel[key].length}</span></header>
        <p className="al-muted">{sub}</p>
        {intel[key].length === 0 && <p className="al-empty">Nothing here.</p>}
        {intel[key].map((item) => <button type="button" key={item.finding_id} className="al-intel" onClick={() => onOpenFinding(item.finding_id)}>
          <strong>{item.title}</strong>
          <span>{item.why}</span>
          <em>{item.where_to_look}</em>
        </button>)}
      </section>)}
    </div>
    {notExplained.length > 0 && <section className="al-panel"><h3 className="al-h3">Not explained by your files</h3>
      <p className="al-muted">For these, more than 30% of the change cannot be tied to any column you gave Alpha. Something outside the data may be involved.</p>
      <ul className="al-plain">{notExplained.map((n) => <li key={n.finding_id}>{n.title} <span className="al-muted">({Math.round(n.share * 100)}% unexplained)</span></li>)}</ul></section>}
  </div>;
}
