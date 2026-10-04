import { useState } from "react";
import { Check, X } from "lucide-react";
import { api } from "../api/client";
import type { Approval } from "../api/types";
import { RiskBadge } from "../ui/primitives";
import { timeAgo } from "../ui/time";
import { useToast } from "../ui/toast";

interface Outcome {
  ok: boolean;
  error?: string | null;
  approval?: Approval;
}

/** One decision the operator is waiting on, with the details needed to decide. */
export function ApprovalCard({ approval, onDecided, compact = false }: { approval: Approval; onDecided: () => void; compact?: boolean }) {
  const notify = useToast();
  const [busy, setBusy] = useState<"" | "approve" | "reject">("");
  const [current, setCurrent] = useState(approval);
  const decided = current.status !== "pending";

  const decide = async (decision: "approve" | "reject") => {
    setBusy(decision);
    try {
      const res = await api<Outcome>(`/api/approvals/${approval.id}/${decision}`, "POST");
      if (res.approval) setCurrent(res.approval);
      if (decision === "approve") notify(res.ok ? "Done — action completed." : `Couldn't complete: ${res.error}`, !res.ok);
      else notify("Dismissed.");
      onDecided();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy("");
    }
  };

  const params = Object.entries(approval.params).filter(([, v]) => v !== "" && v !== null && v !== undefined);

  return (
    <div className={compact ? "list-item" : "card card-flat"} style={compact ? { alignItems: "flex-start" } : undefined}>
      <div className="grow">
        <div className="row wrap" style={{ gap: 8 }}>
          <span className="strong">{approval.title}</span>
          <RiskBadge risk={approval.risk} />
          {decided && <span className={`badge ${current.status === "executed" ? "badge-success" : current.status === "failed" ? "badge-danger" : ""}`}>{current.status}</span>}
        </div>
        {approval.rationale && <p className="muted small" style={{ marginTop: 4 }}>{approval.rationale}</p>}
        {!compact && params.length > 0 && (
          <div className="code" style={{ marginTop: 10, whiteSpace: "pre-wrap" }}>
            {params.map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join("\n")}
          </div>
        )}
        {current.status === "failed" && current.result?.error && <p className="small" style={{ color: "var(--danger)", marginTop: 6 }}>{current.result.error}</p>}
        <div className="tiny faint" style={{ marginTop: 6 }}>From {approval.source} · {timeAgo(approval.created_at)}</div>
      </div>
      {!decided && (
        <div className="row" style={{ flexShrink: 0 }}>
          <button className="btn btn-sm btn-icon" title="Dismiss" aria-label="Dismiss" disabled={!!busy} onClick={() => decide("reject")}>
            <X size={15} />
          </button>
          <button className="btn btn-sm btn-primary" disabled={!!busy} onClick={() => decide("approve")}>
            <Check size={15} /> {busy === "approve" ? "Running…" : "Approve"}
          </button>
        </div>
      )}
    </div>
  );
}
