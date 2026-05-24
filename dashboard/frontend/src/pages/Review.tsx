import { useState, useMemo, useEffect, useRef } from "react";
import type { Status } from "../types";
import { cls, capitalize } from "../utils";
import { candidates as mockData } from "../data";
import { api, type RawCandidate } from "../api";
import { useAppContext } from "../App";
import Markdown from "react-markdown";
import { StatusPill } from "../components/StatusPill";
import { Confidence } from "../components/Confidence";
import { ScoreRow } from "../components/ScoreRow";
import { PageHead } from "../components/PageHead";
import {
  Search,
  Sort,
  Download,
  Sparkles,
  X,
  Flag,
  Check,
  Book,
  Shield,
  Fit,
  Refresh,
  Send,
  School,
  Location,
} from "../components/icons";

/* ── Types for the review page ── */
interface AgentEval {
  role: string;
  decision: string;
  confidence: number;
  scores: Record<string, number>;
  justifications: Record<string, { pros: string[]; cons: string[] }>;
}

interface DebateBlock {
  dimension: string;
  entries: { role: string; round: number; argument: string }[];
}

interface MinorRec {
  minor_name: string;
  section_code: string;
  fit_score: number;
  reasoning: string;
}

interface MinorRecommendation {
  recommended: MinorRec[];
  primary_minor: string;
}

interface ReviewCandidate {
  id: string;
  name: string;
  school: string;
  program: string;
  country: string;
  gpa: string;
  gpaDisplay: string;
  confidence: number;
  status: Status;
  pros: string[];
  cons: string[];
  finalScores: Record<string, number>;
  compositeScore: number;
  agents: AgentEval[];
  debates: DebateBlock[];
  committee_decision?: string;
  minor?: MinorRecommendation;
  primaryMinor: string;
}

function rawToReview(r: RawCandidate): ReviewCandidate {
  const hasGpa = r.gpa && r.gpa !== "N/A" && r.gpa !== "n/a";
  const hasMax = r.gpa_max && r.gpa_max !== "N/A" && r.gpa_max !== "n/a";
  const gpaDisplay = hasGpa && hasMax
    ? `${r.gpa} / ${r.gpa_max}`
    : hasGpa ? r.gpa : "";

  const agents: AgentEval[] = r.evaluations.map((ev) => ({
    role: ev.role,
    decision: ev.decision,
    confidence: ev.confidence,
    scores: ev.scores,
    justifications: ev.justifications,
  }));

  const debates: DebateBlock[] = r.debates.map((d) => ({
    dimension: d.conflict_dimension,
    entries: d.entries.map((e) => ({
      role: e.role,
      round: e.round_number,
      argument: e.argument,
    })),
  }));

  const minor = r.minor_recommendation as MinorRecommendation | undefined;
  const primaryMinor = minor?.primary_minor || minor?.recommended?.[0]?.minor_name || "";

  return {
    id: r.candidate_id,
    name: r.candidate_name || r.candidate_id.replace(/_/g, " ").replace(/^\d{4}-\d{2}-\w+\s/, "").replace(/\b\w/g, (c) => c.toUpperCase()),
    school: r.school || "Unknown",
    program: r.study_level || "",
    country: r.school_country || "",
    gpa: r.gpa || "",
    gpaDisplay,
    confidence: r.confidence,
    status: (r.status as Status) || "pending",
    pros: r.moderator.pros,
    cons: r.moderator.cons,
    finalScores: r.final_scores,
    compositeScore: r.moderator.composite,
    agents,
    debates,
    committee_decision: r.committee_decision,
    minor,
    primaryMinor,
  };
}

/* ── Status dot ── */
function StatusDot({ status }: { readonly status: Status }) {
  return <span className={cls("candidate-status-dot", status)} />;
}

/* ── Candidate row ── */
function CandidateRow({
  c,
  selected,
  onClick,
}: {
  readonly c: ReviewCandidate;
  readonly selected: boolean;
  readonly onClick: () => void;
}) {
  return (
    <div className="candidate-row" aria-selected={selected || undefined} onClick={onClick}>
      <StatusDot status={c.status} />
      <div className="c-info">
        <div className="c-name">{c.name}</div>
        <div className="c-sub">
          {c.school}
          {c.program ? ` · ${c.program}` : ""}
          {c.primaryMinor ? ` · ${c.primaryMinor}` : ""}
        </div>
      </div>
      <StatusPill status={c.status} />
      <div>
        <div className="c-gpa">{c.gpaDisplay || "\u2014"}</div>
        <div className="c-gpa-sub">
          {c.confidence ? `${Math.round(c.confidence * 100)}%` : "\u2014"}
        </div>
      </div>
    </div>
  );
}

/* ── Status filter chips ── */
function StatusFilters({
  filter,
  setFilter,
  counts,
}: {
  readonly filter: string;
  readonly setFilter: (f: string) => void;
  readonly counts: Record<string, number>;
}) {
  const opts = [
    { id: "all", label: "All" },
    { id: "admit", label: "Admit" },
    { id: "discuss", label: "Discuss" },
    { id: "reject", label: "Reject" },
    { id: "pending", label: "Pending" },
  ];
  return (
    <div className="toolbar" style={{ marginBottom: 12 }}>
      {opts.map((o) => (
        <button
          key={o.id}
          className="filter-chip"
          aria-pressed={filter === o.id || undefined}
          onClick={() => setFilter(o.id)}
        >
          {o.id !== "all" && <StatusDot status={o.id as Status} />}
          {o.label}
          <span className="count">{counts[o.id] ?? 0}</span>
        </button>
      ))}
    </div>
  );
}

/* ── Agent icons ── */
const AGENT_ICONS: Record<string, React.ComponentType<{ size?: number }>> = {
  Academic: Book,
  Research: Sparkles,
  Fit: Fit,
  Risk: Shield,
  Reference: Book,
  Motivation: Flag,
  "Devil's Advocate": Shield,
};

function decisionColor(decision: string): string {
  const d = decision.toUpperCase();
  if (d === "ACCEPT") return "var(--admit)";
  if (d === "REJECT") return "var(--reject)";
  return "var(--discuss)";
}

/* ── Full agent evaluation card with justifications ── */
function AgentDetailCard({ a }: { readonly a: AgentEval }) {
  const IconComp = AGENT_ICONS[a.role];
  const avgScore = Object.values(a.scores).length
    ? Object.values(a.scores).reduce((x, y) => x + y, 0) / Object.values(a.scores).length
    : 0;
  const pct = Math.max(0, Math.min(100, (avgScore / 10) * 100));
  const color = decisionColor(a.decision);

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: "var(--r-md)", marginBottom: 12, overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12, borderBottom: "1px solid var(--border-subtle)" }}>
        <div className="agent-icon">{IconComp ? <IconComp size={16} /> : <Sparkles size={16} />}</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{a.role} agent</div>
          <div style={{ fontSize: 11, color, fontWeight: 500, marginTop: 2 }}>{a.decision}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 16, fontWeight: 600, color }}>{avgScore.toFixed(1)}</div>
          <div style={{ fontSize: 10, color: "var(--fg-subtle)" }}>avg score</div>
        </div>
      </div>

      {/* Score bars */}
      <div style={{ padding: "8px 16px", background: "var(--bg-subtle)", borderBottom: "1px solid var(--border-subtle)" }}>
        {Object.entries(a.scores).map(([dim, val]) => (
          <ScoreRow key={dim} label={capitalize(dim.replace(/_/g, " "))} value={val} max={10} />
        ))}
      </div>

      {/* Per-dimension justifications */}
      <div style={{ padding: "12px 16px" }}>
        {Object.entries(a.justifications).map(([dim, j]) => (
          <div key={dim} style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fg-muted)", marginBottom: 6 }}>
              {capitalize(dim.replace(/_/g, " "))}
            </div>
            {j.pros.length > 0 && (
              <div style={{ marginBottom: 4 }}>
                {j.pros.map((p, i) => (
                  <div key={i} style={{ fontSize: 12, color: "var(--fg-muted)", lineHeight: 1.5, padding: "2px 0", display: "flex", gap: 6 }}>
                    <span style={{ color: "var(--admit)", flexShrink: 0 }}>+</span>
                    <span>{p}</span>
                  </div>
                ))}
              </div>
            )}
            {j.cons.length > 0 && (
              <div>
                {j.cons.map((c, i) => (
                  <div key={i} style={{ fontSize: 12, color: "var(--fg-muted)", lineHeight: 1.5, padding: "2px 0", display: "flex", gap: 6 }}>
                    <span style={{ color: "var(--reject)", flexShrink: 0 }}>-</span>
                    <span>{c}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Summary tab — Chair synthesis + final scores ── */
function SummaryTab({ c }: { readonly c: ReviewCandidate }) {
  const vals = Object.values(c.finalScores);
  const avg = vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1) : "\u2014";

  return (
    <>
      {/* Chair synthesis */}
      <div className="section">
        <div className="section-head">
          <div className="section-title">Chair synthesis</div>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: decisionColor(c.status === "admit" ? "ACCEPT" : c.status === "reject" ? "REJECT" : "DISCUSS") }}>
            composite {c.compositeScore.toFixed(1)} / 10
          </span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div>
            <div style={{ fontSize: 11, color: "var(--admit-fg)", fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Strengths · {c.pros.length}
            </div>
            {c.pros.length ? c.pros.map((p, i) => (
              <div key={i} style={{ fontSize: 12, color: "var(--fg-muted)", lineHeight: 1.6, padding: "3px 0", display: "flex", gap: 6 }}>
                <span style={{ color: "var(--admit)", flexShrink: 0, fontWeight: 600 }}>+</span>
                <span>{p}</span>
              </div>
            )) : <span style={{ fontSize: 12, color: "var(--fg-faint)" }}>None recorded</span>}
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--reject-fg)", fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Concerns · {c.cons.length}
            </div>
            {c.cons.length ? c.cons.map((p, i) => (
              <div key={i} style={{ fontSize: 12, color: "var(--fg-muted)", lineHeight: 1.6, padding: "3px 0", display: "flex", gap: 6 }}>
                <span style={{ color: "var(--reject)", flexShrink: 0, fontWeight: 600 }}>-</span>
                <span>{p}</span>
              </div>
            )) : <span style={{ fontSize: 12, color: "var(--fg-faint)" }}>None recorded</span>}
          </div>
        </div>
      </div>

      {/* Final scores (Chair's 8-dimension scores) */}
      {Object.keys(c.finalScores).length > 0 && (
        <div className="section">
          <div className="section-head">
            <div className="section-title">Final scores</div>
            <span style={{ fontSize: 11, color: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }}>avg {avg}</span>
          </div>
          <div>
            {Object.entries(c.finalScores).map(([k, v]) => (
              <ScoreRow key={k} label={capitalize(k.replace(/_/g, " "))} value={v} max={10} />
            ))}
          </div>
        </div>
      )}

      {/* Minor recommendation */}
      {c.minor && c.minor.recommended?.length > 0 && (
        <div className="section">
          <div className="section-head">
            <div className="section-title">Minor recommendation</div>
            <span style={{ fontSize: 11, color: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }}>
              primary: {c.minor.primary_minor}
            </span>
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {c.minor.recommended.map((m, i) => (
              <div key={i} style={{
                padding: "12px 14px",
                border: i === 0 ? "1.5px solid var(--accent)" : "1px solid var(--border)",
                borderRadius: "var(--r-md)",
                background: i === 0 ? "var(--accent-bg)" : "var(--bg-subtle)",
              }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>
                    {m.minor_name}
                    <span style={{ fontSize: 11, color: "var(--fg-subtle)", fontWeight: 400, marginLeft: 6 }}>
                      ({m.section_code})
                    </span>
                  </div>
                  <div style={{
                    fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600,
                    color: m.fit_score >= 8 ? "var(--admit)" : m.fit_score >= 6 ? "var(--discuss)" : "var(--fg-muted)",
                  }}>
                    {m.fit_score}/10
                  </div>
                </div>
                <div style={{ fontSize: 12, color: "var(--fg-muted)", lineHeight: 1.5 }}>
                  {m.reasoning}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick agent overview */}
      {c.agents.length > 0 && (
        <div className="section">
          <div className="section-head"><div className="section-title">Agent verdicts</div></div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8 }}>
            {c.agents.map((a, i) => {
              const avg = Object.values(a.scores).length
                ? Object.values(a.scores).reduce((x, y) => x + y, 0) / Object.values(a.scores).length : 0;
              return (
                <div key={i} style={{ padding: "10px 12px", border: "1px solid var(--border)", borderRadius: "var(--r)", background: "var(--bg-subtle)" }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "var(--fg-muted)" }}>{a.role}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: decisionColor(a.decision), marginTop: 4 }}>{a.decision}</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--fg-subtle)", marginTop: 2 }}>avg {avg.toFixed(1)}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}

/* ── Agents tab — full justifications per agent ── */
function AgentsTab({ c }: { readonly c: ReviewCandidate }) {
  return (
    <div className="section">
      <div className="section-head"><div className="section-title">Agent evaluations</div></div>
      {c.agents.length ? c.agents.map((a, i) => <AgentDetailCard key={i} a={a} />) : <div className="empty">No agent analysis yet for this candidate.</div>}
    </div>
  );
}

/* ── Debate tab — structured by conflict dimension ── */
function DebateTab({ c }: { readonly c: ReviewCandidate }) {
  const totalTurns = c.debates.reduce((n, d) => n + d.entries.length, 0);
  return (
    <div className="section">
      <div className="section-head">
        <div className="section-title">Inter-agent debates</div>
        <span style={{ fontSize: 11, color: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }}>
          {c.debates.length} conflicts · {totalTurns} turns
        </span>
      </div>
      {c.debates.length ? c.debates.map((d, di) => (
        <div key={di} style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--accent-fg)", marginBottom: 10, padding: "6px 10px", background: "var(--accent-bg)", borderRadius: "var(--r)", border: "1px solid var(--border)" }}>
            Conflict: {capitalize(d.dimension.replace(/_/g, " "))}
          </div>
          <div className="debate">
            {d.entries.map((e, ei) => (
              <div key={ei} className="debate-turn neutral">
                <div className="debate-head">
                  <span className="debate-agent">{e.role}</span>
                  <span className="debate-stance">Round {e.round}</span>
                </div>
                <div className="debate-body">{e.argument}</div>
              </div>
            ))}
          </div>
        </div>
      )) : <div className="empty">No debate transcript.</div>}
    </div>
  );
}

/* ── Chat tab with streaming LLM ── */
function ChatTab({ c }: { readonly c: ReviewCandidate }) {
  const { apiAvailable } = useAppContext();
  const [msgs, setMsgs] = useState<{ role: "user" | "assistant"; text: string }[]>([
    { role: "assistant", text: `Hi — I have full context on **${c.name}**'s anonymized dossier and AI evaluation. Ask me anything about their application.` },
  ]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const streamRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs]);

  const send = () => {
    if (!input.trim() || streaming) return;
    const userText = input;
    setInput("");

    // Add user message + empty assistant placeholder
    setMsgs((m) => [...m, { role: "user", text: userText }, { role: "assistant", text: "" }]);

    if (!apiAvailable) {
      // Fallback: no API
      setTimeout(() => {
        setMsgs((m) => {
          const updated = [...m];
          updated[updated.length - 1] = { role: "assistant", text: "Chat requires the API backend. Start it with `uv run poe dashboard`." };
          return updated;
        });
      }, 300);
      return;
    }

    setStreaming(true);

    // Build history for API (exclude the welcome message and current empty placeholder)
    const history = msgs
      .slice(1) // skip welcome
      .map((m) => ({ role: m.role, content: m.text }));

    api.chatStream(c.id, userText, history, {
      onToken: (token) => {
        setMsgs((m) => {
          const updated = [...m];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = { ...last, text: last.text + token };
          return updated;
        });
      },
      onDone: () => setStreaming(false),
      onError: (err) => {
        setMsgs((m) => {
          const updated = [...m];
          updated[updated.length - 1] = { role: "assistant", text: `Error: ${err}` };
          return updated;
        });
        setStreaming(false);
      },
    });
  };

  return (
    <div className="chat" style={{ height: "100%" }}>
      <div className="chat-stream" ref={streamRef}>
        {msgs.map((m, i) => (
          <div key={i} className={cls("chat-msg", m.role)}>
            {m.role === "assistant" ? (
              m.text ? <Markdown>{m.text}</Markdown> : <span style={{ color: "var(--fg-faint)" }}>Thinking...</span>
            ) : (
              m.text
            )}
            <div className="chat-meta">
              {m.role === "user" ? "You" : "Dossier assistant"}
            </div>
          </div>
        ))}
      </div>
      <div className="chat-input-wrap">
        <textarea
          className="chat-input"
          rows={1}
          placeholder={streaming ? "Waiting for response..." : "Ask about this candidate..."}
          value={input}
          disabled={streaming}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
        />
        <button className="btn btn-accent" onClick={send} disabled={streaming}>
          <Send size={13} /> {streaming ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}

/* ── Committee override widget ── */
function CommitteeOverridePanel({
  candidateId,
  overrides,
  onSave,
}: {
  readonly candidateId: string;
  readonly overrides: Record<string, { decision: string; comment: string; updated_at: string }>;
  readonly onSave: (id: string, decision: string, comment: string) => void;
}) {
  const existing = overrides[candidateId];
  const [decision, setDecision] = useState(existing?.decision || "");
  const [comment, setComment] = useState(existing?.comment || "");
  const [saved, setSaved] = useState(false);

  // Reset when candidate changes
  useEffect(() => {
    const ex = overrides[candidateId];
    setDecision(ex?.decision || "");
    setComment(ex?.comment || "");
    setSaved(false);
  }, [candidateId, overrides]);

  const handleSave = () => {
    if (!decision) return;
    onSave(candidateId, decision, comment);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const decisions = [
    { id: "accept", label: "Accept", color: "var(--admit)" },
    { id: "reject", label: "Reject", color: "var(--reject)" },
    { id: "waitlist", label: "Waitlist", color: "var(--discuss)" },
  ];

  return (
    <div style={{
      padding: "12px 16px",
      background: "var(--bg-subtle)",
      borderTop: "1px solid var(--border)",
      borderBottom: "1px solid var(--border)",
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fg-muted)", marginBottom: 8 }}>
        Committee decision
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
        {decisions.map((d) => (
          <button
            key={d.id}
            onClick={() => setDecision(d.id)}
            style={{
              padding: "5px 14px",
              fontSize: 12,
              fontWeight: 600,
              borderRadius: "var(--r)",
              border: decision === d.id ? `2px solid ${d.color}` : "1px solid var(--border)",
              background: decision === d.id ? `${d.color}18` : "var(--bg)",
              color: decision === d.id ? d.color : "var(--fg-muted)",
              cursor: "pointer",
            }}
          >
            {d.label}
          </button>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
        <textarea
          rows={2}
          placeholder="Add a comment (reason for decision)..."
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          style={{
            flex: 1,
            fontSize: 12,
            padding: "6px 10px",
            borderRadius: "var(--r)",
            border: "1px solid var(--border)",
            background: "var(--bg)",
            color: "var(--fg)",
            resize: "vertical",
            fontFamily: "inherit",
          }}
        />
        <button
          className="btn btn-accent btn-sm"
          onClick={handleSave}
          disabled={!decision}
          style={{ alignSelf: "flex-end" }}
        >
          {saved ? <><Check size={12} /> Saved</> : "Save"}
        </button>
      </div>
      {existing && (
        <div style={{ fontSize: 10, color: "var(--fg-faint)", marginTop: 4 }}>
          Last updated: {new Date(existing.updated_at).toLocaleString()}
        </div>
      )}
    </div>
  );
}

/* ── Detail panel ── */
function DetailPanel({
  c,
  overrides,
  onSaveOverride,
}: {
  readonly c: ReviewCandidate | undefined;
  readonly overrides: Record<string, { decision: string; comment: string; updated_at: string }>;
  readonly onSaveOverride: (id: string, decision: string, comment: string) => void;
}) {
  const { navigateToDossier } = useAppContext();
  const [tab, setTab] = useState("summary");
  if (!c) return <div className="detail-panel"><div className="empty">Select a candidate to view details.</div></div>;

  const totalDebateTurns = c.debates.reduce((n, d) => n + d.entries.length, 0);
  const tabs = [
    { id: "summary", label: "Summary" },
    { id: "agents", label: "Agents", count: c.agents.length },
    { id: "debate", label: "Debate", count: totalDebateTurns },
    { id: "chat", label: "Chat" },
  ];

  return (
    <div className="detail-panel">
      <div className="detail-head">
        <div className="detail-head-info">
          <div className="detail-id">{c.id}</div>
          <div className="detail-name">{c.name}</div>
          <div className="detail-meta">
            <span className="meta-item"><School className="icon" size={13} /> {c.school}</span>
            {c.program && <span className="meta-item"><Book className="icon" size={13} /> {c.program}</span>}
            {c.country && <span className="meta-item"><Location className="icon" size={13} /> {c.country}</span>}
            {c.gpaDisplay && <span className="meta-item" style={{ fontFamily: "var(--font-mono)" }}>GPA {c.gpaDisplay}</span>}
          </div>
          <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 12 }}>
            <StatusPill status={c.status} />
            <div style={{ flex: 1, maxWidth: 220 }}><Confidence value={c.confidence} status={c.status} /></div>
            {c.committee_decision && (
              <span style={{ fontSize: 11, color: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }}>
                Committee: {c.committee_decision}
              </span>
            )}
          </div>
        </div>
        <div className="detail-actions">
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => navigateToDossier(c.id)}
            title="Open this candidate in the Dossier Viewer"
          >
            <Book size={12} /> View Dossier
          </button>
          <a href={api.candidatePdfUrl(c.id)} className="btn btn-sm" target="_blank" rel="noreferrer">
            <Download size={12} /> PDF Report
          </a>
        </div>
      </div>
      <CommitteeOverridePanel candidateId={c.id} overrides={overrides} onSave={onSaveOverride} />
      <div className="tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.id} className="tab" role="tab" aria-selected={tab === t.id || undefined} onClick={() => setTab(t.id)}>
            {t.label}{t.count != null && <span className="tab-count">{t.count}</span>}
          </button>
        ))}
      </div>
      <div className="tab-panel">
        {tab === "summary" && <SummaryTab c={c} />}
        {tab === "agents" && <AgentsTab c={c} />}
        {tab === "debate" && <DebateTab c={c} />}
        {tab === "chat" && <ChatTab c={c} />}
      </div>
    </div>
  );
}

/* ── Review page ── */
export function ReviewPage() {
  const { apiAvailable } = useAppContext();
  const [data, setData] = useState<ReviewCandidate[]>([]);
  const [semesters, setSemesters] = useState<string[]>([]);
  const [semester, setSemester] = useState<string>("");
  const [selectedId, setSelectedId] = useState<string>("");
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [overrides, setOverrides] = useState<Record<string, { decision: string; comment: string; updated_at: string }>>({});

  // Load overrides
  useEffect(() => {
    if (!apiAvailable) return;
    api.overrides().then(setOverrides).catch(() => {});
  }, [apiAvailable]);

  const handleSaveOverride = (id: string, decision: string, comment: string) => {
    api.setOverride(id, decision, comment).then((saved) => {
      setOverrides((prev) => ({ ...prev, [id]: saved }));
    }).catch(() => {});
  };

  // Load semesters
  useEffect(() => {
    if (!apiAvailable) {
      // Use mock data — map to ReviewCandidate shape
      const mock: ReviewCandidate[] = mockData.map((c) => ({
        id: c.id, name: c.name, school: c.school, program: c.program,
        country: c.country, gpa: String(c.gpa), gpaDisplay: `${c.gpa} / ${c.gpaScale}`,
        confidence: c.confidence, status: c.status, pros: [...c.pros], cons: [...c.cons],
        finalScores: { ...c.scores }, compositeScore: 0,
        agents: c.agents.map((a) => ({
          role: a.name, decision: a.color === "admit" ? "ACCEPT" : "DISCUSS",
          confidence: a.score / 10, scores: {}, justifications: {},
        })),
        debates: [],
        primaryMinor: "",
      }));
      setData(mock);
      if (mock.length) setSelectedId(mock[0].id);
      setLoading(false);
      return;
    }
    api.semesters().then((s) => {
      setSemesters(s);
      if (s.length) setSemester(s[0]);
    });
  }, [apiAvailable]);

  // Load candidates for selected semester
  useEffect(() => {
    if (!apiAvailable || !semester) return;
    setLoading(true);
    api.candidates(semester).then((raw) => {
      const mapped = raw.map(rawToReview);
      setData(mapped);
      if (mapped.length) setSelectedId(mapped[0].id);
      setLoading(false);
    });
  }, [apiAvailable, semester]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: data.length, admit: 0, reject: 0, discuss: 0, pending: 0 };
    data.forEach((d) => { c[d.status] = (c[d.status] || 0) + 1; });
    return c;
  }, [data]);

  const filtered = useMemo(() => {
    return data.filter((c) => {
      if (filter !== "all" && c.status !== filter) return false;
      if (query && !`${c.name} ${c.school} ${c.program}`.toLowerCase().includes(query.toLowerCase())) return false;
      return true;
    });
  }, [data, filter, query]);

  const selected = data.find((c) => c.id === selectedId);

  return (
    <>
      <PageHead
        title="Review"
        sub={`${data.length} applications · ${counts.pending} pending`}
        right={
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {semesters.length > 0 && (
              <select className="select" style={{ width: "auto", height: 32 }} value={semester} onChange={(e) => setSemester(e.target.value)}>
                {semesters.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            )}
            {apiAvailable && (
              <>
                <a href={api.candidatesCsvUrl(semester)} className="btn btn-sm"><Download size={12} /> CSV</a>
                <a href={api.candidatesExcelUrl(semester)} className="btn btn-sm"><Download size={12} /> Excel</a>
              </>
            )}
          </div>
        }
      />

      <StatusFilters filter={filter} setFilter={setFilter} counts={counts} />

      <div className="review-split">
        <div className="candidate-list">
          <div className="candidate-list-head">
            <div className="search-wrap" style={{ flex: 1 }}>
              <Search className="icon" size={14} />
              <input className="input" placeholder="Search candidates..." value={query} onChange={(e) => setQuery(e.target.value)} />
            </div>
            <button className="btn btn-ghost btn-icon" title="Sort"><Sort size={14} /></button>
          </div>
          <div className="candidate-list-body">
            {loading && <div className="empty">Loading...</div>}
            {!loading && filtered.map((c) => (
              <CandidateRow key={c.id} c={c} selected={c.id === selectedId} onClick={() => setSelectedId(c.id)} />
            ))}
            {!loading && !filtered.length && <div className="empty">No candidates match.</div>}
          </div>
        </div>
        <DetailPanel c={selected} overrides={overrides} onSaveOverride={handleSaveOverride} />
      </div>
    </>
  );
}
