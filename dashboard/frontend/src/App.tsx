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

/* Global context for API availability check */
interface AppState {
  readonly apiAvailable: boolean;
}

export const AppContext = createContext<AppState>({ apiAvailable: false });
export const useAppContext = () => useContext(AppContext);

export function App() {
  const [page, setPage] = useState<Page>("review");
  const [apiAvailable, setApiAvailable] = useState(false);

  useEffect(() => {
    fetch("/api/semesters")
      .then((r) => { if (r.ok) setApiAvailable(true); })
      .catch(() => setApiAvailable(false));
  }, []);

  const ctx = useMemo(() => ({ apiAvailable }), [apiAvailable]);
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
