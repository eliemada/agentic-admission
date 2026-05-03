import type { ReactNode } from "react";
import { cls } from "../utils";

interface StatProps {
  readonly label: string;
  readonly value: ReactNode;
  readonly unit?: string;
  readonly delta?: string;
  readonly deltaDir?: "up" | "down";
}

export function Stat({ label, value, unit, delta, deltaDir }: StatProps) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        {unit && <span className="unit">{unit}</span>}
      </div>
      {delta && <div className={cls("stat-delta", deltaDir)}>{delta}</div>}
    </div>
  );
}
