export type Tenant = "development" | "properties";
export type DistributionChannel = "linkedin" | "youtube" | "twitter" | "website";

export interface DistributionConfig {
  linkedin: boolean;
  youtube: boolean;
  website: boolean;
  twitter: boolean;
}

export interface MediaConfig {
  video_generated: boolean;
  video_path?: string | null;
  video_url?: string | null;
  render_status?: string | null;
  render_job_id?: string | null;
  youtube_video_id?: string | null;
  youtube_status?: string | null;
}

export interface Content {
  id: string;
  tenant: Tenant;
  type: string;
  title: string;
  body: string;
  tags: string[];
  distribution: DistributionConfig;
  media: MediaConfig;
  publish_linkedin: boolean;
  publish_site: boolean;
  linkedin_post_id?: string | null;
  linkedin_status?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContentCreate {
  tenant: Tenant;
  type: string;
  title: string;
  body: string;
  tags: string[];
  distribution: DistributionConfig;
  media: MediaConfig;
  publish_linkedin: boolean;
  publish_site: boolean;
}

export interface Inquiry {
  id: string;
  tenant: "properties";
  asset_type: string;
  location: string;
  problem: string;
  contact_name: string;
  email: string;
  phone: string;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface DistributionResponse {
  content_id: string;
  results: Record<string, { status?: string; detail?: string; video_id?: string }>;
}
