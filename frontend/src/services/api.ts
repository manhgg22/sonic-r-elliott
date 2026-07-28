import type { CandleRow, TerminalSnapshot } from "../shared/types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function errorFrom(response: Response): Promise<ApiError> {
  let detail = `${response.status} ${response.statusText}`;
  try {
    const body = await response.json();
    if (body?.detail) detail = String(body.detail);
  } catch { /* body không phải JSON */ }
  return new ApiError(response.status, detail);
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { Accept: "application/json" }
  });
  if (!response.ok) throw await errorFrom(response);
  return response.json() as Promise<T>;
}

export interface AuthSession {
  authenticated: true;
  username: string;
  expires_at: number;
}

export const getAuthSession = () =>
  getJson<AuthSession>("/api/v1/auth/session");

export async function login(
  username: string, password: string
): Promise<AuthSession> {
  const response = await fetch("/api/v1/auth/login", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ username, password })
  });
  if (!response.ok) throw await errorFrom(response);
  return response.json() as Promise<AuthSession>;
}

export async function logout(): Promise<void> {
  const response = await fetch("/api/v1/auth/logout", {
    method: "POST",
    credentials: "same-origin"
  });
  if (!response.ok && response.status !== 401) {
    throw await errorFrom(response);
  }
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
  const response = await fetch("/api/v1/scanner/run", {
    method: "POST",
    credentials: "same-origin"
  });
  if (!response.ok) throw await errorFrom(response);
  return response.json();
};
