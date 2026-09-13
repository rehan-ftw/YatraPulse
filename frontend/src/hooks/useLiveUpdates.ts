import { useEffect, useRef, useState } from "react";
import type { LiveMessage } from "../types";

type Handler = (msg: LiveMessage) => void;

/**
 * Connects to the backend WebSocket and invokes `onMessage` for every live
 * update. Auto-reconnects with a small backoff so the demo survives a hiccup.
 */
export function useLiveUpdates(onMessage: Handler) {
  const [connected, setConnected] = useState(false);
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let closedByUs = false;

    const connect = () => {
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${window.location.host}/ws/live-updates`);
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closedByUs) retry = setTimeout(connect, 1500);
      };
      ws.onerror = () => ws?.close();
      ws.onmessage = (ev) => {
        try {
          handlerRef.current(JSON.parse(ev.data) as LiveMessage);
        } catch {
          /* ignore malformed frames */
        }
      };
    };
    connect();

    return () => {
      closedByUs = true;
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, []);

  return { connected };
}
