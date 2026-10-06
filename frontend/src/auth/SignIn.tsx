import { useState, type FormEvent } from "react";
import { ArrowRight, Sparkles } from "lucide-react";
import { api } from "../api/client";
import type { Owner } from "../api/types";
import { ErrorNote } from "../ui/primitives";
import { useSession } from "./session";

export function SignIn() {
  const { signIn } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api<{ token: string; owner: Owner }>("/api/auth/login", "POST", { email, password });
      signIn(res.token, res.owner);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flow">
      <form className="flow-card" onSubmit={submit}>
        <div className="flow-logo">
          <Sparkles size={24} />
        </div>
        <h1 className="flow-title">Welcome back</h1>
        <p className="flow-subtitle">Sign in to your Business Operating System.</p>
        <div className="flow-body">
          {error && <ErrorNote message={error} />}
          <div className="field" style={{ marginTop: error ? 14 : 0 }}>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
          </div>
          <div className="field">
            <label className="label" htmlFor="password">Password</label>
            <input id="password" className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
        </div>
        <div className="flow-actions">
          <span />
          <button className="btn btn-primary btn-lg" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"} <ArrowRight size={18} />
          </button>
        </div>
      </form>
    </div>
  );
}
