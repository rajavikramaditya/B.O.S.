import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Bot, CheckCircle2, Mail, MessageCircle, Send, Sparkles } from "lucide-react";
import { api } from "../api/client";
import type { BusinessProfile, Connector, Owner } from "../api/types";
import { useSession } from "../auth/session";
import { ConnectorForm } from "../integrations/ConnectorForm";
import { ErrorNote } from "../ui/primitives";

type StepId = "account" | "business" | "ai" | "channel" | "done";

const INDUSTRIES = [
  "Retail store",
  "Restaurant & café",
  "Salon & spa",
  "Clinic & healthcare",
  "Education & coaching",
  "Real estate",
  "Agency & services",
  "E-commerce",
  "Media & radio",
];
const LANGUAGES = ["English", "Hindi", "Hinglish", "Marathi", "Tamil", "Bengali", "Gujarati", "Arabic", "Spanish"];

export function Onboarding() {
  const { owner, setup, signIn, refreshSetup } = useSession();
  const navigate = useNavigate();

  // The step list is fixed when the wizard opens so it doesn't jump mid-flow.
  const [steps] = useState<StepId[]>(() => {
    const list: StepId[] = [];
    if (!owner) list.push("account");
    list.push("business");
    if (!setup?.ai.configured) list.push("ai");
    list.push("channel", "done");
    return list;
  });
  const [index, setIndex] = useState(0);
  const step = steps[index];
  const next = () => setIndex((i) => Math.min(i + 1, steps.length - 1));
  const back = () => setIndex((i) => Math.max(i - 1, 0));

  const finish = async () => {
    await refreshSetup();
    navigate("/", { replace: true });
  };

  return (
    <div className="flow">
      <div className={`flow-card${step === "business" ? " wide" : ""}`}>
        <div className="progress" aria-hidden>
          {steps.map((s, i) => (
            <span key={s} className={i <= index ? "done" : ""} />
          ))}
        </div>
        {step === "account" && <AccountStep onDone={(token, who) => { signIn(token, who); next(); }} />}
        {step === "business" && <BusinessStep onDone={next} onBack={index > 0 && steps[index - 1] !== "account" ? back : undefined} />}
        {step === "ai" && <AiStep onDone={next} onBack={back} />}
        {step === "channel" && <ChannelStep onDone={next} onBack={back} />}
        {step === "done" && <DoneStep onFinish={finish} onPreview={async () => { await refreshSetup(); navigate("/assistant?preview=1", { replace: true }); }} />}
      </div>
    </div>
  );
}

function AccountStep({ onDone }: { onDone: (token: string, owner: Owner) => void }) {
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api<{ token: string; owner: Owner }>("/api/setup/owner", "POST", form);
      onDone(res.token, res.owner);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <div className="flow-logo"><Sparkles size={24} /></div>
      <h1 className="flow-title">Let's set up your <span className="gradient-text">B.O.S.</span></h1>
      <p className="flow-subtitle">An AI operator that runs your business with you — it guides customers, follows up, and keeps everything moving. Setup takes about three minutes.</p>
      <div className="flow-body">
        {error && <div style={{ marginBottom: 14 }}><ErrorNote message={error} /></div>}
        <div className="field">
          <label className="label" htmlFor="name">Your name</label>
          <input id="name" className="input" required autoFocus value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div className="field">
          <label className="label" htmlFor="email">Email</label>
          <input id="email" className="input" type="email" required autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </div>
        <div className="field">
          <label className="label" htmlFor="password">Password</label>
          <input id="password" className="input" type="password" minLength={8} required autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <span className="hint">At least 8 characters. You're the owner — only you approve important actions.</span>
        </div>
      </div>
      <div className="flow-actions">
        <span />
        <button className="btn btn-primary btn-lg" disabled={busy}>{busy ? "Creating…" : "Create account"} <ArrowRight size={18} /></button>
      </div>
    </form>
  );
}

function BusinessStep({ onDone, onBack }: { onDone: () => void; onBack?: () => void }) {
  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<BusinessProfile>("/api/business/profile").then(setProfile).catch((e) => setError(e.message));
  }, []);

  if (!profile) return error ? <ErrorNote message={error} /> : <div className="skeleton" style={{ height: 260 }} />;
  const set = (patch: Partial<BusinessProfile>) => setProfile({ ...profile, ...patch });
  const toggleLanguage = (lang: string) =>
    set({ languages: profile.languages.includes(lang) ? profile.languages.filter((l) => l !== lang) : [...profile.languages, lang] });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/api/business/profile", "PUT", profile);
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <h1 className="flow-title">Tell us about your business</h1>
      <p className="flow-subtitle">This is what your AI operator learns from. Write like you'd brief a new manager — plain words are perfect.</p>
      <div className="flow-body">
        {error && <div style={{ marginBottom: 14 }}><ErrorNote message={error} /></div>}
        <div className="form-grid">
          <div className="field">
            <label className="label" htmlFor="bname">Business name</label>
            <input id="bname" className="input" required value={profile.name} onChange={(e) => set({ name: e.target.value })} autoFocus />
          </div>
          <div className="field">
            <label className="label" htmlFor="industry">Industry</label>
            <input id="industry" className="input" list="industries" placeholder="Pick or type" value={profile.industry} onChange={(e) => set({ industry: e.target.value })} />
            <datalist id="industries">{INDUSTRIES.map((i) => <option key={i} value={i} />)}</datalist>
          </div>
          <div className="field span-2">
            <label className="label" htmlFor="desc">What does your business do?</label>
            <textarea id="desc" className="textarea" required placeholder="e.g. A neighbourhood bakery in Pune known for custom birthday cakes and same-day delivery." value={profile.description} onChange={(e) => set({ description: e.target.value })} />
          </div>
          <div className="field span-2">
            <label className="label" htmlFor="offer">Products, services & prices</label>
            <textarea id="offer" className="textarea" placeholder="List what you sell with prices if you like. Your operator will never invent prices that aren't here." value={profile.offerings} onChange={(e) => set({ offerings: e.target.value })} />
          </div>
          <div className="field">
            <label className="label" htmlFor="customers">Who are your customers?</label>
            <input id="customers" className="input" placeholder="e.g. Families, offices nearby" value={profile.target_customers} onChange={(e) => set({ target_customers: e.target.value })} />
          </div>
          <div className="field">
            <label className="label" htmlFor="hours">Hours & location</label>
            <input id="hours" className="input" placeholder="e.g. 9am–9pm, Baner, Pune" value={profile.hours} onChange={(e) => set({ hours: e.target.value })} />
          </div>
          <div className="field">
            <label className="label" htmlFor="aname">Name your AI operator</label>
            <input id="aname" className="input" value={profile.assistant_name} onChange={(e) => set({ assistant_name: e.target.value })} />
          </div>
          <div className="field">
            <label className="label" htmlFor="tone">Tone of voice</label>
            <input id="tone" className="input" value={profile.tone} onChange={(e) => set({ tone: e.target.value })} />
          </div>
          <div className="field span-2">
            <span className="label">Languages your customers use</span>
            <div className="chips">
              {LANGUAGES.map((l) => (
                <button type="button" key={l} className="chip" aria-pressed={profile.languages.includes(l)} onClick={() => toggleLanguage(l)}>{l}</button>
              ))}
            </div>
          </div>
        </div>
      </div>
      <div className="flow-actions">
        {onBack ? <button type="button" className="btn btn-ghost" onClick={onBack}><ArrowLeft size={16} /> Back</button> : <span />}
        <button className="btn btn-primary btn-lg" disabled={busy}>{busy ? "Saving…" : "Continue"} <ArrowRight size={18} /></button>
      </div>
    </form>
  );
}

function useConnectors() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  useEffect(() => {
    api<{ connectors: Connector[] }>("/api/integrations").then((r) => setConnectors(r.connectors)).catch(() => {});
  }, []);
  return connectors;
}

function AiStep({ onDone, onBack }: { onDone: () => void; onBack: () => void }) {
  const connectors = useConnectors().filter((c) => c.kind === "ai");
  const [chosen, setChosen] = useState("anthropic");
  const connector = connectors.find((c) => c.id === chosen);

  return (
    <div>
      <div className="flow-logo"><Bot size={24} /></div>
      <h1 className="flow-title">Connect an AI model</h1>
      <p className="flow-subtitle">This is the brain your operator thinks with. You can switch any time — B.O.S. isn't locked to one vendor.</p>
      <div className="flow-body stack">
        <div className="stack-sm">
          {connectors.map((c) => (
            <button key={c.id} type="button" className="choice" aria-pressed={chosen === c.id} onClick={() => setChosen(c.id)}>
              <div className="icon-tile"><Sparkles size={18} /></div>
              <div>
                <div className="choice-title">{c.name} <span className="faint small">by {c.vendor}</span> {c.id === "anthropic" && <span className="badge badge-accent">Recommended</span>}</div>
                <div className="choice-desc">{c.description}</div>
              </div>
            </button>
          ))}
        </div>
        {connector && <ConnectorForm key={connector.id} connector={connector} onConnected={onDone} submitLabel="Connect & continue" />}
      </div>
      <div className="flow-actions">
        <button type="button" className="btn btn-ghost" onClick={onBack}><ArrowLeft size={16} /> Back</button>
        <button type="button" className="btn btn-ghost" onClick={onDone}>I'll do this later</button>
      </div>
    </div>
  );
}

const CHANNEL_ICON: Record<string, typeof Send> = { telegram: Send, whatsapp: MessageCircle, email: Mail };

function ChannelStep({ onDone, onBack }: { onDone: () => void; onBack: () => void }) {
  const connectors = useConnectors().filter((c) => c.kind === "channel");
  const [chosen, setChosen] = useState<string>("");
  const connector = connectors.find((c) => c.id === chosen);

  return (
    <div>
      <div className="flow-logo"><MessageCircle size={24} /></div>
      <h1 className="flow-title">Where do customers reach you?</h1>
      <p className="flow-subtitle">Connect a channel and your operator starts answering, guiding and following up on its own. Telegram is the fastest to try.</p>
      <div className="flow-body stack">
        <div className="stack-sm">
          {connectors.map((c) => {
            const Icon = CHANNEL_ICON[c.id] ?? MessageCircle;
            return (
              <button key={c.id} type="button" className="choice" aria-pressed={chosen === c.id} onClick={() => setChosen(c.id)}>
                <div className="icon-tile"><Icon size={18} /></div>
                <div>
                  <div className="choice-title">{c.name} {c.connected && <span className="badge badge-success">Connected</span>}</div>
                  <div className="choice-desc">{c.description}</div>
                </div>
              </button>
            );
          })}
        </div>
        {connector && !connector.connected && <ConnectorForm key={connector.id} connector={connector} onConnected={onDone} submitLabel="Connect & continue" />}
      </div>
      <div className="flow-actions">
        <button type="button" className="btn btn-ghost" onClick={onBack}><ArrowLeft size={16} /> Back</button>
        <button type="button" className="btn" onClick={onDone}>Skip for now</button>
      </div>
    </div>
  );
}

function DoneStep({ onFinish, onPreview }: { onFinish: () => void; onPreview: () => void }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div className="flow-logo" style={{ margin: "0 auto 22px" }}><CheckCircle2 size={26} /></div>
      <h1 className="flow-title">You're all set</h1>
      <p className="flow-subtitle">Your operator is live. It will review your business on its own, act on safe tasks, and ask you before anything important. Try talking to it the way a customer would.</p>
      <div className="flow-actions" style={{ justifyContent: "center" }}>
        <button className="btn btn-lg" onClick={onPreview}>Try as a customer</button>
        <button className="btn btn-primary btn-lg" onClick={onFinish}>Open my dashboard <ArrowRight size={18} /></button>
      </div>
    </div>
  );
}
