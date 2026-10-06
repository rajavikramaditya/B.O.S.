import { useState } from "react";
import { CheckCircle2, Hand, Pause, Rocket, Zap, XCircle } from "lucide-react";
import { api } from "../api/client";
import type { AutopilotMode, AutopilotRun } from "../api/types";
import { Empty, ErrorNote, LoadingCard, PageHeader, RichText } from "../ui/primitives";
import { timeAgo } from "../ui/time";
import { useToast } from "../ui/toast";
import { useResource } from "../ui/useResource";

const MODES: { id: AutopilotMode; title: string; desc: string; icon: typeof Rocket; badge?: string }[] = [
  { id: "off", title: "Off", desc: "No scheduled reviews. The operator still answers when someone writes.", icon: Pause },
  { id: "assist", title: "Assist", desc: "Plans everything, but asks before every action — even internal record keeping.", icon: Hand },
  { id: "autopilot", title: "Autopilot", desc: "Keeps records and plans follow-ups on its own. Asks before contacting people.", icon: Rocket, badge: "Recommended" },
  { id: "autonomous", title: "Autonomous", desc: "Also messages customers on its own. Money, deletions and broadcasts always wait for you.", icon: Zap },
];

interface Overview {
  settings: { mode: AutopilotMode };
  latest: AutopilotRun | null;
  history: AutopilotRun[];
}

export function Autopilot() {
  const notify = useToast();
  const { data, error, reload } = useResource<Overview>("/api/autopilot");
  const [running, setRunning] = useState(false);

  const setMode = async (mode: AutopilotMode) => {
    try {
      await api("/api/autopilot", "PUT", { mode });
      notify(`Autopilot set to ${mode}.`);
      reload();
    } catch (e) {
      notify((e as Error).message, true);
    }
  };

  const run = async () => {
    setRunning(true);
    try {
      const res = await api<AutopilotRun>("/api/autopilot/run", "POST");
      notify(res.status === "completed" ? "Review complete." : res.error || "Review couldn't run.", res.status !== "completed");
      reload();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="page">
      <PageHeader
        title="Autopilot"
        subtitle="B.O.S. doesn't wait for orders. On a schedule it reviews your whole business, acts on what's safe, and lines up the rest for you."
        actions={<button className="btn btn-primary" onClick={run} disabled={running}><Rocket size={16} /> {running ? "Reviewing…" : "Run a review now"}</button>}
      />
      {error && <ErrorNote message={error} />}
      {!data && !error && <LoadingCard />}
      {data && (
        <div className="stack">
          <div className="grid-cards">
            {MODES.map(({ id, title, desc, icon: Icon, badge }) => (
              <button key={id} className="choice" aria-pressed={data.settings.mode === id} onClick={() => setMode(id)} style={{ flexDirection: "column" }}>
                <div className="icon-tile"><Icon size={18} /></div>
                <div>
                  <div className="choice-title">{title} {badge && <span className="badge badge-accent">{badge}</span>}</div>
                  <div className="choice-desc">{desc}</div>
                </div>
              </button>
            ))}
          </div>

          <div className="card">
            <div className="card-title" style={{ marginBottom: 12 }}>Review history</div>
            {!data.history.length && <Empty icon={<Rocket size={22} />} title="No reviews yet">Run one now, or wait for the next scheduled review.</Empty>}
            <div className="list">
              {data.history.map((r) => (
                <details key={r.id} className="list-item" style={{ display: "block" }}>
                  <summary className="row-between" style={{ cursor: "pointer", listStyle: "none" }}>
                    <div className="row">
                      {r.status === "completed" ? <CheckCircle2 size={18} color="var(--success)" /> : <XCircle size={18} color="var(--warning)" />}
                      <div>
                        <div className="strong small">{r.trigger === "schedule" ? "Scheduled review" : "Manual review"}</div>
                        <div className="tiny faint">{timeAgo(r.started_at)} · {r.executed.length} action{r.executed.length === 1 ? "" : "s"} · {r.pending_approvals.length} awaiting you</div>
                      </div>
                    </div>
                    <span className={`badge ${r.status === "completed" ? "badge-success" : "badge-warning"}`}>{r.status}</span>
                  </summary>
                  <div style={{ padding: "12px 0 4px 28px" }} className="stack-sm">
                    {r.summary ? <RichText text={r.summary} /> : <p className="muted small">{r.error}</p>}
                    {r.executed.map((e, i) => (
                      <div key={i} className={`step ${e.success ? "step-ok" : "step-fail"}`}>
                        {e.success ? <CheckCircle2 /> : <XCircle />} <span style={{ color: "var(--text)" }}>{e.title}</span>
                      </div>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
