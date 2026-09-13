import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "../services/api";
import type { AffectedTrain, RouteStop, TrainDetail } from "../types";
import { ETACard } from "../components/ETACard";
import { RouteTimeline } from "../components/RouteTimeline";
import { MapView } from "../components/MapView";
import { SimulationPanel } from "../components/SimulationPanel";
import { DownstreamImpact } from "../components/DownstreamImpact";
import { ErrorState, LiveDot, Loading, SourceTag, StatusBadge } from "../components/common";
import { useLiveEvent } from "../live";

function recomputeRoute(route: RouteStop[], currentName: string | null): RouteStop[] {
  if (!currentName) return route;
  const idx = route.findIndex((s) => s.station_name === currentName);
  if (idx < 0) return route;
  return route.map((s, i) => ({
    ...s,
    state: i < idx ? "done" : i === idx ? "current" : "upcoming",
  }));
}

export function TrainDetails() {
  const { id } = useParams();
  const trainId = Number(id);

  const [detail, setDetail] = useState<TrainDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [route, setRoute] = useState<RouteStop[]>([]);
  const [pos, setPos] = useState<{ lat: number; lng: number } | null>(null);
  const [eta, setEta] = useState<string | null>(null);
  const [prevEta, setPrevEta] = useState<string | null>(null);
  const [scheduled, setScheduled] = useState<string | null>(null);
  const [delay, setDelay] = useState<number | null>(0);
  const [statusText, setStatusText] = useState("ON TIME");
  const [currentStation, setCurrentStation] = useState<string | null>(null);
  const [nextStation, setNextStation] = useState<string | null>(null);
  const [reason, setReason] = useState("Running to schedule");
  const [components, setComponents] = useState<Record<string, unknown> | undefined>();
  const [simState, setSimState] = useState("idle");
  const [affected, setAffected] = useState<AffectedTrain[]>([]);
  const [impactReason, setImpactReason] = useState("");
  const [tracked, setTracked] = useState(false);
  const [dataSource, setDataSource] = useState("SCHEDULED");
  const [lastMoveAt, setLastMoveAt] = useState<number | null>(null);
  const [, setClockTick] = useState(0);

  const applyDetail = useCallback((d: TrainDetail) => {
    setDetail(d);
    setRoute(d.route);
    setEta(d.status.current_eta);
    setPrevEta(null);
    setScheduled(d.status.scheduled_arrival_dest);
    setDelay(d.status.delay_minutes);
    setStatusText(d.status.status_text);
    setCurrentStation(d.status.current_station);
    setNextStation(d.status.next_station);
    setSimState(d.status.is_live ? "running" : "idle");
    setTracked(d.status.tracked);
    setDataSource(d.status.data_source);
    if (d.status.current_lat != null && d.status.current_lng != null) {
      setPos({ lat: d.status.current_lat, lng: d.status.current_lng });
    } else {
      setPos(null);
    }
    setLastMoveAt(d.status.is_live ? Date.now() : null);
  }, []);

  // tick a 1s clock so "updated Ns ago" stays live
  useEffect(() => {
    const id = setInterval(() => setClockTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const load = useCallback(() => {
    setError(null);
    api
      .trainDetail(trainId)
      .then((d) => {
        applyDetail(d);
        return Promise.all([api.trainEta(trainId), api.trainImpact(trainId), api.simStatus(trainId)]);
      })
      .then(([etaOut, impact, sim]) => {
        setComponents(etaOut.components);
        setReason(etaOut.reason);
        setAffected(impact.affected_trains);
        setImpactReason(impact.reason);
        setSimState(sim.state === "arrived" ? "arrived" : sim.is_live ? sim.state : "idle");
      })
      .catch((e: ApiError) => setError(e.status === 404 ? "Train not found" : e.message));
  }, [trainId, applyDetail]);

  useEffect(load, [load]);

  // ---- live updates ----
  useLiveEvent(
    (msg) => {
      if (!detail) return;
      // messages carrying a train_id for a different train are ignored;
      // DOWNSTREAM_IMPACT_UPDATED has no train_id and is matched by number below.
      if ("train_id" in msg && msg.train_id !== detail.train_id) {
        return;
      }
      switch (msg.type) {
        case "TRAIN_MOVEMENT_UPDATED":
          setPos({ lat: msg.latitude, lng: msg.longitude });
          setCurrentStation(msg.current_station);
          setNextStation(msg.next_station);
          setRoute((r) => recomputeRoute(r, msg.current_station));
          setTracked(true);
          setDataSource("SIMULATED");
          setLastMoveAt(Date.now());
          break;
        case "ETA_UPDATED":
          setPrevEta(msg.previous_eta);
          setEta(msg.new_eta);
          setDelay(msg.delay_minutes);
          setReason(msg.reason);
          setStatusText(msg.delay_minutes > 0 ? `${msg.delay_minutes} MIN LATE` : "ON TIME");
          setTracked(true);
          setDataSource("SIMULATED");
          // refresh transparent components breakdown
          api.trainEta(trainId).then((e) => setComponents(e.components)).catch(() => {});
          break;
        case "DOWNSTREAM_IMPACT_UPDATED":
          if (detail && msg.source_train === detail.train_number) {
            setAffected(msg.affected_trains);
            setImpactReason(msg.reason);
          }
          break;
        case "SIMULATION_STATE_CHANGED":
          if (msg.state === "reset") {
            // restored to pristine starting state — reload it
            load();
          } else {
            setSimState(msg.state);
          }
          break;
      }
    },
    [detail?.train_id]
  );

  if (error) return <ErrorState title={error} hint="Try searching for another train." />;
  if (!detail) return <Loading label="Loading train…" />;

  const late = (delay ?? 0) > 0;
  const isLive = simState === "running";
  const updatedLabel = (() => {
    if (!tracked) return "Not currently tracked · showing scheduled timetable";
    if (lastMoveAt == null) return "Updated just now";
    const secs = Math.max(0, Math.round((Date.now() - lastMoveAt) / 1000));
    return secs <= 1 ? "Updated just now" : `Updated ${secs}s ago`;
  })();

  return (
    <div>
      <div className="detail-head">
        <div>
          <div className="train-no">{detail.train_number}</div>
          <h1>{detail.train_name}</h1>
          <div className="od">
            {detail.source.station_name} <span className="arrow">→</span>{" "}
            {detail.destination.station_name}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="row" style={{ gap: 10, justifyContent: "flex-end" }}>
            {isLive && <LiveDot live />}
            <SourceTag source={dataSource} />
          </div>
          <div className="muted" style={{ fontSize: 13, marginTop: 10 }}>
            {updatedLabel}
          </div>
        </div>
      </div>

      <div className="detail-grid">
        {/* LEFT column */}
        <div className="detail-col">
          <section className="card status-hero">
            {tracked ? (
              <>
                <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
                  <div className={`big-status ${late ? "late" : "ontime"}`}>
                    {late ? `RUNNING ${delay} MIN LATE` : "RUNNING ON TIME"}
                  </div>
                  <StatusBadge statusText={statusText} delay={delay ?? 0} />
                </div>
                {isLive && (
                  <div className="row gap-8" style={{ marginTop: 8 }}>
                    <LiveDot live />
                    <span className="muted" style={{ fontSize: 13 }}>
                      Live tracking · {updatedLabel.toLowerCase()}
                    </span>
                  </div>
                )}
                <div className="loc-row">
                  <div className="loc-item">
                    <div className="k">Current location</div>
                    <div className="v">{currentStation ?? "—"}</div>
                  </div>
                  <div className="loc-item">
                    <div className="k">Next station</div>
                    <div className="v">{nextStation ?? "Destination"}</div>
                  </div>
                  <div className="loc-item">
                    <div className="k">Total distance</div>
                    <div className="v">
                      {Math.round(route[route.length - 1]?.distance_from_origin ?? 0)} km
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="big-status" style={{ color: "var(--ink-2)" }}>
                  SCHEDULED SERVICE
                </div>
                <div className="muted" style={{ marginTop: 8, fontSize: 14.5 }}>
                  This train is in the catalogue from timetable data. Live position and
                  delay are not tracked. Start a simulated journey below to see the
                  dynamic ETA in action.
                </div>
                <div className="loc-row">
                  <div className="loc-item">
                    <div className="k">Current location</div>
                    <div className="v muted">Not tracked</div>
                  </div>
                  <div className="loc-item">
                    <div className="k">Total distance</div>
                    <div className="v">
                      {Math.round(route[route.length - 1]?.distance_from_origin ?? 0)} km
                    </div>
                  </div>
                </div>
              </>
            )}
          </section>

          <section className="card map-wrap">
            <div className="map-head">
              <div className="section-title" style={{ margin: 0 }}>
                Route map
              </div>
              <span className="muted" style={{ fontSize: 13 }}>
                Leaflet · OpenStreetMap
              </span>
            </div>
            <MapView route={route} trainPos={pos} polyline={detail.polyline} />
          </section>

          <RouteTimeline route={route} />
          {!detail.intermediate_stops_available && (
            <div className="muted" style={{ fontSize: 13, marginTop: -6 }}>
              Detailed intermediate stops are not available for this train — showing
              origin and destination. The map shows the true route.
            </div>
          )}
        </div>

        {/* RIGHT column */}
        <div className="detail-col">
          <ETACard
            eta={eta}
            scheduled={scheduled}
            delay={delay ?? 0}
            reason={tracked ? reason : "Scheduled arrival from timetable · not currently tracked"}
            previousEta={prevEta}
            components={tracked ? components : undefined}
            scheduledOnly={!tracked}
          />

          <SimulationPanel trainId={detail.train_id} state={simState} onStateChange={setSimState} />

          <DownstreamImpact
            sourceTrain={detail.train_number}
            sourceName={detail.train_name}
            sourceDelay={delay ?? 0}
            reason={impactReason || reason}
            affected={affected}
          />

          <section className="card hist">
            <div className="section-title">Historical delay context</div>
            {detail.historical.length === 0 ? (
              <div className="muted" style={{ fontSize: 14 }}>
                Historical delay data is not available for this train.
              </div>
            ) : (
              <>
                <div className="muted" style={{ fontSize: 13, marginBottom: 6 }}>
                  From historical railway data — separate from today's simulated
                  operations.
                </div>
                {detail.historical
                  .filter((h) =>
                    ["current", "upcoming"].includes(
                      route.find((r) => r.station_code === h.station_code)?.state ?? "upcoming"
                    )
                  )
                  .slice(0, 5)
                  .map((h) => (
                    <div className="hist-row" key={h.station_code}>
                      <div>
                        <div style={{ fontWeight: 600 }}>{h.station_name}</div>
                        <div className="muted" style={{ fontSize: 12.5 }}>
                          Punctuality {h.punctuality_percent}%
                        </div>
                      </div>
                      <div className="hv">+{h.average_delay_minutes} min avg</div>
                    </div>
                  ))}
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
