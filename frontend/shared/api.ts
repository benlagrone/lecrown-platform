import type {
  Content,
  ContentCreate,
  DistributionChannel,
  DistributionResponse,
  Inquiry,
  LoginRequest,
  TokenResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
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
