import type { CandleRow, TerminalSnapshot } from "../shared/types";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

export const getTerminalSnapshot = () =>
  getJson<TerminalSnapshot>("/api/v1/terminal/snapshot");

export async function getCandles(instrumentId: string): Promise<CandleRow[]> {
  const payload = await getJson<{ candles: CandleRow[] }>(
    `/api/v1/market/candles/${encodeURIComponent(instrumentId)}?bar=15m&limit=300`
  );
  return payload.candles;
}

export const runScanner = async () => {
  const response = await fetch("/api/v1/scanner/run", { method: "POST" });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch { /* body không phải JSON */ }
    throw new Error(detail);
  }
  return response.json();
};
