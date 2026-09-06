// Every code the engine can emit has a sentence in both languages. A missing key would show
// up as a raw identifier in the panel, in one language only, which nobody would notice until
// a user did.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const engine = join(root, "custom_components", "hosekeeper", "engine");

async function load(relative) {
  const source = readFileSync(join(root, "custom_components", "hosekeeper", "frontend", relative), "utf8");
  return import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
}

const i18n = await load("i18n.js");
const en = i18n.strings("en");
const it = i18n.strings("it");

const rules = readFileSync(join(engine, "rules.py"), "utf8");
const planSource = readFileSync(join(engine, "plan.py"), "utf8");
// The done-by table lists maintenance kinds, not reasons.
const plan = planSource.replace(/DONE_BY[\s\S]*?\n}\n/, "");
const nutrition = readFileSync(join(engine, "nutrition.py"), "utf8");
const schedule = readFileSync(join(engine, "schedule.py"), "utf8");
const adaptation = readFileSync(join(engine, "adaptation.py"), "utf8");

const adviceBlock = rules.slice(rules.indexOf("ADVICE_CODES"), rules.indexOf("RULES: tuple"));
const adviceCodes = [...adviceBlock.matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);

const operationCodes = [...plan.matchAll(/\(\s*"([a-z_]+)",\s*"(general|weeds|mowing|fertilizing|aeration|seeding|disease|irrigation)"/g)].map((m) => m[1]);
const basisCodes = [...plan.matchAll(/"((?:research|pro_programme)_[a-z0-9_]+)"/g)].map((m) => m[1]);
const reasonSources = [rules, plan, nutrition, schedule, adaptation].join("\n");
// Reason codes are the snake_case strings passed as reasons or appended to tailoring/reasons.
const reasonCodes = new Set([
  ...[...reasonSources.matchAll(/(?:reasons|tailoring|blockers)\.append\(\s*"([a-z0-9_]+)"/g)].map((m) => m[1]),
  ...[...reasonSources.matchAll(/\("([a-z0-9_]+)",\)/g)].map((m) => m[1]),
  ...[...reasonSources.matchAll(/MowingWindow\(\w+,\s*\("([a-z_]+)",\)\)/g)].map((m) => m[1]),
  ...[...adaptation.matchAll(/BOUNDS,\s*"([a-z_]+)"/g)].map((m) => m[1]),
  ...basisCodes,
]);

let failed = 0;
const missing = (table, code, lang) => {
  console.error(`  ${lang}.${table} is missing ${code}`);
  failed = 1;
};
for (const code of adviceCodes) {
  for (const [lang, s] of [["en", en], ["it", it]]) {
    const entry = s.advice[code];
    if (!entry || !entry.title || !entry.body) missing("advice", code, lang);
  }
}
for (const code of operationCodes) {
  for (const [lang, s] of [["en", en], ["it", it]]) {
    if (!s.operations[code]) missing("operations", code, lang);
    if (!s.howto[code]) missing("howto", code, lang);
  }
}
for (const code of reasonCodes) {
  for (const [lang, s] of [["en", en], ["it", it]]) if (!s.reasons[code]) missing("reasons", code, lang);
}
for (const table of ["ui", "status", "issues", "maintenance", "phases", "categories", "npk", "seedMix", "views", "howto", "exposures"]) {
  for (const key of Object.keys(en[table])) if (!(key in it[table])) missing(table, key, "it");
  for (const key of Object.keys(it[table])) if (!(key in en[table])) missing(table, key, "en");
}
// Placeholders in templates must agree between languages.
for (const [code, entry] of Object.entries(en.advice)) {
  const holes = (text) => [...(text || "").matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");
  const other = it.advice[code];
  if (other && holes(entry.body) !== holes(other.body)) {
    console.error(`  advice ${code}: placeholders differ (${holes(entry.body)} vs ${holes(other.body)})`);
    failed = 1;
  }
}
console.log(`  ${adviceCodes.length} advice codes, ${operationCodes.length} operations, ${reasonCodes.size} reasons checked`);
process.exit(failed);
