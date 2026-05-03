import { useState, useMemo, useEffect } from "react";
import { api, type RawUniversity } from "../api";
import { useAppContext } from "../App";
import { universities as mockData } from "../data";
import { PageHead } from "../components/PageHead";
import { Stat } from "../components/Stat";
import { Search, Download, Plus, Filter, Columns, Check, Edit } from "../components/icons";

type SortDir = "ascending" | "descending";

interface DisplayUni {
  name: string;
  country: string;
  tier: string;
  applicants: number;
  admits: number;
  admitRate: number;
  avgGpa: number | null;
  notes: string;
}

function rawToDisplay(r: RawUniversity): DisplayUni {
  const total = r.applicants || 0;
  const admits = r.accepts || 0;
  return {
    name: r.name,
    country: r.country,
    tier: r.tier || "X",
    applicants: total,
    admits,
    admitRate: total > 0 ? admits / total : 0,
    avgGpa: null,
    notes: r.board_notes || "",
  };
}

const TIER_COLORS: Record<string, string> = {
  A: "tier-1",
  B: "tier-2",
  C: "tier-3",
  X: "tier-4",
  "1": "tier-1",
  "2": "tier-2",
  "3": "tier-3",
  "4": "tier-4",
};

function TierPill({ tier }: { readonly tier: string }) {
  const cls = TIER_COLORS[tier] || "tier-4";
  const label = tier.length === 1 && "ABCX".includes(tier) ? tier : `T${tier}`;
  return (
    <span className={`tier-pill ${cls}`}>
      <span className="dot" />
      {label}
    </span>
  );
}

type SortKey = keyof DisplayUni;

export function TiersPage() {
  const { apiAvailable } = useAppContext();
  const [data, setData] = useState<DisplayUni[]>([]);
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: "tier", dir: "ascending" });
  const [editing, setEditing] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!apiAvailable) {
      // Use mock data (numeric tiers)
      setData(mockData.map((u) => ({ ...u, tier: String(u.tier), avgGpa: u.avgGpa })));
      setLoading(false);
      return;
    }
    api.universities().then((raw) => {
      setData(raw.map(rawToDisplay));
      setLoading(false);
    });
  }, [apiAvailable]);

  const sorted = useMemo(() => {
    const filtered = data.filter(
      (u) =>
        !query ||
        u.name.toLowerCase().includes(query.toLowerCase()) ||
        u.country.toLowerCase().includes(query.toLowerCase()),
    );
    return [...filtered].sort((a, b) => {
      const va = a[sort.key];
      const vb = b[sort.key];
      if (va === vb) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const r = va > vb ? 1 : -1;
      return sort.dir === "ascending" ? r : -r;
    });
  }, [data, sort, query]);

  const toggleSort = (key: SortKey) => {
    setSort((s) => (s.key === key ? { key, dir: s.dir === "ascending" ? "descending" : "ascending" } : { key, dir: "ascending" }));
  };

  const sortAttr = (key: SortKey): SortDir | undefined => (sort.key === key ? sort.dir : undefined);

  const updateTier = (name: string, tier: string) => {
    setData((d) => d.map((u) => (u.name === name ? { ...u, tier } : u)));
    if (apiAvailable) {
      api.updateTier(name, tier).catch(console.error);
    }
  };

  const tierCounts = useMemo(() => {
    const c: Record<string, number> = { A: 0, B: 0, C: 0, X: 0, "1": 0, "2": 0, "3": 0, "4": 0 };
    data.forEach((u) => { c[u.tier] = (c[u.tier] || 0) + 1; });
    return c;
  }, [data]);

  const tierACount = (tierCounts["A"] || 0) + (tierCounts["1"] || 0);
  const tierBCount = (tierCounts["B"] || 0) + (tierCounts["2"] || 0);
  const tierOther = data.length - tierACount - tierBCount;

  return (
    <>
      <PageHead
        title="University Tiers"
        sub={`${data.length} institutions · calibration applied across all admission decisions`}
        right={
          <div style={{ display: "flex", gap: 8 }}>
            <a href={api.universitiesCsvUrl()} className="btn btn-sm"><Download size={12} /> CSV</a>
            <a href={api.universitiesExcelUrl()} className="btn btn-sm"><Download size={12} /> Excel</a>
          </div>
        }
      />

      <div className="stat-grid">
        <Stat label="Institutions" value={data.length} />
        <Stat label="Tier A / T1" value={tierACount} unit={`/ ${data.length}`} />
        <Stat label="Tier B / T2" value={tierBCount} unit={`/ ${data.length}`} />
        <Stat label="Other" value={tierOther} unit={`/ ${data.length}`} />
      </div>

      <div className="toolbar">
        <div className="search-wrap" style={{ width: 280 }}>
          <Search className="icon" size={14} />
          <input className="input" placeholder="Search institutions or countries..." value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }}>
          {sorted.length} / {data.length}
        </span>
      </div>

      <div className="table-wrap" style={{ maxHeight: "calc(100vh - 340px)", overflowY: "auto" }}>
        {loading ? <div className="empty">Loading...</div> : (
          <table className="data">
            <thead>
              <tr>
                <th aria-sort={sortAttr("name")} onClick={() => toggleSort("name")}>Institution</th>
                <th aria-sort={sortAttr("country")} onClick={() => toggleSort("country")}>Country</th>
                <th aria-sort={sortAttr("tier")} onClick={() => toggleSort("tier")}>Tier</th>
                <th aria-sort={sortAttr("applicants")} onClick={() => toggleSort("applicants")} style={{ textAlign: "right" }}>Applicants</th>
                <th aria-sort={sortAttr("admits")} onClick={() => toggleSort("admits")} style={{ textAlign: "right" }}>Admits</th>
                <th aria-sort={sortAttr("admitRate")} onClick={() => toggleSort("admitRate")} style={{ textAlign: "right" }}>Admit %</th>
                <th>Notes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((u) => (
                <tr key={u.name} className={editing === u.name ? "expanded" : ""}>
                  <td><div className="uni-name">{u.name}</div></td>
                  <td><span style={{ color: "var(--fg-muted)" }}>{u.country}</span></td>
                  <td>
                    {editing === u.name ? (
                      <select className="select" style={{ height: 26, padding: "0 6px", fontSize: 12, width: "auto" }}
                        value={u.tier} onChange={(e) => updateTier(u.name, e.target.value)}>
                        <option value="A">A</option>
                        <option value="B">B</option>
                        <option value="C">C</option>
                        <option value="X">X</option>
                      </select>
                    ) : (
                      <TierPill tier={u.tier} />
                    )}
                  </td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>{u.applicants}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>{u.admits}</td>
                  <td style={{ textAlign: "right" }}>
                    <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <div style={{ width: 40, height: 4, background: "var(--bg-subtle)", borderRadius: 999, overflow: "hidden" }}>
                        <div style={{ width: `${u.admitRate * 100}%`, height: "100%", background: "var(--accent)", borderRadius: 999 }} />
                      </div>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontVariantNumeric: "tabular-nums", minWidth: 36 }}>
                        {Math.round(u.admitRate * 100)}%
                      </span>
                    </div>
                  </td>
                  <td style={{ color: "var(--fg-subtle)", fontSize: 12, maxWidth: 320 }}>
                    {u.notes || <span style={{ color: "var(--fg-faint)" }}>{"\u2014"}</span>}
                  </td>
                  <td>
                    <button className="btn btn-sm btn-ghost" onClick={() => setEditing(editing === u.name ? null : u.name)}>
                      {editing === u.name ? <Check size={12} /> : <Edit size={12} />}
                    </button>
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
