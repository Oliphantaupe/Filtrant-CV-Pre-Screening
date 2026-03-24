export function pad(n: number) { return String(n).padStart(2, '0') }
export function fmtUTC(d: Date) { return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}` }
