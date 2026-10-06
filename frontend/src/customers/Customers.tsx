import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Check, ListTodo, Search, Users } from "lucide-react";
import { api } from "../api/client";
import type { Contact, Task } from "../api/types";
import { Empty, ErrorNote, LoadingCard, PageHeader, StageBadge } from "../ui/primitives";
import { dueLabel, initials, timeAgo } from "../ui/time";
import { useToast } from "../ui/toast";
import { useResource } from "../ui/useResource";

export function Customers() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "tasks" ? "tasks" : "contacts";
  return (
    <div className="page">
      <PageHeader
        title="Customers"
        subtitle="Your operator saves every contact and plans every follow-up automatically. You can always see and steer it here."
        actions={
          <div className="segmented" role="tablist">
            <button role="tab" aria-selected={tab === "contacts"} onClick={() => setParams({})}>Contacts</button>
            <button role="tab" aria-selected={tab === "tasks"} onClick={() => setParams({ tab: "tasks" })}>Tasks</button>
          </div>
        }
      />
      {tab === "contacts" ? <Contacts /> : <Tasks />}
    </div>
  );
}

function Contacts() {
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState("");
  const { data, error } = useResource<Contact[]>(`/api/contacts?search=${encodeURIComponent(search)}&stage=${stage}`);

  return (
    <div className="card">
      <div className="row wrap" style={{ marginBottom: 14 }}>
        <div className="row grow" style={{ position: "relative", minWidth: 220 }}>
          <Search size={16} style={{ position: "absolute", left: 14, color: "var(--text-3)" }} />
          <input className="input" style={{ paddingLeft: 38 }} placeholder="Search name, phone or email" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="segmented">
          {["", "lead", "prospect", "customer"].map((s) => (
            <button key={s || "all"} aria-selected={stage === s} onClick={() => setStage(s)}>{s ? s[0].toUpperCase() + s.slice(1) + "s" : "All"}</button>
          ))}
        </div>
      </div>
      {error && <ErrorNote message={error} />}
      {!data && !error && <LoadingCard />}
      {data && !data.length && <Empty icon={<Users size={22} />} title="No contacts yet">When customers reach out, your operator adds them here with what it learned.</Empty>}
      {data && data.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr><th>Name</th><th>Stage</th><th>Reach</th><th>Channel</th><th>Notes</th><th>Last active</th></tr>
            </thead>
            <tbody>
              {data.map((c) => (
                <tr key={c.id}>
                  <td>
                    <div className="row">
                      <div className="avatar" style={{ width: 30, height: 30, fontSize: 11 }}>{initials(c.name || c.phone || c.email)}</div>
                      <span className="strong">{c.name || "Unnamed"}</span>
                    </div>
                  </td>
                  <td><StageBadge stage={c.stage} /></td>
                  <td className="small">{c.phone || c.email || "—"}</td>
                  <td className="small muted">{c.channel || "—"}</td>
                  <td className="small muted" style={{ maxWidth: 280 }}><div className="truncate">{c.notes || "—"}</div></td>
                  <td className="small faint">{timeAgo(c.last_interaction_at ?? c.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Tasks() {
  const notify = useToast();
  const [filter, setFilter] = useState<"open" | "done">("open");
  const { data, error, reload } = useResource<Task[]>(`/api/tasks?status_filter=${filter}`);

  const complete = async (task: Task) => {
    try {
      await api(`/api/tasks/${task.id}/complete`, "POST");
      notify(`Completed: ${task.title}`);
      reload();
    } catch (e) {
      notify((e as Error).message, true);
    }
  };

  return (
    <div className="card">
      <div className="row-between" style={{ marginBottom: 8 }}>
        <div className="card-title">Tasks</div>
        <div className="segmented">
          <button aria-selected={filter === "open"} onClick={() => setFilter("open")}>Open</button>
          <button aria-selected={filter === "done"} onClick={() => setFilter("done")}>Done</button>
        </div>
      </div>
      {error && <ErrorNote message={error} />}
      {!data && !error && <LoadingCard />}
      {data && !data.length && <Empty icon={<ListTodo size={22} />} title={filter === "open" ? "No open tasks" : "Nothing completed yet"}>Follow-ups planned by your operator appear here.</Empty>}
      <div className="list">
        {data?.map((t) => {
          const due = dueLabel(t.due_at);
          return (
            <div key={t.id} className="list-item">
              {filter === "open" ? (
                <button className="btn btn-icon btn-sm" aria-label="Mark done" onClick={() => complete(t)} style={{ borderRadius: "50%", border: "1.5px solid var(--line-strong)", background: "transparent" }}>
                  <Check size={14} color="var(--text-3)" />
                </button>
              ) : (
                <span className="icon-tile" style={{ width: 30, height: 30, background: "var(--success-soft)", color: "var(--success)" }}><Check size={14} /></span>
              )}
              <div className="list-item-main">
                <div className="list-item-title">{t.title}</div>
                <div className="list-item-sub" style={due.overdue && filter === "open" ? { color: "var(--danger)" } : undefined}>
                  {due.text}{t.description ? ` · ${t.description}` : ""}
                </div>
              </div>
              <span className="badge">{t.created_by === "runtime" ? "by operator" : t.created_by}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
