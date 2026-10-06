import { useEffect, useState, type ReactNode } from "react";
import { Check, Copy, X } from "lucide-react";

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow?: string; title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <div className="page-eyebrow">{eyebrow}</div>}
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="row wrap">{actions}</div>}
    </header>
  );
}

export function Empty({ icon, title, children, action }: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <div className="empty-title">{title}</div>
      {children && <div className="small">{children}</div>}
      {action && <div style={{ marginTop: 14 }}>{action}</div>}
    </div>
  );
}

export function Spinner() {
  return <span className="spinner" aria-label="Loading" />;
}

export function LoadingCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="card stack-sm" aria-busy="true">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton" style={{ height: 14, width: `${90 - i * 18}%` }} />
      ))}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return <div className="alert alert-danger">{message}</div>;
}

export function Modal({ title, onClose, children, actions }: { title: string; onClose: () => void; children: ReactNode; actions?: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="row-between" style={{ marginBottom: 16 }}>
          <h2 className="modal-title">{title}</h2>
          <button className="btn btn-icon btn-sm" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>
        {children}
        {actions && <div className="modal-actions">{actions}</div>}
      </div>
    </div>
  );
}

export function CopyField({ value, mono = true }: { value: string; mono?: boolean }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked — the value stays selectable */
    }
  };
  return (
    <div className="copy-row">
      <input className={`input${mono ? " input-mono" : ""}`} readOnly value={value} onFocus={(e) => e.target.select()} />
      <button className="btn btn-icon" onClick={copy} aria-label="Copy">
        {copied ? <Check size={16} /> : <Copy size={16} />}
      </button>
    </div>
  );
}

const STAGE_TONE: Record<string, string> = {
  lead: "badge-accent",
  prospect: "badge-violet",
  customer: "badge-success",
  partner: "badge-warning",
};

export function StageBadge({ stage }: { stage: string }) {
  return <span className={`badge ${STAGE_TONE[stage] ?? ""}`}>{stage || "contact"}</span>;
}

const RISK_TONE: Record<string, string> = { safe: "badge-success", external: "badge-warning", sensitive: "badge-danger", read: "" };
const RISK_LABEL: Record<string, string> = { safe: "Internal", external: "Reaches people", sensitive: "Sensitive", read: "Read only" };

export function RiskBadge({ risk }: { risk: string }) {
  return <span className={`badge ${RISK_TONE[risk] ?? ""}`}>{RISK_LABEL[risk] ?? risk}</span>;
}

/** Renders AI text safely: paragraphs, bullet lists and **bold** — no HTML injection. */
export function RichText({ text }: { text: string }) {
  const blocks = text.trim().split(/\n{2,}/);
  return (
    <div className="prose">
      {blocks.map((block, i) => {
        const lines = block.split("\n");
        if (lines.every((l) => /^\s*([-*•]|\d+\.)\s+/.test(l))) {
          return (
            <ul key={i}>
              {lines.map((l, j) => (
                <li key={j}>{bold(l.replace(/^\s*([-*•]|\d+\.)\s+/, ""))}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i}>
            {lines.map((l, j) => (
              <span key={j}>
                {j > 0 && <br />}
                {bold(l)}
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}

function bold(line: string): ReactNode[] {
  return line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  );
}
