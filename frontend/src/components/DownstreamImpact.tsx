import type { AffectedTrain } from "../types";

interface Props {
  sourceTrain: string;
  sourceName: string;
  sourceDelay: number;
  reason: string;
  affected: AffectedTrain[];
}

export function DownstreamImpact({ sourceTrain, sourceName, sourceDelay, reason, affected }: Props) {
  const hasImpact = affected.length > 0;
  return (
    <section className="card impact">
      <div className="impact-head">
        <div className="section-title" style={{ margin: 0 }}>
          Downstream impact
        </div>
        <span className="sim-tag">SIMULATED IMPACT</span>
      </div>

      {!hasImpact ? (
        <div className="muted" style={{ marginTop: 10, fontSize: 14 }}>
          No downstream impact yet. When this train is delayed by an operational
          event, trailing trains on the same corridor are affected here.
        </div>
      ) : (
        <>
          <div className="row" style={{ gap: 14, marginTop: 6 }}>
            <div className="impact-count">{affected.length}</div>
            <div className="muted" style={{ fontSize: 14 }}>
              trains affected downstream
              <br />
              {reason}
            </div>
          </div>

          <div className="impact-chain stack">
            <div className="impact-node source">
              <div>
                <div className="in-id">{sourceTrain}</div>
                <div className="in-nm">{sourceName} · source</div>
              </div>
              <div className="in-delay">+{sourceDelay} min</div>
            </div>
            {affected.map((a) => (
              <div key={a.train_number}>
                <div className="impact-connector" />
                <div className="impact-node">
                  <div>
                    <div className="in-id">{a.train_number}</div>
                    <div className="in-nm">{a.train_name}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="in-delay">+{a.added_delay_minutes} min</div>
                    {a.new_eta && (
                      <div className="in-nm">ETA {a.new_eta}</div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
