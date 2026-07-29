export function formatNumber(value: unknown, digits = 4) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return "—";

  return numericValue.toLocaleString("en-US", {
    maximumFractionDigits: Math.abs(numericValue) >= 1000 ? 2 : digits
  });
}

export function formatUsd(value: unknown, signed = false) {
  if (value == null || value === "") return "—";
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return "—";
  const formatted = Math.abs(numericValue).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
  if (numericValue < 0) return `-${formatted}`;
  return signed && numericValue > 0 ? `+${formatted}` : formatted;
}

export function formatUsdPrice(value: unknown) {
  if (value == null || value === "") return "—";
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return "—";
  const absolute = Math.abs(numericValue);
  const maximumFractionDigits =
    absolute >= 1000 ? 2 : absolute >= 1 ? 4 : absolute >= 0.01 ? 6 : 8;
  return numericValue.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits
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
