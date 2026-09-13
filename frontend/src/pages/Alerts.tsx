import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";
import type { Alert } from "../types";
import { EmptyState, Loading } from "../components/common";
import { useLiveEvent } from "../live";

function timeAgo(iso: string): string {
  const d = new Date(iso).getTime();
  const diff = Math.max(0, Date.now() - d);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs} hr ago`;
}

const ICONS: Record<string, string> = {
  congestion: "⚠",
  signal_hold: "⛔",
  station_delay: "⏱",
};

export function Alerts() {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);

  const load = useCallback(() => {
    api.alerts().then(setAlerts).catch(() => setAlerts([]));
  }, []);

  useEffect(load, [load]);
  useLiveEvent((msg) => {
    if (msg.type === "OPERATIONAL_EVENT" || msg.type === "ETA_UPDATED") load();
  });

  if (alerts === null) return <Loading label="Loading alerts…" />;

  return (
    <div>
      <div className="results-head">
        <h2>Alerts</h2>
        <span className="muted">{alerts.length} updates</span>
      </div>

      {alerts.length === 0 ? (
        <EmptyState icon="🔔" title="No active alerts" hint="Journey updates will appear here as they happen." />
      ) : (
        <div className="card">
          {alerts.map((a) => (
            <div className="alert-item" key={a.id}>
              <div className="alert-ic">{ICONS[a.type] ?? "•"}</div>
              <div className="alert-body">
                <div className="a-title">
                  {a.title} — {a.train_number} {a.train_name}
                </div>
                <div className="a-meta">
                  {a.reason} · {timeAgo(a.timestamp)}
                </div>
                <div className="a-impact">
                  {a.previous_eta && a.new_eta && (
                    <>
                      <span className="old">{a.previous_eta}</span>
                      <span>→</span>
                      <span className="new">{a.new_eta}</span>
                    </>
                  )}
                  <span className="badge late">+{a.impact_minutes} min</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
