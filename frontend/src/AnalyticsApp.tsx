import { useEffect, useState } from "react";
import { fetchAnalyticsSummary, type AnalyticsSummary } from "./api";

const STATUS_DOT: Record<string, string> = {
  valid: "good",
  invalid: "bad",
  pending_validation: "neutral",
  received: "neutral",
  validated: "neutral",
  pending_approval: "neutral",
  exception_workflow: "attention",
  posted: "good",
  rejected: "bad",
  returned_to_vendor: "bad",
  error: "bad",
  warning: "attention",
};

export function AnalyticsApp() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchAnalyticsSummary()
      .then((body) => {
        if (!cancelled) setSummary(body);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load analytics.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <section className="section">
        <h2 className="section-title">Invoices by lifecycle status</h2>
        <StatusBars counts={summary?.status_counts ?? []} />
      </section>

      <section className="section">
        <h2 className="section-title">Top exception reasons</h2>
        <table className="ledger">
          <thead>
            <tr>
              <th>Step</th>
              <th>Rule</th>
              <th className="num">Count</th>
            </tr>
          </thead>
          <tbody>
            <ExceptionRows reasons={summary?.exception_reasons ?? []} loaded={summary !== null} />
          </tbody>
        </table>
      </section>

      <section className="section">
        <h2 className="section-title">Agent usage by day</h2>
        <table className="ledger">
          <thead>
            <tr>
              <th>Date</th>
              <th className="num">Investigations</th>
              <th className="num">Tokens</th>
              <th className="num">Est. cost (USD)</th>
            </tr>
          </thead>
          <tbody>
            <UsageRows days={summary?.usage_by_day ?? []} loaded={summary !== null} />
          </tbody>
        </table>
        <p className="cost-note">Cost is an estimate from illustrative per-token rates, not an actual billed amount.</p>
      </section>

      {error && <p className="error-text">{error}</p>}
    </>
  );
}

function StatusBars({ counts }: { counts: AnalyticsSummary["status_counts"] }) {
  if (counts.length === 0) return <p className="muted">No invoices yet.</p>;
  const max = Math.max(...counts.map((c) => c.count));
  return (
    <>
      {counts.map((c) => {
        const status = c.decision_status || "unknown";
        const dotClass = STATUS_DOT[status] || "neutral";
        const pct = max > 0 ? Math.round((c.count / max) * 100) : 0;
        return (
          <div className="bar-row" key={status}>
            <span className="bar-label mono">{status}</span>
            <span className="bar-track">
              <span className={`bar-fill ${dotClass}`} style={{ width: `${pct}%` }} />
            </span>
            <span className="bar-count mono">{c.count}</span>
          </div>
        );
      })}
    </>
  );
}

function ExceptionRows({ reasons, loaded }: { reasons: AnalyticsSummary["exception_reasons"]; loaded: boolean }) {
  if (!loaded) return null;
  if (reasons.length === 0) {
    return (
      <tr>
        <td colSpan={3} className="muted">
          No validation issues recorded.
        </td>
      </tr>
    );
  }
  return (
    <>
      {reasons.map((r, i) => (
        <tr key={`${r.step}-${r.rule_code}-${i}`}>
          <td className="mono">{r.step}</td>
          <td className="mono">{r.rule_code}</td>
          <td className="num mono">{r.count}</td>
        </tr>
      ))}
    </>
  );
}

function UsageRows({ days, loaded }: { days: AnalyticsSummary["usage_by_day"]; loaded: boolean }) {
  if (!loaded) return null;
  if (days.length === 0) {
    return (
      <tr>
        <td colSpan={4} className="muted">
          No agent investigations recorded.
        </td>
      </tr>
    );
  }
  return (
    <>
      {days.map((d) => (
        <tr key={d.date}>
          <td className="mono">{d.date}</td>
          <td className="num mono">{d.investigations}</td>
          <td className="num mono">{d.total_tokens}</td>
          <td className="num mono">${d.estimated_cost_usd}</td>
        </tr>
      ))}
    </>
  );
}
