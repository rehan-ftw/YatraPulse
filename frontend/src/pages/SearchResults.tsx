import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "../services/api";
import type { TrainSummary } from "../types";
import { SearchBar } from "../components/SearchBar";
import { TrainCard } from "../components/TrainCard";
import { EmptyState, ErrorState, Loading } from "../components/common";

export function SearchResults() {
  const [params] = useSearchParams();
  const q = params.get("q") ?? "";
  const [results, setResults] = useState<TrainSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setResults(null);
    setError(null);
    api
      .searchTrains(q)
      .then(setResults)
      .catch((e: ApiError) => setError(e.message || "Search failed"));
  }, [q]);

  return (
    <div>
      <div style={{ maxWidth: 620, marginBottom: 22 }}>
        <SearchBar initial={q} />
      </div>

      <div className="results-head">
        <h2>{q ? `Results for “${q}”` : "All trains"}</h2>
        {results && <span className="muted">{results.length} trains</span>}
      </div>

      {error ? (
        <ErrorState title="Something went wrong" hint={error} />
      ) : results === null ? (
        <Loading label="Searching trains…" />
      ) : results.length === 0 ? (
        <EmptyState
          icon="🔎"
          title="Train not found"
          hint="Try a train number like 12952, or a name like “Rajdhani”."
        />
      ) : (
        <div className="card">
          {results.map((t) => (
            <TrainCard key={t.id} t={t} />
          ))}
        </div>
      )}
    </div>
  );
}
