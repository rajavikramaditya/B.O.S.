import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { SessionProvider, useSession } from "../auth/session";
import { SignIn } from "../auth/SignIn";
import { Onboarding } from "../onboarding/Onboarding";
import { ToastProvider } from "../ui/toast";
import { Spinner } from "../ui/primitives";
import { Shell, MorePage } from "./Shell";
import { Home } from "../home/Home";
import { Assistant } from "../assistant/Assistant";
import { InboxPage } from "../inbox/InboxPage";
import { Approvals } from "../approvals/Approvals";
import { Customers } from "../customers/Customers";
import { Autopilot } from "../autopilot/Autopilot";
import { Integrations } from "../integrations/Integrations";
import { Settings } from "../settings/Settings";

function Gate() {
  const { ready, owner, setup } = useSession();
  if (!ready) {
    return (
      <div className="flow"><Spinner /></div>
    );
  }
  if (!setup?.owner_exists) return <Onboarding />;
  if (!owner) return <SignIn />;

  return (
    <Routes>
      <Route path="/setup" element={<Onboarding />} />
      <Route element={<Shell />}>
        <Route index element={<Home />} />
        <Route path="assistant" element={<Assistant />} />
        <Route path="inbox" element={<InboxPage />} />
        <Route path="approvals" element={<Approvals />} />
        <Route path="customers" element={<Customers />} />
        <Route path="autopilot" element={<Autopilot />} />
        <Route path="integrations" element={<Integrations />} />
        <Route path="settings" element={<Settings />} />
        <Route path="more" element={<MorePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <SessionProvider>
          <Gate />
        </SessionProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
