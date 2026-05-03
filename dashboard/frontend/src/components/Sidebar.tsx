import {
  ReviewIcon,
  DossierIcon,
  TiersIcon,
  CohortIcon,
  Book,
  Settings,
} from "./icons";
import type { Page } from "../types";
import type { LucideIcon } from "lucide-react";

interface SidebarProps {
  readonly page: Page;
  readonly onNav: (p: Page) => void;
  readonly pendingCount: number;
}

const NAV_ITEMS: { id: Page; label: string; Icon: LucideIcon; hasBadge?: boolean }[] = [
  { id: "review", label: "Review", Icon: ReviewIcon, hasBadge: true },
  { id: "dossier", label: "Dossier Viewer", Icon: DossierIcon },
  { id: "tiers", label: "University Tiers", Icon: TiersIcon },
  { id: "cohort", label: "Cohort Viewer", Icon: CohortIcon },
];

export function Sidebar({ page, onNav, pendingCount }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">E</div>
        <div>
          <div className="brand-name">Admission Console</div>
          <div className="brand-sub">EPFL · IC Master's · 2026</div>
        </div>
      </div>

      <div className="nav-section">
        <div className="nav-label">Workspace</div>
        {NAV_ITEMS.map((it) => (
          <button
            key={it.id}
            className="nav-item"
            aria-current={page === it.id || undefined}
            onClick={() => onNav(it.id)}
          >
            <it.Icon className="icon" size={16} strokeWidth={1.75} />
            <span>{it.label}</span>
            {it.hasBadge && pendingCount > 0 && (
              <span className="badge">{pendingCount}</span>
            )}
          </button>
        ))}
      </div>

      <div className="nav-section">
        <div className="nav-label">Resources</div>
        <button className="nav-item">
          <Book className="icon" size={16} strokeWidth={1.75} />
          <span>Rubric & Policies</span>
        </button>
        <button className="nav-item">
          <Settings className="icon" size={16} strokeWidth={1.75} />
          <span>Committee Settings</span>
        </button>
      </div>

      <div className="sidebar-footer">
        <div className="avatar">EB</div>
        <div className="avatar-meta">
          <div className="nm">Elie BRUNO</div>
          <div className="role">Agentic Evaluator</div>
        </div>
      </div>
    </aside>
  );
}
