import { useEffect, useState, type FormEvent } from "react";
import { Moon, Sun, SunMoon } from "lucide-react";
import { api } from "../api/client";
import type { BusinessProfile } from "../api/types";
import { useSession } from "../auth/session";
import { ErrorNote, LoadingCard, PageHeader } from "../ui/primitives";
import { useToast } from "../ui/toast";
import { saveTheme, storedTheme, type Theme } from "../ui/theme";

const FIELDS: { key: keyof BusinessProfile; label: string; area?: boolean; hint?: string }[] = [
  { key: "name", label: "Business name" },
  { key: "industry", label: "Industry" },
  { key: "description", label: "What the business does", area: true },
  { key: "offerings", label: "Products, services & prices", area: true, hint: "Your operator only quotes what's written here." },
  { key: "target_customers", label: "Customers" },
  { key: "hours", label: "Hours" },
  { key: "location", label: "Location" },
  { key: "website", label: "Website" },
  { key: "assistant_name", label: "Operator name" },
  { key: "tone", label: "Tone of voice" },
];

export function Settings() {
  const notify = useToast();
  const { owner, refreshSetup } = useSession();
  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [theme, setTheme] = useState<Theme>(storedTheme);

  useEffect(() => {
    api<BusinessProfile>("/api/business/profile").then(setProfile).catch((e) => setError(e.message));
  }, []);

  const chooseTheme = (t: Theme) => {
    saveTheme(t);
    setTheme(t);
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    setSaving(true);
    try {
      setProfile(await api<BusinessProfile>("/api/business/profile", "PUT", profile));
      notify("Saved. Your operator uses this right away.");
      refreshSetup();
    } catch (err) {
      notify((err as Error).message, true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <PageHeader title="Settings" subtitle="Your business profile is your operator's playbook. Keep it current and it gets better every day." />
      <div className="grid-2">
        <form className="card" onSubmit={save}>
          <div className="card-title" style={{ marginBottom: 16 }}>Business profile</div>
          {error && <ErrorNote message={error} />}
          {!profile && !error && <LoadingCard lines={5} />}
          {profile && (
            <>
              <div className="form-grid">
                {FIELDS.map((f) => (
                  <div key={f.key} className={`field${f.area ? " span-2" : ""}`}>
                    <label className="label" htmlFor={f.key}>{f.label}</label>
                    {f.area ? (
                      <textarea id={f.key} className="textarea" value={String(profile[f.key] ?? "")} onChange={(e) => setProfile({ ...profile, [f.key]: e.target.value })} />
                    ) : (
                      <input id={f.key} className="input" value={String(profile[f.key] ?? "")} onChange={(e) => setProfile({ ...profile, [f.key]: e.target.value })} />
                    )}
                    {f.hint && <span className="hint">{f.hint}</span>}
                  </div>
                ))}
                <div className="field span-2">
                  <label className="label" htmlFor="languages">Languages (comma separated)</label>
                  <input id="languages" className="input" value={profile.languages.join(", ")} onChange={(e) => setProfile({ ...profile, languages: e.target.value.split(",").map((l) => l.trim()).filter(Boolean) })} />
                </div>
              </div>
              <div className="row" style={{ justifyContent: "flex-end", marginTop: 20 }}>
                <button className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : "Save changes"}</button>
              </div>
            </>
          )}
        </form>
        <div className="stack">
          <div className="card stack-sm">
            <div className="card-title">Appearance</div>
            <div className="segmented">
              <button aria-selected={theme === "system"} onClick={() => chooseTheme("system")}><SunMoon size={14} /> Auto</button>
              <button aria-selected={theme === "light"} onClick={() => chooseTheme("light")}><Sun size={14} /> Light</button>
              <button aria-selected={theme === "dark"} onClick={() => chooseTheme("dark")}><Moon size={14} /> Dark</button>
            </div>
          </div>
          <div className="card stack-sm">
            <div className="card-title">Account</div>
            <div className="small"><span className="muted">Owner:</span> {owner?.name}</div>
            <div className="small"><span className="muted">Email:</span> {owner?.email}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
