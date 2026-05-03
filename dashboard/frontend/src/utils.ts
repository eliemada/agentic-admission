import type { Candidate } from "./types";

export function cls(...xs: (string | boolean | undefined | null)[]): string {
  return xs.filter(Boolean).join(" ");
}

export function formatGpa(c: Candidate): string {
  if (c.gpaScale === 1.0) return `${c.gpa.toFixed(1)} / 1`;
  if (c.gpaScale === 30) return `${c.gpa.toFixed(1)} / 30`;
  if (c.gpaScale === 20) return `${c.gpa.toFixed(1)} / 20`;
  if (c.gpaScale === 10) return `${c.gpa.toFixed(1)} / 10`;
  if (c.gpaScale === 6) return `${c.gpa.toFixed(2)} / 6`;
  return `${c.gpa.toFixed(2)} / ${c.gpaScale}`;
}

export function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
