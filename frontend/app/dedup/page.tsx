"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import styles from "./page.module.css";

type ContentKind = "text" | "article" | "image" | "batch";
type PreviewRecord = {
  kind: ContentKind;
  label: string;
  identities: string[];
};
type NurturePayload = Record<string, unknown> & {
  ready_to_send?: boolean;
  reason?: string;
  nurture_id?: number;
  lead_id?: number;
  content_type?: string;
  deduplication?: DeduplicationReport;
};
type DeduplicationReport = {
  candidate_count?: number;
  skipped_duplicates?: Array<{
    identities: string[];
    matched_identities: string[];
  }>;
  selected_identities?: string[];
  selected_previously_used?: boolean;
  persisted?: boolean;
  persisted_identities?: string[];
};
type DedupTestPayload = NurturePayload & {
  dedup_test?: boolean;
  test_candidate_count?: number;
};

const contentKinds: Array<{ value: ContentKind; label: string }> = [
  { value: "text", label: "Text" },
  { value: "article", label: "Article / newsletter" },
  { value: "image", label: "Image" },
  { value: "batch", label: "Batch update" },
];

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ||
  "http://localhost:8000";

function normalizedText(value: string): string {
  return value.replace(/\r\n?/g, "\n").trim();
}

function canonicalUrl(value: string): string {
  let parsed: URL;
  try {
    parsed = new URL(value.trim());
  } catch {
    throw new Error("Enter a valid absolute HTTP(S) URL.");
  }

  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    !parsed.hostname ||
    parsed.username ||
    parsed.password
  ) {
    throw new Error("URL must be HTTP(S) and must not contain credentials.");
  }

  const hostname = parsed.hostname.toLowerCase().replace(/^www\./, "");
  const port =
    (parsed.protocol === "http:" && parsed.port === "80") ||
    (parsed.protocol === "https:" && parsed.port === "443")
      ? ""
      : parsed.port;
  const pathname =
    parsed.pathname === "/" ? "/" : parsed.pathname.replace(/\/+$/, "") || "/";
  const query: Array<[string, string]> = [];
  parsed.searchParams.forEach((queryValue, key) => {
    const normalizedKey = key.toLowerCase();
    if (
      !["fbclid", "gclid", "mc_cid", "mc_eid"].includes(normalizedKey) &&
      !normalizedKey.startsWith("utm_")
    ) {
      query.push([key, queryValue]);
    }
  });
  query.sort(([keyA, valueA], [keyB, valueB]) => {
    if (keyA !== keyB) return keyA < keyB ? -1 : 1;
    return valueA === valueB ? 0 : valueA < valueB ? -1 : 1;
  });
  const search = new URLSearchParams();
  query.forEach(([key, queryValue]) => search.append(key, queryValue));

  return `https://${hostname}${port ? `:${port}` : ""}${pathname}${
    search.size ? `?${search.toString()}` : ""
  }`;
}

async function sha256(value: string): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new Error("Secure browser SHA-256 is not available on this page.");
  }
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

function fieldValue(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

async function makeIdentities(
  kind: ContentKind,
  form: FormData,
): Promise<string[]> {
  const id = fieldValue(form, "stableId");
  const url = fieldValue(form, "url");
  const text = normalizedText(fieldValue(form, "text"));
  const hash = fieldValue(form, "contentHash").toLowerCase();
  const identities = new Set<string>();

  if (kind === "text") {
    if (!text) throw new Error("Enter text content to calculate its identity.");
    identities.add(`text:sha256:${await sha256(text)}`);
    return Array.from(identities);
  }

  if (kind === "article" && id) identities.add(`article:id:${id}`);
  if (kind === "image" && id) identities.add(`image:id:${id}`);
  if (kind === "batch") {
    if (!id) throw new Error("A stable batch ID is required.");
    identities.add(`batch:id:${id}`);
  }

  if (url) {
    identities.add(
      `${kind === "image" ? "image" : "article"}:url:${canonicalUrl(url)}`,
    );
  }
  if (kind === "image" && hash) {
    if (!/^[0-9a-f]{64}$/.test(hash)) {
      throw new Error("Image hash must be a 64-character SHA-256 hex digest.");
    }
    identities.add(`image:sha256:${hash}`);
  }
  if (text) identities.add(`text:sha256:${await sha256(text)}`);
  if (!identities.size) {
    throw new Error("Enter a stable ID, URL, image hash, or text.");
  }
  return Array.from(identities);
}

function responseError(payload: unknown): string {
  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload
  ) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail !== undefined) return JSON.stringify(detail);
  }
  return "The API request failed without a detail message.";
}

function duplicateHint(payload: NurturePayload): string {
  if (payload.reason === "duplicate_content_conflict") {
    return "Duplicate selection was blocked by the backend identity constraint.";
  }
  if (payload.reason === "already_generated_today") {
    return "The backend reports that this lead already has a nurture generated today.";
  }
  if (payload.ready_to_send === true && payload.nurture_id) {
    return "The backend generated and saved a nurture record. Content identities are persisted within that transaction.";
  }
  return "No successful persisted generation was reported. Review the reason below.";
}

export default function DedupWorkbenchPage() {
  const [kind, setKind] = useState<ContentKind>("text");
  const [records, setRecords] = useState<PreviewRecord[]>([]);
  const [previewResult, setPreviewResult] = useState<{
    identities: string[];
    duplicate: boolean;
    matches: string[];
  } | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [leadId, setLeadId] = useState("");
  const [apiResult, setApiResult] = useState<NurturePayload | null>(null);
  const [apiError, setApiError] = useState("");
  const [apiLoading, setApiLoading] = useState(false);
  const [dedupKind, setDedupKind] = useState<ContentKind>("text");
  const [dedupResult, setDedupResult] = useState<DedupTestPayload | null>(null);
  const [dedupError, setDedupError] = useState("");
  const [dedupLoading, setDedupLoading] = useState(false);

  const knownIdentities = useMemo(
    () => new Set(records.flatMap((record) => record.identities)),
    [records],
  );

  async function submitPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPreviewError("");
    setPreviewResult(null);
    const form = new FormData(event.currentTarget);

    try {
      const identities = await makeIdentities(kind, form);
      const matches = identities.filter((identity) =>
        knownIdentities.has(identity),
      );
      setPreviewResult({
        identities,
        duplicate: matches.length > 0,
        matches,
      });
    } catch (error) {
      setPreviewError(
        error instanceof Error ? error.message : "Unable to calculate identity.",
      );
    }
  }

  function rememberPreview() {
    if (!previewResult || previewResult.duplicate) return;
    setRecords((current) => [
      ...current,
      {
        kind,
        label: `${contentKinds.find((item) => item.value === kind)?.label ?? kind} ${current.length + 1}`,
        identities: previewResult.identities,
      },
    ]);
  }

  async function submitNurture(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setApiResult(null);
    setApiError("");
    setApiLoading(true);

    try {
      const response = await fetch(
        `${apiBaseUrl}/ai/nurture/${encodeURIComponent(leadId.trim())}`,
        {
          method: "POST",
          headers: { Accept: "application/json" },
        },
      );
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(
          `HTTP ${response.status}: ${responseError(payload)}`,
        );
      }
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw new Error("The backend returned a non-object response.");
      }
      setApiResult(payload as NurturePayload);
    } catch (error) {
      setApiError(
        error instanceof Error
          ? error.message
          : "Unable to connect to the nurture API.",
      );
    } finally {
      setApiLoading(false);
    }
  }

  async function submitDedupTest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDedupResult(null);
    setDedupError("");
    setDedupLoading(true);

    try {
      const response = await fetch(
        `${apiBaseUrl}/ai/dedup-test/${encodeURIComponent(leadId.trim())}/${dedupKind}`,
        {
          method: "POST",
          headers: { Accept: "application/json" },
        },
      );
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${responseError(payload)}`);
      }
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw new Error("The backend returned a non-object response.");
      }
      setDedupResult(payload as DedupTestPayload);
    } catch (error) {
      setDedupError(
        error instanceof Error
          ? error.message
          : "Unable to run the backend deduplication test.",
      );
    } finally {
      setDedupLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>EXACT CONTENT DEDUPLICATION</p>
          <h1>Backend test workbench</h1>
          <p>Exercise content identities and the saved nurture workflow.</p>
        </div>
        <Link className={styles.backLink} href="/">
          Dashboard
        </Link>
      </header>

      <div className={styles.notice}>
        <strong>Preview versus backend verification</strong>
        <span>
          Content identity tests below run in browser memory only. They do not
          read or write database history. The nurture request calls the actual
          backend, which loads approved sources and performs selection and
          persistence using its configured database.
        </span>
      </div>

      <div className={styles.columns}>
        <section className={styles.panel}>
          <div className={styles.sectionTitle}>
            <div>
              <p className={styles.eyebrow}>LOCAL IDENTITY PREVIEW</p>
              <h2>Test text and approved-source identities</h2>
            </div>
            <span className={styles.localBadge}>Not persisted</span>
          </div>

          <div className={styles.tabs} aria-label="Select content type">
            {contentKinds.map((item) => (
              <button
                aria-pressed={kind === item.value}
                className={kind === item.value ? styles.selectedTab : ""}
                key={item.value}
                onClick={() => {
                  setKind(item.value);
                  setPreviewResult(null);
                  setPreviewError("");
                }}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>

          <form className={styles.form} onSubmit={submitPreview}>
            {kind === "text" ? (
              <label>
                Text content
                <textarea
                  name="text"
                  placeholder="Line endings and surrounding whitespace are normalized before hashing."
                  required
                  rows={5}
                />
              </label>
            ) : (
              <>
                {kind !== "article" && (
                  <label>
                    {kind === "image" ? "Stable image ID (optional)" : "Stable batch ID"}
                    <input
                      name="stableId"
                      required={kind === "batch"}
                      placeholder={kind === "image" ? "e.g. image-001" : "e.g. 2026-Q3"}
                    />
                  </label>
                )}
                {kind === "article" && (
                  <label>
                    Article/content ID (optional)
                    <input name="stableId" placeholder="Existing source ID" />
                  </label>
                )}
                {kind !== "batch" && (
                  <label>
                    Canonical URL (optional if another identity is supplied)
                    <input name="url" placeholder="https://example.org/content" type="url" />
                  </label>
                )}
                {kind === "image" && (
                  <label>
                    Image SHA-256 content hash (optional)
                    <input name="contentHash" placeholder="64 hexadecimal characters" />
                  </label>
                )}
                <label>
                  {kind === "article"
                    ? "Article summary (optional)"
                    : kind === "image"
                      ? "Image description (optional)"
                      : "Batch message (optional)"}
                  <textarea name="text" rows={3} />
                </label>
              </>
            )}
            <button className={styles.primaryButton} type="submit">
              Calculate dedup identity
            </button>
          </form>

          {previewError && (
            <p className={styles.error} role="alert">{previewError}</p>
          )}
          {previewResult && (
            <div className={styles.result} aria-live="polite">
              <strong>
                {previewResult.duplicate
                  ? "Duplicate detected in local test history"
                  : "No duplicate in local test history"}
              </strong>
              {previewResult.matches.length > 0 && (
                <p>Matching identity: {previewResult.matches.join(", ")}</p>
              )}
              <ul>
                {previewResult.identities.map((identity) => (
                  <li key={identity}><code>{identity}</code></li>
                ))}
              </ul>
              {!previewResult.duplicate && (
                <button
                  className={styles.secondaryButton}
                  onClick={rememberPreview}
                  type="button"
                >
                  Add to local test history
                </button>
              )}
            </div>
          )}

          <div className={styles.historyHeading}>
            <div>
              <strong>Browser-local test history</strong>
              <span>{records.length} test item(s); cleared when page is reloaded</span>
            </div>
            <button
              className={styles.secondaryButton}
              disabled={records.length === 0}
              onClick={() => setRecords([])}
              type="button"
            >
              Clear
            </button>
          </div>
          {records.length > 0 && (
            <ul className={styles.historyList}>
              {records.map((record, index) => (
                <li key={`${record.kind}-${index}`}>
                  <strong>{record.label}</strong>
                  <code>{record.identities.join(" · ")}</code>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className={styles.panel}>
          <div className={styles.sectionTitle}>
            <div>
              <p className={styles.eyebrow}>BACKEND + TEST DATABASE</p>
              <h2>Prove persisted deduplication</h2>
            </div>
            <span className={styles.persistedBadge}>Server fixtures</span>
          </div>
          <p className={styles.endpoint}>
            <code>{apiBaseUrl}/ai/dedup-test/{"{lead_id}/{content_kind}"}</code>
          </p>
          <form className={styles.form} onSubmit={submitDedupTest}>
            <label>
              Lead ID in the dedicated lead_db_test database
              <input
                inputMode="numeric"
                min="1"
                onChange={(event) => setLeadId(event.target.value)}
                pattern="[0-9]+"
                placeholder="Enter a lead ID present in the backend database"
                required
                value={leadId}
              />
            </label>
            <p className={styles.helper}>
              Select a content type, then submit twice. The backend uses its
              bundled approved fixtures, reads this lead’s saved identities,
              runs the normal selector, and persists each result. This test
              endpoint is disabled unless explicitly enabled and connected to
              loopback PostgreSQL database lead_db_test.
            </p>
            <label>
              Content type
              <select
                onChange={(event) =>
                  setDedupKind(event.target.value as ContentKind)
                }
                value={dedupKind}
              >
                {contentKinds.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              className={styles.primaryButton}
              disabled={dedupLoading}
              type="submit"
            >
              {dedupLoading ? "Checking and saving…" : "Run backend dedup test"}
            </button>
          </form>

          {dedupError && (
            <div className={styles.error} role="alert">
              <strong>Backend dedup test failed</strong>
              <span>{dedupError}</span>
              <small>
                Enable DEDUP test mode on the AI API and connect it to the
                loopback lead_db_test database. Production and remote databases
                are intentionally rejected.
              </small>
            </div>
          )}
          {dedupResult && (
            <div className={styles.apiResult} aria-live="polite">
              <div className={styles.resultHeader}>
                <strong>
                  {dedupResult.ready_to_send
                    ? dedupResult.deduplication?.selected_previously_used
                      ? "Backend selected previously used content"
                      : "Backend selected unused content"
                    : "No content selected"}
                </strong>
                <span
                  className={dedupResult.deduplication?.persisted
                    ? styles.persistedBadge
                    : styles.localBadge}
                >
                  {dedupResult.deduplication?.persisted
                    ? "Saved in test DB"
                    : "Not persisted"}
                </span>
              </div>
              <p>{duplicateHint(dedupResult)}</p>
              <dl className={styles.responseFields}>
                <div><dt>Result</dt><dd>{String(dedupResult.reason ?? "—")}</dd></div>
                <div><dt>Lead ID</dt><dd>{String(dedupResult.lead_id ?? leadId)}</dd></div>
                <div><dt>Nurture ID</dt><dd>{String(dedupResult.nurture_id ?? "—")}</dd></div>
                <div><dt>Content type</dt><dd>{String(dedupResult.content_type ?? "—")}</dd></div>
                <div><dt>Candidates</dt><dd>{String(dedupResult.deduplication?.candidate_count ?? dedupResult.test_candidate_count ?? 0)}</dd></div>
                <div><dt>Duplicate candidates skipped</dt><dd>{String(dedupResult.deduplication?.skipped_duplicates?.length ?? 0)}</dd></div>
                <div><dt>Previously used selected</dt><dd>{String(dedupResult.deduplication?.selected_previously_used ?? false)}</dd></div>
              </dl>
              {dedupResult.deduplication?.skipped_duplicates?.map((skip, index) => (
                <div className={styles.message} key={`${index}-${skip.identities.join("|")}`}>
                  <strong>Skipped duplicate candidate {index + 1}</strong>
                  <p>Matched saved identity: {skip.matched_identities.join(", ")}</p>
                </div>
              ))}
              {dedupResult.deduplication?.selected_identities && (
                <div className={styles.message}>
                  <strong>Selected identity</strong>
                  <p><code>{dedupResult.deduplication.selected_identities.join("\n")}</code></p>
                </div>
              )}
              {dedupResult.deduplication?.persisted_identities && (
                <div className={styles.message}>
                  <strong>Identities confirmed persisted by backend</strong>
                  <p><code>{dedupResult.deduplication.persisted_identities.join("\n")}</code></p>
                </div>
              )}
              {typeof dedupResult.message === "string" && (
                <div className={styles.message}>
                  <strong>Prepared message</strong>
                  <p>{dedupResult.message}</p>
                </div>
              )}
              <details>
                <summary>Full API response</summary>
                <pre>{JSON.stringify(dedupResult, null, 2)}</pre>
              </details>
              <p className={styles.helper}>
                Run this again with the same lead and content type. The backend
                should skip the first fixture and select the second; persistence
                is confirmed by the returned nurture ID and stored identity set.
              </p>
            </div>
          )}
          <details className={styles.liveNurture}>
            <summary>Run normal engagement-based nurture endpoint</summary>
            <p className={styles.endpoint}>
              <code>{apiBaseUrl}/ai/nurture/{"{lead_id}"}</code>
            </p>
            <form className={styles.form} onSubmit={submitNurture}>
              <button
                className={styles.secondaryButton}
                disabled={apiLoading || !leadId.trim()}
                type="submit"
              >
                {apiLoading ? "Calling backend…" : "Run normal nurture"}
              </button>
            </form>
            {apiError && <p className={styles.error} role="alert">{apiError}</p>}
            {apiResult && (
              <div className={styles.apiResult}>
                <p>{duplicateHint(apiResult)}</p>
                <pre>{JSON.stringify(apiResult, null, 2)}</pre>
              </div>
            )}
          </details>
        </section>
      </div>
    </main>
  );
}
