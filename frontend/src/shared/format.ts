export function formatNumber(value: unknown, digits = 4) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return "—";

  return numericValue.toLocaleString("en-US", {
    maximumFractionDigits: Math.abs(numericValue) >= 1000 ? 2 : digits
  });
}

export const displayText = (value: unknown) => String(value ?? "—");

export const isTruthyFlag = (value: unknown) =>
  value === true || value === 1 || value === "1";

export const sideTone = (side: unknown) =>
  displayText(side).toLowerCase() === "long" ? "positive" : "negative";

export function formatDateTime(value: unknown) {
  if (!value) return "—";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Bangkok",
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(date);
}
