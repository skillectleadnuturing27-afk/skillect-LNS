"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { type Lead, type LeadStatus } from "../lib/api";

// ==================================================
// TYPES
// ==================================================

type FollowUp = {
  date: string;
  time: string;
  priority: "low" | "medium" | "high";
  note: string;
};

type FollowUpStatus =
  | "Not Scheduled"
  | "Upcoming"
  | "Due Today"
  | "Overdue";

// ==================================================
// CONSTANTS
// ==================================================

const LEADS_STORAGE_KEY = "leadflow-leads";
const FOLLOWUPS_STORAGE_KEY = "leadflow-followups";

const statusClass: Record<LeadStatus, string> = {
  new: "blue",
  contacted: "purple",
  qualified: "green",
  hot: "red",
  closed: "gray",
};

const emptyFollowUp: FollowUp = {
  date: "",
  time: "",
  priority: "medium",
  note: "",
};

// ==================================================
// HELPERS
// ==================================================

function scoreClass(score: number) {
  return score >= 80 ? "hot" : score >= 50 ? "warm" : "cold";
}

function getFollowUpStatus(
  date: string,
  time: string
): FollowUpStatus {
  if (!date || !time) {
    return "Not Scheduled";
  }

  const scheduledDateTime = new Date(`${date}T${time}`);

  if (Number.isNaN(scheduledDateTime.getTime())) {
    return "Not Scheduled";
  }

  const now = new Date();

  const today = new Date(now);
  today.setHours(0, 0, 0, 0);

  const scheduledDay = new Date(scheduledDateTime);
  scheduledDay.setHours(0, 0, 0, 0);

  if (scheduledDay.getTime() === today.getTime()) {
    if (scheduledDateTime.getTime() < now.getTime()) {
      return "Overdue";
    }

    return "Due Today";
  }

  if (scheduledDateTime.getTime() < now.getTime()) {
    return "Overdue";
  }

  return "Upcoming";
}

function isSameDay(dateValue: string, compareDate: Date) {
  const date = new Date(dateValue);

  return (
    date.getFullYear() === compareDate.getFullYear() &&
    date.getMonth() === compareDate.getMonth() &&
    date.getDate() === compareDate.getDate()
  );
}

// ==================================================
// INITIAL MOCK LEADS
// ==================================================

const initialLeads: Lead[] = [
  {
    id: "1",
    name: "Priya",
    email: "priya@example.com",
    phone: "9876543212",
    source: "Instagram",
    status: "hot",
    score: 92,
    created_at: "2026-09-14T10:00:00",
    conversations: [
      {
        id: "p1",
        sender: "lead",
        message:
          "Hi, I am interested in the AWS Cloud Engineering course.",
        created_at: "2026-09-14T10:05:00",
      },
      {
        id: "p2",
        sender: "ai",
        message:
          "Great! Do you have any previous experience with AWS or cloud computing?",
        created_at: "2026-09-14T10:06:00",
      },
      {
        id: "p3",
        sender: "lead",
        message:
          "I am a beginner. I want to learn AWS and get a cloud job.",
        created_at: "2026-09-14T10:07:00",
      },
      {
        id: "p4",
        sender: "ai",
        message:
          "Perfect. Our AWS Cloud Engineering course is suitable for beginners and focuses on practical cloud skills and job preparation.",
        created_at: "2026-09-14T10:08:00",
      },
    ],
  },
  {
    id: "2",
    name: "Vathsan",
    email: "vathsan@example.com",
    phone: "9876543213",
    source: "Website",
    status: "qualified",
    score: 72,
    created_at: "2026-09-14T11:00:00",
    conversations: [],
  },
  {
    id: "3",
    name: "Test Lead",
    email: "test@example.com",
    phone: "9876543214",
    source: "Website",
    status: "new",
    score: 20,
    created_at: "2026-09-14T12:00:00",
    conversations: [],
  },
];

// ==================================================
// DASHBOARD
// ==================================================

export default function Dashboard() {
  // ==================================================
  // MAIN STATE
  // ==================================================

  const [leads, setLeads] = useState<Lead[]>(initialLeads);
  const [selected, setSelected] = useState<Lead | null>(null);
  const [storageLoaded, setStorageLoaded] = useState(false);

  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  const [filter, setFilter] =
    useState<"all" | LeadStatus>("all");
const [followUpFilter, setFollowUpFilter] =
  useState<"all" | "today" | "overdue">("all");

  // ==================================================
  // CREATE LEAD STATE
  // ==================================================

  const [showCreateForm, setShowCreateForm] =
    useState(false);

  const [newLead, setNewLead] = useState({
    name: "",
    phone: "",
    email: "",
    source: "",
    status: "new" as LeadStatus,
  });

  // ==================================================
  // EDIT LEAD STATE
  // ==================================================

  const [isEditing, setIsEditing] = useState(false);

  const [editLead, setEditLead] = useState({
    name: "",
    phone: "",
    email: "",
    source: "",
    status: "new" as LeadStatus,
  });

  // ==================================================
  // FOLLOW-UP STATE
  // ==================================================

  const [followUp, setFollowUp] =
    useState<FollowUp>(emptyFollowUp);

  const [followUpSaved, setFollowUpSaved] =
    useState(false);

  const [savedFollowUps, setSavedFollowUps] =
    useState<Record<string, FollowUp>>({});

  // ==================================================
  // LOAD LOCAL STORAGE
  // ==================================================

  useEffect(() => {
    let loadedLeads = initialLeads;

    try {
      const savedLeads =
        localStorage.getItem(LEADS_STORAGE_KEY);

      if (savedLeads) {
        const parsedLeads =
          JSON.parse(savedLeads) as Lead[];

        if (Array.isArray(parsedLeads)) {
          loadedLeads = parsedLeads;
        }
      }

      const storedFollowUps =
        localStorage.getItem(FOLLOWUPS_STORAGE_KEY);

      if (storedFollowUps) {
        const parsedFollowUps =
          JSON.parse(storedFollowUps);

        if (
          parsedFollowUps &&
          typeof parsedFollowUps === "object"
        ) {
          setSavedFollowUps(parsedFollowUps);
        }
      }
    } catch (err) {
      console.error(
        "Could not load LocalStorage data:",
        err
      );
    }

    setLeads(loadedLeads);
    setSelected(loadedLeads[0] ?? null);
    setStorageLoaded(true);
  }, []);

  // ==================================================
  // SAVE LEADS
  // ==================================================

  useEffect(() => {
    if (!storageLoaded) return;

    localStorage.setItem(
      LEADS_STORAGE_KEY,
      JSON.stringify(leads)
    );
  }, [leads, storageLoaded]);

  // ==================================================
  // SAVE FOLLOW-UPS
  // ==================================================

  useEffect(() => {
    if (!storageLoaded) return;

    localStorage.setItem(
      FOLLOWUPS_STORAGE_KEY,
      JSON.stringify(savedFollowUps)
    );
  }, [savedFollowUps, storageLoaded]);

  // ==================================================
  // LOAD SELECTED FOLLOW-UP
  // ==================================================

  useEffect(() => {
    if (!selected) {
      setFollowUp(emptyFollowUp);
      setFollowUpSaved(false);
      return;
    }

    const saved = savedFollowUps[selected.id];

    if (saved) {
      setFollowUp(saved);
      setFollowUpSaved(true);
    } else {
      setFollowUp(emptyFollowUp);
      setFollowUpSaved(false);
    }
  }, [selected, savedFollowUps]);

  // ==================================================
  // SEARCH + FILTER
  // ==================================================

 const visibleLeads = useMemo(() => {
  const searchText = query.trim().toLowerCase();

  return leads.filter((lead) => {
    const matchesSearch =
      `${lead.name} ${lead.email} ${lead.phone}`
        .toLowerCase()
        .includes(searchText);

    const matchesStatus =
      filter === "all" || lead.status === filter;

    let matchesFollowUp = true;

    // FOLLOW-UPS TODAY
    if (followUpFilter === "today") {
      const followUp = savedFollowUps[lead.id];

      if (!followUp?.date) {
        matchesFollowUp = false;
      } else {
        matchesFollowUp = isSameDay(
          followUp.date,
          new Date()
        );
      }
    }

    // OVERDUE FOLLOW-UPS
    if (followUpFilter === "overdue") {
      const followUp = savedFollowUps[lead.id];

      if (!followUp?.date || !followUp?.time) {
        matchesFollowUp = false;
      } else {
        matchesFollowUp =
          getFollowUpStatus(
            followUp.date,
            followUp.time
          ) === "Overdue";
      }
    }

    return (
      matchesSearch &&
      matchesStatus &&
      matchesFollowUp
    );
  });
}, [
  leads,
  query,
  filter,
  followUpFilter,
  savedFollowUps,
]);
// ==================================================
// SYNC SELECTED LEAD WITH FILTERED LIST
// ==================================================

useEffect(() => {
  if (!storageLoaded) return;

  // No leads match the current filter
  if (visibleLeads.length === 0) {
    setSelected(null);
    return;
  }

  // Keep current selection if it is still visible
  const selectedStillVisible = visibleLeads.some(
    (lead) => lead.id === selected?.id
  );

  // Otherwise select the first visible lead
  if (!selectedStillVisible) {
    setSelected(visibleLeads[0]);
    setIsEditing(false);
  }
}, [visibleLeads, selected, storageLoaded]);
  // ==================================================
  // DASHBOARD METRICS
  // ==================================================

  const today = new Date();

  const todayLeadCount = leads.filter((lead) =>
    isSameDay(lead.created_at, today)
  ).length;

  const qualifiedCount = leads.filter(
    (lead) =>
      lead.status === "qualified" ||
      lead.status === "hot"
  ).length;

  const hotCount = leads.filter(
    (lead) =>
      lead.status === "hot" ||
      lead.score >= 80
  ).length;

  const todayFollowUpCount =
    Object.values(savedFollowUps).filter((item) => {
      if (!item.date) return false;

      const followUpDate =
        new Date(`${item.date}T00:00:00`);

      return (
        followUpDate.getFullYear() === today.getFullYear() &&
        followUpDate.getMonth() === today.getMonth() &&
        followUpDate.getDate() === today.getDate()
      );
    }).length;

  const overdueFollowUpCount =
    Object.values(savedFollowUps).filter(
      (item) =>
        getFollowUpStatus(item.date, item.time) ===
        "Overdue"
    ).length;

  // ==================================================
  // OPEN LEAD
  // ==================================================

  function openLead(id: string) {
    const lead = leads.find(
      (item) => item.id === id
    );

    if (!lead) {
      setError("Lead could not be found.");
      return;
    }

    setError("");
    setSelected(lead);
    setIsEditing(false);
  }

  // ==================================================
  // CREATE LEAD
  // ==================================================

  function handleCreateLead(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();
    setError("");

    const name = newLead.name.trim();
    const phone = newLead.phone.trim();
    const email =
      newLead.email.trim().toLowerCase();
    const source = newLead.source.trim();

    const emailExists = leads.some(
      (lead) =>
        lead.email.toLowerCase() === email
    );

    if (emailExists) {
      setError(
        "A lead with this email already exists."
      );
      return;
    }

    const phoneExists = leads.some(
      (lead) => lead.phone === phone
    );

    if (phoneExists) {
      setError(
        "A lead with this phone number already exists."
      );
      return;
    }

    const createdLead: Lead = {
      id: Date.now().toString(),
      name,
      phone,
      email,
      source,
      status: newLead.status,
      score:
        newLead.status === "hot"
          ? 85
          : newLead.status === "qualified"
            ? 60
            : newLead.status === "contacted"
              ? 30
              : 10,
      created_at: new Date().toISOString(),
      conversations: [],
    };

    setLeads((current) => [
      createdLead,
      ...current,
    ]);

    setSelected(createdLead);

    setNewLead({
      name: "",
      phone: "",
      email: "",
      source: "",
      status: "new",
    });

    setShowCreateForm(false);
  }

  // ==================================================
  // START EDIT
  // ==================================================

  function startEditing() {
    if (!selected) return;

    setEditLead({
      name: selected.name,
      phone: selected.phone,
      email: selected.email,
      source: selected.source,
      status: selected.status,
    });

    setError("");
    setIsEditing(true);
  }

  function cancelEditing() {
    setIsEditing(false);
    setError("");
  }

  // ==================================================
  // SAVE EDIT
  // ==================================================

  function handleSaveEdit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    if (!selected) return;

    const selectedId = selected.id;

    setError("");

    const name = editLead.name.trim();
    const phone = editLead.phone.trim();

    const email =
      editLead.email.trim().toLowerCase();

    const source = editLead.source.trim();

    const emailExists = leads.some(
      (lead) =>
        lead.id !== selectedId &&
        lead.email.toLowerCase() === email
    );

    if (emailExists) {
      setError(
        "A lead with this email already exists."
      );
      return;
    }

    const phoneExists = leads.some(
      (lead) =>
        lead.id !== selectedId &&
        lead.phone === phone
    );

    if (phoneExists) {
      setError(
        "A lead with this phone number already exists."
      );
      return;
    }

    const updatedLead: Lead = {
      ...selected,
      name,
      phone,
      email,
      source,
      status: editLead.status,
    };

    setLeads((current) =>
      current.map((lead) =>
        lead.id === selectedId
          ? updatedLead
          : lead
      )
    );

    setSelected(updatedLead);
    setIsEditing(false);
  }

  // ==================================================
  // DELETE LEAD
  // ==================================================

  function handleDeleteLead() {
    if (!selected) return;

    const selectedId = selected.id;
    const selectedName = selected.name;

    const confirmed = window.confirm(
      `Delete ${selectedName}?`
    );

    if (!confirmed) return;

    const remainingLeads = leads.filter(
      (lead) => lead.id !== selectedId
    );

    setLeads(remainingLeads);
    setSelected(remainingLeads[0] ?? null);
    setIsEditing(false);

    setSavedFollowUps((current) => {
      const updated = { ...current };
      delete updated[selectedId];
      return updated;
    });

    setError("");
  }

  // ==================================================
  // SCHEDULE FOLLOW-UP
  // ==================================================

  function handleScheduleFollowUp() {
    if (!selected) return;

    const selectedId = selected.id;

    setError("");

    if (!followUp.date) {
      setError(
        "Please select a follow-up date."
      );
      return;
    }

    if (!followUp.time) {
      setError(
        "Please select a follow-up time."
      );
      return;
    }

    setSavedFollowUps((current) => ({
      ...current,
      [selectedId]: {
        ...followUp,
      },
    }));

    setFollowUpSaved(true);
  }

  // ==================================================
  // REMOVE FOLLOW-UP
  // ==================================================

  function handleRemoveFollowUp() {
    if (!selected) return;

    const selectedId = selected.id;
    const selectedName = selected.name;

    const confirmed = window.confirm(
      `Remove the follow-up for ${selectedName}?`
    );

    if (!confirmed) return;

    setSavedFollowUps((current) => {
      const updated = { ...current };
      delete updated[selectedId];
      return updated;
    });

    setFollowUp(emptyFollowUp);
    setFollowUpSaved(false);
    setError("");
  }

  // ==================================================
  // UI
  // ==================================================

  return (
    <main>
      {/* HEADER */}
      <header>
        <div>
          <p className="eyebrow">
            AI LEAD NURTURING MVP
          </p>

          <h1>Admin dashboard</h1>
        </div>

        <div className="live">
          <span />
          Live lead view
        </div>
      </header>

      {/* METRICS */}
      <section
        className="metrics"
        aria-label="Dashboard summary"
      >
        <Metric
          label="New Today"
          value={todayLeadCount}
          note="Leads entered today"
        />

        <Metric
          label="Qualified"
          value={qualifiedCount}
          note="Ready for follow-up"
        />

        <Metric
          label="Hot Leads"
          value={hotCount}
          note="Needs immediate attention"
          hot={hotCount > 0}
        />

        <Metric
          label="Follow-ups Today"
          value={todayFollowUpCount}
          note="Scheduled for today"
        />

        <Metric
          label="Overdue"
          value={overdueFollowUpCount}
          note="Requires attention"
          hot={overdueFollowUpCount > 0}
        />

        <Metric
          label="Total Leads"
          value={leads.length}
          note="All captured enquiries"
        />
      </section>

      {/* ERROR */}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

     {/* =========================
    NEEDS ATTENTION
========================= */}

<section
  className="attention-section"
  aria-label="Needs attention"
>
  <div className="attention-header">
    <div>
      <p className="eyebrow">
        ACTION CENTER
      </p>

      <h2>Needs Attention</h2>
    </div>

    <span className="attention-subtitle">
      Priority items requiring action
    </span>
  </div>

  <div className="attention-grid">

    {/* HOT LEADS */}
    <button
      type="button"
      className="attention-card hot-attention"
     onClick={() => {
  setFollowUpFilter("all");
  setFilter("hot");
}}
    >
      <div>
        <span className="attention-label">
          Hot Leads
        </span>

        <strong>{hotCount}</strong>

        <small>
          High-priority leads
        </small>
      </div>

      <span
        className="attention-icon"
        aria-hidden="true"
      >
        🔥
      </span>
    </button>


    {/* FOLLOW-UPS TODAY */}
  <button
  type="button"
  className="attention-card today-attention"
  onClick={() => {
    setFilter("all");
    setFollowUpFilter("today");
  }}
>
  <div>
    <span className="attention-label">
      Follow-ups Today
    </span>

    <strong>
      {todayFollowUpCount}
    </strong>

    <small>
      Scheduled for today
    </small>
  </div>

  <span
    className="attention-icon"
    aria-hidden="true"
  >
    📅
  </span>
</button>


    {/* OVERDUE FOLLOW-UPS */}
<button
  type="button"
  className="attention-card overdue-attention"
  onClick={() => {
    setFilter("all");
    setFollowUpFilter("overdue");
  }}
>
  <div>
    <span className="attention-label">
      Overdue Follow-ups
    </span>

    <strong>
      {overdueFollowUpCount}
    </strong>

    <small>
      Requires immediate action
    </small>
  </div>

  <span
    className="attention-icon"
    aria-hidden="true"
  >
    ⚠️
  </span>
</button>
  
  </div>
</section>


      {/* WORKSPACE */}

<section className="workspace-section">
  <div className="workspace-heading">
    <div>
      <p className="eyebrow">LEAD MANAGEMENT</p>
      <h2>Leads & Customer Details</h2>
    </div>

    <span>
      Search, manage and follow up with your leads
    </span>
  </div>

  
      <section className="workspace">
        {/* LEFT PANEL */}
        <div className="lead-panel">
          <div className="panel-title">
            <div>
              <h2>Leads</h2>

              <span>
                {visibleLeads.length} shown
              </span>
            </div>

            <button
              type="button"
              className="add-lead-button"
              onClick={() => {
                setShowCreateForm(
                  (current) => !current
                );
                setError("");
              }}
            >
              {showCreateForm
                ? "Cancel"
                : "+ Add Lead"}
            </button>
          </div>

          {/* CREATE FORM */}
          {showCreateForm && (
            <form
              className="create-lead-form"
              onSubmit={handleCreateLead}
            >
              <h3>Create new lead</h3>

              <input
                type="text"
                placeholder="Customer name"
                value={newLead.name}
                onChange={(event) =>
                  setNewLead({
                    ...newLead,
                    name: event.target.value,
                  })
                }
                required
                minLength={2}
              />

              <input
                type="tel"
                placeholder="Phone number"
                value={newLead.phone}
                onChange={(event) =>
                  setNewLead({
                    ...newLead,
                    phone: event.target.value,
                  })
                }
                required
                pattern="[0-9]{10}"
                maxLength={10}
              />

              <input
                type="email"
                placeholder="Email address"
                value={newLead.email}
                onChange={(event) =>
                  setNewLead({
                    ...newLead,
                    email: event.target.value,
                  })
                }
                required
              />

              <input
                type="text"
                placeholder="Lead source (Website, Instagram...)"
                value={newLead.source}
                onChange={(event) =>
                  setNewLead({
                    ...newLead,
                    source: event.target.value,
                  })
                }
                required
              />

              <select
                value={newLead.status}
                onChange={(event) =>
                  setNewLead({
                    ...newLead,
                    status:
                      event.target
                        .value as LeadStatus,
                  })
                }
              >
                <option value="new">
                  New
                </option>

                <option value="contacted">
                  Contacted
                </option>

                <option value="qualified">
                  Qualified
                </option>

                <option value="hot">
                  Hot
                </option>

                <option value="closed">
                  Closed
                </option>
              </select>

              <button type="submit">
                Create Lead
              </button>
            </form>
          )}

          {/* SEARCH + FILTER */}
          <div className="controls">
            <input
              aria-label="Search leads"
              placeholder="Search name, email or phone"
              value={query}
              onChange={(event) =>
                setQuery(event.target.value)
              }
            />

            <select
              aria-label="Filter by status"
              value={filter}
              onChange={(event) =>
                setFilter(
                  event.target.value as
                    | "all"
                    | LeadStatus
                )
              }
            >
              <option value="all">
                All statuses
              </option>

              <option value="new">
                New
              </option>

              <option value="contacted">
                Contacted
              </option>

              <option value="qualified">
                Qualified
              </option>

              <option value="hot">
                Hot
              </option>

              <option value="closed">
                Closed
              </option>
            </select>

<button
  type="button"
  className="clear-filter-btn"
  onClick={() => {
    setQuery("");
    setFilter("all");
    setFollowUpFilter("all");
  }}
>
  All Leads
</button>

</div>

{/* LEAD LIST */}

          
          {!storageLoaded ? (
            <p className="empty">
              Loading leads...
            </p>
          ) : visibleLeads.length === 0 ? (
            <p className="empty">
              No leads match your filters.
            </p>
          ) : (
            <ul className="lead-list">
              {visibleLeads.map((lead) => (
                <li key={lead.id}>
                  <button
                    type="button"
                    className={
                      selected?.id === lead.id
                        ? "lead active"
                        : "lead"
                    }
                    onClick={() =>
                      openLead(lead.id)
                    }
                  >
                    <span className="avatar">
                      {lead.name
                        .split(" ")
                        .map(
                          (part) => part[0]
                        )
                        .join("")
                        .slice(0, 2)}
                    </span>

                    <span className="lead-copy">
                      <strong>
                        {lead.name}
                      </strong>

                      <small>
                        {lead.email}
                      </small>
                    </span>

                    <span>
                      <b
                        className={`score ${scoreClass(
                          lead.score
                        )}`}
                      >
                        {lead.score}
                      </b>

                      <i
                        className={`status ${
                          statusClass[
                            lead.status
                          ]
                        }`}
                      >
                        {lead.status}
                      </i>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* RIGHT PANEL */}
        <article className="detail-panel">
          {selected === null ? (
            <p className="empty">
              Select a lead to see its details.
            </p>
          ) : (
            <LeadDetails
              selected={selected}
              isEditing={isEditing}
              editLead={editLead}
              setEditLead={setEditLead}
              followUp={followUp}
              setFollowUp={setFollowUp}
              followUpSaved={followUpSaved}
              startEditing={startEditing}
              cancelEditing={cancelEditing}
              handleSaveEdit={handleSaveEdit}
              handleDeleteLead={handleDeleteLead}
              handleScheduleFollowUp={
                handleScheduleFollowUp
              }
              handleRemoveFollowUp={
                handleRemoveFollowUp
              }
            />
          )}
                </article>
      </section>

    </section>
    </main>
  );
}

// ==================================================
// LEAD DETAILS
// ==================================================

type LeadDetailsProps = {
  selected: Lead;
  isEditing: boolean;

  editLead: {
    name: string;
    phone: string;
    email: string;
    source: string;
    status: LeadStatus;
  };

  setEditLead: React.Dispatch<
    React.SetStateAction<{
      name: string;
      phone: string;
      email: string;
      source: string;
      status: LeadStatus;
    }>
  >;

  followUp: FollowUp;

  setFollowUp: React.Dispatch<
    React.SetStateAction<FollowUp>
  >;

  followUpSaved: boolean;

  startEditing: () => void;
  cancelEditing: () => void;

  handleSaveEdit: (
    event: FormEvent<HTMLFormElement>
  ) => void;

  handleDeleteLead: () => void;
  handleScheduleFollowUp: () => void;
  handleRemoveFollowUp: () => void;
};

function LeadDetails({
  selected,
  isEditing,
  editLead,
  setEditLead,
  followUp,
  setFollowUp,
  followUpSaved,
  startEditing,
  cancelEditing,
  handleSaveEdit,
  handleDeleteLead,
  handleScheduleFollowUp,
  handleRemoveFollowUp,
}: LeadDetailsProps) {
  return (
    <>
      {/* DETAIL HEADER */}
      <div className="detail-header">
        <div>
          <p className="eyebrow">
            LEAD DETAILS
          </p>

          <h2>{selected.name}</h2>

          <p>
            {selected.email} ·{" "}
            {selected.phone}
          </p>
        </div>

        <div className="score-block">
          <strong>
            {selected.score}
          </strong>

          <span>Lead score</span>
        </div>
      </div>

      {/* EDIT + DELETE */}
      {!isEditing && (
        <div className="edit-actions">
          <button
            type="button"
            className="edit-lead-btn"
            onClick={startEditing}
          >
            Edit Lead
          </button>

          <button
            type="button"
            onClick={handleDeleteLead}
          >
            Delete Lead
          </button>
        </div>
      )}

      {/* EDIT FORM */}
      {isEditing && (
        <form
          className="edit-lead-form"
          onSubmit={handleSaveEdit}
        >
          <h3>Edit Lead</h3>

          <label>
            Name

            <input
              type="text"
              value={editLead.name}
              onChange={(event) =>
                setEditLead({
                  ...editLead,
                  name: event.target.value,
                })
              }
              required
            />
          </label>

          <label>
            Phone

            <input
              type="tel"
              value={editLead.phone}
              onChange={(event) =>
                setEditLead({
                  ...editLead,
                  phone: event.target.value,
                })
              }
              required
              pattern="[0-9]{10}"
              maxLength={10}
            />
          </label>

          <label>
            Email

            <input
              type="email"
              value={editLead.email}
              onChange={(event) =>
                setEditLead({
                  ...editLead,
                  email: event.target.value,
                })
              }
              required
            />
          </label>

          <label>
            Source

            <input
              type="text"
              value={editLead.source}
              onChange={(event) =>
                setEditLead({
                  ...editLead,
                  source: event.target.value,
                })
              }
              required
            />
          </label>

          <label>
            Status

            <select
              value={editLead.status}
              onChange={(event) =>
                setEditLead({
                  ...editLead,
                  status:
                    event.target
                      .value as LeadStatus,
                })
              }
            >
              <option value="new">
                New
              </option>

              <option value="contacted">
                Contacted
              </option>

              <option value="qualified">
                Qualified
              </option>

              <option value="hot">
                Hot
              </option>

              <option value="closed">
                Closed
              </option>
            </select>
          </label>

          <div className="edit-actions">
            <button
              type="button"
              onClick={cancelEditing}
            >
              Cancel
            </button>

            <button type="submit">
              Save Changes
            </button>
          </div>
        </form>
      )}

      {/* DETAILS */}
      {!isEditing && (
        <div className="details">
          <div>
            <span>Status</span>

            <b
              className={`status ${
                statusClass[selected.status]
              }`}
            >
              {selected.status}
            </b>
          </div>

          <div>
            <span>Source</span>

            <strong>
              {selected.source}
            </strong>
          </div>

          <div>
            <span>Created</span>

            <strong>
              {new Date(
                selected.created_at
              ).toLocaleDateString("en-GB")}
            </strong>
          </div>
        </div>
      )}

      {/* FOLLOW-UP */}
      {!isEditing && (
        <div className="follow-up-section">
          <h3>Follow-up</h3>

          <div className="follow-up-grid">
            <label>
              Date

              <input
                type="date"
                value={followUp.date}
                onChange={(event) =>
                  setFollowUp({
                    ...followUp,
                    date: event.target.value,
                  })
                }
              />
            </label>

            <label>
              Time

              <input
                type="time"
                value={followUp.time}
                onChange={(event) =>
                  setFollowUp({
                    ...followUp,
                    time: event.target.value,
                  })
                }
              />
            </label>

            <label>
              Priority

              <select
                value={followUp.priority}
                onChange={(event) =>
                  setFollowUp({
                    ...followUp,
                    priority:
                      event.target
                        .value as FollowUp["priority"],
                  })
                }
              >
                <option value="low">
                  Low
                </option>

                <option value="medium">
                  Medium
                </option>

                <option value="high">
                  High
                </option>
              </select>
            </label>

            <label>
              Note

              <input
                type="text"
                placeholder="Follow-up note"
                value={followUp.note}
                onChange={(event) =>
                  setFollowUp({
                    ...followUp,
                    note: event.target.value,
                  })
                }
              />
            </label>
          </div>

          <button
            type="button"
            onClick={handleScheduleFollowUp}
          >
            Schedule Follow-up
          </button>

          {followUpSaved && (
            <div className="follow-up-saved">
              <h4>
                Scheduled Follow-up
              </h4>

              <p>
                <strong>Date:</strong>{" "}
                {followUp.date}
              </p>

              <p>
                <strong>Time:</strong>{" "}
                {followUp.time}
              </p>

              <p>
                <strong>
                  Priority:
                </strong>{" "}
                {followUp.priority}
              </p>

              <p>
                <strong>Note:</strong>{" "}
                {followUp.note ||
                  "No note"}
              </p>

              <p>
                <strong>Status:</strong>{" "}
                {getFollowUpStatus(
                  followUp.date,
                  followUp.time
                )}
              </p>

              <span>
                Follow-up scheduled
                successfully.
              </span>

              <div className="edit-actions">
                <button
                  type="button"
                  onClick={
                    handleRemoveFollowUp
                  }
                >
                  Remove Follow-up
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* CONVERSATION */}
      {!isEditing && (
        <>
          <h3>Conversation</h3>

          <div className="conversation">
            {selected.conversations.length ===
            0 ? (
              <p className="empty">
                No messages recorded yet.
              </p>
            ) : (
              selected.conversations.map(
                (message) => (
                  <div
                    className={`message ${message.sender}`}
                    key={message.id}
                  >
                    <span>
                      {message.sender ===
                      "ai"
                        ? "AI assistant"
                        : selected.name}
                    </span>

                    <p>
                      {message.message}
                    </p>

                    <time>
                      {new Date(
                        message.created_at
                      ).toLocaleString(
                        "en-GB",
                        {
                          dateStyle:
                            "medium",
                          timeStyle:
                            "short",
                        }
                      )}
                    </time>
                  </div>
                )
              )
            )}
          </div>
        </>
      )}
    </>
  );
}

// ==================================================
// METRIC COMPONENT
// ==================================================

function Metric({
  label,
  value,
  note,
  hot,
}: {
  label: string;
  value: number;
  note: string;
  hot?: boolean;
}) {
  return (
    <article
      className={
        hot
          ? "metric alert"
          : "metric"
      }
    >
      <span>{label}</span>

      <strong>{value}</strong>

      <small>{note}</small>
    </article>
  );
}