import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken, SIGNED_OUT_EVENT } from "../api/client";
import type { Owner, SetupStatus } from "../api/types";

interface Session {
  owner: Owner | null;
  setup: SetupStatus | null;
  ready: boolean;
  signIn: (token: string, owner: Owner) => void;
  signOut: () => void;
  refreshSetup: () => Promise<SetupStatus | null>;
}

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [owner, setOwner] = useState<Owner | null>(null);
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [ready, setReady] = useState(false);

  const refreshSetup = useCallback(async () => {
    try {
      const status = await api<SetupStatus>("/api/setup/status");
      setSetup(status);
      return status;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    (async () => {
      await refreshSetup();
      if (getToken()) {
        try {
          setOwner(await api<Owner>("/api/auth/me"));
        } catch {
          setOwner(null);
        }
      }
      setReady(true);
    })();
    const onSignedOut = () => setOwner(null);
    window.addEventListener(SIGNED_OUT_EVENT, onSignedOut);
    return () => window.removeEventListener(SIGNED_OUT_EVENT, onSignedOut);
  }, [refreshSetup]);

  const signIn = useCallback(
    (token: string, who: Owner) => {
      setToken(token);
      setOwner(who);
      refreshSetup(); // full status is only shown to the signed-in owner
    },
    [refreshSetup],
  );

  const signOut = useCallback(() => {
    setToken("");
    setOwner(null);
  }, []);

  return (
    <SessionContext.Provider value={{ owner, setup, ready, signIn, signOut, refreshSetup }}>{children}</SessionContext.Provider>
  );
}

export function useSession(): Session {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
