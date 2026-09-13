import { useEffect, useRef, useState } from "react";

interface Props {
  eta: string | null;
  scheduled: string | null;
  delay: number;
  reason: string;
  previousEta?: string | null; // set when a live change just happened
  components?: Record<string, unknown>;
  scheduledOnly?: boolean; // timetable-only train (not tracked live)
}

export function ETACard({ eta, scheduled, delay, reason, previousEta, components, scheduledOnly }: Props) {
  const [bump, setBump] = useState(false);
  const prevRef = useRef<string | null>(eta);

  useEffect(() => {
    if (prevRef.current !== eta) {
      setBump(true);
      const id = setTimeout(() => setBump(false), 650);
      prevRef.current = eta;
      return () => clearTimeout(id);
    }
  }, [eta]);

  const late = delay > 0;
  const showChange = previousEta && previousEta !== eta;

  return (
    <section className="card eta-card">
      <div className="eta-label">{scheduledOnly ? "Scheduled arrival" : "Expected arrival"}</div>
      <div className={`eta-time ${bump ? "bump" : ""} ${late ? "late" : ""}`}>
        {eta ?? "—"}
      </div>

      {late && !scheduledOnly && (
        <div className="eta-delta">▲ +{delay} min vs schedule</div>
      )}

      {showChange ? (
        <div className="eta-prevnext">
          <div>
            <div className="k">Previous ETA</div>
            <div className="v old">{previousEta}</div>
          </div>
          <div>
            <div className="k">Updated ETA</div>
            <div className="v">{eta}</div>
          </div>
        </div>
      ) : (
        <div className="eta-prevnext">
          <div>
            <div className="k">Scheduled arrival</div>
            <div className="v">{scheduled ?? "—"}</div>
          </div>
        </div>
      )}

      <div className="eta-reason">{reason}</div>

      {components && (
        <details className="eta-components">
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>
            How this ETA is calculated
          </summary>
          <div style={{ marginTop: 10 }}>
            <div className="cr">
              <span>Scheduled arrival</span>
              <b>{String(components.scheduled_arrival ?? "—")}</b>
            </div>
            <div className="cr">
              <span>Current delay</span>
              <b>+{String(components.current_delay ?? 0)} min</b>
            </div>
            <div className="cr">
              <span>Operational impact (congestion etc.)</span>
              <b>+{String(components.operational_impact ?? 0)} min</b>
            </div>
            <div className="cr">
              <span>Historical avg delay (context)</span>
              <b>{String(components.historical_avg_delay ?? 0)} min</b>
            </div>
            <div className="cr" style={{ marginTop: 6, color: "var(--ink-2)" }}>
              <span>Applied delay</span>
              <b>+{String(components.applied_delay ?? 0)} min</b>
            </div>
          </div>
        </details>
      )}
    </section>
  );
}
