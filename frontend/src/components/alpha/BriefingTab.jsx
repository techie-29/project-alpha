import { useState } from "react";
import { LevelBadge } from "./FindingCard";
import { percent } from "../../utils/alphaFormat";

export default function BriefingTab({ report, onOpenFinding, onAnswer, answers }) {
  const b = report.briefing;
  const answered = new Map((answers || []).map((a) => [a.questionId, a.answer]));
  return <div className="al-stack">
    <section className="al-hero">
      <span className="eyebrow">Briefing</span>
      <h2>{b.headline}</h2>
      <p>{b.status}</p>
      {b.coverage && <p className="al-muted">{b.coverage}</p>}
      <p className="al-muted">Checked {b.checked.series.toLocaleString()} measure-and-group combinations ({b.checked.tests.toLocaleString()} statistical tests) across {b.checked.files} file{b.checked.files === 1 ? "" : "s"}.</p>
    </section>

    {b.stories.length > 0 && <section>
      <h3 className="al-h3">What matters most</h3>
      <div className="al-cards">{b.stories.map((s) => <button type="button" key={s.finding_id} className={`al-story al-pol-${s.polarity}`} onClick={() => onOpenFinding(s.finding_id)}>
        <LevelBadge level={s.level} claim={s.claim}/>
        <strong>{s.title}</strong>
        <span>{s.detail}</span>
        <em>{s.action}</em>
        {s.more > 0 && <small>+{s.more} related finding{s.more === 1 ? "" : "s"}</small>}
      </button>)}</div>
    </section>}

    {report.questions?.length > 0 && <section className="al-panel">
      <h3 className="al-h3">Questions only you can answer</h3>
      <p className="al-muted">The files show what changed, not always why. Your answers are saved with this analysis.</p>
      {report.questions.map((q) => <QuestionRow key={q.id} q={q} saved={answered.get(q.id)} onAnswer={onAnswer}/>)}
    </section>}

    {b.caveats.length > 0 && <section className="al-panel al-caveat">
      <h3 className="al-h3">Things to keep in mind</h3>
      <ul className="al-plain">{b.caveats.map((c, i) => <li key={i}>{c}</li>)}</ul>
    </section>}

    <section className="al-panel">
      <h3 className="al-h3">How to read this</h3>
      <p>{b.what_this_means}</p>
      <ul className="al-plain">{report.limits.map((l, i) => <li key={i}>{l}</li>)}</ul>
      <p className="al-muted">Strength labels: <strong>Calculated</strong> means plain arithmetic on your rows. <strong>Supported by evidence</strong> means the change passed a shuffle test that allows for chance. <strong>Possible (early sign)</strong> means it is worth watching but not yet solid.</p>
    </section>
  </div>;
}

function QuestionRow({ q, saved, onAnswer }) {
  const [value, setValue] = useState(saved || "");
  return <form className="al-question" onSubmit={(e) => { e.preventDefault(); if (value.trim()) onAnswer(q.id, value.trim()); }}>
    <label>{q.text}<textarea rows={2} value={value} maxLength={1000} onChange={(e) => setValue(e.target.value)} placeholder="Type what you know, or leave blank"/></label>
    <button type="submit" className="secondary-button" disabled={!value.trim() || value.trim() === saved}>{saved ? (value.trim() === saved ? "Saved" : "Update") : "Save answer"}</button>
  </form>;
}

