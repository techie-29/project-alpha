/** The sample businesses shipped with the app (public/samples). Plain static files: nothing is paid for or sent anywhere. */
const BASE = `${import.meta.env.BASE_URL || "/"}samples/`;

export async function listSamples() {
  const r = await fetch(`${BASE}index.json`);
  if (!r.ok) throw new Error("The sample businesses could not be loaded.");
  return r.json();
}

/** Downloads a sample's CSV files as File objects, ready for the normal upload. */
export async function sampleFiles(sample) {
  return Promise.all(sample.files.map(async (name) => {
    const r = await fetch(`${BASE}${sample.key}/${name}`);
    if (!r.ok) throw new Error(`Could not load ${name}.`);
    return new File([await r.blob()], name, { type: "text/csv" });
  }));
}

/** Which sample an analysis was made from (by its file names), or null for real data. */
export function sampleOf(report) {
  const names = (report?.files || []).map((f) => f.name || "");
  if (!names.length) return null;
  const m = names[0].match(/^sample-([a-z]+)-/);
  return m && names.every((n) => n.startsWith(`sample-${m[1]}-`)) ? m[1] : null;
}
