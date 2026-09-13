import { Link } from "react-router-dom";
import type { TrainSummary } from "../types";
import { LiveDot, SourceTag, StatusBadge } from "./common";

export function TrainCard({ t }: { t: TrainSummary }) {
  return (
    <div className="train-card">
      <div className="tc-id">
        <div className="num">{t.train_number}</div>
        <div className="nm">{t.train_name}</div>
      </div>

      <div className="tc-route">
        <div className="tc-od">
          {t.source} <span className="arrow">→</span> {t.destination}
        </div>
        <div className="tc-sub">
          {t.tracked ? (
            <>
              <span>
                <StatusBadge statusText={t.status_text} delay={t.delay_minutes ?? 0} />
              </span>
              {t.current_station && (
                <span>
                  At <b>{t.current_station}</b>
                </span>
              )}
              {t.next_station && (
                <span>
                  Next <b>{t.next_station}</b>
                </span>
              )}
            </>
          ) : (
            <>
              <span className="badge minor">Scheduled</span>
              <span className="muted">Not currently tracked</span>
              <SourceTag source={t.data_source} />
            </>
          )}
        </div>
      </div>

      <div className="tc-right">
        <div className="tc-eta">
          <div className="label">
            {t.tracked ? "Expected arrival" : "Scheduled arrival"}
          </div>
          <div className="val">{t.current_eta ?? "—"}</div>
        </div>
        <div className="row gap-12">
          {t.is_live && <LiveDot live />}
          <Link className="btn btn-primary" to={`/train/${t.id}`}>
            {t.tracked ? "Track train" : "View train"}
          </Link>
        </div>
      </div>
    </div>
  );
}
