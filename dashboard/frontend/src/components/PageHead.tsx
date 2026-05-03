import type { ReactNode } from "react";

interface PageHeadProps {
  readonly title: string;
  readonly sub?: string;
  readonly right?: ReactNode;
}

export function PageHead({ title, sub, right }: PageHeadProps) {
  return (
    <div className="page-head">
      <div>
        <h2>{title}</h2>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {right}
    </div>
  );
}
