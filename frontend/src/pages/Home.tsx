import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { TrainSummary } from "../types";
import { DataProvenance } from "../components/common";
import { SearchBar } from "../components/SearchBar";

export function Home() {
  const [popular, setPopular] = useState<TrainSummary[]>([]);

  useEffect(() => {
    api.listTrains().then((t) => setPopular(t.slice(0, 3))).catch(() => setPopular([]));
  }, []);

  return (
    <div>
      <section className="hero">
        <h1>Track your train with a changing ETA.</h1>
        <p>
          See where your train is, when it is expected to arrive, and how
          operational changes affect your journey — live.
        </p>
        <div className="hero-search">
          <SearchBar />
        </div>
        <div className="hero-meta">
          <DataProvenance />
        </div>

        <div className="rail-illustration">
          <div className="train-dot" />
        </div>
      </section>

      {popular.length > 0 && (
        <section className="popular">
          <div className="section-title">Popular trains</div>
          <div className="popular-grid">
            {popular.map((t) => (
              <Link to={`/train/${t.id}`} key={t.id} className="card" style={{ padding: 18 }}>
                <div style={{ fontWeight: 800, fontSize: 17 }}>{t.train_number}</div>
                <div className="muted" style={{ fontSize: 14 }}>{t.train_name}</div>
                <div style={{ marginTop: 10, fontWeight: 600, fontSize: 14 }}>
                  {t.source} <span style={{ color: "var(--burgundy)" }}>→</span>{" "}
                  {t.destination}
                </div>
                <div className="muted" style={{ fontSize: 13, marginTop: 6 }}>
                  Expected {t.current_eta ?? "—"}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
