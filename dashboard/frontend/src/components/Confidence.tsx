import { cls } from "../utils";

interface ConfidenceProps {
  readonly value: number;
  readonly status?: string;
}

export function Confidence({ value, status = "" }: ConfidenceProps) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div className="confidence">
      <div className="confidence-track">
        <div className={cls("confidence-fill", status)} style={{ width: `${pct}%` }} />
      </div>
      <span className="confidence-pct">{pct}%</span>
    </div>
  );
}
