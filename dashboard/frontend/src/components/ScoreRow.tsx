interface ScoreRowProps {
  readonly label: string;
  readonly value: number;
  readonly max?: number;
}

export function ScoreRow({ label, value, max = 10 }: ScoreRowProps) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="score-row">
      <span className="score-label">{label}</span>
      <div className="score-track">
        <div className="score-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="score-num">{value.toFixed(1)}</span>
    </div>
  );
}
