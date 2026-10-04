import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";

/** Load a GET endpoint, with reload() and optional polling. */
export function useResource<T>(path: string | null, pollMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(Boolean(path));
  const alive = useRef(true);

  const reload = useCallback(async () => {
    if (!path) return;
    try {
      const result = await api<T>(path);
      if (alive.current) {
        setData(result);
        setError("");
      }
    } catch (e) {
      if (alive.current) setError((e as Error).message);
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    alive.current = true;
    setLoading(Boolean(path));
    reload();
    if (!pollMs) return () => void (alive.current = false);
    const id = setInterval(reload, pollMs);
    return () => {
      alive.current = false;
      clearInterval(id);
    };
  }, [reload, pollMs, path]);

  return { data, error, loading, reload, setData };
}
