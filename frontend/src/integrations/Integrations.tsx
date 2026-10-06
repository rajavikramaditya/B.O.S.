import { useState } from "react";
import { Blocks, Bot, Code2, ExternalLink, KeyRound, Mail, MessageCircle, Plug, Send, Trash2, Webhook } from "lucide-react";
import { api } from "../api/client";
import type { ApiKey, Connector, WebhookSub } from "../api/types";
import { useSession } from "../auth/session";
import { CopyField, Empty, ErrorNote, LoadingCard, Modal, PageHeader } from "../ui/primitives";
import { timeAgo } from "../ui/time";
import { useToast } from "../ui/toast";
import { useResource } from "../ui/useResource";
import { ConnectorForm } from "./ConnectorForm";

const ICONS: Record<string, typeof Send> = {
  anthropic: Bot,
  gemini: Bot,
  telegram: Send,
  whatsapp: MessageCircle,
  email: Mail,
  webhooks: Webhook,
  rest_api: Code2,
  mcp: Plug,
};

export function Integrations() {
  const [tab, setTab] = useState<"apps" | "developer">("apps");
  return (
    <div className="page">
      <PageHeader
        title="Integrations"
        subtitle="Plug B.O.S. into the tools you already use. Everything connects through open standards — REST, webhooks and MCP."
        actions={
          <div className="segmented" role="tablist">
            <button role="tab" aria-selected={tab === "apps"} onClick={() => setTab("apps")}>Apps & channels</button>
            <button role="tab" aria-selected={tab === "developer"} onClick={() => setTab("developer")}>Developer</button>
          </div>
        }
      />
      {tab === "apps" ? <Apps /> : <Developer />}
    </div>
  );
}

function Apps() {
  const notify = useToast();
  const { refreshSetup } = useSession();
  const { data, error, reload } = useResource<{ connectors: Connector[]; public_base_url: string }>("/api/integrations");
  const [open, setOpen] = useState<Connector | null>(null);

  if (error) return <ErrorNote message={error} />;
  if (!data) return <LoadingCard />;

  const groups = data.connectors.filter((c) => c.kind !== "builtin").reduce<Record<string, Connector[]>>((acc, c) => {
    (acc[c.category] ??= []).push(c);
    return acc;
  }, {});

  const disconnect = async (c: Connector) => {
    if (!confirm(`Disconnect ${c.name}?`)) return;
    try {
      await api(`/api/integrations/${c.id}`, "DELETE");
      notify(`${c.name} disconnected.`);
      reload();
      refreshSetup();
    } catch (e) {
      notify((e as Error).message, true);
    }
  };

  return (
    <div className="stack">
      {!data.public_base_url && (
        <div className="alert alert-info">Set <code>PUBLIC_BASE_URL</code> on the server to an https address so channels like Telegram and WhatsApp can deliver messages to B.O.S.</div>
      )}
      {Object.entries(groups).map(([category, list]) => (
        <section key={category} className="stack-sm">
          <h2 className="small muted strong" style={{ textTransform: "uppercase", letterSpacing: "0.06em" }}>{category}</h2>
          <div className="grid-cards">
            {list.map((c) => {
              const Icon = ICONS[c.id] ?? Blocks;
              return (
                <div key={c.id} className="card stack-sm" style={{ display: "flex", flexDirection: "column" }}>
                  <div className="row-between">
                    <div className="icon-tile"><Icon size={18} /></div>
                    {c.connected ? <span className="badge badge-success"><span className="dot" /> Connected</span> : <span className="badge">Not connected</span>}
                  </div>
                  <div>
                    <div className="strong">{c.name}</div>
                    <div className="small muted">{c.description}</div>
                  </div>
                  {c.connected && c.meta && Object.keys(c.meta).length > 0 && (
                    <div className="tiny muted stack-sm">
                      {Object.entries(c.meta).map(([k, v]) => <div key={k}><span className="faint">{k.replace(/_/g, " ")}:</span> {String(v)}</div>)}
                    </div>
                  )}
                  {c.model && c.connected && <div className="tiny muted">Model: {c.model}</div>}
                  <div className="row" style={{ marginTop: "auto" }}>
                    <button className={`btn btn-sm ${c.connected ? "" : "btn-primary"}`} onClick={() => setOpen(c)}>{c.connected ? "Update" : "Connect"}</button>
                    {c.connected && <button className="btn btn-sm btn-ghost" onClick={() => disconnect(c)}>Disconnect</button>}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ))}
      {open && (
        <Modal title={`Connect ${open.name}`} onClose={() => setOpen(null)}>
          <p className="muted small" style={{ marginBottom: 16 }}>{open.description}</p>
          {open.inbound_url && (
            <div className="field" style={{ marginBottom: 14 }}>
              <span className="label">Webhook URL for {open.vendor}</span>
              <CopyField value={open.inbound_url} />
            </div>
          )}
          <ConnectorForm
            connector={open}
            onConnected={(c) => {
              notify(`${c.name} connected.`);
              setOpen(null);
              reload();
              refreshSetup();
            }}
          />
        </Modal>
      )}
    </div>
  );
}

function Developer() {
  const origin = window.location.origin;
  return (
    <div className="stack">
      <div className="grid-halves">
        <ApiKeys />
        <div className="card stack-sm">
          <div className="row"><div className="icon-tile"><Plug size={18} /></div><div><div className="card-title">MCP server</div><div className="card-subtitle">Let Claude, Cursor or any MCP client operate your business.</div></div></div>
          <p className="small muted">Add this to your MCP client config, using an API key with the <code>operator</code> scope (add <code>records:read</code> to let agents read contacts and tasks):</p>
          <div className="code">{JSON.stringify({ mcpServers: { bos: { type: "http", url: `${origin}/mcp`, headers: { Authorization: "Bearer bos_live_…" } } } }, null, 2)}</div>
          <p className="tiny faint">Agents go through the same policy and approvals as everyone else.</p>
        </div>
      </div>
      <Webhooks />
      <div className="card row-between wrap">
        <div className="row"><div className="icon-tile"><Code2 size={18} /></div><div><div className="card-title">REST API</div><div className="card-subtitle">Versioned <code>/v1</code> endpoints for messages, actions, events, contacts and tasks.</div></div></div>
        <a className="btn" href="/api/docs" target="_blank" rel="noreferrer">Open API docs <ExternalLink size={14} /></a>
      </div>
    </div>
  );
}

const SCOPE_HELP: Record<string, string> = {
  runtime: "Customer messages. Safe for a website chat.",
  operator: "Act as staff: /v1/actions and the MCP server.",
  "records:read": "Read contacts and tasks.",
  "records:write": "Save contacts and tasks.",
  events: "Report external events.",
};

function ApiKeys() {
  const notify = useToast();
  const { data, reload } = useResource<{ keys: ApiKey[]; scopes: string[]; default_scopes: string[] }>("/api/developer/keys");
  const [name, setName] = useState("");
  const [picked, setPicked] = useState<string[] | null>(null);
  const [created, setCreated] = useState<ApiKey | null>(null);
  const scopes = picked ?? data?.default_scopes ?? ["runtime"];
  const toggle = (s: string) => setPicked(scopes.includes(s) ? scopes.filter((x) => x !== s) : [...scopes, s]);

  const create = async () => {
    if (!scopes.length) {
      notify("Pick at least one permission for this key.", true);
      return;
    }
    try {
      setCreated(await api<ApiKey>("/api/developer/keys", "POST", { name: name || "API key", scopes }));
      setName("");
      setPicked(null);
      reload();
    } catch (e) {
      notify((e as Error).message, true);
    }
  };

  const revoke = async (k: ApiKey) => {
    if (!confirm(`Revoke "${k.name}"? Apps using it will stop working.`)) return;
    await api(`/api/developer/keys/${k.id}`, "DELETE");
    reload();
  };

  const active = data?.keys.filter((k) => !k.revoked) ?? [];
  return (
    <div className="card stack-sm">
      <div className="row"><div className="icon-tile"><KeyRound size={18} /></div><div><div className="card-title">API keys</div><div className="card-subtitle">For websites, apps and automation tools.</div></div></div>
      <div className="row">
        <input className="input" placeholder="Key name, e.g. Website chat" value={name} onChange={(e) => setName(e.target.value)} />
        <button className="btn btn-primary" onClick={create}>Create</button>
      </div>
      <div className="stack-sm">
        <div className="tiny faint">Permissions. Give each key only what it needs.</div>
        <div className="chips">
          {(data?.scopes ?? []).map((s) => (
            <button key={s} type="button" className="chip" aria-pressed={scopes.includes(s)} title={SCOPE_HELP[s]} onClick={() => toggle(s)}>{s}</button>
          ))}
        </div>
        <div className="tiny faint">{scopes.map((s) => SCOPE_HELP[s]).filter(Boolean).join(" ")}</div>
      </div>
      <div className="list">
        {active.map((k) => (
          <div key={k.id} className="list-item">
            <div className="list-item-main">
              <div className="list-item-title">{k.name}</div>
              <div className="list-item-sub"><code>{k.prefix}…</code> · {k.scopes.join(", ")} · {k.last_used_at ? `used ${timeAgo(k.last_used_at)}` : "never used"}</div>
            </div>
            <button className="btn btn-icon btn-sm" aria-label="Revoke" onClick={() => revoke(k)}><Trash2 size={14} /></button>
          </div>
        ))}
      </div>
      {created?.key && (
        <Modal title="Your new API key" onClose={() => setCreated(null)} actions={<button className="btn btn-primary" onClick={() => setCreated(null)}>Done</button>}>
          <p className="small muted" style={{ marginBottom: 12 }}>Copy it now — for your security it won't be shown again.</p>
          <CopyField value={created.key} />
        </Modal>
      )}
    </div>
  );
}

function Webhooks() {
  const notify = useToast();
  const { data, reload } = useResource<{ webhooks: WebhookSub[]; events: string[]; deliveries: { event: string; success: boolean; status_code: number | null; attempted_at: number }[] }>("/api/developer/webhooks");
  const [url, setUrl] = useState("");
  const [created, setCreated] = useState<WebhookSub | null>(null);

  const add = async () => {
    try {
      setCreated(await api<WebhookSub>("/api/developer/webhooks", "POST", { url, events: ["*"] }));
      setUrl("");
      reload();
    } catch (e) {
      notify((e as Error).message, true);
    }
  };

  const remove = async (w: WebhookSub) => {
    await api(`/api/developer/webhooks/${w.id}`, "DELETE");
    reload();
  };

  return (
    <div className="card stack-sm">
      <div className="row"><div className="icon-tile"><Webhook size={18} /></div><div><div className="card-title">Webhooks</div><div className="card-subtitle">Real-time, signed events to Zapier, Make, n8n or your own servers.</div></div></div>
      <div className="row">
        <input className="input" placeholder="https://hooks.zapier.com/…" value={url} onChange={(e) => setUrl(e.target.value)} />
        <button className="btn btn-primary" onClick={add} disabled={!url}>Add</button>
      </div>
      {data && !data.webhooks.length && <Empty icon={<Webhook size={22} />} title="No webhooks yet">Events: {data.events.join(", ")}</Empty>}
      <div className="list">
        {data?.webhooks.map((w) => (
          <div key={w.id} className="list-item">
            <div className="list-item-main">
              <div className="list-item-title">{w.url}</div>
              <div className="list-item-sub">{w.events.join(", ")}</div>
            </div>
            <button className="btn btn-icon btn-sm" aria-label="Delete" onClick={() => remove(w)}><Trash2 size={14} /></button>
          </div>
        ))}
      </div>
      {data && data.deliveries.length > 0 && (
        <div className="tiny muted">
          Recent deliveries: {data.deliveries.slice(0, 5).map((d, i) => <span key={i} style={{ color: d.success ? "var(--success)" : "var(--danger)", marginRight: 10 }}>{d.event} {d.status_code ?? "×"}</span>)}
        </div>
      )}
      {created?.secret && (
        <Modal title="Webhook signing secret" onClose={() => setCreated(null)} actions={<button className="btn btn-primary" onClick={() => setCreated(null)}>Done</button>}>
          <p className="small muted" style={{ marginBottom: 12 }}>
            Verify each delivery: compute HMAC-SHA256 of <code>{"<t>.<body>"}</code> with this secret and compare it to <code>v1</code> in the <code>BOS-Signature</code> header. Shown once.
          </p>
          <CopyField value={created.secret} />
        </Modal>
      )}
    </div>
  );
}
