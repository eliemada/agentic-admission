import type { Status } from "../types";

const STATUS_MAP: Record<Status, { cls: string; label: string }> = {
  admit: { cls: "pill-admit", label: "Admit" },
  reject: { cls: "pill-reject", label: "Reject" },
  discuss: { cls: "pill-discuss", label: "Discuss" },
  pending: { cls: "pill-pending", label: "Pending" },
};

export function StatusPill({ status }: { readonly status: Status }) {
  const m = STATUS_MAP[status] ?? STATUS_MAP.pending;
  return (
    <span className={`pill ${m.cls}`}>
      <span className="dot" />
      {m.label}
    </span>
  );
}
