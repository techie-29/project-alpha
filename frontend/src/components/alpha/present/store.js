import { THEMES } from "../../../utils/deck";

const key = (id) => `alphaDeck:${id}`;
export const DEFAULTS = { title: "", business: "", presenter: "", theme: "ink", off: [] };

export function loadSettings(id) {
  try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(key(id)) || "{}") }; } catch { return { ...DEFAULTS }; }
}
export function saveSettings(id, s) { try { localStorage.setItem(key(id), JSON.stringify(s)); } catch { /* storage blocked: settings just aren't remembered */ } }
export const themeOf = (s) => THEMES[s.theme] || THEMES.ink;
export const themeVars = (t) => Object.fromEntries(Object.entries(t).filter(([k]) => k !== "name").map(([k, v]) => [`--dk-${k}`, `#${v}`]));
