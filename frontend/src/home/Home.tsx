import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CalendarClock, CheckCircle2, Circle, Inbox, ListTodo, RefreshCw, Rocket, Sparkles, TrendingUp, Users } from "lucide-react";
import { api } from "../api/client";
import type { AutopilotRun, Dashboard } from "../api/types";
import { useSession } from "../auth/session";
import { ApprovalCard } from "../approvals/ApprovalCard";
import { Empty, ErrorNote, LoadingCard, RichText } from "../ui/primitives";
import { dueLabel, greeting, initials, timeAgo } from "../ui/time";
import { useToast } from "../ui/toast";
import { useResource } from "../ui/useResource";

const PRIORITY_TONE: Record<string, string> = { high: "badge-danger", medium: "badge-warning", low: "" };

export function Home() {
  const { owner } = useSession();
  const { data, error, reload } = useResource<Dashboard>("/api/dashboard", 45000);
  const firstName = owner?.name.split(" ")[0] ?? "";
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <div className="page-eyebrow">{today}</div>
          <h1 className="page-title">{greeting()}{firstName ? `, ${firstName}` : ""}</h1>
          <p className="page-subtitle">
            {data?.profile.assistant_name || "Your operator"} is running {data?.profile.name || "your business"} with you. Here's what matters right now.
          </p>
        </div>
        <Link className="btn btn-primary" to="/assistant">
          <Sparkles size={16} /> Ask {data?.profile.assistant_name || "assistant"}
        </Link>
      </header>

      {error && <ErrorNote message={error} />}
      {!data && !error && <div className="stack"><LoadingCard /><LoadingCard lines={2} /></div>}
      {data && (
        <div className="stack">
          {!data.setup.complete && <SetupCard data={data} />}
          <div className="stats">
            <Stat icon={<Users size={15} />} label="Contacts" value={data.stats.contacts.total} foot={`${data.stats.contacts.new_this_week} new this week`} />
            <Stat icon={<ListTodo size={15} />} label="Open tasks" value={data.stats.tasks.open} foot={data.stats.tasks.overdue ? `${data.stats.tasks.overdue} overdue` : "Nothing overdue"} warn={data.stats.tasks.overdue > 0} />
            <Stat icon={<CheckCircle2 size={15} />} label="Needs your decision" value={data.stats.pending_approvals} foot="Approvals waiting" warn={data.stats.pending_approvals > 0} />
            <Stat icon={<Inbox size={15} />} label="Conversations" value={data.stats.conversations} foot={`${data.stats.tasks.done_this_week} tasks done this week`} />
          </div>
          <div className="grid-2">
            <div className="stack">
              <Briefing latest={data.autopilot.latest} mode={data.autopilot.mode} onRan={reload} />
              <div className="card">
                <div className="card-header">
                  <div>
                    <div className="card-title">Needs your decision</div>
                    <div className="card-subtitle">Your operator prepared these and is waiting for a yes or no.</div>
                  </div>
                  {data.stats.pending_approvals > 0 && <Link to="/approvals" className="btn btn-ghost btn-sm">See all</Link>}
                </div>
                {data.approvals.length ? (
                  <div className="list">{data.approvals.map((a) => <ApprovalCard key={a.id} approval={a} onDecided={reload} compact />)}</div>
                ) : (
                  <Empty icon={<CheckCircle2 size={22} />} title="You're all caught up">Nothing needs your attention.</Empty>
                )}
              </div>
            </div>
            <div className="stack">
              <div className="card">
                <div className="card-header">
                  <div className="card-title">Up next</div>
                  <Link to="/customers?tab=tasks" className="btn btn-ghost btn-sm">All tasks</Link>
                </div>
                {data.tasks.length ? (
                  <div className="list">
                    {data.tasks.map((t) => {
                      const due = dueLabel(t.due_at);
                      return (
                        <div className="list-item" key={t.id}>
                          <CalendarClock size={18} color={due.overdue ? "var(--danger)" : "var(--text-3)"} />
                          <div className="list-item-main">
                            <div className="list-item-title">{t.title}</div>
                            <div className="list-item-sub" style={due.overdue ? { color: "var(--danger)" } : undefined}>{due.text}</div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <Empty icon={<ListTodo size={22} />} title="No open tasks">Your operator adds follow-ups here as it works.</Empty>
                )}
              </div>
              <div className="card">
                <div className="card-header">
                  <div className="card-title">Latest conversations</div>
                  <Link to="/inbox" className="btn btn-ghost btn-sm">Inbox</Link>
                </div>
                {data.conversations.length ? (
                  <div className="list">
                    {data.conversations.map((c) => (
                      <Link to={`/inbox?c=${encodeURIComponent(c.id)}`} className="list-item clickable" key={c.id} style={{ color: "inherit", textDecoration: "none" }}>
                        <div className="avatar">{initials(c.title || c.channel)}</div>
                        <div className="list-item-main">
                          <div className="list-item-title">{c.title || "Customer"}</div>
                          <div className="list-item-sub">{c.last_message}</div>
                        </div>
                        <div className="list-item-meta">{timeAgo(c.updated_at)}</div>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <Empty icon={<Inbox size={22} />} title="No customer chats yet">Connect a channel or try a customer preview.</Empty>
                )}
              </div>
              <div className="card">
                <div className="card-title" style={{ marginBottom: 10 }}>Activity</div>
                {data.activity.length ? (
                  <div className="timeline">
                    {data.activity.slice(0, 8).map((a) => (
                      <div className="timeline-item" key={a.id}>
                        <span className="timeline-dot" />
                        <div>
                          <div className="small">{a.title}</div>
                          <div className="tiny">{timeAgo(a.created_at)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="muted small">Activity from your operator will appear here.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ icon, label, value, foot, warn }: { icon: ReactNode; label: string; value: number; foot: string; warn?: boolean }) {
  return (
    <div className="card stat">
      <div className="stat-label">{icon} {label}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-foot" style={warn ? { color: "var(--warning)" } : undefined}>{foot}</div>
    </div>
  );
}

function Briefing({ latest, mode, onRan }: { latest: AutopilotRun | null; mode: string; onRan: () => void }) {
  const notify = useToast();
  const [running, setRunning] = useState(false);

  const run = async () => {
    setRunning(true);
    try {
      const res = await api<AutopilotRun>("/api/autopilot/run", "POST");
      if (res.status !== "completed") notify(res.error || "Review couldn't run.", true);
      onRan();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="card card-hero">
      <div className="card-header">
        <div className="row">
          <div className="icon-tile" style={{ background: "var(--violet-soft)", color: "var(--violet)" }}><TrendingUp size={18} /></div>
          <div>
            <div className="card-title">Today's briefing</div>
            <div className="card-subtitle">
              {latest ? `Autopilot review · ${timeAgo(latest.finished_at ?? latest.started_at)}` : "Your operator reviews the business on its own"} · <Link to="/autopilot">mode: {mode}</Link>
            </div>
          </div>
        </div>
        <button className="btn btn-sm" onClick={run} disabled={running}>
          <RefreshCw size={14} style={running ? { animation: "spin 1s linear infinite" } : undefined} /> {running ? "Reviewing…" : "Review now"}
        </button>
      </div>
      {latest ? (
        <div className="stack-sm">
          <RichText text={latest.summary} />
          {latest.insights.length > 0 && (
            <div className="stack-sm" style={{ marginTop: 6 }}>
              {latest.insights.map((i, n) => (
                <div key={n} className="row" style={{ alignItems: "flex-start" }}>
                  <span className={`badge ${PRIORITY_TONE[i.priority] ?? ""}`}>{i.priority}</span>
                  <div className="small"><span className="strong">{i.title}</span> — <span className="muted">{i.detail}</span></div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <Empty icon={<Rocket size={22} />} title="No briefing yet" action={<button className="btn btn-primary btn-sm" onClick={run} disabled={running}>Run the first review</button>}>
          Autopilot studies your customers, tasks and setup, acts on safe work and tells you what needs you.
        </Empty>
      )}
    </div>
  );
}

function SetupCard({ data }: { data: Dashboard }) {
  const done = data.setup.steps.filter((s) => s.done).length;
  const link: Record<string, string> = { ai: "/integrations", profile: "/settings", channel: "/integrations", owner: "/settings" };
  return (
    <div className="card card-hero">
      <div className="row-between wrap">
        <div>
          <div className="card-title">Finish setting up</div>
          <div className="card-subtitle">{done} of {data.setup.steps.length} done — each step makes your operator more capable.</div>
        </div>
        <Link to="/setup" className="btn btn-primary btn-sm">Continue setup <ArrowRight size={14} /></Link>
      </div>
      <div className="row wrap" style={{ gap: 18, marginTop: 14 }}>
        {data.setup.steps.map((s) => (
          <Link key={s.id} to={link[s.id]} className="row small" style={{ color: s.done ? "var(--text-2)" : "var(--text)", textDecoration: "none" }}>
            {s.done ? <CheckCircle2 size={17} color="var(--success)" /> : <Circle size={17} color="var(--text-3)" />} {s.title}
          </Link>
        ))}
      </div>
    </div>
  );
}
