import type {
  AuthUser,
  ChangePasswordRequest,
  Content,
  ContentCreate,
  DistributionChannel,
  DistributionResponse,
  GovContractAgencyPreference,
  GovContractCapabilities,
  GovContractImportRun,
  GovContractKeywordRule,
  GovContractOpportunity,
  InvoiceDefaults,
  InvoiceDraftResult,
  InvoiceRenderRequest,
  IntakeDashboard,
  Inquiry,
  LoginRequest,
  TokenResponse,
  UserInvite,
  UserInviteCreateResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const AUTH_TOKEN_KEY = "lecrown_admin_token";

function getStoredAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

function buildHeaders(init?: RequestInit): HeadersInit {
  const token = getStoredAuthToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(init?.headers ?? {}),
  };
}

function resolveApiUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(resolveApiUrl(path), {
    ...init,
    headers: buildHeaders(init),
  });

  if (!response.ok) {
    const body = await response.text();
    if (body) {
      let detail: string | undefined;
      try {
        const parsed = JSON.parse(body) as { detail?: string };
        detail = parsed.detail;
      } catch {}
      if (detail) {
        throw new Error(detail);
      }
      throw new Error(body);
    }
    throw new Error(`Request failed with ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function ensureOkResponse(response: Response): Promise<void> {
  if (response.ok) {
    return;
  }

  const body = await response.text();
  if (body) {
    let detail: string | undefined;
    try {
      const parsed = JSON.parse(body) as { detail?: string };
      detail = parsed.detail;
    } catch {}
    if (detail) {
      throw new Error(detail);
    }
    throw new Error(body);
  }
  throw new Error(`Request failed with ${response.status}`);
}

function getDownloadFilename(response: Response, fallbackFilename: string): string {
  const disposition = response.headers.get("Content-Disposition");
  if (!disposition) {
    return fallbackFilename;
  }

  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }

  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] ?? fallbackFilename;
}

async function downloadResponse(response: Response, fallbackFilename: string): Promise<void> {
  await ensureOkResponse(response);
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = getDownloadFilename(response, fallbackFilename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export function storeAuthToken(token: string): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(AUTH_TOKEN_KEY, token);
  }
}

export function clearAuthToken(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(AUTH_TOKEN_KEY);
  }
}

export function hasStoredAuthToken(): boolean {
  return Boolean(getStoredAuthToken());
}

export async function createContent(payload: ContentCreate): Promise<Content> {
  return request<Content>("/content/create", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listContent(tenant: Content["tenant"]): Promise<Content[]> {
  const query = new URLSearchParams({ tenant });
  return request<Content[]>(`/content/list?${query.toString()}`);
}

export async function listInquiries(): Promise<Inquiry[]> {
  return request<Inquiry[]>("/inquiry/list");
}

export async function getIntakeDashboard(sourceLimit = 12, recentLimit = 12): Promise<IntakeDashboard> {
  const query = new URLSearchParams({
    source_limit: String(sourceLimit),
    recent_limit: String(recentLimit),
  });
  return request<IntakeDashboard>(`/intake/dashboard?${query.toString()}`);
}

export async function listGovContracts(
  limit = 12,
  source?: string,
  options?: { matchesOnly?: boolean; openOnly?: boolean; minPriorityScore?: number },
): Promise<GovContractOpportunity[]> {
  const query = new URLSearchParams({
    limit: String(limit),
    matches_only: String(options?.matchesOnly ?? true),
    open_only: String(options?.openOnly ?? true),
    min_priority_score: String(options?.minPriorityScore ?? 0),
  });
  if (source) {
    query.set("source", source);
  }
  return request<GovContractOpportunity[]>(`/contracts/list?${query.toString()}`);
}

export async function listGovContractRuns(limit = 5): Promise<GovContractImportRun[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  return request<GovContractImportRun[]>(`/contracts/runs?${query.toString()}`);
}

export async function getGovContractCapabilities(): Promise<GovContractCapabilities> {
  return request<GovContractCapabilities>("/contracts/capabilities");
}

export async function listGovContractKeywordRules(): Promise<GovContractKeywordRule[]> {
  return request<GovContractKeywordRule[]>("/contracts/keywords");
}

export async function listGovContractAgencyPreferences(): Promise<GovContractAgencyPreference[]> {
  return request<GovContractAgencyPreference[]>("/contracts/agency-preferences");
}

export async function createGovContractAgencyPreference(payload: {
  agency_name: string;
  weight: number;
}): Promise<GovContractAgencyPreference> {
  return request<GovContractAgencyPreference>("/contracts/agency-preferences", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateGovContractAgencyPreference(
  agencyPreferenceId: string,
  payload: { agency_name: string; weight: number },
): Promise<GovContractAgencyPreference> {
  return request<GovContractAgencyPreference>(`/contracts/agency-preferences/${agencyPreferenceId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteGovContractAgencyPreference(agencyPreferenceId: string): Promise<void> {
  return request<void>(`/contracts/agency-preferences/${agencyPreferenceId}`, {
    method: "DELETE",
  });
}

export async function createGovContractKeywordRule(payload: {
  phrase: string;
  weight: number;
}): Promise<GovContractKeywordRule> {
  return request<GovContractKeywordRule>("/contracts/keywords", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateGovContractKeywordRule(
  keywordRuleId: string,
  payload: { phrase: string; weight: number },
): Promise<GovContractKeywordRule> {
  return request<GovContractKeywordRule>(`/contracts/keywords/${keywordRuleId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteGovContractKeywordRule(keywordRuleId: string): Promise<void> {
  return request<void>(`/contracts/keywords/${keywordRuleId}`, {
    method: "DELETE",
  });
}

export async function refreshGovContracts(windowDays = 7): Promise<GovContractImportRun> {
  return request<GovContractImportRun>("/contracts/refresh", {
    method: "POST",
    body: JSON.stringify({ window_days: windowDays }),
  });
}

export async function refreshFederalContracts(): Promise<GovContractImportRun> {
  return request<GovContractImportRun>("/contracts/refresh-federal", {
    method: "POST",
  });
}

export async function refreshGrantsContracts(): Promise<GovContractImportRun> {
  return request<GovContractImportRun>("/contracts/refresh-grants", {
    method: "POST",
  });
}

export async function refreshSbaSubnetContracts(): Promise<GovContractImportRun> {
  return request<GovContractImportRun>("/contracts/refresh-sba-subnet", {
    method: "POST",
  });
}

export async function refreshGmailRfqs(limit = 50): Promise<GovContractImportRun> {
  const query = new URLSearchParams({ limit: String(limit) });
  return request<GovContractImportRun>(`/contracts/refresh-gmail?${query.toString()}`, {
    method: "POST",
  });
}

export async function funnelGovContract(
  contractId: string,
  payload?: { notes?: string; force?: boolean },
): Promise<GovContractOpportunity> {
  return request<GovContractOpportunity>(`/contracts/${contractId}/funnel`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function getGovContractsExportUrl(windowDays = 7): string {
  const query = new URLSearchParams({ window_days: String(windowDays) });
  return `${API_BASE_URL}/contracts/export.csv?${query.toString()}`;
}

export async function downloadGovContractsExport(windowDays = 7): Promise<void> {
  const query = new URLSearchParams({ window_days: String(windowDays) });
  const response = await fetch(`${API_BASE_URL}/contracts/export.csv?${query.toString()}`, {
    headers: buildHeaders(),
  });

  if (!response.ok) {
    const body = await response.text();
    if (body) {
      let detail: string | undefined;
      try {
        const parsed = JSON.parse(body) as { detail?: string };
        detail = parsed.detail;
      } catch {}
      if (detail) {
        throw new Error(detail);
      }
      throw new Error(body);
    }
    throw new Error(`Request failed with ${response.status}`);
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `txsmartbuy-esbd-${windowDays}-day-export.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function downloadFederalContractsExport(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/contracts/export-federal.csv`, {
    headers: buildHeaders(),
  });

  if (!response.ok) {
    const body = await response.text();
    if (body) {
      let detail: string | undefined;
      try {
        const parsed = JSON.parse(body) as { detail?: string };
        detail = parsed.detail;
      } catch {}
      if (detail) {
        throw new Error(detail);
      }
      throw new Error(body);
    }
    throw new Error(`Request failed with ${response.status}`);
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "federal-forecast-export.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function downloadGrantsContractsExport(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/contracts/export-grants.csv`, {
    headers: buildHeaders(),
  });

  if (!response.ok) {
    const body = await response.text();
    if (body) {
      let detail: string | undefined;
      try {
        const parsed = JSON.parse(body) as { detail?: string };
        detail = parsed.detail;
      } catch {}
      if (detail) {
        throw new Error(detail);
      }
      throw new Error(body);
    }
    throw new Error(`Request failed with ${response.status}`);
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "grants-gov-export.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function publishToLinkedIn(contentId: string): Promise<{ status: string; content_id: string }> {
  return request<{ status: string; content_id: string }>("/linkedin/publish", {
    method: "POST",
    body: JSON.stringify({ content_id: contentId }),
  });
}

export async function publishDistribution(
  contentId: string,
  channels: DistributionChannel[],
  youtubeVideoPath?: string,
): Promise<DistributionResponse> {
  return request<DistributionResponse>("/distribution/publish", {
    method: "POST",
    body: JSON.stringify({
      content_id: contentId,
      channels,
      youtube_video_path: youtubeVideoPath,
    }),
  });
}

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getCurrentAdmin(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}

export async function changePassword(payload: ChangePasswordRequest): Promise<AuthUser> {
  return request<AuthUser>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listUserInvites(): Promise<UserInvite[]> {
  return request<UserInvite[]>("/auth/invitations");
}

export async function createUserInvite(payload: { email: string }): Promise<UserInviteCreateResponse> {
  return request<UserInviteCreateResponse>("/auth/invitations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function revokeUserInvite(inviteId: string): Promise<void> {
  return request<void>(`/auth/invitations/${inviteId}`, {
    method: "DELETE",
  });
}

export async function acceptInvite(payload: {
  invite_code: string;
  username: string;
  password: string;
}): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/accept-invite", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getInvoiceDefaults(companyKey?: string): Promise<InvoiceDefaults> {
  const query = new URLSearchParams();
  if (companyKey) {
    query.set("company_key", companyKey);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<InvoiceDefaults>(`/invoice/defaults${suffix}`);
}

export async function downloadRenderedInvoice(payload: InvoiceRenderRequest): Promise<void> {
  const response = await fetch(resolveApiUrl("/invoice/render"), {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });
  await downloadResponse(response, "invoice.pdf");
}

export async function createInvoiceDraft(payload: InvoiceRenderRequest): Promise<InvoiceDraftResult> {
  return request<InvoiceDraftResult>("/invoice/draft", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function downloadGeneratedInvoice(downloadUrl: string, fallbackFilename: string): Promise<void> {
  const response = await fetch(resolveApiUrl(downloadUrl), {
    headers: buildHeaders(),
  });
  await downloadResponse(response, fallbackFilename);
}
