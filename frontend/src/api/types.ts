// Shapes returned by the B.O.S. API.

export interface SetupStep {
  id: "owner" | "ai" | "profile" | "channel";
  title: string;
  done: boolean;
}

export interface AiStatus {
  configured: boolean;
  active: { id: string; provider: string; model: string } | null;
}

/** Signed-out visitors only see `owner_exists` once a workspace has been set up. */
export interface SetupStatus {
  owner_exists: boolean;
  setup_token_required?: boolean;
  ai?: AiStatus;
  steps?: SetupStep[];
  complete?: boolean;
  connected_channels?: string[];
}

export interface Owner {
  id: string;
  name: string;
  email: string;
}

export interface BusinessProfile {
  name: string;
  industry: string;
  description: string;
  offerings: string;
  target_customers: string;
  goals: string[];
  tone: string;
  languages: string[];
  assistant_name: string;
  website: string;
  hours: string;
  location: string;
}

export interface Insight {
  title: string;
  detail: string;
  priority: "high" | "medium" | "low";
}

export interface AutopilotRun {
  id: string;
  trigger: string;
  status: string;
  summary: string;
  insights: Insight[];
  executed: { title: string; success: boolean; error?: string | null }[];
  pending_approvals: string[];
  error: string;
  started_at: number;
  finished_at: number | null;
}

export type AutopilotMode = "off" | "assist" | "autopilot" | "autonomous";

export interface Approval {
  id: string;
  title: string;
  rationale: string;
  capability: string;
  action: string;
  params: Record<string, unknown>;
  risk: string;
  source: string;
  status: string;
  result: { error?: string | null };
  created_at: number;
  decided_at: number | null;
}

export interface Contact {
  id: string;
  name: string;
  phone: string;
  email: string;
  channel: string;
  stage: string;
  tags: string[];
  notes: string;
  last_interaction_at: number | null;
  created_at: number;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: string;
  due_at: number | null;
  contact_id: string | null;
  created_by: string;
  created_at: number;
}

export interface Conversation {
  id: string;
  channel: string;
  actor: string;
  title: string;
  message_count: number;
  last_message: string;
  updated_at: number;
}

export interface MemoryMessage {
  role: "user" | "assistant";
  content: string;
  created_at: number;
}

export interface ActivityItem {
  id: number;
  kind: string;
  title: string;
  created_at: number;
}

export interface StepResult {
  step_id: number;
  title: string;
  success: boolean;
  error?: string | null;
  capability: string;
  action: string;
}

export interface RuntimeResult {
  reply: string;
  conversation_id: string;
  ai_available: boolean;
  workflow_status: string;
  executed_steps: StepResult[];
  approvals: Approval[];
  denied_steps: { step_id: number; reason: string }[];
}

export interface Dashboard {
  profile: BusinessProfile;
  autopilot: { mode: AutopilotMode; latest: AutopilotRun | null };
  stats: {
    contacts: { total: number; new_this_week: number; by_stage: Record<string, number> };
    tasks: { open: number; overdue: number; done_this_week: number };
    pending_approvals: number;
    conversations: number;
  };
  approvals: Approval[];
  tasks: Task[];
  conversations: Conversation[];
  activity: ActivityItem[];
  setup: { steps: SetupStep[]; complete: boolean };
}

export interface ConnectorField {
  key: string;
  label: string;
  secret: boolean;
  placeholder?: string;
}

export interface Connector {
  id: string;
  name: string;
  vendor: string;
  category: string;
  description: string;
  fields: ConnectorField[];
  docs_url?: string;
  docs_path?: string;
  kind: "ai" | "channel" | "builtin";
  connected: boolean;
  model?: string;
  meta?: Record<string, string>;
  inbound_url?: string;
}

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  revoked: boolean;
  created_at: number;
  last_used_at: number | null;
  key?: string;
}

export interface WebhookSub {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  description: string;
  secret?: string;
}
