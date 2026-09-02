export function sliceLabel(slice: Record<string, string>): string {
  return Object.values(slice).join(" · ");
}

export function sliceEntries(slice: Record<string, string>): string {
  return Object.entries(slice)
    .map(([k, v]) => `${k}=${v}`)
    .join(", ");
}

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}
