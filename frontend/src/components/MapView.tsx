import { useEffect } from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Marker, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import type { RouteStop } from "../types";

const trainIcon = L.divIcon({
  className: "",
  html: `<div style="width:20px;height:20px;border-radius:50%;background:#8a1a2b;border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,.35)"></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

function FitRoute({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 1) {
      map.fitBounds(L.latLngBounds(points), { padding: [30, 30] });
    }
  }, [map, points.length]); // eslint-disable-line
  return null;
}

interface Props {
  route: RouteStop[];
  trainPos: { lat: number; lng: number } | null;
  polyline?: [number, number][]; // real route geometry
}

export function MapView({ route, trainPos, polyline }: Props) {
  const stationPts = route
    .filter((s) => s.latitude != null && s.longitude != null)
    .map((s) => [s.latitude, s.longitude]) as [number, number][];
  // prefer the real route geometry for the line; fall back to station-to-station
  const line = polyline && polyline.length > 1 ? polyline : stationPts;
  const center: [number, number] = line.length
    ? line[Math.floor(line.length / 2)]
    : [23, 76];

  return (
    <MapContainer center={center} zoom={6} scrollWheelZoom={false} attributionControl>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap contributors"
      />
      <FitRoute points={line} />

      <Polyline positions={line} pathOptions={{ color: "#c9bfb4", weight: 4 }} />
      {/* completed portion in burgundy up to the train's current position */}
      {trainPos && (
        <Polyline
          positions={[...stationPts.filter((_, i) => route[i]?.state === "done"), [trainPos.lat, trainPos.lng]] as [number, number][]}
          pathOptions={{ color: "#8a1a2b", weight: 5 }}
        />
      )}

      {route
        .filter((s) => s.latitude != null && s.longitude != null)
        .map((s) => (
          <CircleMarker
            key={s.station_code}
            center={[s.latitude as number, s.longitude as number]}
            radius={5}
            pathOptions={{
              color: s.state === "done" ? "#2f7d5b" : "#8a7f74",
              fillColor: "#fff",
              fillOpacity: 1,
              weight: 2,
            }}
          >
            <Tooltip>{s.station_name}</Tooltip>
          </CircleMarker>
        ))}

      {trainPos && (
        <Marker position={[trainPos.lat, trainPos.lng]} icon={trainIcon}>
          <Tooltip permanent direction="top" offset={[0, -12]}>
            Train
          </Tooltip>
        </Marker>
      )}
    </MapContainer>
  );
}
