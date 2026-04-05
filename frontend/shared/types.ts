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

export interface GovContractOpportunity {
  id: string;
  source: string;
  source_key: string;
  source_url: string;
  title: string;
  solicitation_id: string;
  agency_name?: string | null;
  agency_number?: string | null;
  status_code?: string | null;
  status_name?: string | null;
  due_date?: string | null;
  due_time?: string | null;
  posting_date?: string | null;
  source_created_at?: string | null;
  source_last_modified_at?: string | null;
  nigp_codes?: string | null;
  score: number;
  priority_score: number;
  fit_bucket: "high" | "medium" | "low" | "none";
  is_match: boolean;
  is_open: boolean;
  matched_keywords: string[];
  score_breakdown?: Record<string, unknown> | null;
  funnel_status: string;
  funnel_submission_id?: string | null;
  funnel_delivery_target?: string | null;
  funnel_delivery_status?: string | null;
  funnel_record_id?: string | null;
  funnel_payload?: Record<string, unknown> | null;
  funnel_response?: Record<string, unknown> | null;
  funneled_at?: string | null;
  first_seen_at: string;
  last_seen_at: string;
  created_at: string;
  updated_at: string;
}

export interface GovContractImportRun {
  id: string;
  source: string;
  status: string;
  window_start: string;
  window_end: string;
  source_total_records: number;
  total_records: number;
  matched_records: number;
  open_records: number;
  csv_bytes: number;
  error_message?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface GovContractCapabilities {
  gmail_rfq_sync_enabled: boolean;
  gmail_rfq_feed_label?: string | null;
}

export interface GovContractKeywordRule {
  id: string;
  phrase: string;
  weight: number;
  created_at: string;
  updated_at: string;
}

export interface GovContractAgencyPreference {
  id: string;
  agency_name: string;
  weight: number;
  created_at: string;
  updated_at: string;
}
