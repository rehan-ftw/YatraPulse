// API contract shapes (mirror of the backend Pydantic schemas).

export interface TrainSummary {
  id: number;
  train_number: string;
  train_name: string;
  source: string;
  destination: string;
  status_text: string;
  delay_minutes: number | null;
  current_station: string | null;
  next_station: string | null;
  current_eta: string | null;
  is_live: boolean;
  data_source: string; // SCHEDULED | SIMULATED | HISTORICAL | LIVE
  tracked: boolean;
}

export interface Station {
  id: number;
  station_code: string;
  station_name: string;
  latitude: number | null;
  longitude: number | null;
}

export interface RouteStop {
  station_code: string;
  station_name: string;
  sequence_number: number;
  scheduled_arrival: string | null;
  scheduled_departure: string | null;
  distance_from_origin: number;
  latitude: number | null;
  longitude: number | null;
  state: "done" | "current" | "upcoming";
}

export interface HistoricalDelay {
  station_code: string;
  station_name: string;
  average_delay_minutes: number;
  punctuality_percent: number;
  delay_category: string;
}

export interface TrainStatus {
  train_id: number;
  train_number: string;
  train_name: string;
  source: string;
  destination: string;
  current_station: string | null;
  next_station: string | null;
  current_lat: number | null;
  current_lng: number | null;
  delay_minutes: number | null;
  scheduled_arrival_dest: string | null;
  current_eta: string | null;
  status_text: string;
  is_live: boolean;
  last_updated: string;
  data_source: string;
  tracked: boolean;
}

export interface TrainDetail {
  train_id: number;
  train_number: string;
  train_name: string;
  source: Station;
  destination: Station;
  status: TrainStatus;
  route: RouteStop[];
  historical: HistoricalDelay[];
  polyline: [number, number][];
  intermediate_stops_available: boolean;
  is_demo: boolean;
}

export interface AffectedTrain {
  train_number: string;
  train_name: string;
  added_delay_minutes: number;
  new_eta: string | null;
}

export interface DownstreamImpact {
  source_train: string;
  source_train_name: string;
  reason: string;
  affected_count: number;
  affected_trains: AffectedTrain[];
  note: string;
}

export interface Alert {
  id: number;
  type: string;
  train_number: string;
  train_name: string;
  title: string;
  reason: string;
  impact_minutes: number;
  previous_eta: string | null;
  new_eta: string | null;
  timestamp: string;
}

export interface SimulationStatus {
  train_id: number;
  state: string;
  tick: number;
  is_live: boolean;
}

// WebSocket message union
export type LiveMessage =
  | { type: "CONNECTED"; message: string }
  | {
      type: "ETA_UPDATED";
      train_id: number;
      train_number: string;
      previous_eta: string | null;
      new_eta: string | null;
      delay_minutes: number;
      reason: string;
      timestamp: string;
    }
  | {
      type: "TRAIN_MOVEMENT_UPDATED";
      train_id: number;
      train_number: string;
      latitude: number;
      longitude: number;
      current_station: string | null;
      next_station: string | null;
      timestamp: string;
    }
  | {
      type: "OPERATIONAL_EVENT";
      event_type: string;
      train_id: number;
      train_number: string;
      location: string;
      impact_minutes: number;
      reason: string;
      timestamp: string;
    }
  | {
      type: "DOWNSTREAM_IMPACT_UPDATED";
      source_train: string;
      source_train_name: string;
      reason: string;
      affected_count: number;
      affected_trains: AffectedTrain[];
      note: string;
      timestamp: string;
    }
  | {
      type: "SIMULATION_STATE_CHANGED";
      train_id: number;
      train_number: string;
      state: string;
      timestamp: string;
    };
