import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useLiveUpdates } from "./hooks/useLiveUpdates";
import type { LiveMessage } from "./types";

type Subscriber = (msg: LiveMessage) => void;

interface LiveContextValue {
  connected: boolean;
  subscribe: (fn: Subscriber) => () => void;
}

const LiveContext = createContext<LiveContextValue>({
  connected: false,
  subscribe: () => () => {},
});

export interface PassengerToast {
  id: number;
  train_number: string;
  previous_eta: string | null;
  new_eta: string | null;
  delay_minutes: number;
  reason: string;
}

let toastId = 0;

export function LiveProvider({ children }: { children: ReactNode }) {
  const subs = useRef<Set<Subscriber>>(new Set());
  const [toasts, setToasts] = useState<PassengerToast[]>([]);

  const subscribe = useCallback((fn: Subscriber) => {
    subs.current.add(fn);
    return () => {
      subs.current.delete(fn);
    };
  }, []);

  const { connected } = useLiveUpdates((msg) => {
    subs.current.forEach((fn) => fn(msg));
    // Global passenger alert on ETA change
    if (msg.type === "ETA_UPDATED" && msg.new_eta !== msg.previous_eta) {
      const t: PassengerToast = {
        id: ++toastId,
        train_number: msg.train_number,
        previous_eta: msg.previous_eta,
        new_eta: msg.new_eta,
        delay_minutes: msg.delay_minutes,
        reason: msg.reason,
      };
      setToasts((prev) => [...prev, t]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((x) => x.id !== t.id));
      }, 9000);
    }
  });

  const dismiss = (id: number) => setToasts((p) => p.filter((t) => t.id !== id));

  return (
    <LiveContext.Provider value={{ connected, subscribe }}>
      {children}
      <div className="toast-wrap">
        {toasts.map((t) => (
          <div className="toast card" key={t.id} role="status">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div className="t-title">● YOUR ETA HAS CHANGED</div>
              <button
                className="btn btn-ghost"
                style={{ padding: "2px 8px", fontSize: 12 }}
                onClick={() => dismiss(t.id)}
              >
                ✕
              </button>
            </div>
            <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
              Train {t.train_number}
            </div>
            <div className="t-etas">
              <div>
                <div className="k">Previous</div>
                <div className="v old">{t.previous_eta ?? "—"}</div>
              </div>
              <div>
                <div className="k">Updated</div>
                <div className="v">{t.new_eta ?? "—"}</div>
              </div>
              <div>
                <div className="k">Delay</div>
                <div className="v">+{t.delay_minutes}m</div>
              </div>
            </div>
            <div className="t-reason">{t.reason}</div>
          </div>
        ))}
      </div>
    </LiveContext.Provider>
  );
}

export function useLive() {
  return useContext(LiveContext);
}

/** Subscribe to live messages for the lifetime of a component. */
export function useLiveEvent(handler: Subscriber, deps: unknown[] = []) {
  const { subscribe } = useLive();
  useEffect(() => subscribe(handler), [subscribe, ...deps]); // eslint-disable-line
}
