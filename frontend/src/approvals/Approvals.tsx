import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import type { Approval } from "../api/types";
import { Empty, ErrorNote, LoadingCard, PageHeader } from "../ui/primitives";
import { useResource } from "../ui/useResource";
import { ApprovalCard } from "./ApprovalCard";

export function Approvals() {
  const [tab, setTab] = useState<"pending" | "all">("pending");
  const { data, error, reload } = useResource<Approval[]>(`/api/approvals?status_filter=${tab}`, 20000);

  return (
    <div className="page">
      <PageHeader
        title="Approvals"
        subtitle="Your operator handles routine work on its own. Anything that reaches people outside the business, or can't be undone, waits here for you."
        actions={
          <div className="segmented" role="tablist">
            <button role="tab" aria-selected={tab === "pending"} onClick={() => setTab("pending")}>Waiting</button>
            <button role="tab" aria-selected={tab === "all"} onClick={() => setTab("all")}>History</button>
          </div>
        }
      />
      {error && <ErrorNote message={error} />}
      {!data && !error && <LoadingCard />}
      {data && !data.length && (
        <div className="card">
          <Empty icon={<CheckCircle2 size={22} />} title={tab === "pending" ? "Nothing waiting" : "No decisions yet"}>
            {tab === "pending" ? "When your operator needs a yes or no, it shows up here." : "Approved and dismissed actions will be listed here."}
          </Empty>
        </div>
      )}
      <div className="stack">{data?.map((a) => <ApprovalCard key={a.id} approval={a} onDecided={reload} />)}</div>
    </div>
  );
}
