export type Status = "admit" | "reject" | "discuss" | "pending";
export type Gender = "M" | "F";
export type Stance = "agree" | "disagree" | "neutral";

export interface AgentAnalysis {
  readonly name: string;
  readonly verdict: string;
  readonly score: number;
  readonly color: string;
  readonly inverted?: boolean;
}

export interface DebateTurn {
  readonly agent: string;
  readonly stance: Stance;
  readonly time: string;
  readonly text: string;
}

export interface ChatMessage {
  readonly role: "user" | "assistant";
  readonly text: string;
}

export interface Candidate {
  readonly id: string;
  readonly name: string;
  readonly school: string;
  readonly program: string;
  readonly country: string;
  readonly gender: Gender;
  readonly gpa: number;
  readonly gpaScale: number;
  readonly gpaNote?: string;
  readonly confidence: number;
  readonly status: Status;
  readonly pros: readonly string[];
  readonly cons: readonly string[];
  readonly summary: string;
  readonly scores: Readonly<Record<string, number>>;
  readonly agents: readonly AgentAnalysis[];
  readonly synthesis: string;
  readonly debate: readonly DebateTurn[];
  readonly chat: readonly ChatMessage[];
}

export interface University {
  readonly name: string;
  readonly country: string;
  readonly tier: 1 | 2 | 3 | 4;
  readonly applicants: number;
  readonly admits: number;
  readonly admitRate: number;
  readonly avgGpa: number | null;
  readonly notes: string;
}

export interface DossierSection {
  readonly id: string;
  readonly title: string;
  readonly page: number;
}

export interface DossierData {
  readonly candidate: string;
  readonly sections: readonly DossierSection[];
}

export type Page = "review" | "dossier" | "tiers" | "cohort";

export type SortDir = "ascending" | "descending";

export interface SortState<K extends string = string> {
  readonly key: K;
  readonly dir: SortDir;
}
