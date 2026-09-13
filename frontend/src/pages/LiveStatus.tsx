import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";
import type { TrainSummary } from "../types";
import { TrainCard } from "../components/TrainCard";
import { EmptyState, Loading } from "../components/common";
import { useLiveEvent } from "../live";

export function LiveStatus() {
  const [trains, setTrains] = useState<TrainSummary[] | null>(null);

  const load = useCallback(() => {
    api.listTrains().then(setTrains).catch(() => setTrains([]));
  }, []);

  useEffect(load, [load]);

  // refresh the list when anything material changes over the wire
  useLiveEvent((msg) => {
    if (
      msg.type === "ETA_UPDATED" ||
      msg.type === "SIMULATION_STATE_CHANGED" ||
      msg.type === "DOWNSTREAM_IMPACT_UPDATED"
    ) {
      load();
    }
  });

  if (trains === null) return <Loading label="Loading live status…" />;

  const live = trains.filter((t) => t.is_live);
  const rest = trains.filter((t) => !t.is_live);

  return (
    <div>
      <div className="results-head">
        <h2>Live status</h2>
        <span className="muted">{live.length} running now</span>
      </div>

      {trains.length === 0 ? (
        <EmptyState title="No trains available" hint="Seed the demo data to get started." />
      ) : (
        <div className="stack">
          {live.length > 0 && (
            <div className="card">
              {live.map((t) => (
                <TrainCard key={t.id} t={t} />
              ))}
            </div>
          )}
          <div>
            <div className="section-title">All trains</div>
            <div className="card">
              {rest.map((t) => (
                <TrainCard key={t.id} t={t} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
