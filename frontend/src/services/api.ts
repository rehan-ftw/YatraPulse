import type {
  Alert,
  DownstreamImpact,
  SimulationStatus,
  TrainDetail,
  TrainStatus,
  TrainSummary,
} from "../types";

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new ApiError(res.status, (detail as any)?.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new ApiError(res.status, (detail as any)?.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const api = {
  searchTrains: (q: string) =>
    get<TrainSummary[]>(`/api/trains/search?q=${encodeURIComponent(q)}`),
  listTrains: () => get<TrainSummary[]>(`/api/trains`),
  trainDetail: (id: number) => get<TrainDetail>(`/api/trains/${id}`),
  trainStatus: (id: number) => get<TrainStatus>(`/api/trains/${id}/status`),
  trainEta: (id: number) =>
    get<{
      current_eta: string | null;
      scheduled_arrival: string | null;
      delay_minutes: number;
      reason: string;
      predictor: string;
      components: Record<string, unknown>;
    }>(`/api/trains/${id}/eta`),
  trainImpact: (id: number) => get<DownstreamImpact>(`/api/trains/${id}/impact`),
  alerts: () => get<Alert[]>(`/api/alerts`),
  simStatus: (id: number) =>
    get<SimulationStatus>(`/api/simulation/status?train_id=${id}`),

  simStart: (train_id: number) => post(`/api/simulation/start`, { train_id }),
  simPause: (train_id: number) => post(`/api/simulation/pause`, { train_id }),
  simResume: (train_id: number) => post(`/api/simulation/resume`, { train_id }),
  simStop: (train_id: number) => post(`/api/simulation/stop`, { train_id }),
  simReset: (train_id: number) => post(`/api/simulation/reset`, { train_id }),
  injectCongestion: (train_id: number, event_type = "congestion") =>
    post<{
      previous_eta: string | null;
      new_eta: string | null;
      delay_minutes: number;
      reason: string;
      location: string;
    }>(`/api/simulation/congestion`, { train_id, event_type }),
};
