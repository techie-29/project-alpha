/** PowerPoint export. pptxgenjs is free and open source; it loads only when someone clicks the button. */
export async function exportPptx(slides, theme, fileName) {
  const { default: Pptx } = await import("pptxgenjs");
  const p = new Pptx();
  p.layout = "LAYOUT_WIDE";                                  // 13.33 x 7.5 in
  const T = theme, FONT = "Calibri";
  const txt = (s, text, o) => s.addText(Array.isArray(text) ? text : String(text ?? ""), { fontFace: FONT, color: T.text, ...o });
  const chartBase = { catAxisLabelColor: T.dim, valAxisLabelColor: T.dim, catAxisLabelFontSize: 11, valAxisLabelFontSize: 11, valGridLine: { color: T.panel, size: 0.5 }, legendColor: T.dim, legendFontSize: 11 };
  slides.forEach((d, i) => {
    const s = p.addSlide();
    s.background = { color: T.bg };
    if (d.notes) s.addNotes(d.notes);
    const head = (t) => txt(s, t, { x: 0.6, y: 0.4, w: 12.1, h: 0.9, fontSize: 28, bold: true, valign: "top" });
    const foot = () => { txt(s, d.biz || "", { x: 0.6, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: T.dim }); txt(s, `${i + 1} / ${slides.length}`, { x: 11.7, y: 7.0, w: 1, h: 0.3, fontSize: 10, color: T.dim, align: "right" }); };
    switch (d.kind) {
      case "title":
        s.addShape(p.ShapeType.rect, { x: 0.6, y: 2.6, w: 0.12, h: 1.8, fill: { color: T.accent } });
        txt(s, d.title, { x: 0.95, y: 2.5, w: 11.5, h: 1.3, fontSize: 40, bold: true, valign: "top" });
        txt(s, [d.subtitle, d.presenter && `Presented by ${d.presenter}`].filter(Boolean).join("\n"), { x: 0.95, y: 3.9, w: 11, h: 0.9, fontSize: 18, color: T.dim, valign: "top" });
        break;
      case "verdict":
        txt(s, "THE HEADLINE", { x: 0.8, y: 1.0, w: 6, h: 0.4, fontSize: 13, bold: true, color: T.accent });
        txt(s, d.title, { x: 0.8, y: 1.5, w: 11.7, h: 2.6, fontSize: 36, bold: true, valign: "top" });
        txt(s, d.bullets.map((b) => ({ text: b, options: { bullet: true, breakLine: true } })), { x: 0.8, y: 4.3, w: 11.5, h: 2.2, fontSize: 18, color: T.dim, valign: "top", paraSpaceAfter: 8 });
        foot(); break;
      case "drivers":
        head(d.title);
        txt(s, `${d.share}%`, { x: 0.6, y: 1.8, w: 5, h: 1.5, fontSize: 72, bold: true, color: T.accent });
        txt(s, d.caption, { x: 0.6, y: 3.4, w: 5.2, h: 1.5, fontSize: 18, color: T.dim, valign: "top" });
        s.addChart(p.charts.BAR, [{ name: d.chart.title, labels: d.chart.rows.map((r) => String(r.group)), values: d.chart.rows.map((r) => r.value) }], { x: 6.3, y: 1.5, w: 6.5, h: 5, barDir: "bar", ...chartBase, chartColors: d.chart.rows.map((r, k) => k === 0 ? T.accent : T.line), showLegend: false, catAxisOrientation: "maxMin" });
        foot(); break;
      case "snapshot":
        head(d.title);
        d.figures.slice(0, 5).forEach((f, k, arr) => {
          const cw = (12.1 - 0.2 * (arr.length - 1)) / arr.length, x = 0.6 + k * (cw + 0.2);
          s.addShape(p.ShapeType.roundRect, { x, y: 1.7, w: cw, h: 2.0, fill: { color: T.panel }, rectRadius: 0.1 });
          txt(s, f.label, { x: x + 0.2, y: 1.8, w: cw - 0.3, h: 0.4, fontSize: 13, color: T.dim });
          txt(s, f.value, { x: x + 0.2, y: 2.2, w: cw - 0.3, h: 0.8, fontSize: 28, bold: true });
          if (f.change) txt(s, f.change, { x: x + 0.2, y: 3.0, w: cw - 0.3, h: 0.4, fontSize: 13, color: f.tone === "bad" ? T.bad : f.tone === "good" ? T.accent : T.dim });
        });
        [d.business && [`Business health ${d.business.score}`, d.business.label], d.data != null && [`Data health ${d.data}`, "how clean the files are"]].filter(Boolean).forEach(([a, b], k) => {
          txt(s, a, { x: 0.6 + k * 6, y: 4.4, w: 5.5, h: 0.7, fontSize: 26, bold: true, color: T.accent }); txt(s, b, { x: 0.6 + k * 6, y: 5.0, w: 5.5, h: 0.4, fontSize: 14, color: T.dim });
        });
        foot(); break;
      case "sales":
        head(d.title);
        s.addChart(p.charts.LINE, [{ name: "Sales", labels: d.line.x, values: d.line.y }], { x: 0.6, y: 1.5, w: 12.1, h: 4.9, ...chartBase, lineSize: 3, lineDataSymbol: "none", chartColors: [T.accent], showLegend: false });
        txt(s, d.caption, { x: 0.6, y: 6.4, w: 12.1, h: 0.5, fontSize: 14, color: T.dim }); foot(); break;
      case "risk":
        txt(s, (d.kicker || `PROBLEM ${d.n}`).toUpperCase(), { x: 0.6, y: 0.4, w: 4, h: 0.35, fontSize: 12, bold: true, color: T.bad });
        txt(s, d.title, { x: 0.6, y: 0.8, w: d.chart ? 6.2 : 12, h: 1.8, fontSize: 24, bold: true, valign: "top" });
        if (d.money) txt(s, `${d.money} involved`, { x: 0.6, y: 2.7, w: 6, h: 0.5, fontSize: 20, bold: true, color: T.warn });
        if (d.point) txt(s, d.point, { x: 0.6, y: 3.3, w: d.chart ? 6.2 : 12, h: 1.4, fontSize: 15, color: T.dim, valign: "top" });
        if (d.action) { s.addShape(p.ShapeType.roundRect, { x: 0.6, y: 4.9, w: d.chart ? 6.2 : 12, h: 1.8, fill: { color: T.panel }, rectRadius: 0.1 }); txt(s, [{ text: "What to do\n", options: { bold: true, color: T.accent, fontSize: 13 } }, { text: d.action, options: { fontSize: 15 } }], { x: 0.8, y: 5.0, w: d.chart ? 5.8 : 11.6, h: 1.6, valign: "top" }); }
        if (d.chart) { txt(s, d.chart.title, { x: 7.2, y: 0.8, w: 5.5, h: 0.4, fontSize: 13, color: T.dim });
          s.addChart(p.charts.BAR, [{ name: d.chart.title, labels: d.chart.rows.map((r) => String(r.group)), values: d.chart.rows.map((r) => r.value) }], { x: 7.2, y: 1.3, w: 5.6, h: 5.3, barDir: "bar", ...chartBase, chartColors: d.chart.rows.map((r, k) => (d.chart.focus ? String(r.group) === String(d.chart.focus) : k === 0) ? T.bad : T.line), showLegend: false, catAxisOrientation: "maxMin" }); }
        if (d.table) { txt(s, d.table.title, { x: 7.2, y: 0.8, w: 5.5, h: 0.4, fontSize: 13, color: T.dim });
          s.addTable([d.table.columns.map((c) => ({ text: c, options: { bold: true, color: T.dim, fontSize: 11 } })), ...d.table.rows.map((r) => r.map((v) => ({ text: v, options: { color: T.text, fontSize: 14 } })))], { x: 7.2, y: 1.3, w: 5.6, border: { type: "solid", color: T.panel, pt: 1 }, fontFace: FONT }); }
        foot(); break;
      case "good":
        head(d.title);
        d.items.slice(0, 3).forEach((it, k) => { const x = 0.6 + k * 4.1; s.addShape(p.ShapeType.roundRect, { x, y: 1.7, w: 3.9, h: 4.6, fill: { color: T.panel }, rectRadius: 0.1 });
          txt(s, it.headline, { x: x + 0.25, y: 1.9, w: 3.4, h: 1.7, fontSize: 18, bold: true, color: T.accent, valign: "top" }); txt(s, it.point || "", { x: x + 0.25, y: 3.7, w: 3.4, h: 2.4, fontSize: 14, color: T.dim, valign: "top" }); });
        foot(); break;
      case "forecast": {
        head(d.title);
        const labels = [...d.line.x, ...d.forecast.x], pad = Array(d.line.x.length - 1).fill(null), last = d.line.y[d.line.y.length - 1];
        s.addChart(p.charts.LINE, [
          { name: "Actual", labels, values: [...d.line.y, ...d.forecast.x.map(() => null)] },
          { name: "Most likely", labels, values: [...pad, last, ...d.forecast.mid] },
          { name: "Low end", labels, values: [...pad, last, ...d.forecast.low] },
          { name: "High end", labels, values: [...pad, last, ...d.forecast.high] }],
          { x: 0.6, y: 1.4, w: 7.8, h: 5.3, ...chartBase, lineSize: 2.5, lineDataSymbol: "none", chartColors: [T.line, T.accent, T.dim, T.dim], lineDash: ["solid", "dash", "sysDot", "sysDot"], showLegend: true, legendPos: "b" });
        txt(s, d.total.mid, { x: 8.8, y: 1.6, w: 4, h: 0.9, fontSize: 36, bold: true, color: T.accent });
        txt(s, `most likely over three months. Likely between ${d.total.low} and ${d.total.high}.`, { x: 8.8, y: 2.6, w: 4, h: 1.2, fontSize: 15, color: T.dim, valign: "top" });
        s.addShape(p.ShapeType.roundRect, { x: 8.8, y: 4.2, w: 4, h: 2.2, fill: { color: T.panel }, rectRadius: 0.1 });
        txt(s, [{ text: "How far to trust it\n", options: { bold: true, color: T.accent, fontSize: 13 } }, { text: d.trust ? `Tested on your last 3 months: off by about ${d.trust.error}% a month.` : d.untested || "", options: { fontSize: 14 } }], { x: 9.0, y: 4.3, w: 3.6, h: 2, valign: "top" });
        foot(); break; }
      case "actions":
        head(d.title);
        d.items.slice(0, 4).forEach((a, k) => { const y = 1.6 + k * 1.3; s.addShape(p.ShapeType.ellipse, { x: 0.6, y: y + 0.1, w: 0.6, h: 0.6, fill: { color: T.accent } });
          txt(s, String(k + 1), { x: 0.6, y: y + 0.1, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: T.bg, align: "center", valign: "middle" });
          txt(s, a.title, { x: 1.5, y, w: 8.6, h: 0.45, fontSize: 18, bold: true }); txt(s, `${a.action || ""}   Owner: ________`, { x: 1.5, y: y + 0.45, w: 8.6, h: 0.7, fontSize: 13, color: T.dim, valign: "top" });
          if (a.when) txt(s, a.when, { x: 10.2, y: y + 0.5, w: 2.5, h: 0.4, fontSize: 12, color: T.accent, align: "right" });
          if (a.impact) txt(s, a.impact, { x: 10.2, y, w: 2.5, h: 0.5, fontSize: 16, bold: true, color: T.warn, align: "right" }); });
        foot(); break;
      case "quality": {
        head(d.title);
        if (d.health != null) txt(s, `Data health ${d.health}`, { x: 0.6, y: 1.6, w: 5, h: 0.8, fontSize: 30, bold: true, color: T.accent });
        const r = d.rows;
        s.addChart(p.charts.BAR, [{ name: "Rows", labels: ["Fine", "Cleaned", "Flagged", "Left out"], values: [r.ok || 0, r.fixed || 0, r.flagged || 0, r.left_out || 0] }], { x: 5.2, y: 1.4, w: 7.5, h: 4.3, barDir: "col", ...chartBase, chartColors: [T.accent, T.line, T.warn, T.bad], showLegend: false, showValue: true, dataLabelColor: T.text });
        txt(s, d.headline || "", { x: 0.6, y: 2.6, w: 4.4, h: 3, fontSize: 15, color: T.dim, valign: "top" }); foot(); break; }
      case "close":
        head(d.title);
        txt(s, d.bullets.map((b) => ({ text: b, options: { bullet: true, breakLine: true } })), { x: 0.8, y: 1.7, w: 11.5, h: 3.8, fontSize: 20, valign: "top", paraSpaceAfter: 14 });
        txt(s, `Thank you${d.presenter ? `. ${d.presenter}` : ""}`, { x: 0.8, y: 5.9, w: 11, h: 0.6, fontSize: 22, bold: true, color: T.accent }); foot(); break;
      default: break;
    }
  });
  await p.writeFile({ fileName: `${fileName}.pptx` });
}
