import { useState } from "react";
import { api } from "../services/api";
import { LiveDot } from "./common";

interface Props {
  trainId: number;
  state: string; // idle | running | paused | stopped | arrived
  onStateChange: (s: string) => void;
}

export function SimulationPanel({ trainId, state, onStateChange }: Props) {
  const [busy, setBusy] = useState(false);
  const running = state === "running";
  const paused = state === "paused";
  const active = running || paused;
  const halted = state === "stopped" || state === "arrived";

  const run = async (fn: () => Promise<unknown>, next: string) => {
    setBusy(true);
    try {
      await fn();
      onStateChange(next);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card sim-panel">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="section-title" style={{ margin: 0 }}>
          Demo / Simulation
        </div>
        <LiveDot live={running} />
      </div>
      <div className="sim-note">
        Drive a <b>simulated</b> live journey. This is the demo/operational-simulation
        surface — actions here simulate events; they are not real Indian Railways
        operations and not a passenger report.
      </div>

      <div className="sim-controls">
        {!active ? (
          <button
            className="btn btn-primary"
            disabled={busy}
            onClick={() => run(() => api.simStart(trainId), "running")}
          >
            ▶ {halted ? "Start again" : "Start live simulation"}
          </button>
        ) : (
          <>
            {running ? (
              <button
                className="btn btn-ghost"
                disabled={busy}
                onClick={() => run(() => api.simPause(trainId), "paused")}
              >
                ❚❚ Pause
              </button>
            ) : (
              <button
                className="btn btn-primary"
                disabled={busy}
                onClick={() => run(() => api.simResume(trainId), "running")}
              >
                ▶ Resume
              </button>
            )}
            <button
              className="btn btn-danger"
              disabled={busy}
              onClick={() => run(() => api.simStop(trainId), "stopped")}
            >
              ■ Stop
            </button>
          </>
        )}
        {state !== "idle" && (
          <button
            className="btn btn-ghost"
            disabled={busy}
            onClick={() => run(() => api.simReset(trainId), "idle")}
            title="Restore the pristine starting state"
          >
            ↺ Reset
          </button>
        )}
      </div>

      <div className="sim-inject">
        <button
          className="btn btn-warn btn-block"
          disabled={busy || !active}
          onClick={() => run(() => api.injectCongestion(trainId, "congestion"), state)}
          title={active ? "" : "Start the simulation first"}
        >
          ⚠ Simulate congestion
        </button>
        <div className="row gap-8" style={{ marginTop: 10 }}>
          <button
            className="btn btn-ghost"
            style={{ flex: 1 }}
            disabled={busy || !active}
            onClick={() => run(() => api.injectCongestion(trainId, "signal_hold"), state)}
          >
            Simulate signal hold
          </button>
          <button
            className="btn btn-ghost"
            style={{ flex: 1 }}
            disabled={busy || !active}
            onClick={() => run(() => api.injectCongestion(trainId, "station_delay"), state)}
          >
            Simulate station delay
          </button>
        </div>
      </div>
    </section>
  );
}
