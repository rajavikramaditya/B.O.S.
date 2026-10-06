import { NavLink, Outlet, Link } from "react-router-dom";
import {
  Blocks,
  CheckCircle2,
  Home,
  Inbox,
  LogOut,
  MessageSquareText,
  MoreHorizontal,
  Rocket,
  Settings,
  Sparkles,
  Users,
} from "lucide-react";
import { useSession } from "../auth/session";
import { useResource } from "../ui/useResource";

const NAV = [
  { to: "/", label: "Today", icon: Home, end: true },
  { to: "/assistant", label: "Assistant", icon: MessageSquareText },
  { to: "/inbox", label: "Inbox", icon: Inbox },
  { to: "/approvals", label: "Approvals", icon: CheckCircle2, badge: true },
  { to: "/customers", label: "Customers", icon: Users },
];
const NAV_SYSTEM = [
  { to: "/autopilot", label: "Autopilot", icon: Rocket },
  { to: "/integrations", label: "Integrations", icon: Blocks },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Shell() {
  const { setup, signOut, owner } = useSession();
  const { data: approvals } = useResource<unknown[]>("/api/approvals", 30000);
  const pending = approvals?.length ?? 0;
  const ai = setup?.ai;

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link to="/" className="brand" style={{ textDecoration: "none", color: "inherit" }}>
          <div className="brand-mark"><Sparkles size={16} /></div>
          <div>
            <div className="brand-name">B.O.S.</div>
            <div className="brand-sub">Business Operating System</div>
          </div>
        </Link>
        {NAV.map(({ to, label, icon: Icon, end, badge }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            <Icon /> {label}
            {badge && pending > 0 && <span className="nav-count">{pending}</span>}
          </NavLink>
        ))}
        <div className="nav-section">System</div>
        {NAV_SYSTEM.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            <Icon /> {label}
          </NavLink>
        ))}
        <div className="sidebar-foot">
          <Link to="/integrations" className="ai-status" style={{ textDecoration: "none" }}>
            <span className="dot" style={{ color: ai?.configured ? "var(--success)" : "var(--warning)" }} />
            <span className="truncate">{ai?.configured ? `AI · ${ai.active?.model}` : "AI not connected"}</span>
          </Link>
          <button className="nav-link" style={{ border: 0, background: "transparent", width: "100%" }} onClick={signOut} title={owner?.email}>
            <LogOut /> Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>

      <nav className="mobile-bar" aria-label="Primary">
        {[NAV[0], NAV[1], NAV[2], NAV[3]].map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "active" : "")}>
            <Icon /> {label}
            {to === "/approvals" && pending > 0 && <span className="nav-count" style={{ position: "absolute", top: 6, right: "calc(50% - 22px)" }}>{pending}</span>}
          </NavLink>
        ))}
        <NavLink to="/more" className={({ isActive }) => (isActive ? "active" : "")}>
          <MoreHorizontal /> More
        </NavLink>
      </nav>
    </div>
  );
}

export function MorePage() {
  const { signOut } = useSession();
  return (
    <div className="page">
      <h1 className="page-title" style={{ marginBottom: 20 }}>More</h1>
      <div className="card list">
        {[NAV[4], ...NAV_SYSTEM].map(({ to, label, icon: Icon }) => (
          <Link key={to} to={to} className="list-item clickable" style={{ color: "inherit", textDecoration: "none" }}>
            <div className="icon-tile"><Icon size={18} /></div>
            <div className="list-item-main list-item-title">{label}</div>
          </Link>
        ))}
        <button className="list-item clickable" style={{ border: 0, background: "transparent", width: "100%", textAlign: "left" }} onClick={signOut}>
          <div className="icon-tile"><LogOut size={18} /></div>
          <div className="list-item-main list-item-title">Sign out</div>
        </button>
      </div>
    </div>
  );
}
