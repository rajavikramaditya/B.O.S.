import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowUp, CheckCircle2, Clock3, RotateCcw, Sparkles, XCircle } from "lucide-react";
import { api } from "../api/client";
import type { Approval, BusinessProfile, RuntimeResult, StepResult } from "../api/types";
import { ApprovalCard } from "../approvals/ApprovalCard";
import { PageHeader, RichText } from "../ui/primitives";
import { useResource } from "../ui/useResource";

type Mode = "owner" | "customer";

interface Turn {
  id: number;
  role: "me" | "them";
  text: string;
  steps?: StepResult[];
  approvals?: Approval[];
  denied?: { step_id: number; reason: string }[];
}

const OWNER_PROMPTS = [
  "What should I focus on today?",
  "Who are my warmest leads right now?",
  "Remind me to call Priya tomorrow at 11am",
  "Draft a festive offer message for my customers",
];
const CUSTOMER_PROMPTS = ["Hi! What do you offer?", "What are your prices?", "Can I book for this weekend?", "Do you deliver near me?"];

export function Assistant() {
  const [params] = useSearchParams();
  const [mode, setMode] = useState<Mode>(params.get("preview") ? "customer" : "owner");
  const { data: profile } = useResource<BusinessProfile>("/api/business/profile");
  const [threads, setThreads] = useState<Record<Mode, { id: string | null; turns: Turn[] }>>({
    owner: { id: null, turns: [] },
    customer: { id: null, turns: [] },
  });
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const thread = threads[mode];
  const name = profile?.assistant_name || "your operator";

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [thread.turns.length, busy]);

  const push = (m: Mode, turn: Turn, conversationId?: string) =>
    setThreads((t) => ({ ...t, [m]: { id: conversationId ?? t[m].id, turns: [...t[m].turns, turn] } }));

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    const m = mode;
    setDraft("");
    push(m, { id: Date.now(), role: "me", text: message });
    setBusy(true);
    try {
      const res = await api<RuntimeResult>("/api/chat", "POST", {
        message,
        conversation_id: threads[m].id,
        as_customer: m === "customer",
      });
      push(
        m,
        { id: Date.now() + 1, role: "them", text: res.reply || "…", steps: res.executed_steps, approvals: res.approvals, denied: res.denied_steps },
        res.conversation_id,
      );
    } catch (e) {
      push(m, { id: Date.now() + 1, role: "them", text: `⚠️ ${(e as Error).message}` });
    } finally {
      setBusy(false);
    }
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(draft);
    }
  };

  const reset = () => setThreads((t) => ({ ...t, [mode]: { id: null, turns: [] } }));

  return (
    <div className="page">
      <PageHeader
        title="Assistant"
        subtitle={mode === "owner" ? `Run your business by talking to ${name}. It acts, then tells you what it did.` : `See exactly what your customers experience — ${name} leads the conversation.`}
        actions={
          <>
            <div className="segmented" role="tablist">
              <button role="tab" aria-selected={mode === "owner"} onClick={() => setMode("owner")}>Talk to {name}</button>
              <button role="tab" aria-selected={mode === "customer"} onClick={() => setMode("customer")}>Preview as customer</button>
            </div>
            {thread.turns.length > 0 && (
              <button className="btn btn-sm" onClick={reset}><RotateCcw size={14} /> New chat</button>
            )}
          </>
        }
      />

      <div className="chat">
        <div className="chat-scroll" ref={scroller}>
          {thread.turns.length === 0 && (
            <div className="empty" style={{ margin: "auto 0" }}>
              <div className="flow-logo" style={{ margin: "0 auto 16px" }}><Sparkles size={24} /></div>
              <div className="empty-title" style={{ fontSize: 20 }}>{mode === "owner" ? `What can ${name} do for you?` : "You're a customer now"}</div>
              <div className="small">{mode === "owner" ? "Ask anything, or give an instruction in your own words." : "Say hello the way a real customer would."}</div>
              <div className="suggestions">
                {(mode === "owner" ? OWNER_PROMPTS : CUSTOMER_PROMPTS).map((p) => (
                  <button key={p} className="chip" onClick={() => send(p)}>{p}</button>
                ))}
              </div>
            </div>
          )}
          {thread.turns.map((turn) => (
            <div key={turn.id} className={`bubble-row ${turn.role}`}>
              <div className="bubble">
                {turn.role === "them" ? <RichText text={turn.text} /> : turn.text}
                {mode === "owner" && turn.role === "them" && <StepList turn={turn} />}
              </div>
            </div>
          ))}
          {busy && (
            <div className="bubble-row them">
              <div className="bubble typing" aria-label="Thinking"><span /><span /><span /></div>
            </div>
          )}
        </div>
        <div className="composer">
          <textarea
            rows={1}
            placeholder={mode === "owner" ? `Message ${name}…` : "Write as a customer…"}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKey}
            aria-label="Message"
          />
          <button className="btn btn-primary btn-icon" style={{ borderRadius: "50%" }} onClick={() => send(draft)} disabled={busy || !draft.trim()} aria-label="Send">
            <ArrowUp size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}

function StepList({ turn }: { turn: Turn }) {
  const steps = (turn.steps ?? []).filter((s) => s.action && !s.action.startsWith("list_") && !s.action.startsWith("find_"));
  if (!steps.length && !turn.approvals?.length && !turn.denied?.length) return null;
  return (
    <div className="bubble-steps">
      {steps.map((s) => (
        <div key={s.step_id} className={`step ${s.success ? "step-ok" : "step-fail"}`}>
          {s.success ? <CheckCircle2 /> : <XCircle />}
          <span style={{ color: "var(--text)" }}>{s.title}</span>
          {!s.success && s.error && <span className="tiny muted truncate">— {s.error}</span>}
        </div>
      ))}
      {turn.approvals?.map((a) => (
        <div key={a.id} className="step step-wait" style={{ display: "block", padding: 0, background: "transparent" }}>
          <div className="row tiny" style={{ marginBottom: 4 }}><Clock3 size={13} /> Waiting for your approval</div>
          <ApprovalCard approval={a} onDecided={() => {}} compact />
        </div>
      ))}
    </div>
  );
}
