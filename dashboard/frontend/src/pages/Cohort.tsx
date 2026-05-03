import { useState, useMemo, useEffect } from "react";
import { cls } from "../utils";
import { api, type RawCohortCandidate } from "../api";
import { useAppContext } from "../App";
import { PageHead } from "../components/PageHead";
import { Stat } from "../components/Stat";
import { Search, Download, Grid } from "../components/icons";

/* ── SVG donut chart ── */
function Donut({
  segments,
  size = 140,
  label,
}: {
  readonly segments: { value: number; color: string; label: string }[];
  readonly size?: number;
  readonly label: string;
}) {
  const total = segments.reduce((a, s) => a + s.value, 0);
  if (total === 0) return null;
  const r = size / 2 - 14;
  const cx = size / 2;
  const cy = size / 2;
  const C = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div className="donut" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--border)" strokeWidth="14" />
        {segments.map((s, i) => {
          const len = (s.value / total) * C;
          const dasharray = `${len} ${C - len}`;
          const dashoffset = -offset;
          offset += len;
          return (
            <circle key={i} cx={cx} cy={cy} r={r} fill="none" stroke={s.color} strokeWidth="14"
              strokeDasharray={dasharray} strokeDashoffset={dashoffset}
              transform={`rotate(-90 ${cx} ${cy})`} />
          );
        })}
      </svg>
      <div className="donut-center">
        <div>
          <div className="donut-num">{total}</div>
          <div className="donut-label">{label}</div>
        </div>
      </div>
    </div>
  );
}

/* ── Horizontal bar chart ── */
function BarChart({ rows }: { readonly rows: { label: string; value: number; color?: string }[] }) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <div>
      {rows.map((r, i) => (
        <div key={i} className="bar-row">
          <span className="bar-label">{r.label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(r.value / max) * 100}%`, background: r.color || "var(--accent)" }} />
          </div>
          <span className="bar-num">{r.value}</span>
        </div>
      ))}
    </div>
  );
}

/* ── Display type for cohort candidates ── */
interface CohortRow {
  id: string;
  name: string;
  institution: string;
  country: string;
  nationality: string;
  fieldOfStudy: string;
  studyLevel: string;
  gender: string;
  gpa: string;
  gpaMax: string;
  gpaNum: number;
}

function rawToRow(r: RawCohortCandidate): CohortRow {
  const gpaNum = parseFloat(r.gpa) || 0;
  const gpaMax = parseFloat(r.gpa_max) || 0;
  return {
    id: r.application_id || r.folder_name,
    name: r.full_name,
    institution: r.institution_name,
    country: r.institution_country,
    nationality: r.nationality,
    fieldOfStudy: r.field_of_study,
    studyLevel: r.study_level,
    gender: r.gender,
    gpa: r.gpa,
    gpaMax: r.gpa_max,
    gpaNum: gpaMax > 0 ? gpaNum / gpaMax : 0,
  };
}

/* ── Cohort page ── */
export function CohortPage() {
  const { apiAvailable } = useAppContext();
  const [semesters, setSemesters] = useState<string[]>([]);
  const [semester, setSemester] = useState("");
  const [data, setData] = useState<CohortRow[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  // Load semesters
  useEffect(() => {
    if (!apiAvailable) {
      setLoading(false);
      return;
    }
    api.cohortSemesters().then((s) => {
      setSemesters(s);
      if (s.length) setSemester(s[s.length - 1]); // latest
    });
  }, [apiAvailable]);

  // Load cohort data
  useEffect(() => {
    if (!semester) return;
    setLoading(true);
    api.cohort(semester).then((raw) => {
      setData(raw.map(rawToRow));
      setLoading(false);
    });
  }, [semester]);

  const filtered = useMemo(
    () => data.filter((c) =>
      !query || `${c.name} ${c.institution} ${c.country} ${c.nationality}`.toLowerCase().includes(query.toLowerCase()),
    ),
    [data, query],
  );

  const genderSegs = useMemo(() => {
    const f = data.filter((c) => c.gender === "F").length;
    const m = data.filter((c) => c.gender === "M").length;
    return [
      { label: "Women", value: f, color: "var(--accent)" },
      { label: "Men", value: m, color: "#06b6d4" },
    ];
  }, [data]);

  const countrySegs = useMemo(() => {
    const map: Record<string, number> = {};
    data.forEach((c) => { map[c.country] = (map[c.country] || 0) + 1; });
    return Object.entries(map).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
  }, [data]);

  const studySegs = useMemo(() => {
    const map: Record<string, number> = {};
    data.forEach((c) => { map[c.studyLevel || "Unknown"] = (map[c.studyLevel || "Unknown"] || 0) + 1; });
    return Object.entries(map).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
  }, [data]);

  const total = data.length;
  const womenPct = total > 0 ? Math.round((data.filter((c) => c.gender === "F").length / total) * 100) : 0;

  if (!apiAvailable) {
    return (
      <>
        <PageHead title="Cohort Viewer" sub="Connect the API to browse cohort data" />
        <div className="empty">
          Start the API backend with <code style={{ fontFamily: "var(--font-mono)" }}>uv run poe dashboard</code> to view cohort data.
        </div>
      </>
    );
  }

  return (
    <>
      <PageHead
        title="Cohort Viewer"
        sub={`${total} candidates · ${semester}`}
        right={
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <select className="select" style={{ width: "auto", height: 32 }} value={semester} onChange={(e) => setSemester(e.target.value)}>
              {semesters.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            {semester && (
              <>
                <a href={api.cohortCsvUrl(semester)} className="btn btn-sm"><Download size={12} /> CSV</a>
                <a href={api.cohortExcelUrl(semester)} className="btn btn-sm"><Download size={12} /> Excel</a>
              </>
            )}
          </div>
        }
      />

      <div className="stat-grid">
        <Stat label="Total applicants" value={total} />
        <Stat label="Women" value={`${womenPct}%`} />
        <Stat label="Countries" value={countrySegs.length} />
        <Stat label="Institutions" value={new Set(data.map((c) => c.institution)).size} />
      </div>

      {!loading && total > 0 && (
        <div className="chart-grid">
          <div className="chart-card">
            <div className="chart-title">Gender split</div>
            <Donut segments={genderSegs} label="Total" />
            <div className="legend">
              {genderSegs.map((s, i) => (
                <div key={i} className="legend-item">
                  <span className="legend-dot" style={{ background: s.color }} />
                  <span className="legend-label">{s.label}</span>
                  <span className="legend-num">{s.value}</span>
                  <span className="legend-pct">{total > 0 ? Math.round((s.value / total) * 100) : 0}%</span>
                </div>
              ))}
            </div>
          </div>
          <div className="chart-card">
            <div className="chart-title">Country distribution</div>
            <BarChart rows={countrySegs.slice(0, 8).map((s) => ({ ...s, color: "var(--accent)" }))} />
          </div>
          <div className="chart-card">
            <div className="chart-title">Study level</div>
            <BarChart rows={studySegs.map((s) => ({ ...s, color: "#0891b2" }))} />
          </div>
        </div>
      )}

      <div className="toolbar">
        <div className="search-wrap" style={{ width: 280 }}>
          <Search className="icon" size={14} />
          <input className="input" placeholder="Search candidates..." value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }}>
          {filtered.length} / {total}
        </span>
      </div>

      <div className="table-wrap" style={{ maxHeight: "calc(100vh - 480px)", overflowY: "auto" }}>
        {loading ? <div className="empty">Loading...</div> : (
          <table className="data">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Institution</th>
                <th>Country</th>
                <th>Field of study</th>
                <th>Level</th>
                <th>Gender</th>
                <th style={{ textAlign: "right" }}>GPA</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id}>
                  <td>
                    <div className="uni-name">{c.name}</div>
                    <div className="uni-meta">{c.id}</div>
                  </td>
                  <td style={{ color: "var(--fg-muted)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.institution}</td>
                  <td style={{ color: "var(--fg-muted)" }}>{c.country}</td>
                  <td style={{ color: "var(--fg-muted)", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.fieldOfStudy}</td>
                  <td style={{ color: "var(--fg-muted)" }}>{c.studyLevel}</td>
                  <td style={{ color: "var(--fg-muted)" }}>{c.gender}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>
                    {c.gpa}{c.gpaMax ? ` / ${c.gpaMax}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
