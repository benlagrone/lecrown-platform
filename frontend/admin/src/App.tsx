import { useEffect, useState, type FormEvent } from "react";

import {
  clearAuthToken,
  createContent,
  createGovContractAgencyPreference,
  createGovContractKeywordRule,
  deleteGovContractAgencyPreference,
  deleteGovContractKeywordRule,
  downloadGovContractsExport,
  funnelGovContract,
  getCurrentAdmin,
  getGovContractCapabilities,
  hasStoredAuthToken,
  listGovContractAgencyPreferences,
  listGovContractKeywordRules,
  listContent,
  listGovContractRuns,
  listGovContracts,
  listInquiries,
  login,
  publishDistribution,
  publishToLinkedIn,
  refreshGmailRfqs,
  refreshGovContracts,
  storeAuthToken,
  updateGovContractAgencyPreference,
  updateGovContractKeywordRule,
} from "../../shared/api";
import type {
  Content,
  ContentCreate,
  DistributionChannel,
  GovContractAgencyPreference,
  GovContractImportRun,
  GovContractOpportunity,
  GovContractCapabilities,
  GovContractKeywordRule,
  Inquiry,
  Tenant,
} from "../../shared/types";

type AdminView = "dashboard" | "opportunities";
type OpportunitiesAuthStatus = "checking" | "authenticated" | "unauthenticated";
const DEFAULT_KEYWORD_WEIGHT = 3;
const DEFAULT_AGENCY_WEIGHT = 7;
const OPPORTUNITY_LIST_LIMIT = 200;

function buildInitialForm(tenant: Tenant = "development"): ContentCreate {
  return {
    tenant,
    type: "insight",
    title: "",
    body: "",
    tags: [],
    distribution: {
      linkedin: false,
      youtube: false,
      website: true,
      twitter: false,
    },
    media: {
      video_generated: false,
      video_path: "",
      youtube_video_id: null,
      youtube_status: null,
    },
    publish_linkedin: false,
    publish_site: true,
  };
}

function getCurrentView(): AdminView {
  if (typeof window === "undefined") {
    return "dashboard";
  }
  return window.location.hash.startsWith("#/opportunities") ? "opportunities" : "dashboard";
}

function navigateToView(view: AdminView): void {
  if (typeof window === "undefined") {
    return;
  }
  window.location.hash = view === "opportunities" ? "#/opportunities" : "#/";
}

export default function App() {
  const [view, setView] = useState<AdminView>(getCurrentView());
  const [tenant, setTenant] = useState<Tenant>("development");
  const [form, setForm] = useState<ContentCreate>(buildInitialForm());
  const [contentItems, setContentItems] = useState<Content[]>([]);
  const [inquiries, setInquiries] = useState<Inquiry[]>([]);
  const [gmailContracts, setGmailContracts] = useState<GovContractOpportunity[]>([]);
  const [esbdContracts, setEsbdContracts] = useState<GovContractOpportunity[]>([]);
  const [contractRuns, setContractRuns] = useState<GovContractImportRun[]>([]);
  const [contractCapabilities, setContractCapabilities] = useState<GovContractCapabilities>({
    gmail_rfq_sync_enabled: false,
    gmail_rfq_feed_label: null,
  });
  const [agencyPreferences, setAgencyPreferences] = useState<GovContractAgencyPreference[]>([]);
  const [keywordRules, setKeywordRules] = useState<GovContractKeywordRule[]>([]);
  const [message, setMessage] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [refreshingContracts, setRefreshingContracts] = useState(false);
  const [refreshingGmailContracts, setRefreshingGmailContracts] = useState(false);
  const [downloadingExport, setDownloadingExport] = useState(false);
  const [funnelingContractId, setFunnelingContractId] = useState<string | null>(null);
  const [opportunitiesAuthStatus, setOpportunitiesAuthStatus] =
    useState<OpportunitiesAuthStatus>("unauthenticated");
  const [loginUsername, setLoginUsername] = useState("admin");
  const [loginPassword, setLoginPassword] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);
  const [authMessage, setAuthMessage] = useState("");
  const [minPriorityScoreFilter, setMinPriorityScoreFilter] = useState(0);
  const [matchesOnlyFilter, setMatchesOnlyFilter] = useState(true);
  const [openOnlyFilter, setOpenOnlyFilter] = useState(true);
  const [agencyName, setAgencyName] = useState("");
  const [agencyWeight, setAgencyWeight] = useState(DEFAULT_AGENCY_WEIGHT);
  const [editingAgencyId, setEditingAgencyId] = useState<string | null>(null);
  const [editingAgencyName, setEditingAgencyName] = useState("");
  const [editingAgencyWeight, setEditingAgencyWeight] = useState(DEFAULT_AGENCY_WEIGHT);
  const [savingAgencyPreference, setSavingAgencyPreference] = useState(false);
  const [deletingAgencyId, setDeletingAgencyId] = useState<string | null>(null);
  const [keywordPhrase, setKeywordPhrase] = useState("");
  const [keywordWeight, setKeywordWeight] = useState(DEFAULT_KEYWORD_WEIGHT);
  const [editingKeywordId, setEditingKeywordId] = useState<string | null>(null);
  const [editingKeywordPhrase, setEditingKeywordPhrase] = useState("");
  const [editingKeywordWeight, setEditingKeywordWeight] = useState(DEFAULT_KEYWORD_WEIGHT);
  const [savingKeyword, setSavingKeyword] = useState(false);
  const [deletingKeywordId, setDeletingKeywordId] = useState<string | null>(null);

  useEffect(() => {
    function handleHashChange() {
      setView(getCurrentView());
    }

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  useEffect(() => {
    void refreshContent(tenant);
    if (tenant === "properties") {
      void refreshInquiries();
    }
  }, [tenant]);

  useEffect(() => {
    if (view !== "opportunities") {
      return;
    }
    void ensureOpportunitiesAccess();
  }, [view]);

  useEffect(() => {
    if (view !== "opportunities" || opportunitiesAuthStatus !== "authenticated") {
      return;
    }
    void refreshContractsView();
  }, [matchesOnlyFilter, minPriorityScoreFilter, openOnlyFilter]);

  async function ensureOpportunitiesAccess() {
    if (!hasStoredAuthToken()) {
      setOpportunitiesAuthStatus("unauthenticated");
      return;
    }

    setOpportunitiesAuthStatus("checking");
    try {
      await getCurrentAdmin();
      const capabilities = await getGovContractCapabilities();
      setContractCapabilities(capabilities);
      setAuthMessage("");
      setOpportunitiesAuthStatus("authenticated");
      await refreshContractsView(capabilities);
    } catch {
      clearAuthToken();
      setOpportunitiesAuthStatus("unauthenticated");
      setAuthMessage("Sign in to view opportunities.");
    }
  }

  async function refreshContent(selectedTenant: Tenant) {
    try {
      const items = await listContent(selectedTenant);
      setContentItems(items);
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function refreshInquiries() {
    try {
      const items = await listInquiries();
      setInquiries(items);
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function refreshContractsView(capabilitiesOverride?: GovContractCapabilities) {
    try {
      const capabilities = capabilitiesOverride ?? contractCapabilities;
      const [gmailItems, esbdItems, runs, keywords, agencyPrefs] = await Promise.all([
        capabilities.gmail_rfq_sync_enabled
          ? listGovContracts(OPPORTUNITY_LIST_LIMIT, "gmail_rfqs", {
              matchesOnly: matchesOnlyFilter,
              minPriorityScore: minPriorityScoreFilter,
              openOnly: openOnlyFilter,
            })
          : Promise.resolve([]),
        listGovContracts(OPPORTUNITY_LIST_LIMIT, "txsmartbuy_esbd", {
          matchesOnly: matchesOnlyFilter,
          minPriorityScore: minPriorityScoreFilter,
          openOnly: openOnlyFilter,
        }),
        listGovContractRuns(10),
        listGovContractKeywordRules(),
        listGovContractAgencyPreferences(),
      ]);
      setGmailContracts(gmailItems);
      setEsbdContracts(esbdItems);
      setContractRuns(runs);
      setKeywordRules(keywords);
      setAgencyPreferences(agencyPrefs);
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setMessage("");

    try {
      const payload: ContentCreate = {
        ...form,
        tenant,
        publish_linkedin: form.distribution.linkedin,
        publish_site: form.distribution.website,
      };
      await createContent(payload);
      setForm(buildInitialForm(tenant));
      setMessage("Content saved.");
      await refreshContent(tenant);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePublish(contentId: string) {
    setMessage("");
    try {
      await publishToLinkedIn(contentId);
      setMessage("LinkedIn publish request completed.");
      await refreshContent(tenant);
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function handleDistribution(item: Content) {
    const channels = getEnabledChannels(item);
    if (channels.length === 0) {
      setMessage("Enable at least one distribution channel first.");
      return;
    }

    setMessage("");
    try {
      const result = await publishDistribution(item.id, channels, item.media.video_path ?? undefined);
      const statuses = Object.entries(result.results)
        .map(([channel, value]) => `${channel}: ${value.status ?? "completed"}`)
        .join(" | ");
      setMessage(`Distribution finished. ${statuses}`);
      await refreshContent(tenant);
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function handleContractRefresh() {
    setRefreshingContracts(true);
    setMessage("");
    try {
      const run = await refreshGovContracts();
      await refreshContractsView();
      setMessage(
        `ESBD refreshed for ${run.window_start} to ${run.window_end}. ${run.matched_records} matches from ${run.total_records} opportunities.`,
      );
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setRefreshingContracts(false);
    }
  }

  async function handleGmailContractRefresh() {
    setRefreshingGmailContracts(true);
    setMessage("");
    try {
      const run = await refreshGmailRfqs();
      await refreshContractsView();
      setMessage(`Gmail RFQs synced. ${run.matched_records} opportunities updated.`);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setRefreshingGmailContracts(false);
    }
  }

  async function handleContractExport() {
    setDownloadingExport(true);
    setMessage("");
    try {
      await downloadGovContractsExport();
      setMessage("ESBD CSV download started.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setDownloadingExport(false);
    }
  }

  async function handleFunnelContract(contract: GovContractOpportunity) {
    setFunnelingContractId(contract.id);
    setMessage("");
    try {
      const result = await funnelGovContract(contract.id);
      await refreshContractsView();
      const syncMessage =
        result.funnel_delivery_status === "delivered"
          ? `Contract sent to CRM lead funnel${result.funnel_record_id ? ` as ${result.funnel_record_id}` : ""}.`
          : "Contract was recorded in the funnel attempt, but CRM delivery failed.";
      setMessage(syncMessage);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setFunnelingContractId(null);
    }
  }

  async function handleOpportunitiesLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoggingIn(true);
    setAuthMessage("");
    setMessage("");

    try {
      const token = await login({ username: loginUsername, password: loginPassword });
      storeAuthToken(token.access_token);
      await getCurrentAdmin();
      const capabilities = await getGovContractCapabilities();
      setContractCapabilities(capabilities);
      setOpportunitiesAuthStatus("authenticated");
      await refreshContractsView(capabilities);
      setMessage("Signed in.");
    } catch (error) {
      clearAuthToken();
      setOpportunitiesAuthStatus("unauthenticated");
      setAuthMessage(getErrorMessage(error));
    } finally {
      setLoggingIn(false);
    }
  }

  function handleLogout() {
    clearAuthToken();
    setOpportunitiesAuthStatus("unauthenticated");
    setAuthMessage("");
    setGmailContracts([]);
    setEsbdContracts([]);
    setContractRuns([]);
    setAgencyPreferences([]);
    setKeywordRules([]);
    setContractCapabilities({
      gmail_rfq_sync_enabled: false,
      gmail_rfq_feed_label: null,
    });
    setMinPriorityScoreFilter(0);
    setEditingKeywordId(null);
    setEditingKeywordPhrase("");
    setEditingKeywordWeight(DEFAULT_KEYWORD_WEIGHT);
    setEditingAgencyId(null);
    setEditingAgencyName("");
    setEditingAgencyWeight(DEFAULT_AGENCY_WEIGHT);
    setAgencyName("");
    setAgencyWeight(DEFAULT_AGENCY_WEIGHT);
    setKeywordPhrase("");
    setKeywordWeight(DEFAULT_KEYWORD_WEIGHT);
    setDeletingAgencyId(null);
    setDeletingKeywordId(null);
  }

  function startEditingKeyword(rule: GovContractKeywordRule) {
    setEditingKeywordId(rule.id);
    setEditingKeywordPhrase(rule.phrase);
    setEditingKeywordWeight(rule.weight);
  }

  function startEditingAgency(preference: GovContractAgencyPreference) {
    setEditingAgencyId(preference.id);
    setEditingAgencyName(preference.agency_name);
    setEditingAgencyWeight(preference.weight);
  }

  function cancelEditingKeyword() {
    setEditingKeywordId(null);
    setEditingKeywordPhrase("");
    setEditingKeywordWeight(DEFAULT_KEYWORD_WEIGHT);
  }

  function cancelEditingAgency() {
    setEditingAgencyId(null);
    setEditingAgencyName("");
    setEditingAgencyWeight(DEFAULT_AGENCY_WEIGHT);
  }

  async function handleCreateAgencyPreference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingAgencyPreference(true);
    setMessage("");

    try {
      await createGovContractAgencyPreference({
        agency_name: agencyName,
        weight: agencyWeight,
      });
      setAgencyName("");
      setAgencyWeight(DEFAULT_AGENCY_WEIGHT);
      await refreshContractsView();
      setMessage("Agency preference added. Stored opportunities were rescored.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setSavingAgencyPreference(false);
    }
  }

  async function handleUpdateAgencyPreference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingAgencyId) {
      return;
    }

    setSavingAgencyPreference(true);
    setMessage("");

    try {
      await updateGovContractAgencyPreference(editingAgencyId, {
        agency_name: editingAgencyName,
        weight: editingAgencyWeight,
      });
      cancelEditingAgency();
      await refreshContractsView();
      setMessage("Agency preference updated. Stored opportunities were rescored.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setSavingAgencyPreference(false);
    }
  }

  async function handleDeleteAgencyPreference(preference: GovContractAgencyPreference) {
    setDeletingAgencyId(preference.id);
    setMessage("");

    try {
      await deleteGovContractAgencyPreference(preference.id);
      if (editingAgencyId === preference.id) {
        cancelEditingAgency();
      }
      await refreshContractsView();
      setMessage("Agency preference removed. Stored opportunities were rescored.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setDeletingAgencyId(null);
    }
  }

  async function handleCreateKeyword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingKeyword(true);
    setMessage("");

    try {
      await createGovContractKeywordRule({
        phrase: keywordPhrase,
        weight: keywordWeight,
      });
      setKeywordPhrase("");
      setKeywordWeight(DEFAULT_KEYWORD_WEIGHT);
      await refreshContractsView();
      setMessage("Keyword added. Stored opportunities were rescored.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setSavingKeyword(false);
    }
  }

  async function handleUpdateKeyword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingKeywordId) {
      return;
    }

    setSavingKeyword(true);
    setMessage("");

    try {
      await updateGovContractKeywordRule(editingKeywordId, {
        phrase: editingKeywordPhrase,
        weight: editingKeywordWeight,
      });
      cancelEditingKeyword();
      await refreshContractsView();
      setMessage("Keyword updated. Stored opportunities were rescored.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setSavingKeyword(false);
    }
  }

  async function handleDeleteKeyword(keywordRule: GovContractKeywordRule) {
    setDeletingKeywordId(keywordRule.id);
    setMessage("");

    try {
      await deleteGovContractKeywordRule(keywordRule.id);
      if (editingKeywordId === keywordRule.id) {
        cancelEditingKeyword();
      }
      await refreshContractsView();
      setMessage("Keyword removed. Stored opportunities were rescored.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setDeletingKeywordId(null);
    }
  }

  const latestContractRun = contractRuns[0];
  const hasAnyContracts =
    esbdContracts.length > 0 || (contractCapabilities.gmail_rfq_sync_enabled && gmailContracts.length > 0);

  function renderContractCard(contract: GovContractOpportunity) {
    return (
      <article className="content-card contract-card" key={contract.id}>
        <div className="content-meta">
          <div>
            <strong>{contract.title}</strong>
            <span>{contract.agency_name ?? contract.agency_number ?? "Unknown agency"}</span>
          </div>
          <div className="contract-score-stack">
            <span className="fit-tag fit-tag-high">Priority {contract.priority_score}</span>
            <span className={`fit-tag fit-tag-${contract.fit_bucket}`}>
              {contract.fit_bucket} fit - {contract.score}
            </span>
          </div>
        </div>

        <div className="contract-detail-grid">
          <span>Solicitation: {contract.solicitation_id}</span>
          <span>Status: {contract.status_name ?? "Unknown"}</span>
          <span>Due: {formatDateLabel(contract.due_date, contract.due_time)}</span>
          <span>Posted: {formatDateLabel(contract.posting_date)}</span>
        </div>

        <div className="score-matrix">
          <span className="tag">Closeness {getClosenessScore(contract)}/10</span>
          <span className="tag">Timing {getScoreBreakdownValue(contract, "timing") ?? "n/a"}/10</span>
          <span className="tag">Competition edge {getScoreBreakdownValue(contract, "competition") ?? "n/a"}/10</span>
          <span className="tag">Agency affinity {getScoreBreakdownValue(contract, "agency_affinity") ?? "n/a"}/10</span>
        </div>

        {getMatchedAgencyPreferences(contract).length > 0 ? (
          <div className="tag-row">
            {getMatchedAgencyPreferences(contract).map((agencyName) => (
              <span className="tag" key={agencyName}>
                Preferred agency: {agencyName}
              </span>
            ))}
          </div>
        ) : null}

        <div className="tag-row">
          <span className="tag">{formatContractSource(contract.source)}</span>
          {contract.matched_keywords.map((keyword) => (
            <span className="tag" key={keyword}>
              {keyword}
            </span>
          ))}
        </div>

        {contract.nigp_codes ? <p>{formatNigpPreview(contract.nigp_codes)}</p> : null}

        <div className="content-footer">
          <div className="status-stack">
            <span>Funnel: {formatFunnelLabel(contract)}</span>
            {contract.funnel_record_id ? <span>CRM record: {contract.funnel_record_id}</span> : null}
            <span>Last seen: {formatTimestamp(contract.last_seen_at)}</span>
          </div>
          <div className="action-row">
            <button
              type="button"
              onClick={() => void handleFunnelContract(contract)}
              disabled={funnelingContractId === contract.id}
            >
              {funnelingContractId === contract.id
                ? "Sending..."
                : contract.funnel_delivery_status === "delivered"
                  ? "Resend to CRM"
                  : "Add to lead funnel"}
            </button>
            <a className="button-link secondary-link" href={contract.source_url} target="_blank" rel="noreferrer">
              {contract.source === "gmail_rfqs" ? "Open Gmail" : "Open source"}
            </a>
          </div>
        </div>
      </article>
    );
  }

  function renderDashboard() {
    return (
      <>
        <section className="grid">
          <article className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Create Content</p>
                <h2>Draft once, route by tenant</h2>
              </div>
            </div>

            <form className="content-form" onSubmit={handleSubmit}>
              <label>
                <span>Type</span>
                <input
                  value={form.type}
                  onChange={(event) => setForm((current) => ({ ...current, type: event.target.value }))}
                  placeholder="insight"
                />
              </label>

              <label>
                <span>Title</span>
                <input
                  value={form.title}
                  onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                  placeholder="What changed in the market this week?"
                />
              </label>

              <label>
                <span>Body</span>
                <textarea
                  rows={8}
                  value={form.body}
                  onChange={(event) => setForm((current) => ({ ...current, body: event.target.value }))}
                  placeholder="Write the actual post body here."
                />
              </label>

              <label>
                <span>Tags</span>
                <input
                  value={form.tags.join(", ")}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      tags: event.target.value
                        .split(",")
                        .map((tag) => tag.trim())
                        .filter(Boolean),
                    }))
                  }
                  placeholder="houston, multifamily, acquisition"
                />
              </label>

              <div className="toggle-row">
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={form.distribution.linkedin}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        distribution: { ...current.distribution, linkedin: event.target.checked },
                        publish_linkedin: event.target.checked,
                      }))
                    }
                  />
                  <span>Publish to LinkedIn</span>
                </label>

                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={form.distribution.youtube}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        distribution: { ...current.distribution, youtube: event.target.checked },
                      }))
                    }
                  />
                  <span>Publish to YouTube</span>
                </label>

                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={form.distribution.website}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        distribution: { ...current.distribution, website: event.target.checked },
                        publish_site: event.target.checked,
                      }))
                    }
                  />
                  <span>Publish to site</span>
                </label>
              </div>

              {form.distribution.youtube ? (
                <label>
                  <span>Video path</span>
                  <input
                    value={form.media.video_path ?? ""}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        media: { ...current.media, video_path: event.target.value },
                      }))
                    }
                    placeholder="/videos/warehouse.mp4"
                  />
                </label>
              ) : null}

              <button type="submit" disabled={submitting}>
                {submitting ? "Saving..." : "Create content"}
              </button>
            </form>
          </article>

          <article className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Content Queue</p>
                <h2>{tenant === "development" ? "Development feed" : "Properties feed"}</h2>
              </div>
            </div>

            <div className="stack">
              {contentItems.length === 0 ? (
                <p className="empty-state">No content has been created for this tenant yet.</p>
              ) : (
                contentItems.map((item) => (
                  <div className="content-card" key={item.id}>
                    <div className="content-meta">
                      <strong>{item.title}</strong>
                      <span>{item.type}</span>
                    </div>
                    <p>{item.body}</p>
                    <div className="tag-row">
                      {getEnabledChannels(item).map((channel) => (
                        <span className="tag" key={channel}>
                          {channel}
                        </span>
                      ))}
                    </div>
                    <div className="tag-row">
                      {item.tags.map((tag) => (
                        <span className="tag" key={tag}>
                          {tag}
                        </span>
                      ))}
                    </div>
                    <div className="content-footer">
                      <div className="status-stack">
                        <span>LinkedIn: {item.linkedin_status ?? "not queued"}</span>
                        <span>YouTube: {item.media.youtube_status ?? "not queued"}</span>
                      </div>
                      <div className="action-row">
                        <button type="button" onClick={() => void handlePublish(item.id)}>
                          LinkedIn now
                        </button>
                        <button type="button" onClick={() => void handleDistribution(item)}>
                          Run distribution
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </article>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Inquiry CRM</p>
              <h2>Properties pipeline</h2>
            </div>
          </div>

          {tenant !== "properties" ? (
            <p className="empty-state">Inquiry capture is scoped to the properties tenant.</p>
          ) : inquiries.length === 0 ? (
            <p className="empty-state">No inquiries captured yet.</p>
          ) : (
            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>Contact</th>
                    <th>Asset Type</th>
                    <th>Location</th>
                    <th>Problem</th>
                  </tr>
                </thead>
                <tbody>
                  {inquiries.map((inquiry) => (
                    <tr key={inquiry.id}>
                      <td>
                        <strong>{inquiry.contact_name}</strong>
                        <span>{inquiry.email}</span>
                        <span>{inquiry.phone}</span>
                      </td>
                      <td>{inquiry.asset_type}</td>
                      <td>{inquiry.location}</td>
                      <td>{inquiry.problem}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Opportunities</p>
              <h2>Dedicated list page</h2>
            </div>
            <div className="action-row">
              <button type="button" onClick={() => navigateToView("opportunities")}>
                Open opportunities page
              </button>
            </div>
          </div>
          <p className="panel-subcopy">
            ESBD opportunities and Gmail RFQs now live on a separate page and require admin sign-in.
          </p>
        </section>
      </>
    );
  }

  function renderOpportunitiesPage() {
    if (opportunitiesAuthStatus === "checking") {
      return (
        <section className="panel auth-panel">
          <p className="empty-state">Checking admin access...</p>
        </section>
      );
    }

    if (opportunitiesAuthStatus === "unauthenticated") {
      return (
        <section className="panel auth-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Admin Login</p>
              <h2>Protected opportunities page</h2>
            </div>
          </div>

          <p className="panel-subcopy">
            This page is protected. Sign in with the admin credentials configured for `lecrown-platform`.
          </p>

          {authMessage ? <div className="message-banner auth-banner">{authMessage}</div> : null}

          <form className="content-form auth-form" onSubmit={handleOpportunitiesLogin}>
            <label>
              <span>Username</span>
              <input value={loginUsername} onChange={(event) => setLoginUsername(event.target.value)} />
            </label>

            <label>
              <span>Password</span>
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
              />
            </label>

            <div className="action-row auth-actions">
              <button type="submit" disabled={loggingIn}>
                {loggingIn ? "Signing in..." : "Sign in"}
              </button>
              <button type="button" className="secondary-link" onClick={() => navigateToView("dashboard")}>
                Back to dashboard
              </button>
            </div>
          </form>
        </section>
      );
    }

    return (
      <>
        <section className="panel">
          <div className="panel-heading contract-toolbar">
            <div>
              <p className="eyebrow">Government Work Finder</p>
              <h2>ESBD + Gmail RFQs for LeCrown</h2>
            </div>

            <div className="action-row">
              <button type="button" onClick={() => void handleContractExport()} disabled={downloadingExport}>
                {downloadingExport ? "Downloading..." : "Download ESBD CSV"}
              </button>
              <button type="button" onClick={() => void handleContractRefresh()} disabled={refreshingContracts}>
                {refreshingContracts ? "Refreshing..." : "Refresh ESBD"}
              </button>
              {contractCapabilities.gmail_rfq_sync_enabled ? (
                <button
                  type="button"
                  onClick={() => void handleGmailContractRefresh()}
                  disabled={refreshingGmailContracts}
                >
                  {refreshingGmailContracts ? "Syncing..." : "Sync Gmail RFQs"}
                </button>
              ) : null}
            </div>
          </div>

          {!contractCapabilities.gmail_rfq_sync_enabled ? (
            <p className="panel-subcopy">
              Gmail RFQ sync is not configured in this environment. ESBD imports remain available.
            </p>
          ) : null}

          <div className="toggle-row opportunity-filter-row">
            <label className="toggle">
              <input
                type="checkbox"
                checked={matchesOnlyFilter}
                onChange={(event) => setMatchesOnlyFilter(event.target.checked)}
              />
              <span>Matched only</span>
            </label>
            <label className="toggle">
              <input type="checkbox" checked={openOnlyFilter} onChange={(event) => setOpenOnlyFilter(event.target.checked)} />
              <span>Open only</span>
            </label>
            <label className="priority-filter-field">
              <span>Min priority</span>
              <input
                type="number"
                min={0}
                max={100}
                value={minPriorityScoreFilter}
                onChange={(event) => setMinPriorityScoreFilter(Number(event.target.value) || 0)}
              />
            </label>
          </div>

          {latestContractRun ? (
            <div className="metric-row">
              <div className="metric-pill">
                <strong>{latestContractRun.total_records}</strong>
                <span>loaded</span>
              </div>
              <div className="metric-pill">
                <strong>{latestContractRun.matched_records}</strong>
                <span>matched</span>
              </div>
              <div className="metric-pill">
                <strong>{latestContractRun.open_records}</strong>
                <span>still open</span>
              </div>
              <div className="metric-pill">
                <strong>{formatContractSource(latestContractRun.source)}</strong>
                <span>latest source</span>
              </div>
              <div className="metric-pill">
                <strong>
                  {latestContractRun.window_start} to {latestContractRun.window_end}
                </strong>
                <span>current window</span>
              </div>
            </div>
          ) : (
            <p className="empty-state">
              No opportunity sync has run yet. Refresh ESBD or sync Gmail RFQs to pull current bid opportunities.
            </p>
          )}
        </section>

        <section className="panel">
          <div className="panel-heading contract-toolbar">
            <div>
              <p className="eyebrow">Agency Preferences</p>
              <h2>Bias the list toward target buyers</h2>
            </div>
          </div>

          <p className="panel-subcopy">
            Add agencies you want to prioritize. Matching agencies lift the `agency affinity` score and feed into
            overall priority.
          </p>

          <form className="keyword-form" onSubmit={handleCreateAgencyPreference}>
            <label>
              <span>Agency</span>
              <input
                value={agencyName}
                onChange={(event) => setAgencyName(event.target.value)}
                placeholder="Texas A&M University System"
              />
            </label>
            <label className="keyword-weight-field">
              <span>Affinity</span>
              <input
                type="number"
                min={1}
                max={10}
                value={agencyWeight}
                onChange={(event) => setAgencyWeight(Number(event.target.value) || DEFAULT_AGENCY_WEIGHT)}
              />
            </label>
            <div className="action-row keyword-form-actions">
              <button type="submit" disabled={savingAgencyPreference}>
                {savingAgencyPreference ? "Saving..." : "Add agency"}
              </button>
            </div>
          </form>

          <div className="stack keyword-rule-stack">
            {agencyPreferences.length === 0 ? (
              <p className="empty-state">No preferred agencies are configured yet.</p>
            ) : (
              agencyPreferences.map((preference) =>
                editingAgencyId === preference.id ? (
                  <form
                    className="keyword-rule-card keyword-rule-form"
                    key={preference.id}
                    onSubmit={handleUpdateAgencyPreference}
                  >
                    <label>
                      <span>Agency</span>
                      <input
                        value={editingAgencyName}
                        onChange={(event) => setEditingAgencyName(event.target.value)}
                      />
                    </label>
                    <label className="keyword-weight-field">
                      <span>Affinity</span>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        value={editingAgencyWeight}
                        onChange={(event) =>
                          setEditingAgencyWeight(Number(event.target.value) || DEFAULT_AGENCY_WEIGHT)
                        }
                      />
                    </label>
                    <div className="action-row keyword-rule-actions">
                      <button type="submit" disabled={savingAgencyPreference}>
                        {savingAgencyPreference ? "Saving..." : "Save"}
                      </button>
                      <button type="button" className="secondary-link" onClick={cancelEditingAgency}>
                        Cancel
                      </button>
                    </div>
                  </form>
                ) : (
                  <div className="keyword-rule-card" key={preference.id}>
                    <div className="keyword-rule-copy">
                      <strong>{preference.agency_name}</strong>
                      <span>Affinity: {preference.weight}/10</span>
                    </div>
                    <div className="action-row keyword-rule-actions">
                      <button type="button" className="secondary-link" onClick={() => startEditingAgency(preference)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        className="secondary-link destructive-button"
                        onClick={() => void handleDeleteAgencyPreference(preference)}
                        disabled={deletingAgencyId === preference.id}
                      >
                        {deletingAgencyId === preference.id ? "Removing..." : "Remove"}
                      </button>
                    </div>
                  </div>
                ),
              )
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading contract-toolbar">
            <div>
              <p className="eyebrow">Match Keywords</p>
              <h2>Control what counts as a fit</h2>
            </div>
          </div>

          <p className="panel-subcopy">
            Add, edit, or remove the keyword rules that score ESBD opportunities. Changes rescore the stored list
            immediately.
          </p>

          <form className="keyword-form" onSubmit={handleCreateKeyword}>
            <label>
              <span>Keyword</span>
              <input
                value={keywordPhrase}
                onChange={(event) => setKeywordPhrase(event.target.value)}
                placeholder="property management"
              />
            </label>
            <label className="keyword-weight-field">
              <span>Score</span>
              <input
                type="number"
                min={1}
                max={25}
                value={keywordWeight}
                onChange={(event) => setKeywordWeight(Number(event.target.value) || DEFAULT_KEYWORD_WEIGHT)}
              />
            </label>
            <div className="action-row keyword-form-actions">
              <button type="submit" disabled={savingKeyword}>
                {savingKeyword ? "Saving..." : "Add keyword"}
              </button>
            </div>
          </form>

          <div className="stack keyword-rule-stack">
            {keywordRules.length === 0 ? (
              <p className="empty-state">No keyword rules are configured yet.</p>
            ) : (
              keywordRules.map((rule) =>
                editingKeywordId === rule.id ? (
                  <form className="keyword-rule-card keyword-rule-form" key={rule.id} onSubmit={handleUpdateKeyword}>
                    <label>
                      <span>Keyword</span>
                      <input
                        value={editingKeywordPhrase}
                        onChange={(event) => setEditingKeywordPhrase(event.target.value)}
                      />
                    </label>
                    <label className="keyword-weight-field">
                      <span>Score</span>
                      <input
                        type="number"
                        min={1}
                        max={25}
                        value={editingKeywordWeight}
                        onChange={(event) =>
                          setEditingKeywordWeight(Number(event.target.value) || DEFAULT_KEYWORD_WEIGHT)
                        }
                      />
                    </label>
                    <div className="action-row keyword-rule-actions">
                      <button type="submit" disabled={savingKeyword}>
                        {savingKeyword ? "Saving..." : "Save"}
                      </button>
                      <button type="button" className="secondary-link" onClick={cancelEditingKeyword}>
                        Cancel
                      </button>
                    </div>
                  </form>
                ) : (
                  <div className="keyword-rule-card" key={rule.id}>
                    <div className="keyword-rule-copy">
                      <strong>{rule.phrase}</strong>
                      <span>Score: {rule.weight}</span>
                    </div>
                    <div className="action-row keyword-rule-actions">
                      <button type="button" className="secondary-link" onClick={() => startEditingKeyword(rule)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        className="secondary-link destructive-button"
                        onClick={() => void handleDeleteKeyword(rule)}
                        disabled={deletingKeywordId === rule.id}
                      >
                        {deletingKeywordId === rule.id ? "Removing..." : "Remove"}
                      </button>
                    </div>
                  </div>
                ),
              )
            )}
          </div>
        </section>

        {!hasAnyContracts ? (
          <section className="panel">
            <p className="empty-state">No opportunities match the current view filters.</p>
          </section>
        ) : (
          <section className="grid opportunity-grid">
            {contractCapabilities.gmail_rfq_sync_enabled ? (
              <article className="panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">Source</p>
                    <h2>Gmail RFQs</h2>
                  </div>
                  <span>{gmailContracts.length} shown</span>
                </div>
                <div className="stack">
                  {gmailContracts.length === 0 ? (
                    <p className="empty-state">No open Gmail RFQs are synced yet.</p>
                  ) : (
                    gmailContracts.map(renderContractCard)
                  )}
                </div>
              </article>
            ) : null}

            <article className="panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Source</p>
                  <h2>Texas ESBD</h2>
                </div>
                <span>{esbdContracts.length} shown</span>
              </div>
              <div className="stack">
                {esbdContracts.length === 0 ? (
                  <p className="empty-state">No matched ESBD opportunities are stored yet.</p>
                ) : (
                  esbdContracts.map(renderContractCard)
                )}
              </div>
            </article>
          </section>
        )}
      </>
    );
  }

  return (
    <main className="page-shell">
      <nav className="view-nav">
        <button
          type="button"
          className={`nav-pill${view === "dashboard" ? " nav-pill-active" : ""}`}
          onClick={() => navigateToView("dashboard")}
        >
          Dashboard
        </button>
        <button
          type="button"
          className={`nav-pill${view === "opportunities" ? " nav-pill-active" : ""}`}
          onClick={() => navigateToView("opportunities")}
        >
          Opportunities
        </button>
      </nav>

      <section className="hero-card">
        <div>
          <p className="eyebrow">LeCrown Platform</p>
          <h1>
            {view === "dashboard"
              ? "Multi-tenant content and inquiry control room"
              : "Opportunity list and lead-funnel review"}
          </h1>
          <p className="hero-copy">
            {view === "dashboard"
              ? "One backend, two business surfaces. Switch tenants, create content, and push live when the publishing path is ready."
              : "Review matched ESBD opportunities and Gmail RFQs, then push strong fits into the CRM lead funnel."}
          </p>
        </div>

        {view === "dashboard" ? (
          <label className="tenant-picker">
            <span>Tenant</span>
            <select
              value={tenant}
              onChange={(event) => {
                const nextTenant = event.target.value as Tenant;
                setTenant(nextTenant);
                setForm(buildInitialForm(nextTenant));
              }}
            >
              <option value="development">Development</option>
              <option value="properties">Properties</option>
            </select>
          </label>
        ) : (
          <div className="hero-side">
            <span className="hero-badge">
              {opportunitiesAuthStatus === "authenticated" ? "Admin protected" : "Login required"}
            </span>
            {opportunitiesAuthStatus === "authenticated" ? (
              <button type="button" className="secondary-link" onClick={handleLogout}>
                Log out
              </button>
            ) : null}
          </div>
        )}
      </section>

      {message ? <div className="message-banner">{message}</div> : null}

      {view === "dashboard" ? renderDashboard() : renderOpportunitiesPage()}
    </main>
  );
}

function getEnabledChannels(item: Pick<Content, "distribution">): DistributionChannel[] {
  const channels: DistributionChannel[] = [];
  if (item.distribution.linkedin) {
    channels.push("linkedin");
  }
  if (item.distribution.youtube) {
    channels.push("youtube");
  }
  if (item.distribution.website) {
    channels.push("website");
  }
  if (item.distribution.twitter) {
    channels.push("twitter");
  }
  return channels;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}

function formatDateLabel(value?: string | null, time?: string | null): string {
  if (!value) {
    return "n/a";
  }
  return time ? `${value} at ${time}` : value;
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function formatNigpPreview(value: string): string {
  return value
    .replace(/\s+/g, " ")
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 3)
    .join(" | ");
}

function getScoreBreakdownValue(contract: GovContractOpportunity, key: string): number | null {
  const value = contract.score_breakdown?.[key];
  return typeof value === "number" ? value : null;
}

function getMatchedAgencyPreferences(contract: GovContractOpportunity): string[] {
  const value = contract.score_breakdown?.matched_agency_preferences;
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function getClosenessScore(contract: GovContractOpportunity): number {
  return getScoreBreakdownValue(contract, "closeness") ?? Math.max(0, Math.min(10, Math.round(contract.score / 2)));
}

function formatContractSource(source: string): string {
  if (source === "gmail_rfqs") {
    return "Gmail RFQs";
  }
  if (source === "txsmartbuy_esbd") {
    return "Texas ESBD";
  }
  return source.split("_").join(" ");
}

function formatFunnelLabel(contract: GovContractOpportunity): string {
  if (contract.funnel_delivery_status === "delivered") {
    return "in CRM";
  }
  if (contract.funnel_delivery_status === "failed") {
    return "CRM sync failed";
  }
  return contract.funnel_status;
}
