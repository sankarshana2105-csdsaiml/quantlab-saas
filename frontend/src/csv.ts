import type { OhlcvBar } from "./types";

const REQUIRED = ["timestamp", "open", "high", "low", "close", "volume"] as const;
export const MAX_CSV_BYTES = 10 * 1024 * 1024;
export const MAX_DATASET_BARS = 100_000;

function parseRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], value = "", quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    if (char === '"') {
      if (quoted && text[i + 1] === '"') { value += '"'; i += 1; }
      else quoted = !quoted;
    } else if (char === "," && !quoted) { row.push(value.trim()); value = ""; }
    else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && text[i + 1] === "\n") i += 1;
      row.push(value.trim()); value = "";
      if (row.some(Boolean)) rows.push(row);
      row = [];
    } else value += char;
  }
  if (quoted) throw new Error("CSV contains an unterminated quoted field.");
  row.push(value.trim());
  if (row.some(Boolean)) rows.push(row);
  return rows;
}

export function parseOhlcvCsv(text: string): OhlcvBar[] {
  if (new Blob([text]).size > MAX_CSV_BYTES) throw new Error("CSV must be 10 MB or smaller.");
  const rows = parseRows(text.replace(/^\uFEFF/, ""));
  if (rows.length < 2) throw new Error("CSV must contain a header and at least one data row.");
  if (rows.length - 1 > MAX_DATASET_BARS) throw new Error(`CSV exceeds the ${MAX_DATASET_BARS.toLocaleString()}-bar limit.`);
  const headers = rows[0].map((value) => value.toLowerCase());
  const indexes = Object.fromEntries(REQUIRED.map((name) => [name, headers.indexOf(name)]));
  const missing = REQUIRED.filter((name) => indexes[name] < 0);
  if (missing.length) throw new Error(`Missing required columns: ${missing.join(", ")}.`);
  return rows.slice(1).map((values, rowIndex) => {
    const timestamp = values[indexes.timestamp];
    if (!timestamp || Number.isNaN(Date.parse(timestamp))) throw new Error(`Row ${rowIndex + 2}: invalid timestamp.`);
    const numbers = Object.fromEntries(REQUIRED.slice(1).map((name) => [name, Number(values[indexes[name]])]));
    if (Object.values(numbers).some((value) => !Number.isFinite(value))) throw new Error(`Row ${rowIndex + 2}: prices and volume must be numeric.`);
    return { timestamp, ...numbers } as OhlcvBar;
  });
}
