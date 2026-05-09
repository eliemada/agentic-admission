import { useState, useEffect, useMemo, createContext, useContext } from "react";
import type { Page } from "./types";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { Bell } from "./components/icons";
import { ReviewPage } from "./pages/Review";
import { DossierPage } from "./pages/Dossier";
import { TiersPage } from "./pages/Tiers";
import { CohortPage } from "./pages/Cohort";

const CRUMBS: Record<Page, string[]> = {
  review: ["Admissions", "2026 Cycle", "Review"],
  dossier: ["Admissions", "2026 Cycle", "Dossier Viewer"],
  tiers: ["Admissions", "Calibration", "University Tiers"],
  cohort: ["Admissions", "2026 Cycle", "Cohort Viewer"],
};

const PAGE_COMPONENTS: Record<Page, React.ComponentType> = {
  review: ReviewPage,
  dossier: DossierPage,
  tiers: TiersPage,
  cohort: CohortPage,
};

/* Deep-link target consumed by the Dossier page on mount. */
export interface DossierTarget {
  readonly semester: string;
  readonly candidate: string;
}

/* Global context: API availability + cross-page deep-link state. */
interface AppState {
  readonly apiAvailable: boolean;
  readonly dossierTarget: DossierTarget | null;
  readonly navigateToDossier: (candidateId: string) => void;
  readonly clearDossierTarget: () => void;
}

export const AppContext = createContext<AppState>({
  apiAvailable: false,
  dossierTarget: null,
  navigateToDossier: () => {},
  clearDossierTarget: () => {},
});
export const useAppContext = () => useContext(AppContext);

/* Candidate IDs are formatted ``"{semester}_{folder}"`` (e.g.
 * ``"2025-26-spring_0ba6a85ecc4b"``). Semesters never contain
 * underscores, so the first underscore is the safe split point.
 */
function parseCandidateId(id: string): DossierTarget | null {
  const idx = id.indexOf("_");
  if (idx <= 0 || idx >= id.length - 1) return null;
  return { semester: id.slice(0, idx), candidate: id.slice(idx + 1) };
}

export function App() {
  const [page, setPage] = useState<Page>("review");
  const [apiAvailable, setApiAvailable] = useState(false);
  const [dossierTarget, setDossierTarget] = useState<DossierTarget | null>(null);

  useEffect(() => {
    fetch("/api/semesters")
      .then((r) => { if (r.ok) setApiAvailable(true); })
      .catch(() => setApiAvailable(false));
  }, []);

  const ctx = useMemo<AppState>(
    () => ({
      apiAvailable,
      dossierTarget,
      navigateToDossier: (candidateId: string) => {
        const target = parseCandidateId(candidateId);
        if (!target) return;
        setDossierTarget(target);
        setPage("dossier");
      },
      clearDossierTarget: () => setDossierTarget(null),
    }),
    [apiAvailable, dossierTarget],
  );
  const PageComp = PAGE_COMPONENTS[page];

  return (
    <AppContext.Provider value={ctx}>
      <div className="app">
        <Sidebar page={page} onNav={setPage} pendingCount={0} />
        <main className="main">
          <Topbar
            crumbs={CRUMBS[page]}
            actions={
              <>
                <button className="btn btn-sm btn-ghost">
                  <Bell size={14} />
                </button>
                {apiAvailable ? (
                  <button className="btn btn-sm">
                    <span className="candidate-status-dot admit" /> Live
                  </button>
                ) : (
                  <button className="btn btn-sm">
                    <span className="candidate-status-dot pending" /> Demo
                  </button>
                )}
              </>
            }
          />
          <div className="content">
            <PageComp />
          </div>
        </main>
      </div>
    </AppContext.Provider>
  );
}
