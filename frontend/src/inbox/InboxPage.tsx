import { useSearchParams } from "react-router-dom";
import { Bot, Inbox, Mail, MessageCircle, Send, User } from "lucide-react";
import type { Conversation, MemoryMessage } from "../api/types";
import { Empty, ErrorNote, LoadingCard, PageHeader, RichText } from "../ui/primitives";
import { initials, timeAgo } from "../ui/time";
import { useResource } from "../ui/useResource";

const CHANNEL_ICON: Record<string, typeof Send> = { telegram: Send, whatsapp: MessageCircle, email: Mail, dashboard: User, autopilot: Bot };

export function InboxPage() {
  const [params, setParams] = useSearchParams();
  const selected = params.get("c");
  const { data, error } = useResource<{ conversations: Conversation[] }>("/api/conversations?limit=100", 20000);
  const conversations = (data?.conversations ?? []).filter((c) => c.actor !== "system" || c.channel === "autopilot");

  return (
    <div className="page">
      <PageHeader title="Inbox" subtitle="Every conversation across every channel — handled by your operator, visible to you." />
      {error && <ErrorNote message={error} />}
      <div className="inbox">
        <div className="card" style={{ padding: 10 }}>
          {!data && !error && <LoadingCard />}
          {data && !conversations.length && <Empty icon={<Inbox size={22} />} title="No conversations yet">They'll appear here as soon as customers write in.</Empty>}
          <div className="list">
            {conversations.map((c) => {
              const Icon = CHANNEL_ICON[c.channel] ?? MessageCircle;
              return (
                <button
                  key={c.id}
                  className={`list-item clickable${selected === c.id ? " active" : ""}`}
                  style={{ border: 0, background: selected === c.id ? undefined : "transparent", width: "100%", textAlign: "left" }}
                  onClick={() => setParams({ c: c.id })}
                >
                  <div className="avatar">{initials(c.title || c.channel)}</div>
                  <div className="list-item-main">
                    <div className="row" style={{ gap: 6 }}>
                      <span className="list-item-title">{c.title || labelFor(c)}</span>
                      <Icon size={13} color="var(--text-3)" />
                    </div>
                    <div className="list-item-sub">{c.last_message}</div>
                  </div>
                  <div className="list-item-meta">{timeAgo(c.updated_at)}</div>
                </button>
              );
            })}
          </div>
        </div>
        <div className="card">
          {selected ? <Transcript id={selected} /> : <Empty icon={<MessageCircle size={22} />} title="Select a conversation">Read the full exchange and what your operator did.</Empty>}
        </div>
      </div>
    </div>
  );
}

function labelFor(c: Conversation): string {
  if (c.actor === "owner") return "You";
  if (c.channel === "autopilot") return "Autopilot reviews";
  return c.channel ? `${c.channel[0].toUpperCase()}${c.channel.slice(1)} customer` : "Conversation";
}

function Transcript({ id }: { id: string }) {
  const { data, error } = useResource<{ conversation: Conversation; messages: MemoryMessage[] }>(`/api/conversations/${encodeURIComponent(id)}`, 15000);
  if (error) return <ErrorNote message={error} />;
  if (!data) return <LoadingCard />;
  return (
    <div>
      <div className="row-between" style={{ marginBottom: 14 }}>
        <div>
          <div className="card-title">{data.conversation.title || labelFor(data.conversation)}</div>
          <div className="card-subtitle">{data.conversation.channel} · {data.conversation.message_count} messages</div>
        </div>
      </div>
      <div className="transcript">
        {data.messages.map((m, i) => (
          <div key={i} className={`bubble-row ${m.role === "assistant" ? "them" : "me"}`}>
            <div className="bubble">{m.role === "assistant" ? <RichText text={m.content} /> : m.content}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
