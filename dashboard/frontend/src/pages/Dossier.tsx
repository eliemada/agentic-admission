import { useState, useEffect } from "react";
import Markdown from "react-markdown";
import { api, type DossierDocument } from "../api";
import { useAppContext } from "../App";
import { PageHead } from "../components/PageHead";
import { Download, Check } from "../components/icons";

export function DossierPage() {
  const { apiAvailable } = useAppContext();
  const [semesters, setSemesters] = useState<string[]>([]);
  const [semester, setSemester] = useState("");
  const [candidates, setCandidates] = useState<string[]>([]);
  const [candidate, setCandidate] = useState("");
  const [documents, setDocuments] = useState<DossierDocument[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DossierDocument | null>(null);
  const [textContent, setTextContent] = useState("");
  const [anonContent, setAnonContent] = useState("");
  const [viewMode, setViewMode] = useState<"text" | "anonymized" | "pdf">("text");

  // Load semesters
  useEffect(() => {
    if (!apiAvailable) return;
    api.dossierSemesters().then((s) => {
      setSemesters(s);
      if (s.length) setSemester(s[s.length - 1]); // default to latest
    });
  }, [apiAvailable]);

  // Load candidates for semester
  useEffect(() => {
    if (!semester) return;
    api.dossierCandidates(semester).then((c) => {
      setCandidates(c);
      if (c.length) setCandidate(c[0]);
    });
  }, [semester]);

  // Load documents for candidate
  useEffect(() => {
    if (!semester || !candidate) return;
    api.dossierDocuments(semester, candidate).then((d) => {
      setDocuments(d);
      if (d.length) setSelectedDoc(d[0]);
    });
  }, [semester, candidate]);

  // Load text content for selected document
  useEffect(() => {
    if (!semester || !candidate || !selectedDoc) return;
    setTextContent("");
    setAnonContent("");

    if (selectedDoc.has_text) {
      api.dossierText(semester, candidate, selectedDoc.folder)
        .then((r) => setTextContent(r.content))
        .catch(() => setTextContent("(No extracted text available)"));
    }
    if (selectedDoc.has_anonymized) {
      api.dossierAnonymized(semester, candidate, selectedDoc.folder)
        .then((r) => setAnonContent(r.content))
        .catch(() => setAnonContent("(No anonymized text available)"));
    }
  }, [semester, candidate, selectedDoc]);

  if (!apiAvailable) {
    return (
      <>
        <PageHead title="Dossier Viewer" sub="Connect the API to browse real dossiers" />
        <div className="empty">
          Start the API backend with <code style={{ fontFamily: "var(--font-mono)" }}>uv run poe dashboard</code> to browse dossiers.
        </div>
      </>
    );
  }

  const pdfUrl = selectedDoc && selectedDoc.has_pdf
    ? api.dossierPdfUrl(semester, candidate, selectedDoc.folder)
    : null;

  return (
    <>
      <PageHead
        title="Dossier Viewer"
        sub={candidate ? `${candidate} · ${semester}` : "Select a candidate"}
        right={
          <div style={{ display: "flex", gap: 8 }}>
            {pdfUrl && (
              <a href={pdfUrl} target="_blank" rel="noreferrer" className="btn btn-sm">
                <Download size={12} /> PDF
              </a>
            )}
            <button className="btn btn-sm btn-primary"><Check size={12} /> Mark reviewed</button>
          </div>
        }
      />

      <div className="dossier">
        {/* Left: navigation */}
        <div className="dossier-panel">
          <div className="card-head" style={{ borderBottom: "1px solid var(--border)" }}>
            <div style={{ width: "100%" }}>
              <div className="card-title">Navigation</div>
              <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
                <select className="select" value={semester} onChange={(e) => setSemester(e.target.value)}>
                  {semesters.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <select className="select" value={candidate} onChange={(e) => setCandidate(e.target.value)}>
                  {candidates.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>
          </div>
          <div className="dossier-toc">
            {documents.map((d) => {
              // Extract the number prefix and a cleaner label from the folder name
              const match = d.folder.match(/^(\d+)\s*-\s*(.+?)(?:_[A-Z]\d+)?$/);
              const num = match ? match[1] : "";
              const shortLabel = d.label + (d.folder.includes("Referent") ? ` ${d.folder.match(/#(\d)/)?.[1] || ""}` : "");
              return (
                <div
                  key={d.folder}
                  className="toc-item"
                  aria-current={selectedDoc?.folder === d.folder || undefined}
                  onClick={() => setSelectedDoc(d)}
                >
                  <span style={{ display: "flex", gap: 6, alignItems: "center", minWidth: 0 }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--fg-faint)", flexShrink: 0 }}>{num}</span>
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{shortLabel}</span>
                  </span>
                  <span className="pg" style={{ fontSize: 9, flexShrink: 0 }}>
                    {[d.has_pdf && "PDF", d.has_text && "TXT"].filter(Boolean).join(" ")}
                  </span>
                </div>
              );
            })}
            {!documents.length && <div className="empty">No documents found.</div>}
          </div>
        </div>

        {/* Center: document content */}
        <div className="dossier-panel">
          <div className="card-head" style={{ justifyContent: "space-between" }}>
            <div>
              <div className="card-title">{selectedDoc?.label || "Select a document"}</div>
              <div className="card-sub">{selectedDoc?.folder || ""}</div>
            </div>
            <div style={{ display: "flex", gap: 4 }}>
              {["text", "anonymized", "pdf"].map((m) => (
                <button
                  key={m}
                  className={`btn btn-sm ${viewMode === m ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setViewMode(m as typeof viewMode)}
                >
                  {m === "text" ? "Extracted" : m === "anonymized" ? "Anonymized" : "PDF"}
                </button>
              ))}
            </div>
          </div>

          {viewMode === "pdf" && pdfUrl ? (
            <iframe
              src={pdfUrl}
              style={{ flex: 1, border: "none", width: "100%", minHeight: 600 }}
              title="PDF viewer"
            />
          ) : (
            <div className="dossier-doc">
              {viewMode === "text" && (textContent ? (
                <Markdown>{textContent}</Markdown>
              ) : (
                <div className="empty">No extracted text available for this document.</div>
              ))}
              {viewMode === "anonymized" && (anonContent ? (
                <Markdown>{anonContent}</Markdown>
              ) : (
                <div className="empty">No anonymized text available for this document.</div>
              ))}
            </div>
          )}
        </div>

        {/* Right: document info */}
        <div className="dossier-panel">
          <div className="card-head">
            <div>
              <div className="card-title">Document info</div>
              <div className="card-sub">{documents.length} documents</div>
            </div>
          </div>
          <div style={{ padding: 16, overflowY: "auto" }}>
            <div className="section">
              <div className="section-title" style={{ marginBottom: 8 }}>Available documents</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {documents.map((d) => (
                  <div
                    key={d.folder}
                    style={{
                      fontSize: 12,
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "4px 0",
                      color: "var(--fg-muted)",
                    }}
                  >
                    <span>{d.label}</span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--fg-subtle)" }}>
                      {[d.has_pdf && "PDF", d.has_text && "TXT", d.has_anonymized && "ANON"].filter(Boolean).join(" · ")}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="section">
              <div className="section-title" style={{ marginBottom: 8 }}>Notes</div>
              <textarea
                className="chat-input"
                rows={4}
                placeholder="Add reviewer note..."
                style={{ minHeight: 80 }}
              />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
