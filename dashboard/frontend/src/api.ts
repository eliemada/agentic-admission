const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export interface ChatStreamCallbacks {
  onToken: (token: string) => void;
  onDone: () => void;
  onError: (err: string) => void;
}

export const api = {
  // Review / Evaluations
  semesters: () => get<string[]>("/semesters"),
  candidates: (semester?: string) =>
    get<RawCandidate[]>(semester ? `/candidates?semester=${semester}` : "/candidates"),

  // Universities
  universities: () => get<RawUniversity[]>("/universities"),
  updateTier: async (name: string, tier: string) => {
    const res = await fetch(`${BASE}/universities/${encodeURIComponent(name)}/tier?tier=${tier}`, {
      method: "PUT",
    });
    if (!res.ok) throw new Error(`Failed to update tier`);
    return res.json();
  },

  // Cohort
  cohortSemesters: () => get<string[]>("/cohort/semesters"),
  cohort: (semester: string) => get<RawCohortCandidate[]>(`/cohort/${semester}`),

  // Dossier
  dossierSemesters: () => get<string[]>("/dossier/semesters"),
  dossierCandidates: (semester: string) => get<string[]>(`/dossier/${semester}/candidates`),
  dossierDocuments: (semester: string, candidate: string) =>
    get<DossierDocument[]>(`/dossier/${semester}/${candidate}/documents`),
  dossierPdfUrl: (semester: string, candidate: string, docFolder: string) =>
    `${BASE}/dossier/${semester}/${candidate}/${encodeURIComponent(docFolder)}/pdf`,
  dossierText: (semester: string, candidate: string, docFolder: string) =>
    get<{ filename: string; content: string }>(
      `/dossier/${semester}/${candidate}/${encodeURIComponent(docFolder)}/text`,
    ),
  dossierAnonymized: (semester: string, candidate: string, docFolder: string) =>
    get<{ filename: string; content: string }>(
      `/dossier/${semester}/${candidate}/${encodeURIComponent(docFolder)}/anonymized`,
    ),

  // Exports
  candidatesCsvUrl: (semester?: string) =>
    `${BASE}/candidates/export.csv${semester ? `?semester=${semester}` : ""}`,
  candidatesExcelUrl: (semester?: string) =>
    `${BASE}/candidates/export.xlsx${semester ? `?semester=${semester}` : ""}`,
  candidatePdfUrl: (candidateId: string) =>
    `${BASE}/candidates/${encodeURIComponent(candidateId)}/report.pdf`,
  universitiesCsvUrl: () => `${BASE}/universities/export.csv`,
  universitiesExcelUrl: () => `${BASE}/universities/export.xlsx`,
  cohortCsvUrl: (semester: string) => `${BASE}/cohort/${semester}/export.csv`,
  cohortExcelUrl: (semester: string) => `${BASE}/cohort/${semester}/export.xlsx`,

  // Committee overrides
  overrides: () => get<Record<string, { decision: string; comment: string; updated_at: string }>>(
    "/overrides",
  ),
  setOverride: async (candidateId: string, decision: string, comment: string) => {
    const res = await fetch(`${BASE}/overrides/${encodeURIComponent(candidateId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_id: candidateId, decision, comment }),
    });
    if (!res.ok) throw new Error(`Failed to save override`);
    return res.json();
  },
  deleteOverride: async (candidateId: string) => {
    const res = await fetch(`${BASE}/overrides/${encodeURIComponent(candidateId)}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error(`Failed to delete override`);
    return res.json();
  },

  // Chat (streaming)
  chatStream: async (
    candidateId: string,
    message: string,
    history: { role: string; content: string }[],
    callbacks: ChatStreamCallbacks,
  ) => {
    try {
      const res = await fetch(`${BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id: candidateId, message, history }),
      });
      if (!res.ok) {
        callbacks.onError(`Chat failed: ${res.status}`);
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) {
        callbacks.onError("No response body");
        return;
      }
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value, { stream: true });
        if (text) callbacks.onToken(text);
      }
      callbacks.onDone();
    } catch (err) {
      callbacks.onError(String(err));
    }
  },
};

// Raw shapes from the API (before frontend transformation)
export interface RawCandidate {
  readonly candidate_id: string;
  readonly semester: string;
  readonly school: string;
  readonly school_country: string;
  readonly gpa: string;
  readonly gpa_max: string;
  readonly gpa_normalized: number;
  readonly gpa_grading_system: string;
  readonly gpa_confidence: number;
  readonly study_level: string;
  readonly gender: string;
  readonly status: string;
  readonly confidence: number;
  readonly verdict_pros: string[];
  readonly verdict_cons: string[];
  readonly evaluations: RawEvaluation[];
  readonly debates: RawDebate[];
  readonly moderator: {
    readonly pros: string[];
    readonly cons: string[];
    readonly decision: string;
    readonly composite: number;
    readonly debate_summary: string;
  };
  readonly final_scores: Record<string, number>;
  readonly documents: string[];
  readonly minor_recommendation?: Record<string, unknown>;
  readonly candidate_name?: string;
  readonly committee_decision?: string;
}

export interface RawEvaluation {
  readonly role: string;
  readonly decision: string;
  readonly confidence: number;
  readonly justifications: Record<string, { pros: string[]; cons: string[] }>;
  readonly scores: Record<string, number>;
  readonly document_references: { doc_type: string; note: string }[];
}

export interface RawDebate {
  readonly conflict_dimension: string;
  readonly entries: {
    readonly role: string;
    readonly round_number: number;
    readonly argument: string;
  }[];
}

export interface RawUniversity {
  readonly name: string;
  readonly country: string;
  readonly tier: string;
  readonly applicants: number;
  readonly accept_rate: number;
  readonly accepts: number;
  readonly rejects: number;
  readonly board_notes: string;
}

export interface RawCohortCandidate {
  readonly folder_name: string;
  readonly application_id: string;
  readonly last_name: string;
  readonly first_names: string;
  readonly full_name: string;
  readonly gender: string;
  readonly nationality: string;
  readonly institution_name: string;
  readonly institution_country: string;
  readonly field_of_study: string;
  readonly study_level: string;
  readonly gpa: string;
  readonly gpa_max: string;
}

export interface DossierDocument {
  readonly folder: string;
  readonly type: string;
  readonly label: string;
  readonly has_pdf: boolean;
  readonly has_text: boolean;
  readonly has_anonymized: boolean;
}
