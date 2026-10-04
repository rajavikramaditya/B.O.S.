import { useState, type FormEvent } from "react";
import { ExternalLink, Lock } from "lucide-react";
import { api } from "../api/client";
import type { Connector } from "../api/types";
import { ErrorNote } from "../ui/primitives";

/** Credential form for one connector; secrets go straight to the encrypted vault. */
export function ConnectorForm({ connector, onConnected, submitLabel = "Connect" }: { connector: Connector; onConnected: (c: Connector) => void; submitLabel?: string }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onConnected(await api<Connector>(`/api/integrations/${connector.id}/connect`, "POST", { fields: values }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      {error && <div style={{ marginBottom: 14 }}><ErrorNote message={error} /></div>}
      {connector.fields.map((f) => (
        <div className="field" key={f.key}>
          <label className="label" htmlFor={`${connector.id}-${f.key}`}>{f.label}</label>
          <input
            id={`${connector.id}-${f.key}`}
            className={`input${f.secret ? " input-mono" : ""}`}
            type={f.secret ? "password" : "text"}
            placeholder={f.placeholder}
            autoComplete="off"
            value={values[f.key] ?? ""}
            onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
          />
        </div>
      ))}
      <div className="row-between wrap" style={{ marginTop: 18 }}>
        <span className="row tiny faint">
          <Lock size={13} /> Encrypted at rest. Never shown again.
        </span>
        <div className="row">
          {connector.docs_url && (
            <a className="btn btn-ghost btn-sm" href={connector.docs_url} target="_blank" rel="noreferrer">
              Get credentials <ExternalLink size={14} />
            </a>
          )}
          <button className="btn btn-primary" disabled={busy}>
            {busy ? "Checking…" : submitLabel}
          </button>
        </div>
      </div>
    </form>
  );
}
