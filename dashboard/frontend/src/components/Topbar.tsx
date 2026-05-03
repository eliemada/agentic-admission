import type { ReactNode } from "react";

interface TopbarProps {
  readonly crumbs: readonly string[];
  readonly actions?: ReactNode;
}

export function Topbar({ crumbs, actions }: TopbarProps) {
  return (
    <header className="topbar">
      <div className="crumbs">
        {crumbs.map((c, i) => (
          <span key={i}>
            {i > 0 && <span className="crumb-sep"> / </span>}
            <span
              style={{
                color: i === crumbs.length - 1 ? "var(--fg)" : "var(--fg-subtle)",
                fontWeight: i === crumbs.length - 1 ? 500 : 400,
              }}
            >
              {c}
            </span>
          </span>
        ))}
      </div>
      <div className="topbar-actions">{actions}</div>
    </header>
  );
}
