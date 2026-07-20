"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";

const KIND_LABEL = { quote: "Quote", reprice: "Reprice", reorder: "Production" };
const BAND_LABEL = {
  autopilot: "Autopilot",
  soft_review: "Review",
  human_approval: "Held",
  no_discount: "List price",
  no_change: "No change",
  needs_clarification: "Clarification",
  sent: "Sent",
  pending_approval: "Held",
  error: "Error",
};

const PRESETS = [
  {
    label: "Simple quote",
    name: "Marcus Webb",
    email: "marcus.demo",
    subject: "Quote request — AeroBuds X2",
    body: (n) => `Hi, I'm looking to buy the AeroBuds X2 in Black, ${n} units. Can you send me a quote?`,
  },
  {
    label: "Aggressive negotiation",
    name: "Tomás Ferreyra",
    email: "tomas.demo",
    subject: "Large order — BoomCube Mini",
    body: (n) =>
      `Hi, I want to order ${n} units of the BoomCube Mini speaker in black. I need a 22% discount to close the deal today.`,
  },
  {
    label: "Ambiguous product",
    name: "Daniel Osei",
    email: "daniel.demo",
    subject: "Which earbuds do you have?",
    body: () =>
      `Hi, I saw your AeroBuds listing but I'm not sure which version — is there a noise cancelling one? Can you tell me the difference?`,
  },
];

function Stamp({ band }) {
  if (!band) return null;
  const cls = band.replace(/[^a-z_]/g, "");
  return <span className={`stamp ${cls}`}>{BAND_LABEL[band] || band}</span>;
}

function StatLedger({ stats }) {
  const cells = [
    ["Processed today", stats.processed],
    ["Auto-approved", stats.autopilot],
    ["Awaiting your signature", stats.pending],
    ["Active SKUs", stats.skus],
  ];
  return (
    <div className="ledger">
      {cells.map(([label, num]) => (
        <div className="ledger-cell" key={label}>
          <div className="ledger-num">{num ?? "—"}</div>
          <div className="ledger-label">{label}</div>
        </div>
      ))}
    </div>
  );
}

function approvalTitle(item) {
  if (item.kind === "quote") {
    return `${item.buyer_name || "Buyer"} — ${item.product_line || ""} (${item.variant || ""})`;
  }
  return `${item.product_line || ""} (${item.variant || ""})`;
}

function approvalMeta(item) {
  if (item.kind === "quote") {
    return `${item.quantity ?? "?"} units · list $${item.list_price ?? "?"} · asking ${item.requested_discount_pct ?? "?"}%`;
  }
  if (item.kind === "reprice") {
    return `$${item.current_price_usd} → $${item.recommended_price_usd} · deviation ${item.deviation_pct}%`;
  }
  if (item.kind === "reorder") {
    return `stock ${item.current_stock} · produce ${item.recommended_qty} units`;
  }
  return "";
}

function approvalUnits(item) {
  if (item.kind === "quote") return item.quantity ?? null;
  if (item.kind === "reorder") return item.recommended_qty ?? null;
  return null;
}

function ApprovalCard({ item, onDecision, busy }) {
  return (
    <div className="approval-card">
      <div className="approval-kind">{KIND_LABEL[item.kind] || item.kind || "—"}</div>
      <div className="approval-body">
        <div className="title">{approvalTitle(item)}</div>
        <div className="meta">{approvalMeta(item)}</div>
        {item.reasoning && <div className="reasoning">{item.reasoning}</div>}
        {item.draft_memo && <div className="reasoning">{item.draft_memo}</div>}
      </div>
      <div className="approval-actions">
        <button className="btn approve" disabled={busy} onClick={() => onDecision(item.approval_id, true)}>
          Approve
        </button>
        <button className="btn reject" disabled={busy} onClick={() => onDecision(item.approval_id, false)}>
          Reject
        </button>
      </div>
    </div>
  );
}

function ApprovalFilterBar({ approvals, kindFilter, setKindFilter, langFilter, setLangFilter, sortBy, setSortBy, visibleCount }) {
  const languages = useMemo(() => {
    const set = new Set(approvals.map((a) => a.language).filter(Boolean));
    return Array.from(set).sort();
  }, [approvals]);

  function toggleKind(k) {
    setKindFilter((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  }

  return (
    <div className="filter-bar">
      {Object.entries(KIND_LABEL).map(([k, label]) => (
        <button
          key={k}
          className={`filter-chip ${kindFilter.has(k) ? "active" : ""}`}
          onClick={() => toggleKind(k)}
          type="button"
        >
          {label}
        </button>
      ))}

      <select className="filter-select" value={langFilter} onChange={(e) => setLangFilter(e.target.value)}>
        <option value="all">All languages</option>
        {languages.map((l) => (
          <option key={l} value={l}>
            {l.toUpperCase()}
          </option>
        ))}
      </select>

      <select className="filter-select" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
        <option value="none">No sorting</option>
        <option value="qty_desc">Most units first</option>
        <option value="qty_asc">Fewest units first</option>
      </select>

      <span className="filter-spacer" />
      <span className="filter-count">{visibleCount} visible</span>
    </div>
  );
}

function ActivityTable({ items }) {
  if (!items.length) {
    return (
      <div className="empty-state">
        No activity yet. Send a test email above, or run run_demo.py.
      </div>
    );
  }
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Buyer</th>
            <th>Language</th>
            <th>Product</th>
            <th>Qty</th>
            <th>Final price</th>
            <th>Band</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => {
            const li = r.line_items?.[0];
            const hasProduct = li?.product_line;
            return (
              <tr key={r.email_id}>
                <td className="buyer">{r.buyer_name}</td>
                <td>
                  <span className="tag-lang">{r.language}</span>
                </td>
                <td className="mono">{hasProduct ? `${li.product_line} (${li.variant})` : "—"}</td>
                <td className="mono">{li?.quantity ?? "—"}</td>
                <td className="mono">
                  {r.decision?.final_unit_price_usd != null ? `$${r.decision.final_unit_price_usd}` : "—"}
                </td>
                <td>
                  <Stamp band={r.decision?.band || r.status} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CatalogTable({ items }) {
  if (!items.length) {
    return <div className="empty-state">Catalog is empty. Run seed_tablestore.py.</div>;
  }
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>SKU</th>
            <th>Product</th>
            <th>Variant</th>
            <th>Price</th>
            <th>Stock</th>
            <th>MOQ</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.sku_id}>
              <td className="mono">{it.sku_id}</td>
              <td>{it.product_line}</td>
              <td className="mono">{it.variant}</td>
              <td className="mono">${it.unit_price_usd}</td>
              <td className="mono">{it.stock_qty}</td>
              <td className="mono">{it.moq}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LiveIntake({ onProcessed }) {
  const [form, setForm] = useState({ name: "", email: "", subject: "", body: "" });
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  function applyPreset(preset) {
    const n = 100 + Math.floor(Math.random() * 300);
    setForm({
      name: preset.name,
      email: `${preset.email}+${Date.now()}@example.com`,
      subject: preset.subject,
      body: preset.body(n),
    });
    setResult(null);
    setError(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.name || !form.email || !form.subject || !form.body) return;
    setSending(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/proxy/process-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email_id: `live-${Date.now()}`,
          buyer_name: form.name,
          buyer_email: form.email,
          subject: form.subject,
          body: form.body,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        setError(data.error || "The backend returned an error.");
      } else {
        setResult(data);
        onProcessed();
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="intake">
      <div className="intake-presets">
        {PRESETS.map((p) => (
          <button key={p.label} type="button" className="btn preset" onClick={() => applyPreset(p)}>
            {p.label}
          </button>
        ))}
      </div>
      <form className="intake-form" onSubmit={handleSubmit}>
        <div className="intake-row">
          <input
            className="intake-input"
            placeholder="Buyer name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <input
            className="intake-input"
            placeholder="Buyer email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </div>
        <input
          className="intake-input"
          placeholder="Subject"
          value={form.subject}
          onChange={(e) => setForm({ ...form, subject: e.target.value })}
        />
        <textarea
          className="intake-input intake-textarea"
          placeholder="Email body — any language"
          rows={3}
          value={form.body}
          onChange={(e) => setForm({ ...form, body: e.target.value })}
        />
        <button className="btn approve intake-submit" type="submit" disabled={sending}>
          {sending ? "Processing with Qwen…" : "Send email to agent"}
        </button>
      </form>

      {error && <div className="intake-result intake-error">{error}</div>}

      {result && (
        <div className="intake-result">
          <div className="intake-result-head">
            <Stamp band={result.decision?.band || result.status} />
            <span className="section-sub">{result.extracted?.intent}</span>
          </div>
          {result.status === "needs_clarification" ? (
            <div className="reasoning">
              The agent needs clarification: {result.line_items?.[0]?.clarification_reason}
              {result.line_items?.[0]?.candidate_variants?.length > 0 &&
                ` (options: ${result.line_items[0].candidate_variants.join(", ")})`}
            </div>
          ) : (
            <>
              {result.decision?.reasoning && <div className="reasoning">{result.decision.reasoning}</div>}
              {result.reply_draft && <div className="intake-draft">{result.reply_draft}</div>}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function Page() {
  const [approvals, setApprovals] = useState([]);
  const [activity, setActivity] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [online, setOnline] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [lastSync, setLastSync] = useState(null);
  const [theme, setTheme] = useState("dark");
  const pollRef = useRef(null);

  const [kindFilter, setKindFilter] = useState(new Set(["quote", "reprice", "reorder"]));
  const [langFilter, setLangFilter] = useState("all");
  const [sortBy, setSortBy] = useState("none");

  useEffect(() => {
    const saved = window.localStorage.getItem("tradepilot-theme");
    const initial = saved || "dark";
    setTheme(initial);
    document.documentElement.setAttribute("data-theme", initial);
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    window.localStorage.setItem("tradepilot-theme", next);
  }

  const loadAll = useCallback(async () => {
    try {
      const [aRes, actRes, cRes] = await Promise.all([
        fetch("/api/proxy/approvals", { cache: "no-store" }).then((r) => r.json()),
        fetch("/api/proxy/activity", { cache: "no-store" }).then((r) => r.json()),
        fetch("/api/proxy/catalog", { cache: "no-store" }).then((r) => r.json()),
      ]);
      setApprovals(aRes.pending || []);
      setActivity(actRes.items || []);
      setCatalog(cRes.items || []);
      setOnline(true);
      setLastSync(new Date());
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
    pollRef.current = setInterval(loadAll, 8000);
    return () => clearInterval(pollRef.current);
  }, [loadAll]);

  async function handleDecision(approvalId, approved) {
    setBusyId(approvalId);
    try {
      await fetch(`/api/proxy/approvals/${approvalId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved }),
      });
      await loadAll();
    } finally {
      setBusyId(null);
    }
  }

  const visibleApprovals = useMemo(() => {
    let list = approvals.filter((a) => kindFilter.has(a.kind));
    if (langFilter !== "all") {
      list = list.filter((a) => a.language === langFilter);
    }
    if (sortBy !== "none") {
      list = [...list].sort((a, b) => {
        const ua = approvalUnits(a) ?? -1;
        const ub = approvalUnits(b) ?? -1;
        return sortBy === "qty_desc" ? ub - ua : ua - ub;
      });
    }
    return list;
  }, [approvals, kindFilter, langFilter, sortBy]);

  const stats = {
    processed: activity.length || undefined,
    autopilot: activity.filter((a) => a.decision?.band === "autopilot").length || undefined,
    pending: approvals.length,
    skus: catalog.length || undefined,
  };

  return (
    <main className="shell">
      <header className="header">
        <div>
          <div className="wordmark">
            <span className="mark" />
            TradePilot
          </div>
          <div className="seller-line">Shenzhen Aurora Audio Co. · seller_a · ap-southeast-1</div>
        </div>
        <div className="header-right">
          <button className="theme-toggle" onClick={toggleTheme} type="button">
            {theme === "dark" ? "☀ light" : "● dark"}
          </button>
          <button className="btn" onClick={loadAll} title="Refresh now">
            ↻ Refresh {lastSync ? `· ${lastSync.toLocaleTimeString()}` : ""}
          </button>
          <span className="status-pill">
            <span className={`status-dot ${online === null ? "" : online ? "ok" : "err"}`} />
            {online === null ? "connecting…" : online ? "agent online" : "backend unreachable"}
          </span>
        </div>
      </header>

      <StatLedger stats={stats} />

      <section className="section">
        <div className="section-head">
          <span className="section-title">Inbox — send a test email</span>
          <span className="section-sub">live processing, not pre-baked</span>
        </div>
        <LiveIntake onProcessed={loadAll} />
      </section>

      <section className="section">
        <div className="section-head">
          <span className="section-title">Customs — pending your signature</span>
          <span className="section-sub">{approvals.length} waiting</span>
        </div>
        {approvals.length > 0 && (
          <ApprovalFilterBar
            approvals={approvals}
            kindFilter={kindFilter}
            setKindFilter={setKindFilter}
            langFilter={langFilter}
            setLangFilter={setLangFilter}
            sortBy={sortBy}
            setSortBy={setSortBy}
            visibleCount={visibleApprovals.length}
          />
        )}
        {approvals.length === 0 ? (
          <div className="empty-state">Nothing on hold right now. The agent is running on autopilot.</div>
        ) : visibleApprovals.length === 0 ? (
          <div className="empty-state">No pending items match the active filters.</div>
        ) : (
          visibleApprovals.map((item) => (
            <ApprovalCard
              key={item.approval_id}
              item={item}
              onDecision={handleDecision}
              busy={busyId === item.approval_id}
            />
          ))
        )}
      </section>

      <section className="section">
        <div className="section-head">
          <span className="section-title">Activity manifest</span>
          <span className="section-sub">last {activity.length}</span>
        </div>
        <ActivityTable items={activity} />
      </section>

      <section className="section">
        <div className="section-head">
          <span className="section-title">Live catalog</span>
          <span className="section-sub">Tablestore · seller_a</span>
        </div>
        <CatalogTable items={catalog} />
      </section>

      <footer className="foot">
        <span>TradePilot — Qwen Cloud Hackathon · Track 4</span>
        <span>Alibaba Cloud: Model Studio · Tablestore · Function Compute</span>
      </footer>
    </main>
  );
}
