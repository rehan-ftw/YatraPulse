import type { RouteStop } from "../types";

export function RouteTimeline({ route }: { route: RouteStop[] }) {
  return (
    <section className="card timeline">
      <div className="section-title">Route</div>
      <div className="tl">
        {route.map((s) => (
          <div className={`tl-stop ${s.state}`} key={s.station_code}>
            <span className="node" />
            <div className="st-name">
              {s.station_name}
              {s.state === "current" && (
                <span className="muted" style={{ fontWeight: 500, marginLeft: 8, fontSize: 13 }}>
                  • current position
                </span>
              )}
            </div>
            <div className="st-meta">
              {s.scheduled_arrival && <span>Arr {s.scheduled_arrival}</span>}
              {s.scheduled_departure && <span>Dep {s.scheduled_departure}</span>}
              <span>{Math.round(s.distance_from_origin)} km</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
