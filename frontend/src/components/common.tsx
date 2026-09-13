import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";
import { useLive } from "../live";

export function DataProvenance() {
  return (
    <div className="provenance">
      <span className="chip hist">
        <span className="dot" /> Historical data
      </span>
      <span style={{ color: "var(--ink-3)" }}>+</span>
      <span className="chip sim">
        <span className="dot" /> Simulated live operations
      </span>
    </div>
  );
}

const SOURCE_LABEL: Record<string, string> = {
  SIMULATED: "Simulated live operations",
  SCHEDULED: "Scheduled timetable data",
  HISTORICAL: "Historical data",
  LIVE: "Live provider data",
};

export function SourceTag({ source }: { source: string }) {
  const label = SOURCE_LABEL[source] ?? source;
  const cls = source === "SIMULATED" ? "sim" : "hist";
  return (
    <span className={`chip ${cls}`}>
      <span className="dot" /> {label}
    </span>
  );
}

export function LiveDot({ live }: { live: boolean }) {
  return (
    <span className={`live ${live ? "" : "dim"}`}>
      <span className="pulse" />
      {live ? "LIVE" : "OFFLINE"}
    </span>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { connected } = useLive();
  return (
    <>
      <header className="appbar">
        <div className="container appbar-inner">
          <NavLink to="/" className="brand">
            <span className="mark">◇</span>
            <span className="name">
              Yatra<b>Pulse</b>
            </span>
          </NavLink>
          <nav className="nav">
            <NavLink to="/" end>
              Home
            </NavLink>
            <NavLink to="/search">Search</NavLink>
            <NavLink to="/live">Live Status</NavLink>
            <NavLink to="/alerts">Alerts</NavLink>
          </nav>
          <div className="appbar-spacer" />
          <LiveDot live={connected} />
        </div>
      </header>
      <main className="container page-pad">{children}</main>
      <footer className="footer">
        <div className="container">
          YatraPulse — a Smart India Hackathon prototype. Combines{" "}
          <b>historical railway data</b> with a <b>simulated live operations</b>{" "}
          engine to demonstrate dynamic ETA. Simulated events are not actual
          Indian Railways live data.
        </div>
      </footer>
    </>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state-box">
      <div className="ic">⏳</div>
      <div>{label}</div>
    </div>
  );
}

export function EmptyState({
  icon = "🚉",
  title,
  hint,
}: {
  icon?: string;
  title: string;
  hint?: string;
}) {
  return (
    <div className="state-box">
      <div className="ic">{icon}</div>
      <h3>{title}</h3>
      {hint && <div>{hint}</div>}
    </div>
  );
}

export function ErrorState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="state-box">
      <div className="ic">⚠️</div>
      <h3>{title}</h3>
      {hint && <div>{hint}</div>}
    </div>
  );
}

export function StatusBadge({
  statusText,
  delay,
}: {
  statusText: string;
  delay: number;
}) {
  const cls = delay <= 0 ? "ontime" : delay <= 5 ? "minor" : "late";
  return <span className={`badge ${cls}`}>{statusText}</span>;
}
