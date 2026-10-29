export type LeadStatus =
  | "new"
  | "contacted"
  | "qualified"
  | "hot"
  | "closed";

export type Conversation = {
  id: string;
  sender: "lead" | "ai";
  message: string;
  created_at: string;
};

export type Lead = {
  id: string;
  name: string;
  email: string;
  phone: string;
  source: string;
  status: LeadStatus;
  score: number;
  created_at: string;
  conversations: Conversation[];
};

export type LeadAlertStatus = "active" | "acknowledged" | "resolved";

export type LeadAlert = {
  id: number;
  lead_id: number;
  alert_type: string;
  reason: string;
  score: number;
  qualification_summary: string;
  status: LeadAlertStatus;
  created_at: string;
  lead: {
    id: number;
    name: string;
    email: string;
    phone: string;
    source: string;
    lead_score: number;
    lead_temperature: string;
    ai_score: number;
    ai_temperature: string;
  };
};
