import { useEffect, useState, type FormEvent } from "react";

import BillingPage from "./BillingPage";
import {
  acceptInvite,
  changePassword,
  clearAuthToken,
  createContent,
  createGovContractAgencyPreference,
  createGovContractKeywordRule,
  createUserInvite,
  deleteGovContractAgencyPreference,
  deleteGovContractKeywordRule,
  downloadFederalContractsExport,
  downloadGovContractsExport,
  downloadGrantsContractsExport,
  funnelGovContract,
  getIntakeDashboard,
  getCurrentAdmin,
  getGovContractCapabilities,
  hasStoredAuthToken,
  listGovContractAgencyPreferences,
  listGovContractKeywordRules,
  listGovContractTrackedSources,
  listContent,
  listGovContractRuns,
  listGovContracts,
  listInquiries,
  listUserInvites,
  login,
  publishDistribution,
  publishToLinkedIn,
  refreshFederalContracts,
  refreshGmailRfqs,
  refreshGovContracts,
  refreshGrantsContracts,
  refreshSbaSubnetContracts,
  refreshTrackedGovSources,
  revokeUserInvite,
  storeAuthToken,
  updateGovContractAgencyPreference,
  updateGovContractKeywordRule,
} from "../../shared/api";
import type {
  AuthUser,
  Content,
  ContentCreate,
  DistributionChannel,
  GovContractAgencyPreference,
  GovContractImportRun,
  GovContractOpportunity,
  GovContractCapabilities,
  GovContractKeywordRule,
  GovContractTrackedSource,
  IntakeDashboard,
  Inquiry,
  Tenant,
  UserInvite,
  UserInviteCreateResponse,
} from "../../shared/types";

type AdminView = "dashboard" | "intake" | "opportunities" | "sources" | "billing" | "profile";
type OpportunitiesAuthStatus = "checking" | "authenticated" | "unauthenticated";
type OpportunityCategoryTab = "all" | "it_services" | "property_services" | "other";
type OpportunityTagFilterKind = "source" | "tag" | "preferred_agency";
type OpportunityTagFilter = {
  kind: OpportunityTagFilterKind;
  value: string;
  label: string;
};
type MetroVendorResource = {
  title: string;
  description: string;
  href: string;
  cta: string;
  tags: string[];
};
const DEFAULT_KEYWORD_WEIGHT = 3;
const DEFAULT_AGENCY_WEIGHT = 7;
const OPPORTUNITY_LIST_LIMIT = 200;
const OPPORTUNITY_CATEGORY_TABS: Array<{ id: OpportunityCategoryTab; label: string }> = [
  { id: "all", label: "All opportunities" },
  { id: "it_services", label: "IT services" },
  { id: "property_services", label: "Real estate / property" },
  { id: "other", label: "Other" },
];
const METRO_VENDOR_RESOURCES: MetroVendorResource[] = [
  {
    title: "SBE Certification Portal",
    description: "Apply, renew, search firms, and manage METRO small-business certification and compliance in B2Gnow.",
    href: "https://ridemetro.sbdbe.com/",
    cta: "Open portal",
    tags: ["Certification", "Compliance"],
  },
  {
    title: "SBE Business Assessment",
    description: "METRO’s intake form for matching your firm to the right next steps based on performance, bonding, insurance, and revenue profile.",
    href: "https://ridemetro.qualtrics.com/jfe/form/SV_e3C1E0X9CM61Kx8",
    cta: "Start assessment",
    tags: ["Readiness", "Intake"],
  },
  {
    title: "Business University",
    description: "METRO’s training calendar for certification, facilities maintenance, procurement, and vendor-development workshops.",
    href: "https://www.ridemetro.org/about/business-to-business/procurement-opportunities#metro-business-university-active-modal",
    cta: "View events",
    tags: ["Training", "Networking"],
  },
  {
    title: "METRO Procurement Page",
    description: "Primary source for open procurements, forecast tabs, major construction listings, and advance procurement notices.",
    href: "https://www.ridemetro.org/about/business-to-business/procurement-opportunities",
    cta: "Open source",
    tags: ["Source", "Forecasts"],
  },
];

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
  if (window.location.hash.startsWith("#/intake")) {
    return "intake";
  }
  if (window.location.hash.startsWith("#/profile")) {
    return "profile";
  }
  if (window.location.hash.startsWith("#/billing")) {
    return "billing";
  }
  if (window.location.hash.startsWith("#/sources")) {
    return "sources";
  }
  return window.location.hash.startsWith("#/opportunities") ? "opportunities" : "dashboard";
}

function navigateToView(view: AdminView): void {
  if (typeof window === "undefined") {
    return;
  }
  if (view === "opportunities") {
    window.location.hash = "#/opportunities";
    return;
  }
  if (view === "sources") {
    window.location.hash = "#/sources";
    return;
  }
  if (view === "intake") {
    window.location.hash = "#/intake";
    return;
  }
  if (view === "profile") {
    window.location.hash = "#/profile";
    return;
  }
  if (view === "billing") {
    window.location.hash = "#/billing";
    return;
  }
  window.location.hash = "#/";
}

function getInviteCodeFromLocation(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const searchCode = new URLSearchParams(window.location.search).get("invite_code");
  if (searchCode) {
    return searchCode;
  }
  const queryIndex = window.location.hash.indexOf("?");
  if (queryIndex === -1) {
    return null;
  }
  return new URLSearchParams(window.location.hash.slice(queryIndex + 1)).get("invite_code");
}

export default function App() {
  const [view, setView] = useState<AdminView>(getCurrentView());
  const [tenant, setTenant] = useState<Tenant>("development");
  const [form, setForm] = useState<ContentCreate>(buildInitialForm());
  const [contentItems, setContentItems] = useState<Content[]>([]);
  const [inquiries, setInquiries] = useState<Inquiry[]>([]);
  const [intakeDashboard, setIntakeDashboard] = useState<IntakeDashboard | null>(null);
  const [govContracts, setGovContracts] = useState<GovContractOpportunity[]>([]);
  const [contractRuns, setContractRuns] = useState<GovContractImportRun[]>([]);
  const [trackedSources, setTrackedSources] = useState<GovContractTrackedSource[]>([]);
  const [contractCapabilities, setContractCapabilities] = useState<GovContractCapabilities>({
    gmail_rfq_sync_enabled: false,
    gmail_rfq_feed_label: null,
  });
  const [currentAdmin, setCurrentAdmin] = useState<AuthUser | null>(null);
  const [userInvites, setUserInvites] = useState<UserInvite[]>([]);
  const [latestInvite, setLatestInvite] = useState<UserInviteCreateResponse | null>(null);
  const [agencyPreferences, setAgencyPreferences] = useState<GovContractAgencyPreference[]>([]);
  const [keywordRules, setKeywordRules] = useState<GovContractKeywordRule[]>([]);
  const [message, setMessage] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [refreshingIntakeDashboard, setRefreshingIntakeDashboard] = useState(false);
  const [refreshingContracts, setRefreshingContracts] = useState(false);
  const [refreshingFederalContracts, setRefreshingFederalContracts] = useState(false);
  const [refreshingGrantsContracts, setRefreshingGrantsContracts] = useState(false);
  const [refreshingSbaSubnetContracts, setRefreshingSbaSubnetContracts] = useState(false);
  const [refreshingGmailContracts, setRefreshingGmailContracts] = useState(false);
  const [refreshingTrackedSources, setRefreshingTrackedSources] = useState(false);
  const [downloadingExport, setDownloadingExport] = useState(false);
  const [downloadingFederalExport, setDownloadingFederalExport] = useState(false);
  const [downloadingGrantsExport, setDownloadingGrantsExport] = useState(false);
  const [funnelingContractId, setFunnelingContractId] = useState<string | null>(null);
  const [opportunitiesAuthStatus, setOpportunitiesAuthStatus] =
    useState<OpportunitiesAuthStatus>("unauthenticated");
  const [opportunityCategoryTab, setOpportunityCategoryTab] = useState<OpportunityCategoryTab>("all");
  const [selectedOpportunitySourceFilter, setSelectedOpportunitySourceFilter] = useState<string | null>(null);
  const [selectedOpportunitySourceContextFilter, setSelectedOpportunitySourceContextFilter] = useState<string | null>(null);
  const [selectedOpportunityTagFilter, setSelectedOpportunityTagFilter] = useState<OpportunityTagFilter | null>(null);
  const [opportunityKeywordFilter, setOpportunityKeywordFilter] = useState("");
  const [loginUsername, setLoginUsername] = useState("admin");
  const [loginPassword, setLoginPassword] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);
  const [acceptingInvite, setAcceptingInvite] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [inviteUsername, setInviteUsername] = useState("");
  const [invitePassword, setInvitePassword] = useState("");
  const [invitePasswordConfirm, setInvitePasswordConfirm] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [creatingInvite, setCreatingInvite] = useState(false);
  const [revokingInviteId, setRevokingInviteId] = useState<string | null>(null);
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
      const presetInviteCode = getInviteCodeFromLocation();
      if (presetInviteCode) {
        setInviteCode(presetInviteCode);
      }
    }

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  useEffect(() => {
    const presetInviteCode = getInviteCodeFromLocation();
    if (presetInviteCode) {
      setInviteCode(presetInviteCode);
      navigateToView("opportunities");
    }
  }, []);

  useEffect(() => {
    void refreshContent(tenant);
    if (tenant === "properties") {
      void refreshInquiries();
    }
  }, [tenant]);

  useEffect(() => {
    if (view !== "opportunities" && view !== "sources" && view !== "profile" && view !== "intake" && view !== "billing") {
      return;
    }
    void ensureProtectedAccess();
  }, [view]);

  useEffect(() => {
    if ((view !== "opportunities" && view !== "sources") || opportunitiesAuthStatus !== "authenticated") {
      return;
    }
    void refreshContractsView();
  }, [matchesOnlyFilter, minPriorityScoreFilter, openOnlyFilter]);

  useEffect(() => {
    if (view !== "intake" || opportunitiesAuthStatus !== "authenticated") {
      return;
    }
    void refreshIntakeDashboard();
  }, [view, opportunitiesAuthStatus]);

  async function ensureProtectedAccess() {
    if (!hasStoredAuthToken()) {
      setOpportunitiesAuthStatus("unauthenticated");
      setCurrentAdmin(null);
      return;
    }

    setOpportunitiesAuthStatus("checking");
    try {
      const currentUser = await getCurrentAdmin();
      setCurrentAdmin(currentUser);
      const capabilities = await getGovContractCapabilities();
      setContractCapabilities(capabilities);
      setAuthMessage("");
      setOpportunitiesAuthStatus("authenticated");
      if (view === "opportunities" || view === "sources") {
        await refreshContractsView(capabilities);
      }
    } catch {
      clearAuthToken();
      setCurrentAdmin(null);
      setIntakeDashboard(null);
      setOpportunitiesAuthStatus("unauthenticated");
      setAuthMessage("Sign in to continue.");
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

  async function refreshIntakeDashboard() {
    setRefreshingIntakeDashboard(true);
    try {
      const dashboard = await getIntakeDashboard();
      setIntakeDashboard(dashboard);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setRefreshingIntakeDashboard(false);
    }
  }

  async function refreshContractsView(capabilitiesOverride?: GovContractCapabilities) {
    try {
      const capabilities = capabilitiesOverride ?? contractCapabilities;
      const currentUser = currentAdmin ?? (await getCurrentAdmin());
      setCurrentAdmin(currentUser);
      const [contracts, runs, sources, keywords, agencyPrefs, invites] =
        await Promise.all([
          listGovContracts(OPPORTUNITY_LIST_LIMIT, undefined, {
            matchesOnly: matchesOnlyFilter,
            minPriorityScore: minPriorityScoreFilter,
            openOnly: openOnlyFilter,
          }),
          listGovContractRuns(25),
          listGovContractTrackedSources(),
          listGovContractKeywordRules(),
          listGovContractAgencyPreferences(),
          currentUser.is_admin ? listUserInvites() : Promise.resolve([]),
        ]);
      setGovContracts(
        capabilities.gmail_rfq_sync_enabled ? contracts : contracts.filter((contract) => contract.source !== "gmail_rfqs"),
      );
      setContractRuns(runs);
      setTrackedSources(sources);
      setKeywordRules(keywords);
      setAgencyPreferences(agencyPrefs);
      setUserInvites(invites);
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

  async function handleFederalContractRefresh() {
    setRefreshingFederalContracts(true);
    setMessage("");
    try {
      const run = await refreshFederalContracts();
      await refreshContractsView();
      setMessage(
        `Federal forecast refreshed. ${run.matched_records} matches from ${run.total_records} opportunities.`,
      );
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setRefreshingFederalContracts(false);
    }
  }

  async function handleGrantsContractRefresh() {
    setRefreshingGrantsContracts(true);
    setMessage("");
    try {
      const run = await refreshGrantsContracts();
      await refreshContractsView();
      setMessage(`Grants.gov refreshed. ${run.matched_records} matches from ${run.total_records} opportunities.`);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setRefreshingGrantsContracts(false);
    }
  }

  async function handleSbaSubnetContractRefresh() {
    setRefreshingSbaSubnetContracts(true);
    setMessage("");
    try {
      const run = await refreshSbaSubnetContracts();
      await refreshContractsView();
      setMessage(`SBA SUBNet refreshed. ${run.matched_records} matches from ${run.total_records} opportunities.`);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setRefreshingSbaSubnetContracts(false);
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

  async function handleTrackedSourceRefresh() {
    setRefreshingTrackedSources(true);
    setMessage("");
    try {
      const runs = await refreshTrackedGovSources();
      await refreshContractsView();
      const completedCount = runs.filter((run) => run.status === "completed").length;
      const reviewCount = runs.filter((run) => run.status === "manual_review" || run.status === "cataloged").length;
      const blockedCount = runs.filter((run) => run.status === "blocked" || run.status === "failed").length;
      setMessage(
        `Tracked sources refreshed. ${completedCount} loaded, ${reviewCount} need review, ${blockedCount} blocked or failed.`,
      );
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setRefreshingTrackedSources(false);
    }
  }

  async function handleFederalContractExport() {
    setDownloadingFederalExport(true);
    setMessage("");
    try {
      await downloadFederalContractsExport();
      setMessage("Federal forecast CSV download started.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setDownloadingFederalExport(false);
    }
  }

  async function handleGrantsContractExport() {
    setDownloadingGrantsExport(true);
    setMessage("");
    try {
      await downloadGrantsContractsExport();
      setMessage("Grants.gov CSV download started.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setDownloadingGrantsExport(false);
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
      setCurrentAdmin(token.user);
      const capabilities = await getGovContractCapabilities();
      setContractCapabilities(capabilities);
      setOpportunitiesAuthStatus("authenticated");
      if (view === "opportunities" || view === "sources") {
        await refreshContractsView(capabilities);
      }
      setMessage("Signed in.");
    } catch (error) {
      clearAuthToken();
      setOpportunitiesAuthStatus("unauthenticated");
      setAuthMessage(getErrorMessage(error));
    } finally {
      setLoggingIn(false);
    }
  }

  async function handleAcceptInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (invitePassword !== invitePasswordConfirm) {
      setAuthMessage("Invite passwords do not match.");
      return;
    }

    setAcceptingInvite(true);
    setAuthMessage("");
    setMessage("");

    try {
      const token = await acceptInvite({
        invite_code: inviteCode,
        username: inviteUsername,
        password: invitePassword,
      });
      storeAuthToken(token.access_token);
      setCurrentAdmin(token.user);
      const capabilities = await getGovContractCapabilities();
      setContractCapabilities(capabilities);
      setOpportunitiesAuthStatus("authenticated");
      setInviteCode("");
      setInviteUsername("");
      setInvitePassword("");
      setInvitePasswordConfirm("");
      if (view === "opportunities" || view === "sources") {
        await refreshContractsView(capabilities);
      }
      setMessage("Invite accepted. Your account is ready.");
      navigateToView("profile");
    } catch (error) {
      clearAuthToken();
      setCurrentAdmin(null);
      setOpportunitiesAuthStatus("unauthenticated");
      setAuthMessage(getErrorMessage(error));
    } finally {
      setAcceptingInvite(false);
    }
  }

  function handleLogout() {
    clearAuthToken();
    setCurrentAdmin(null);
    setIntakeDashboard(null);
    setOpportunitiesAuthStatus("unauthenticated");
    setAuthMessage("");
    setGovContracts([]);
    setContractRuns([]);
    setTrackedSources([]);
    setAgencyPreferences([]);
    setKeywordRules([]);
    setUserInvites([]);
    setLatestInvite(null);
    setContractCapabilities({
      gmail_rfq_sync_enabled: false,
      gmail_rfq_feed_label: null,
    });
    setOpportunityCategoryTab("all");
    setSelectedOpportunitySourceFilter(null);
    setSelectedOpportunityTagFilter(null);
    setOpportunityKeywordFilter("");
    setMinPriorityScoreFilter(0);
    setEditingKeywordId(null);
    setEditingKeywordPhrase("");
    setEditingKeywordWeight(DEFAULT_KEYWORD_WEIGHT);
    setEditingAgencyId(null);
    setEditingAgencyName("");
    setEditingAgencyWeight(DEFAULT_AGENCY_WEIGHT);
    setAgencyName("");
    setAgencyWeight(DEFAULT_AGENCY_WEIGHT);
    setInviteEmail("");
    setCurrentPassword("");
    setNewPassword("");
    setConfirmNewPassword("");
    setKeywordPhrase("");
    setKeywordWeight(DEFAULT_KEYWORD_WEIGHT);
    setDeletingAgencyId(null);
    setDeletingKeywordId(null);
  }

  async function handleChangePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPassword !== confirmNewPassword) {
      setMessage("New passwords do not match.");
      return;
    }

    setChangingPassword(true);
    setMessage("");
    try {
      const user = await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentAdmin(user);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
      setMessage("Password changed.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setChangingPassword(false);
    }
  }

  async function handleCreateInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreatingInvite(true);
    setMessage("");
    try {
      const invite = await createUserInvite({ email: inviteEmail });
      setInviteEmail("");
      setLatestInvite(invite);
      await refreshContractsView();
      setMessage(buildInviteCreateMessage(invite));
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setCreatingInvite(false);
    }
  }

  async function handleRevokeInvite(invite: UserInvite) {
    setRevokingInviteId(invite.id);
    setMessage("");
    try {
      await revokeUserInvite(invite.id);
      if (latestInvite?.id === invite.id) {
        setLatestInvite(null);
      }
      await refreshContractsView();
      setMessage("Invite revoked.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setRevokingInviteId(null);
    }
  }

  async function handleCopyInviteCode(invite: UserInviteCreateResponse) {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(invite.invite_code);
        setMessage("Invite code copied.");
        return;
      }
      setMessage(`Copy this invite code manually: ${invite.invite_code}`);
    } catch {
      setMessage(`Copy this invite code manually: ${invite.invite_code}`);
    }
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
  const isAdminUser = currentAdmin?.is_admin ?? false;

  function handleOpportunityTagFilterClick(filter: OpportunityTagFilter) {
    setSelectedOpportunityTagFilter((current) =>
      current && current.kind === filter.kind && current.value === filter.value ? null : filter,
    );
  }

  function renderProtectedAuthPanel({
    eyebrow,
    title,
    subcopy,
  }: {
    eyebrow: string;
    title: string;
    subcopy: string;
  }) {
    return (
      <>
        {authMessage ? <div className="message-banner auth-banner">{authMessage}</div> : null}

        <section className="grid auth-grid">
          <article className="panel auth-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">{eyebrow}</p>
                <h2>{title}</h2>
              </div>
            </div>

            <p className="panel-subcopy">{subcopy}</p>

            <form className="content-form auth-form" onSubmit={handleOpportunitiesLogin}>
              <label>
                <span>Username or email</span>
                <input
                  value={loginUsername}
                  onChange={(event) => setLoginUsername(event.target.value)}
                  placeholder="admin or you@example.com"
                />
              </label>

              <label>
                <span>Password</span>
                <input
                  type="password"
                  value={loginPassword}
                  onChange={(event) => setLoginPassword(event.target.value)}
                  placeholder="Enter your password"
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
          </article>

          <article className="panel auth-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Invite Only</p>
                <h2>Activate an invited account</h2>
              </div>
            </div>

            <p className="panel-subcopy">
              This workspace does not allow open signups. Enter the invite code an admin sent you, choose a username,
              and set your password.
            </p>

            <form className="content-form auth-form" onSubmit={handleAcceptInvite}>
              <label>
                <span>Invite code</span>
                <input
                  value={inviteCode}
                  onChange={(event) => setInviteCode(event.target.value)}
                  placeholder="Paste your invite code"
                />
              </label>

              <label>
                <span>Username</span>
                <input
                  value={inviteUsername}
                  onChange={(event) => setInviteUsername(event.target.value)}
                  placeholder="Choose a username"
                />
              </label>

              <label>
                <span>Password</span>
                <input
                  type="password"
                  value={invitePassword}
                  onChange={(event) => setInvitePassword(event.target.value)}
                  placeholder="Create a password"
                />
              </label>

              <label>
                <span>Confirm password</span>
                <input
                  type="password"
                  value={invitePasswordConfirm}
                  onChange={(event) => setInvitePasswordConfirm(event.target.value)}
                  placeholder="Repeat your password"
                />
              </label>

              <div className="action-row auth-actions">
                <button type="submit" disabled={acceptingInvite}>
                  {acceptingInvite ? "Activating..." : "Accept invite"}
                </button>
              </div>
            </form>
          </article>
        </section>
      </>
    );
  }

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
          <span>Reference: {contract.solicitation_id}</span>
          <span>Status: {contract.status_name ?? "Unknown"}</span>
          <span>Due: {formatDateLabel(contract.due_date, contract.due_time)}</span>
          <span>Posted: {formatDateLabel(contract.posting_date)}</span>
          {contract.source_context_label ? <span>Context: {contract.source_context_label}</span> : null}
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
              <button
                type="button"
                className={`tag filter-tag-button${
                  isOpportunityTagFilterActive(selectedOpportunityTagFilter, {
                    kind: "preferred_agency",
                    value: agencyName,
                    label: `Preferred agency: ${agencyName}`,
                  })
                    ? " filter-tag-button-active"
                    : ""
                }`}
                key={agencyName}
                aria-pressed={isOpportunityTagFilterActive(selectedOpportunityTagFilter, {
                  kind: "preferred_agency",
                  value: agencyName,
                  label: `Preferred agency: ${agencyName}`,
                })}
                onClick={() =>
                  handleOpportunityTagFilterClick({
                    kind: "preferred_agency",
                    value: agencyName,
                    label: `Preferred agency: ${agencyName}`,
                  })
                }
              >
                Preferred agency: {agencyName}
              </button>
            ))}
          </div>
        ) : null}

        <div className="tag-row">
          <button
            type="button"
            className={`tag filter-tag-button${
              selectedOpportunitySourceFilter === contract.source
                ? " filter-tag-button-active"
                : ""
            }`}
            aria-pressed={selectedOpportunitySourceFilter === contract.source}
            onClick={() => {
              setSelectedOpportunitySourceFilter((current) =>
                current === contract.source ? null : contract.source,
              );
              setSelectedOpportunitySourceContextFilter(null);
            }}
          >
            {formatContractSource(contract.source)}
          </button>
          {contract.source_context ? (
            <button
              type="button"
              className={`tag filter-tag-button${
                selectedOpportunitySourceContextFilter === contract.source_context
                  ? " filter-tag-button-active"
                  : ""
              }`}
              aria-pressed={selectedOpportunitySourceContextFilter === contract.source_context}
              onClick={() =>
                setSelectedOpportunitySourceContextFilter((current) =>
                  current === contract.source_context ? null : contract.source_context ?? null,
                )
              }
            >
              {formatContractSourceContextLabel(contract.source_context_label, contract.source_context)}
            </button>
          ) : null}
          {getOpportunityDisplayTags(contract).map((tag) => (
            <button
              type="button"
              className={`tag filter-tag-button${
                isOpportunityTagFilterActive(selectedOpportunityTagFilter, {
                  kind: "tag",
                  value: tag,
                  label: tag,
                })
                  ? " filter-tag-button-active"
                  : ""
              }`}
              key={tag}
              aria-pressed={isOpportunityTagFilterActive(selectedOpportunityTagFilter, {
                kind: "tag",
                value: tag,
                label: tag,
              })}
              onClick={() =>
                handleOpportunityTagFilterClick({
                  kind: "tag",
                  value: tag,
                  label: tag,
                })
              }
            >
              {tag}
            </button>
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
            {isAdminUser ? (
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
            ) : null}
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
              <p className="eyebrow">Marketing Intake</p>
              <h2>Dedicated intake page</h2>
            </div>
            <div className="action-row">
              <button type="button" onClick={() => navigateToView("intake")}>
                Open marketing intake page
              </button>
            </div>
          </div>
          <p className="panel-subcopy">
            Review connected intake surfaces, recent source-site activity, and new contact initiations flowing toward CRM.
          </p>
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
            Federal forecast, Grants.gov, SBA SUBNet, ESBD opportunities, and Gmail RFQs now live on a separate page and require an invited account sign-in.
          </p>
        </section>
      </>
    );
  }

  function renderProfilePage() {
    if (opportunitiesAuthStatus === "checking") {
      return (
        <section className="panel auth-panel">
          <p className="empty-state">Checking account access...</p>
        </section>
      );
    }

    if (opportunitiesAuthStatus === "unauthenticated" || !currentAdmin) {
      return renderProtectedAuthPanel({
        eyebrow: "Account Access",
        title: "Profile and password",
        subcopy: "Sign in with your existing account or accept an invite code to activate a new login.",
      });
    }

    return (
      <>
        <section className="grid profile-grid">
          <article className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Account</p>
                <h2>Profile summary</h2>
              </div>
            </div>

            <p className="panel-subcopy">
              Authentication is stored inside this app. It is not delegated to an external Keycloak tenant.
            </p>

            <div className="profile-stat-grid">
              <div className="metric-pill">
                <strong>{currentAdmin.username}</strong>
                <span>username</span>
              </div>
              <div className="metric-pill">
                <strong>{currentAdmin.email}</strong>
                <span>email</span>
              </div>
              <div className="metric-pill">
                <strong>{currentAdmin.is_admin ? "Admin" : "Member"}</strong>
                <span>role</span>
              </div>
              <div className="metric-pill">
                <strong>{formatTimestamp(currentAdmin.created_at)}</strong>
                <span>joined</span>
              </div>
            </div>
          </article>

          <article className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Password</p>
                <h2>Change your password</h2>
              </div>
            </div>

            <p className="panel-subcopy">
              Enter your current password, then set a new one. After bootstrap, password changes are managed here.
            </p>

            <form className="content-form auth-form" onSubmit={handleChangePassword}>
              <label>
                <span>Current password</span>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  placeholder="Enter your current password"
                />
              </label>

              <label>
                <span>New password</span>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  placeholder="Use at least 8 characters"
                />
              </label>

              <label>
                <span>Confirm new password</span>
                <input
                  type="password"
                  value={confirmNewPassword}
                  onChange={(event) => setConfirmNewPassword(event.target.value)}
                  placeholder="Repeat your new password"
                />
              </label>

              <div className="action-row auth-actions">
                <button type="submit" disabled={changingPassword}>
                  {changingPassword ? "Updating..." : "Change password"}
                </button>
              </div>
            </form>
          </article>
        </section>

        {isAdminUser ? (
          <>
            <section className="panel">
              <div className="panel-heading contract-toolbar">
                <div>
                  <p className="eyebrow">Invitations</p>
                  <h2>Invite-only user access</h2>
                </div>
              </div>

              <p className="panel-subcopy">
                Create accounts by invite only. New users cannot self-register without an invite code from an admin.
              </p>

              <form className="keyword-form" onSubmit={handleCreateInvite}>
                <label>
                  <span>Email</span>
                  <input
                    value={inviteEmail}
                    onChange={(event) => setInviteEmail(event.target.value)}
                    placeholder="user@example.com"
                    type="email"
                    required
                  />
                </label>
                <div className="action-row keyword-form-actions">
                  <button type="submit" disabled={creatingInvite}>
                    {creatingInvite ? "Creating..." : "Create invite"}
                  </button>
                </div>
              </form>

              {latestInvite ? (
                <div className="invite-code-card">
                  <div className="invite-code-card-copy">
                    <strong>{latestInvite.email}</strong>
                    <span>
                      {latestInvite.email_delivery_status === "sent"
                        ? "Invite email sent automatically. They can still use this one-time invite code manually."
                        : "Email delivery is not configured. Send this user to the app and give them this one-time invite code."}
                    </span>
                    {latestInvite.email_delivery_status !== "sent" && latestInvite.email_delivery_detail ? (
                      <span>{latestInvite.email_delivery_detail}</span>
                    ) : null}
                  </div>
                  <code className="invite-code">{latestInvite.invite_code}</code>
                  <div className="action-row">
                    <button type="button" className="secondary-link" onClick={() => void handleCopyInviteCode(latestInvite)}>
                      Copy invite code
                    </button>
                  </div>
                </div>
              ) : null}

              <div className="invite-list">
                {userInvites.length === 0 ? (
                  <p className="empty-state">No invites have been created yet.</p>
                ) : (
                  userInvites.map((invite) => (
                    <div className="invite-row" key={invite.id}>
                      <div className="invite-row-meta">
                        <strong>{invite.email}</strong>
                        <span>Status: {formatInviteStatus(invite)}</span>
                        <span>Created: {formatTimestamp(invite.created_at)}</span>
                        <span>Expires: {formatTimestamp(invite.expires_at)}</span>
                        {invite.accepted_at ? <span>Accepted: {formatTimestamp(invite.accepted_at)}</span> : null}
                      </div>
                      {invite.accepted_at || invite.revoked_at ? null : (
                        <div className="action-row">
                          <button
                            type="button"
                            className="secondary-link destructive-button"
                            onClick={() => void handleRevokeInvite(invite)}
                            disabled={revokingInviteId === invite.id}
                          >
                            {revokingInviteId === invite.id ? "Revoking..." : "Revoke"}
                          </button>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </section>
          </>
        ) : (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Access</p>
                <h2>Invite-only membership</h2>
              </div>
            </div>
            <p className="panel-subcopy">
              Your account was created by invite. Admin users control new invitations, scoring rules, source refreshes,
              and CRM funnel actions.
            </p>
          </section>
        )}
      </>
    );
  }

  function renderBillingPage() {
    if (opportunitiesAuthStatus === "checking") {
      return (
        <section className="panel auth-panel">
          <p className="empty-state">Checking billing access...</p>
        </section>
      );
    }

    if (opportunitiesAuthStatus === "unauthenticated" || !currentAdmin) {
      return renderProtectedAuthPanel({
        eyebrow: "Billing Access",
        title: "Operator billing workflow",
        subcopy: "Sign in with your invited account to open the protected Billing page and prepare invoices.",
      });
    }

    return <BillingPage currentUser={currentAdmin} />;
  }

  function renderIntakePage() {
    if (opportunitiesAuthStatus === "checking") {
      return (
        <section className="panel auth-panel">
          <p className="empty-state">Checking intake access...</p>
        </section>
      );
    }

    if (opportunitiesAuthStatus === "unauthenticated") {
      return renderProtectedAuthPanel({
        eyebrow: "Account Access",
        title: "Marketing intake dashboard",
        subcopy: "Sign in with your username or email, or accept an invite code to review connected sources and new contact initiations.",
      });
    }

    if (!intakeDashboard && refreshingIntakeDashboard) {
      return (
        <section className="panel auth-panel">
          <p className="empty-state">Loading marketing intake dashboard...</p>
        </section>
      );
    }

    if (!intakeDashboard) {
      return (
        <section className="panel auth-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Marketing Intake</p>
              <h2>No dashboard data loaded yet</h2>
            </div>
            <div className="action-row">
              <button type="button" onClick={() => void refreshIntakeDashboard()} disabled={refreshingIntakeDashboard}>
                {refreshingIntakeDashboard ? "Refreshing..." : "Refresh intake"}
              </button>
            </div>
          </div>
          <p className="empty-state">Refresh to load the current source and CRM intake summary.</p>
        </section>
      );
    }

    return (
      <>
        <section className="panel">
          <div className="panel-heading contract-toolbar">
            <div>
              <p className="eyebrow">Marketing Intake</p>
              <h2>Cross-site contact funnel</h2>
            </div>
            <div className="action-row">
              <button type="button" onClick={() => void refreshIntakeDashboard()} disabled={refreshingIntakeDashboard}>
                {refreshingIntakeDashboard ? "Refreshing..." : "Refresh intake"}
              </button>
            </div>
          </div>

          <p className="panel-subcopy">
            Review which source sites are sending leads, whether the CRM handoff is configured, and which new contacts have initiated the funnel.
          </p>

          <div className="metric-row">
            <div className="metric-pill">
              <strong>{intakeDashboard.overview.observed_source_sites}</strong>
              <span>source sites observed</span>
            </div>
            <div className="metric-pill">
              <strong>{intakeDashboard.overview.new_contacts_today}</strong>
              <span>new in last 24h</span>
            </div>
            <div className="metric-pill">
              <strong>{intakeDashboard.overview.new_contacts_7d}</strong>
              <span>new in last 7d</span>
            </div>
            <div className="metric-pill">
              <strong>{intakeDashboard.overview.delivered_submissions}</strong>
              <span>delivered to CRM</span>
            </div>
            <div className="metric-pill">
              <strong>{intakeDashboard.overview.failed_submissions}</strong>
              <span>CRM delivery failures</span>
            </div>
            <div className="metric-pill">
              <strong>{intakeDashboard.overview.total_submissions}</strong>
              <span>total submissions</span>
            </div>
          </div>
        </section>

        <section className="grid intake-grid">
          <article className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Connections</p>
                <h2>What is connected</h2>
              </div>
            </div>

            <div className="stack">
              {intakeDashboard.connections.map((connection) => (
                <article className="content-card" key={connection.key}>
                  <div className="content-meta">
                    <div>
                      <strong>{connection.label}</strong>
                      <span>{connection.detail}</span>
                    </div>
                    <span className={getIntakeStatusBadgeClass(connection.status)}>
                      {formatIntakeConnectionStatus(connection.status)}
                    </span>
                  </div>

                  {connection.value ? (
                    <div className="tag-row">
                      <span className="tag">{connection.value}</span>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          </article>

          <article className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Source Sites</p>
                <h2>Observed intake activity</h2>
              </div>
            </div>

            {intakeDashboard.source_sites.length === 0 ? (
              <p className="empty-state">No marketing sources have submitted leads yet.</p>
            ) : (
              <div className="stack">
                {intakeDashboard.source_sites.map((source) => (
                  <article className="content-card" key={source.source_site}>
                    <div className="content-meta">
                      <div>
                        <strong>{source.source_site}</strong>
                        <span>{formatIntakeSourceType(source.source_type)}</span>
                      </div>
                      <span className={getIntakeStatusBadgeClass(source.last_delivery_status)}>
                        {formatIntakeDeliveryStatus(source.last_delivery_status)}
                      </span>
                    </div>

                    {source.business_contexts.length > 0 || source.form_providers.length > 0 || source.form_names.length > 0 ? (
                      <div className="tag-row">
                        {source.business_contexts.map((context) => (
                          <span className="tag" key={`${source.source_site}-context-${context}`}>
                            {context}
                          </span>
                        ))}
                        {source.form_providers.map((provider) => (
                          <span className="tag" key={`${source.source_site}-provider-${provider}`}>
                            {provider}
                          </span>
                        ))}
                        {source.form_names.map((formName) => (
                          <span className="tag" key={`${source.source_site}-form-${formName}`}>
                            {formName}
                          </span>
                        ))}
                      </div>
                    ) : null}

                    <div className="status-stack">
                      <span>Submissions: {source.total_submissions}</span>
                      <span>New 24h: {source.new_contacts_today}</span>
                      <span>New 7d: {source.new_contacts_7d}</span>
                      <span>CRM delivered: {source.delivered_submissions}</span>
                      <span>CRM failed: {source.failed_submissions}</span>
                      <span>Latest contact: {source.last_contact_name ?? "Unknown contact"}</span>
                      <span>Last submission: {formatTimestamp(source.last_submission_at)}</span>
                      {source.last_page_url ? <span>Last page: {source.last_page_url}</span> : null}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </article>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">New Contacts</p>
              <h2>Recent initiations</h2>
            </div>
          </div>

          {intakeDashboard.recent_contacts.length === 0 ? (
            <p className="empty-state">No new contacts have initiated the marketing funnel yet.</p>
          ) : (
            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>Contact</th>
                    <th>Source</th>
                    <th>Context</th>
                    <th>CRM</th>
                    <th>Initiated</th>
                  </tr>
                </thead>
                <tbody>
                  {intakeDashboard.recent_contacts.map((contact) => (
                    <tr key={contact.id}>
                      <td>
                        <strong>{contact.contact_name ?? "Unknown contact"}</strong>
                        {contact.email ? <span>{contact.email}</span> : null}
                        {contact.phone ? <span>{contact.phone}</span> : null}
                      </td>
                      <td>
                        <strong>{contact.source_site}</strong>
                        {contact.page_url ? <span>{contact.page_url}</span> : null}
                        {contact.campaign ? <span>Campaign: {contact.campaign}</span> : null}
                      </td>
                      <td>
                        <strong>{contact.business_context ?? "Unscoped"}</strong>
                        <span>{contact.product_context ?? "No product context"}</span>
                      </td>
                      <td>
                        <span className={getIntakeStatusBadgeClass(contact.delivery_status)}>
                          {formatIntakeDeliveryStatus(contact.delivery_status)}
                        </span>
                        {contact.delivery_record_id ? <span>Record: {contact.delivery_record_id}</span> : null}
                      </td>
                      <td>{formatTimestamp(contact.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </>
    );
  }

  function renderSourcesPage() {
    if (opportunitiesAuthStatus === "checking") {
      return (
        <section className="panel auth-panel">
          <p className="empty-state">Checking source access...</p>
        </section>
      );
    }

    if (opportunitiesAuthStatus === "unauthenticated") {
      return renderProtectedAuthPanel({
        eyebrow: "Account Access",
        title: "Protected source registry",
        subcopy: "Sign in with your username or email, or accept an invite code to review source automation coverage.",
      });
    }

    const automatedSourceCount = trackedSources.filter((source) => source.load_scope === "opportunities").length;
    const probeOnlySourceCount = trackedSources.filter((source) => source.load_scope !== "opportunities").length;
    const loadedSourceCount = trackedSources.filter((source) => source.latest_run_status === "completed").length;
    const needsReviewCount = trackedSources.filter(
      (source) => source.latest_run_status === "manual_review" || source.latest_run_status === "cataloged",
    ).length;
    const blockedSourceCount = trackedSources.filter(
      (source) => source.latest_run_status === "blocked" || source.latest_run_status === "failed",
    ).length;

    return (
      <>
        <section className="panel">
          <div className="panel-heading contract-toolbar">
            <div>
              <p className="eyebrow">Source Registry</p>
              <h2>All eProcurement sources and their automation paths</h2>
            </div>
            <div className="action-row">
              {isAdminUser ? (
                <button
                  type="button"
                  onClick={() => void handleTrackedSourceRefresh()}
                  disabled={refreshingTrackedSources}
                >
                  {refreshingTrackedSources ? "Refreshing..." : "Refresh tracked sites"}
                </button>
              ) : null}
            </div>
          </div>

          <p className="panel-subcopy">
            This page is the coverage map for the opportunities funnel. It shows every automated procurement source,
            what the job does for that source, and which portals still need a deeper integration before they can load opportunities.
            The `Refresh tracked sites` action probes the local municipal, county, and regional portals; core feeds like ESBD,
            federal forecast, Grants.gov, and SBA SUBNet still refresh through their source-specific jobs.
          </p>

          <div className="metric-row">
            <div className="metric-pill">
              <strong>{trackedSources.length}</strong>
              <span>sources tracked</span>
            </div>
            <div className="metric-pill">
              <strong>{automatedSourceCount}</strong>
              <span>automation-backed</span>
            </div>
            <div className="metric-pill">
              <strong>{probeOnlySourceCount}</strong>
              <span>probe only</span>
            </div>
            <div className="metric-pill">
              <strong>{loadedSourceCount}</strong>
              <span>currently loaded</span>
            </div>
            <div className="metric-pill">
              <strong>{needsReviewCount}</strong>
              <span>need review</span>
            </div>
            <div className="metric-pill">
              <strong>{blockedSourceCount}</strong>
              <span>blocked or failed</span>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Registry</p>
              <h2>Source-by-source automation detail</h2>
            </div>
            <span>{trackedSources.length} listed</span>
          </div>
          <div className="table-shell">
            <table className="sources-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Coverage</th>
                  <th>Automation</th>
                  <th>Status</th>
                  <th>Last Check</th>
                </tr>
              </thead>
              <tbody>
                {trackedSources.map((trackedSource) => (
                  <tr key={trackedSource.id}>
                    <td>
                      <strong>{trackedSource.label}</strong>
                      <span>{trackedSource.platform_name}</span>
                      <a href={trackedSource.listing_url} target="_blank" rel="noreferrer">
                        Open source
                      </a>
                    </td>
                    <td>
                      <strong>{formatTrackedSourceJurisdiction(trackedSource.jurisdiction_type)}</strong>
                      <span>{formatTrackedSourceMode(trackedSource.extraction_mode)}</span>
                      <span>{formatTrackedSourceLoadScope(trackedSource.load_scope)}</span>
                    </td>
                    <td>
                      <strong>{trackedSource.automation_summary}</strong>
                      {trackedSource.automation_detail ? <span>{trackedSource.automation_detail}</span> : null}
                      {trackedSource.notes ? <span>{trackedSource.notes}</span> : null}
                    </td>
                    <td>
                      <span className={getTrackedSourceStatusBadgeClass(trackedSource.latest_run_status)}>
                        {formatTrackedSourceStatus(trackedSource.latest_run_status)}
                      </span>
                      <span>{trackedSource.stored_opportunity_count} stored</span>
                      {trackedSource.latest_total_records != null ? (
                        <span>
                          Last run: {trackedSource.latest_total_records} total / {trackedSource.latest_open_records ?? 0} open /{" "}
                          {trackedSource.latest_matched_records ?? 0} matched
                        </span>
                      ) : null}
                      {trackedSource.latest_run_error_message ? <span>{trackedSource.latest_run_error_message}</span> : null}
                    </td>
                    <td>
                      <strong>
                        {trackedSource.latest_run_completed_at
                          ? formatTimestamp(trackedSource.latest_run_completed_at)
                          : "Not checked yet"}
                      </strong>
                      <span>{trackedSource.cadence}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </>
    );
  }

  function renderOpportunitiesPage() {
    if (opportunitiesAuthStatus === "checking") {
      return (
        <section className="panel auth-panel">
          <p className="empty-state">Checking opportunity access...</p>
        </section>
      );
    }

    if (opportunitiesAuthStatus === "unauthenticated") {
      return renderProtectedAuthPanel({
        eyebrow: "Account Access",
        title: "Protected opportunities page",
        subcopy: "Sign in with your username or email, or accept an invite code to create a new login.",
      });
    }

    const allContracts = govContracts;
    const tagFilteredContracts = filterContractsByOpportunityTag(allContracts, selectedOpportunityTagFilter);
    const keywordFilteredContracts = filterContractsByOpportunityKeyword(tagFilteredContracts, opportunityKeywordFilter);
    const sourceScopedContracts = filterContractsByOpportunitySource(
      keywordFilteredContracts,
      selectedOpportunitySourceFilter,
    );
    const sourceContextScopedContracts = filterContractsByOpportunitySourceContext(
      sourceScopedContracts,
      selectedOpportunitySourceContextFilter,
    );
    const categoryCounts = {
      all: sourceContextScopedContracts.length,
      it_services: filterContractsByOpportunityCategory(sourceContextScopedContracts, "it_services").length,
      property_services: filterContractsByOpportunityCategory(sourceContextScopedContracts, "property_services").length,
      other: filterContractsByOpportunityCategory(sourceContextScopedContracts, "other").length,
    };
    const categoryScopedContracts = filterContractsByOpportunityCategory(
      sourceContextScopedContracts,
      opportunityCategoryTab,
    );
    const sourceCountBaseContracts = filterContractsByOpportunityCategory(
      keywordFilteredContracts,
      opportunityCategoryTab,
    );
    const sourceContextCountBaseContracts = filterContractsByOpportunityCategory(
      sourceScopedContracts,
      opportunityCategoryTab,
    );
    const uniqueSourceKeys = Array.from(new Set(allContracts.map((contract) => contract.source))).sort((left, right) =>
      formatContractSource(left).localeCompare(formatContractSource(right)),
    );
    const sourceFilters = [
      {
        key: "all",
        label: "All sources",
        count: sourceCountBaseContracts.length,
      },
      ...uniqueSourceKeys.map((sourceKey) => ({
        key: sourceKey,
        label: formatContractSource(sourceKey),
        count: sourceCountBaseContracts.filter((contract) => contract.source === sourceKey).length,
      })),
    ];
    const sourceContextFilters = [
      {
        key: "all",
        label: "All contexts",
        count: sourceContextCountBaseContracts.length,
      },
      ...Array.from(
        new Map(
          sourceContextCountBaseContracts
            .filter((contract) => contract.source_context && contract.source_context_label)
            .map((contract) => [contract.source_context as string, contract.source_context_label as string]),
        ),
      )
        .map(([key, label]) => ({
          key,
          label,
          count: sourceContextCountBaseContracts.filter((contract) => contract.source_context === key).length,
        }))
        .sort((left, right) => left.label.localeCompare(right.label)),
    ];
    const displayedContracts = sortContractsForDisplay(categoryScopedContracts);
    const hasVisibleContracts = displayedContracts.length > 0;
    const latestLoadedContractRun = contractRuns.find((run) => (run.total_records ?? 0) > 0) ?? contractRuns[0] ?? null;
    const loadedSourceCount = trackedSources.filter((source) => source.latest_run_status === "completed").length;
    const trackedReviewSources = trackedSources.filter(
      (source) => source.latest_run_status === "manual_review" || source.latest_run_status === "cataloged",
    ).length;
    const trackedBlockedSources = trackedSources.filter(
      (source) => source.latest_run_status === "blocked" || source.latest_run_status === "failed",
    ).length;

    return (
      <>
        <section className="panel">
          <div className="panel-heading contract-toolbar">
            <div>
              <p className="eyebrow">Government Work Finder</p>
              <h2>Federal, state, municipal, county, and regional opportunities for LeCrown</h2>
            </div>

            <div className="action-row">
              <button
                type="button"
                onClick={() => void handleFederalContractExport()}
                disabled={downloadingFederalExport}
              >
                {downloadingFederalExport ? "Downloading..." : "Download Federal CSV"}
              </button>
              <button
                type="button"
                onClick={() => void handleGrantsContractExport()}
                disabled={downloadingGrantsExport}
              >
                {downloadingGrantsExport ? "Downloading..." : "Download Grants CSV"}
              </button>
              <button type="button" onClick={() => void handleContractExport()} disabled={downloadingExport}>
                {downloadingExport ? "Downloading..." : "Download ESBD CSV"}
              </button>
              {isAdminUser ? (
                <>
                  <button
                    type="button"
                    onClick={() => void handleFederalContractRefresh()}
                    disabled={refreshingFederalContracts}
                  >
                    {refreshingFederalContracts ? "Refreshing..." : "Refresh Federal"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleGrantsContractRefresh()}
                    disabled={refreshingGrantsContracts}
                  >
                    {refreshingGrantsContracts ? "Refreshing..." : "Refresh Grants"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleSbaSubnetContractRefresh()}
                    disabled={refreshingSbaSubnetContracts}
                  >
                    {refreshingSbaSubnetContracts ? "Refreshing..." : "Refresh SBA SUBNet"}
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
                  <button
                    type="button"
                    onClick={() => void handleTrackedSourceRefresh()}
                    disabled={refreshingTrackedSources}
                  >
                    {refreshingTrackedSources ? "Refreshing..." : "Refresh tracked sites"}
                  </button>
                </>
              ) : null}
            </div>
          </div>

          <p className="panel-subcopy">
            {isAdminUser
              ? "Admin access can refresh sources, tune scoring, create invite-only accounts, and send fits to the CRM."
              : "This account has viewer access to browse, filter, and export opportunities. Source refreshes, scoring changes, and CRM funnel actions stay admin-only."}
          </p>

          {!contractCapabilities.gmail_rfq_sync_enabled ? (
            <p className="panel-subcopy">
              Gmail RFQ sync is not configured in this environment. Federal forecast, Grants.gov, SBA SUBNet, ESBD, and the tracked municipal procurement sites remain available.
            </p>
          ) : null}

          <div className="vendor-resource-grid">
            {METRO_VENDOR_RESOURCES.map((resource) => (
              <article className="vendor-resource-card" key={resource.title}>
                <div>
                  <p className="eyebrow">METRO Vendor Readiness</p>
                  <h3>{resource.title}</h3>
                  <p className="panel-subcopy">{resource.description}</p>
                </div>
                <div className="tag-row">
                  {resource.tags.map((tag) => (
                    <span className="tag" key={`${resource.title}-${tag}`}>
                      {tag}
                    </span>
                  ))}
                </div>
                <a className="secondary-link vendor-resource-link" href={resource.href} target="_blank" rel="noreferrer">
                  {resource.cta}
                </a>
              </article>
            ))}
          </div>

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
            <label className="keyword-search-field">
              <span>Keyword filter</span>
              <input
                value={opportunityKeywordFilter}
                onChange={(event) => setOpportunityKeywordFilter(event.target.value)}
                placeholder="AI, roofing, HUD, cybersecurity"
              />
            </label>
            {opportunityKeywordFilter.trim() ? (
              <button
                type="button"
                className="secondary-link tag-filter-clear-button"
                onClick={() => setOpportunityKeywordFilter("")}
              >
                Clear keyword
              </button>
            ) : null}
          </div>

          {latestLoadedContractRun ? (
            <div className="metric-row">
              <div className="metric-pill">
                <strong>{latestLoadedContractRun.total_records}</strong>
                <span>loaded</span>
              </div>
              <div className="metric-pill">
                <strong>{latestLoadedContractRun.matched_records}</strong>
                <span>matched</span>
              </div>
              <div className="metric-pill">
                <strong>{latestLoadedContractRun.open_records}</strong>
                <span>still open</span>
              </div>
              <div className="metric-pill">
                <strong>{loadedSourceCount}</strong>
                <span>sources loaded</span>
              </div>
              <div className="metric-pill">
                <strong>{trackedReviewSources + trackedBlockedSources}</strong>
                <span>need deeper dive</span>
              </div>
              <div className="metric-pill">
                <strong>{formatContractSource(latestLoadedContractRun.source)}</strong>
                <span>latest source</span>
              </div>
              <div className="metric-pill">
                <strong>
                  {latestLoadedContractRun.window_start} to {latestLoadedContractRun.window_end}
                </strong>
                <span>current window</span>
              </div>
            </div>
          ) : (
            <p className="empty-state">
              No opportunity sync has run yet. Refresh federal forecast, Grants.gov, SBA SUBNet, ESBD, Gmail RFQs, or the tracked municipal procurement sites to pull current opportunities.
            </p>
          )}

          <div className="opportunity-tab-row" role="tablist" aria-label="Opportunity category tabs">
            {OPPORTUNITY_CATEGORY_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={opportunityCategoryTab === tab.id}
                className={`opportunity-tab${opportunityCategoryTab === tab.id ? " opportunity-tab-active" : ""}`}
                onClick={() => setOpportunityCategoryTab(tab.id)}
              >
                <span>{tab.label}</span>
                <strong>{categoryCounts[tab.id]}</strong>
              </button>
            ))}
          </div>

          <div className="source-filter-row" role="tablist" aria-label="Opportunity source filters">
            {sourceFilters.map((sourceFilter) => {
              const isActive =
                sourceFilter.key === "all"
                  ? selectedOpportunitySourceFilter === null
                  : selectedOpportunitySourceFilter === sourceFilter.key;
              return (
                <button
                  key={sourceFilter.key}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  className={`source-filter-button${isActive ? " source-filter-button-active" : ""}`}
                  onClick={() => {
                    setSelectedOpportunitySourceFilter(sourceFilter.key === "all" ? null : sourceFilter.key);
                    setSelectedOpportunitySourceContextFilter(null);
                  }}
                >
                  <span>{sourceFilter.label}</span>
                  <strong>{sourceFilter.count}</strong>
                </button>
              );
            })}
          </div>

          {sourceContextFilters.length > 1 ? (
            <div className="source-filter-row" role="tablist" aria-label="Opportunity context filters">
              {sourceContextFilters.map((contextFilter) => {
                const isActive =
                  contextFilter.key === "all"
                    ? selectedOpportunitySourceContextFilter === null
                    : selectedOpportunitySourceContextFilter === contextFilter.key;
                return (
                  <button
                    key={contextFilter.key}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    className={`source-filter-button${isActive ? " source-filter-button-active" : ""}`}
                    onClick={() =>
                      setSelectedOpportunitySourceContextFilter(
                        contextFilter.key === "all" ? null : contextFilter.key,
                      )
                    }
                  >
                    <span>{contextFilter.label}</span>
                    <strong>{contextFilter.count}</strong>
                  </button>
                );
              })}
            </div>
          ) : null}

          {selectedOpportunitySourceFilter ? (
            <div className="active-tag-filter-row">
              <span className="panel-subcopy">Source:</span>
              <button
                type="button"
                className="tag filter-tag-button filter-tag-button-active"
                onClick={() => setSelectedOpportunitySourceFilter(null)}
              >
                {formatContractSource(selectedOpportunitySourceFilter)}
              </button>
              <button
                type="button"
                className="secondary-link tag-filter-clear-button"
                onClick={() => setSelectedOpportunitySourceFilter(null)}
              >
                Clear source
              </button>
            </div>
          ) : null}

          {selectedOpportunitySourceContextFilter ? (
            <div className="active-tag-filter-row">
              <span className="panel-subcopy">Context:</span>
              <button
                type="button"
                className="tag filter-tag-button filter-tag-button-active"
                onClick={() => setSelectedOpportunitySourceContextFilter(null)}
              >
                {formatContractSourceContextLabel(
                  sourceContextFilters.find(
                    (contextFilter) => contextFilter.key === selectedOpportunitySourceContextFilter,
                  )?.label ?? null,
                  selectedOpportunitySourceContextFilter,
                )}
              </button>
              <button
                type="button"
                className="secondary-link tag-filter-clear-button"
                onClick={() => setSelectedOpportunitySourceContextFilter(null)}
              >
                Clear context
              </button>
            </div>
          ) : null}

          {selectedOpportunityTagFilter ? (
            <div className="active-tag-filter-row">
              <span className="panel-subcopy">Filtering by tag:</span>
              <button
                type="button"
                className="tag filter-tag-button filter-tag-button-active"
                onClick={() => setSelectedOpportunityTagFilter(null)}
              >
                {selectedOpportunityTagFilter.label}
              </button>
              <button
                type="button"
                className="secondary-link tag-filter-clear-button"
                onClick={() => setSelectedOpportunityTagFilter(null)}
              >
                Clear tag filter
              </button>
            </div>
          ) : null}

          {opportunityKeywordFilter.trim() ? (
            <div className="active-tag-filter-row">
              <span className="panel-subcopy">Filtering by keyword:</span>
              <button
                type="button"
                className="tag filter-tag-button filter-tag-button-active"
                onClick={() => setOpportunityKeywordFilter("")}
              >
                {opportunityKeywordFilter.trim()}
              </button>
              <button
                type="button"
                className="secondary-link tag-filter-clear-button"
                onClick={() => setOpportunityKeywordFilter("")}
              >
                Clear keyword
              </button>
            </div>
          ) : null}

          <p className="panel-subcopy opportunity-tab-copy">
            Tabs group opportunities by matched keywords, title, and scope text so you can jump between IT services,
            real estate / property work, and everything else while keeping all sources merged into one ranked list.
          </p>
        </section>

        {isAdminUser ? (
          <>
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

              <div className="keyword-rule-stack keyword-rule-chip-list">
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
                      <div className="keyword-rule-chip" key={preference.id}>
                        <div className="keyword-rule-chip-copy">
                          <strong title={preference.agency_name}>{preference.agency_name}</strong>
                          <span className="keyword-rule-chip-score">A{preference.weight}</span>
                        </div>
                        <div className="keyword-rule-chip-actions">
                          <button
                            type="button"
                            className="secondary-link chip-action-button"
                            onClick={() => startEditingAgency(preference)}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="secondary-link destructive-button chip-action-button"
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
                Add, edit, or remove the keyword rules that score the stored federal, state, municipal, county,
                regional, and Gmail opportunity feeds. Changes rescore the stored list immediately.
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

              <div className="keyword-rule-stack keyword-rule-chip-list">
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
                      <div className="keyword-rule-chip" key={rule.id}>
                        <div className="keyword-rule-chip-copy">
                          <strong title={rule.phrase}>{rule.phrase}</strong>
                          <span className="keyword-rule-chip-score">+{rule.weight}</span>
                        </div>
                        <div className="keyword-rule-chip-actions">
                          <button
                            type="button"
                            className="secondary-link chip-action-button"
                            onClick={() => startEditingKeyword(rule)}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="secondary-link destructive-button chip-action-button"
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
          </>
        ) : null}

        {!hasVisibleContracts ? (
          <section className="panel">
            <p className="empty-state">
              {buildOpportunityEmptyStateMessage(
                opportunityCategoryTab,
                selectedOpportunitySourceFilter,
                selectedOpportunitySourceContextFilter,
                selectedOpportunityTagFilter,
                opportunityKeywordFilter,
              )}
            </p>
          </section>
        ) : (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Combined Feed</p>
                <h2>Consolidated opportunities</h2>
              </div>
              <span>{displayedContracts.length} shown</span>
            </div>
            <p className="panel-subcopy combined-feed-copy">
              All loaded sources are consolidated here. Use the source, category, tag, and keyword filters above to
              narrow the list without switching panels.
            </p>
            <div className="stack">{displayedContracts.map(renderContractCard)}</div>
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
          className={`nav-pill${view === "intake" ? " nav-pill-active" : ""}`}
          onClick={() => navigateToView("intake")}
        >
          Marketing Intake
        </button>
        <button
          type="button"
          className={`nav-pill${view === "opportunities" ? " nav-pill-active" : ""}`}
          onClick={() => navigateToView("opportunities")}
        >
          Opportunities
        </button>
        <button
          type="button"
          className={`nav-pill${view === "sources" ? " nav-pill-active" : ""}`}
          onClick={() => navigateToView("sources")}
        >
          Sources
        </button>
        <button
          type="button"
          className={`nav-pill${view === "billing" ? " nav-pill-active" : ""}`}
          onClick={() => navigateToView("billing")}
        >
          Billing
        </button>
        <button
          type="button"
          className={`nav-pill${view === "profile" ? " nav-pill-active" : ""}`}
          onClick={() => navigateToView("profile")}
        >
          Profile
        </button>
      </nav>

      <section className="hero-card">
        <div>
          <p className="eyebrow">LeCrown Platform</p>
          <h1>
            {view === "dashboard"
              ? "Multi-tenant content and inquiry control room"
              : view === "intake"
              ? "Marketing intake and CRM funnel"
              : view === "sources"
              ? "eProcurement source automation registry"
              : view === "billing"
                ? "Protected invoice creation and Gmail draft workflow"
              : view === "profile"
                ? "Profile, password, and invite-only access"
                : "Opportunity list and lead-funnel review"}
          </h1>
          <p className="hero-copy">
            {view === "dashboard"
              ? "One backend, two business surfaces. Switch tenants, create content, and push live when the publishing path is ready."
              : view === "intake"
              ? "Inspect intake health across connected sites, confirm CRM delivery is wired, and review the newest contacts entering the funnel."
              : view === "sources"
              ? "Review every procurement source feeding the funnel, see what automation is active for each one, and identify which portals still need a deeper integration."
              : view === "billing"
                ? "Prepare LeCrown invoices, generate the exact platform PDF on the backend, and create a Gmail draft with the PDF attached without leaving the admin surface."
              : view === "profile"
                ? "Manage your login inside the app. Admins can invite new users and keep access locked down to invited accounts only."
                : "Review matched federal forecast opportunities, Grants.gov opportunities, SBA SUBNet subcontracting opportunities, ESBD opportunities, and Gmail RFQs, then push strong fits into the CRM lead funnel."}
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
              {opportunitiesAuthStatus === "authenticated"
                ? currentAdmin?.is_admin
                  ? "Admin signed in"
                  : "Member signed in"
                : "Invite-only access"}
            </span>
            {currentAdmin ? (
              <div className="hero-account-copy">
                <strong>{currentAdmin.username}</strong>
                <span>{currentAdmin.email}</span>
              </div>
            ) : null}
            {opportunitiesAuthStatus === "authenticated" ? (
              <button type="button" className="secondary-link" onClick={handleLogout}>
                Log out
              </button>
            ) : null}
          </div>
        )}
      </section>

      {message ? <div className="message-banner">{message}</div> : null}

      {view === "dashboard"
        ? renderDashboard()
        : view === "intake"
          ? renderIntakePage()
          : view === "sources"
            ? renderSourcesPage()
          : view === "billing"
            ? renderBillingPage()
          : view === "profile"
            ? renderProfilePage()
            : renderOpportunitiesPage()}
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

function buildInviteCreateMessage(invite: UserInviteCreateResponse): string {
  const parts = [invite.reissued_existing ? "Invite refreshed." : "Invite created."];
  if (invite.email_delivery_status === "sent") {
    parts.push(`Email sent to ${invite.email}.`);
    return parts.join(" ");
  }
  if (invite.email_delivery_detail) {
    parts.push(invite.email_delivery_detail);
    return parts.join(" ");
  }
  parts.push("Copy the invite code manually.");
  return parts.join(" ");
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

function formatIntakeConnectionStatus(status: string): string {
  if (status === "configured") {
    return "Configured";
  }
  if (status === "protected") {
    return "Protected";
  }
  if (status === "attention") {
    return "Needs attention";
  }
  if (status === "open") {
    return "Open";
  }
  return status;
}

function formatIntakeDeliveryStatus(status: string): string {
  if (status === "delivered") {
    return "Delivered";
  }
  if (status === "failed") {
    return "Failed";
  }
  if (status === "pending") {
    return "Pending";
  }
  if (status === "processed") {
    return "Processed";
  }
  return status;
}

function formatIntakeSourceType(sourceType: string): string {
  return sourceType
    .split(/[_-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function getIntakeStatusBadgeClass(status: string): string {
  if (status === "configured" || status === "delivered" || status === "processed") {
    return "status-badge status-badge-good";
  }
  if (status === "protected" || status === "pending" || status === "open") {
    return "status-badge status-badge-warn";
  }
  if (status === "attention" || status === "failed") {
    return "status-badge status-badge-bad";
  }
  return "status-badge status-badge-neutral";
}

function formatNigpPreview(value: string): string {
  return value
    .replace(/\s+/g, " ")
    .split(/[;|]/)
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
  if (source === "federal_forecast") {
    return "Federal Forecast";
  }
  if (source === "grants_gov") {
    return "Grants.gov";
  }
  if (source === "sba_subnet") {
    return "SBA SUBNet";
  }
  if (source === "txsmartbuy_esbd") {
    return "Texas ESBD";
  }
  if (source === "city_austin_afo") {
    return "City of Austin";
  }
  if (source === "city_san_antonio_bids") {
    return "City of San Antonio";
  }
  if (source === "city_fort_worth_bonfire") {
    return "City of Fort Worth";
  }
  if (source === "city_el_paso_ionwave") {
    return "City of El Paso";
  }
  if (source === "harris_county_bonfire") {
    return "Harris County";
  }
  if (source === "travis_county_bidnet") {
    return "Travis County";
  }
  if (source === "tarrant_county_ionwave") {
    return "Tarrant County";
  }
  if (source === "collin_county_ionwave") {
    return "Collin County";
  }
  if (source === "dallas_county_official") {
    return "Dallas County";
  }
  if (source === "dallas_county_bidnet") {
    return "Dallas County BidNet";
  }
  if (source === "capmetro_planetbids") {
    return "CapMetro";
  }
  if (source === "houston_metro_procurement") {
    return "Houston METRO";
  }
  if (source === "dart_procurement") {
    return "DART";
  }
  if (source === "h_gac_procurement") {
    return "H-GAC";
  }
  return source.split("_").join(" ");
}

function formatContractSourceContextLabel(
  label?: string | null,
  fallbackContext?: string | null,
): string {
  if (label) {
    return label;
  }
  if (!fallbackContext) {
    return "Unknown context";
  }
  return fallbackContext.split("_").join(" ");
}

function formatTrackedSourceJurisdiction(value: string): string {
  if (value === "federal") {
    return "Federal";
  }
  if (value === "state") {
    return "State";
  }
  if (value === "city") {
    return "City";
  }
  if (value === "county") {
    return "County";
  }
  if (value === "regional") {
    return "Regional";
  }
  return value;
}

function formatTrackedSourceMode(value: string): string {
  if (value === "csv_export_api") {
    return "CSV export API";
  }
  if (value === "csv_export") {
    return "CSV export";
  }
  if (value === "json_api") {
    return "JSON API";
  }
  if (value === "paginated_html") {
    return "Paginated HTML";
  }
  if (value === "html_table") {
    return "HTML table";
  }
  if (value === "html_cards") {
    return "HTML cards";
  }
  if (value === "browser_required") {
    return "Browser required";
  }
  if (value === "anti_bot_blocked") {
    return "Anti-bot blocked";
  }
  if (value === "iframe_embed") {
    return "Iframe embed";
  }
  if (value === "manual_review") {
    return "Manual review";
  }
  return value.split("_").join(" ");
}

function formatTrackedSourceLoadScope(value: string): string {
  if (value === "opportunities") {
    return "Loads opportunities";
  }
  if (value === "catalog_only") {
    return "Catalog and status only";
  }
  return value.split("_").join(" ");
}

function formatTrackedSourceStatus(status?: string | null): string {
  if (!status) {
    return "Not checked";
  }
  if (status === "completed") {
    return "Loaded";
  }
  if (status === "cataloged") {
    return "Cataloged";
  }
  if (status === "manual_review") {
    return "Needs review";
  }
  if (status === "blocked") {
    return "Blocked";
  }
  if (status === "failed") {
    return "Failed";
  }
  return status.split("_").join(" ");
}

function getTrackedSourceStatusBadgeClass(status?: string | null): string {
  if (status === "completed") {
    return "status-badge status-badge-good";
  }
  if (status === "cataloged" || status === "manual_review") {
    return "status-badge status-badge-warn";
  }
  if (status === "blocked" || status === "failed") {
    return "status-badge status-badge-bad";
  }
  return "status-badge status-badge-neutral";
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

function formatInviteStatus(invite: UserInvite): string {
  if (invite.revoked_at) {
    return "revoked";
  }
  if (invite.accepted_at) {
    return "accepted";
  }
  const expiresAt = new Date(invite.expires_at);
  if (!Number.isNaN(expiresAt.getTime()) && expiresAt.getTime() < Date.now()) {
    return "expired";
  }
  return "pending";
}

function normalizeOpportunityCategoryText(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  return value.replace(/[^a-z0-9]+/gi, " ").trim().toLowerCase();
}

function normalizeOpportunityTagFilterValue(value: string): string {
  return normalizeOpportunityCategoryText(value);
}

function buildOpportunityKeywordTerms(value: string): string[] {
  return normalizeOpportunityCategoryText(value)
    .split(" ")
    .map((term) => term.trim())
    .filter(Boolean);
}

function isOpportunityTagFilterActive(
  currentFilter: OpportunityTagFilter | null,
  candidate: OpportunityTagFilter,
): boolean {
  return (
    currentFilter?.kind === candidate.kind &&
    normalizeOpportunityTagFilterValue(currentFilter.value) === normalizeOpportunityTagFilterValue(candidate.value)
  );
}

function getOpportunityCategories(contract: GovContractOpportunity): OpportunityCategoryTab[] {
  const opportunityCategories = contract.opportunity_categories ?? [];
  if (opportunityCategories.length > 0) {
    return opportunityCategories.filter(
      (category): category is OpportunityCategoryTab =>
        category === "it_services" || category === "property_services" || category === "other",
    );
  }
  return ["other"];
}

function getOpportunityDisplayTags(contract: GovContractOpportunity): string[] {
  const autoTags = contract.auto_tags ?? [];
  const tags = new Set<string>();

  for (const value of [...autoTags, ...contract.matched_keywords]) {
    const normalizedValue = normalizeOpportunityTagFilterValue(value);
    if (!normalizedValue || tags.has(normalizedValue)) {
      continue;
    }
    tags.add(normalizedValue);
  }

  return [...tags].map((normalizedTag) => {
    const exactAutoTag = autoTags.find((tag) => normalizeOpportunityTagFilterValue(tag) === normalizedTag);
    if (exactAutoTag) {
      return exactAutoTag;
    }
    return (
      contract.matched_keywords.find((keyword) => normalizeOpportunityTagFilterValue(keyword) === normalizedTag) ??
      normalizedTag
    );
  });
}

function matchesOpportunityCategoryTab(
  contract: GovContractOpportunity,
  tab: OpportunityCategoryTab,
): boolean {
  if (tab === "all") {
    return true;
  }
  return getOpportunityCategories(contract).includes(tab);
}

function filterContractsByOpportunityCategory(
  contracts: GovContractOpportunity[],
  tab: OpportunityCategoryTab,
): GovContractOpportunity[] {
  return contracts.filter((contract) => matchesOpportunityCategoryTab(contract, tab));
}

function matchesOpportunityTagFilter(
  contract: GovContractOpportunity,
  filter: OpportunityTagFilter | null,
): boolean {
  if (!filter) {
    return true;
  }

  const normalizedValue = normalizeOpportunityTagFilterValue(filter.value);
  if (!normalizedValue) {
    return true;
  }

  if (filter.kind === "source") {
    return normalizeOpportunityTagFilterValue(contract.source) === normalizedValue;
  }
  if (filter.kind === "tag") {
    return getOpportunityDisplayTags(contract).some(
      (tag) => normalizeOpportunityTagFilterValue(tag) === normalizedValue,
    );
  }
  return getMatchedAgencyPreferences(contract).some(
    (agencyName) => normalizeOpportunityTagFilterValue(agencyName) === normalizedValue,
  );
}

function filterContractsByOpportunityTag(
  contracts: GovContractOpportunity[],
  filter: OpportunityTagFilter | null,
): GovContractOpportunity[] {
  return contracts.filter((contract) => matchesOpportunityTagFilter(contract, filter));
}

function matchesOpportunitySourceFilter(
  contract: GovContractOpportunity,
  sourceFilter: string | null,
): boolean {
  if (!sourceFilter) {
    return true;
  }
  return contract.source === sourceFilter;
}

function filterContractsByOpportunitySource(
  contracts: GovContractOpportunity[],
  sourceFilter: string | null,
): GovContractOpportunity[] {
  return contracts.filter((contract) => matchesOpportunitySourceFilter(contract, sourceFilter));
}

function matchesOpportunitySourceContextFilter(
  contract: GovContractOpportunity,
  sourceContextFilter: string | null,
): boolean {
  if (!sourceContextFilter) {
    return true;
  }
  return contract.source_context === sourceContextFilter;
}

function filterContractsByOpportunitySourceContext(
  contracts: GovContractOpportunity[],
  sourceContextFilter: string | null,
): GovContractOpportunity[] {
  return contracts.filter((contract) =>
    matchesOpportunitySourceContextFilter(contract, sourceContextFilter),
  );
}

function matchesOpportunityKeywordFilter(
  contract: GovContractOpportunity,
  keywordFilter: string,
): boolean {
  const filterTerms = buildOpportunityKeywordTerms(keywordFilter);
  if (filterTerms.length === 0) {
    return true;
  }

  const haystackWords = normalizeOpportunityCategoryText(
    [
      contract.title,
      contract.agency_name,
      contract.agency_number,
      contract.solicitation_id,
      contract.nigp_codes,
      formatContractSource(contract.source),
      contract.source_context_label,
      ...getOpportunityDisplayTags(contract),
      ...getMatchedAgencyPreferences(contract),
    ]
      .filter(Boolean)
      .join(" "),
  )
    .split(" ")
    .filter(Boolean);

  return filterTerms.every((term) =>
    haystackWords.some((word) => word === term || (term.length >= 4 && word.startsWith(term))),
  );
}

function filterContractsByOpportunityKeyword(
  contracts: GovContractOpportunity[],
  keywordFilter: string,
): GovContractOpportunity[] {
  return contracts.filter((contract) => matchesOpportunityKeywordFilter(contract, keywordFilter));
}

function parseOpportunityTimestamp(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function sortContractsForDisplay(contracts: GovContractOpportunity[]): GovContractOpportunity[] {
  return [...contracts].sort((left, right) => {
    if (right.priority_score !== left.priority_score) {
      return right.priority_score - left.priority_score;
    }
    if (right.score !== left.score) {
      return right.score - left.score;
    }
    return parseOpportunityTimestamp(right.last_seen_at) - parseOpportunityTimestamp(left.last_seen_at);
  });
}

function formatOpportunityCategoryTabLabel(tab: OpportunityCategoryTab): string {
  if (tab === "all") {
    return "All opportunities";
  }
  if (tab === "it_services") {
    return "IT services";
  }
  if (tab === "property_services") {
    return "Real estate / property";
  }
  return "Other opportunities";
}

function getOpportunityCategoryEmptyState(
  defaultMessage: string,
  sourceLabel: string,
  tab: OpportunityCategoryTab,
  sourceFilter: string | null,
  sourceContextFilter: string | null,
  tagFilter: OpportunityTagFilter | null,
  keywordFilter: string,
): string {
  const normalizedKeywordFilter = keywordFilter.trim();
  if (tab === "all" && !sourceFilter && !sourceContextFilter && !tagFilter && !normalizedKeywordFilter) {
    return defaultMessage;
  }
  const pieces = [`No ${sourceLabel.toLowerCase()} opportunities match`];
  if (tab !== "all") {
    pieces.push(`the ${formatOpportunityCategoryTabLabel(tab).toLowerCase()} tab`);
  }
  if (sourceFilter) {
    pieces.push(
      tab === "all"
        ? `the ${formatContractSource(sourceFilter).toLowerCase()} source`
        : `and the ${formatContractSource(sourceFilter).toLowerCase()} source`,
    );
  }
  if (sourceContextFilter) {
    pieces.push(
      tab === "all" && !sourceFilter
        ? `the ${formatContractSourceContextLabel(null, sourceContextFilter).toLowerCase()} context`
        : `and the ${formatContractSourceContextLabel(null, sourceContextFilter).toLowerCase()} context`,
    );
  }
  if (tagFilter) {
    pieces.push(
      tab === "all" && !sourceFilter && !sourceContextFilter
        ? `the "${tagFilter.label}" tag`
        : `and the "${tagFilter.label}" tag`,
    );
  }
  if (normalizedKeywordFilter) {
    pieces.push(
      tab === "all" && !sourceFilter && !sourceContextFilter && !tagFilter
        ? `the keyword "${normalizedKeywordFilter}"`
        : `and the keyword "${normalizedKeywordFilter}"`,
    );
  }
  return `${pieces.join(" ")}.`;
}

function buildOpportunityEmptyStateMessage(
  tab: OpportunityCategoryTab,
  sourceFilter: string | null,
  sourceContextFilter: string | null,
  tagFilter: OpportunityTagFilter | null,
  keywordFilter: string,
): string {
  const normalizedKeywordFilter = keywordFilter.trim();
  if (tab === "all" && !sourceFilter && !sourceContextFilter && !tagFilter && !normalizedKeywordFilter) {
    return "No opportunities match the current view filters.";
  }

  const pieces = ["No opportunities match"];
  if (tab !== "all") {
    pieces.push(`the ${formatOpportunityCategoryTabLabel(tab).toLowerCase()} tab`);
  }
  if (sourceFilter) {
    pieces.push(
      tab === "all"
        ? `the ${formatContractSource(sourceFilter).toLowerCase()} source`
        : `and the ${formatContractSource(sourceFilter).toLowerCase()} source`,
    );
  }
  if (sourceContextFilter) {
    pieces.push(
      tab === "all" && !sourceFilter
        ? `the ${formatContractSourceContextLabel(null, sourceContextFilter).toLowerCase()} context`
        : `and the ${formatContractSourceContextLabel(null, sourceContextFilter).toLowerCase()} context`,
    );
  }
  if (tagFilter) {
    pieces.push(
      tab === "all" && !sourceFilter && !sourceContextFilter
        ? `the "${tagFilter.label}" tag`
        : `and the "${tagFilter.label}" tag`,
    );
  }
  if (normalizedKeywordFilter) {
    pieces.push(
      tab === "all" && !sourceFilter && !sourceContextFilter && !tagFilter
        ? `the keyword "${normalizedKeywordFilter}"`
        : `and the keyword "${normalizedKeywordFilter}"`,
    );
  }
  return `${pieces.join(" ")}.`;
}
