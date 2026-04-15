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

export interface IntakeDashboardOverview {
  observed_source_sites: number;
  total_submissions: number;
  new_contacts_today: number;
  new_contacts_7d: number;
  delivered_submissions: number;
  failed_submissions: number;
}

export interface IntakeDashboardConnection {
  key: string;
  label: string;
  status: string;
  detail: string;
  value?: string | null;
}

export interface IntakeDashboardSourceSite {
  source_site: string;
  source_type: string;
  business_contexts: string[];
  form_providers: string[];
  form_names: string[];
  total_submissions: number;
  delivered_submissions: number;
  failed_submissions: number;
  new_contacts_today: number;
  new_contacts_7d: number;
  last_submission_at: string;
  last_contact_name?: string | null;
  last_page_url?: string | null;
  last_delivery_status: string;
}

export interface IntakeDashboardRecentContact {
  id: string;
  source_site: string;
  contact_name?: string | null;
  email?: string | null;
  phone?: string | null;
  business_context?: string | null;
  product_context?: string | null;
  page_url?: string | null;
  campaign?: string | null;
  status: string;
  delivery_status: string;
  delivery_record_id?: string | null;
  created_at: string;
}

export interface IntakeDashboard {
  overview: IntakeDashboardOverview;
  connections: IntakeDashboardConnection[];
  source_sites: IntakeDashboardSourceSite[];
  recent_contacts: IntakeDashboardRecentContact[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface UserInvite {
  id: string;
  email: string;
  created_by_user_id: string;
  accepted_by_user_id?: string | null;
  expires_at: string;
  accepted_at?: string | null;
  revoked_at?: string | null;
  created_at: string;
}

export interface UserInviteCreateResponse extends UserInvite {
  invite_code: string;
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
  opportunity_categories: string[];
  auto_tags: string[];
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

export type InvoiceCompositionMode = "time_entry" | "custom";

export interface InvoiceLineItemInput {
  description: string;
  quantity?: number | null;
  unit_price?: number | null;
  amount?: number | null;
}

export interface InvoiceLineItem {
  description: string;
  quantity?: number | null;
  unit_price?: number | null;
  amount: number;
  subtotal_included: boolean;
}

export interface InvoiceCompanyOption {
  key: string;
  label: string;
  invoice_prefix: string;
  default_composition_mode: InvoiceCompositionMode;
  default_sender_mailbox: string;
}

export interface InvoiceSenderMailbox {
  email: string;
  label: string;
  draft_enabled: boolean;
}

export interface InvoiceDefaultsForm {
  company_key: string;
  company_name: string;
  invoice_prefix: string;
  default_composition_mode: InvoiceCompositionMode;
  sender_mailbox: string;
  recipient_email: string;
  cc_email?: string | null;
  bill_to_name: string;
  bill_to_phone?: string | null;
  bill_to_address: string;
  issue_date: string;
  due_date: string;
  memo: string;
  pay_online_label?: string | null;
  pay_online_url?: string | null;
  currency: string;
  hourly_rate: number;
  week_1_ending: string;
  week_1_hours: number;
  week_2_ending: string;
  week_2_hours: number;
  custom_line_items: InvoiceLineItem[];
}

export interface InvoiceDefaults {
  selected_company_key: string;
  companies: InvoiceCompanyOption[];
  sender_mailboxes: InvoiceSenderMailbox[];
  draft_creation_enabled: boolean;
  defaults: InvoiceDefaultsForm;
}

export interface InvoiceRenderRequest {
  company_key: string;
  sender_mailbox: string;
  recipient_email: string;
  cc_email?: string | null;
  bill_to_name: string;
  bill_to_phone?: string | null;
  bill_to_address: string;
  issue_date: string;
  due_date: string;
  memo: string;
  pay_online_label?: string | null;
  pay_online_url?: string | null;
  invoice_number_override?: string | null;
  composition_mode: InvoiceCompositionMode;
  currency?: string | null;
  hourly_rate?: number | null;
  week_1_ending?: string | null;
  week_1_hours?: number | null;
  week_2_ending?: string | null;
  week_2_hours?: number | null;
  custom_line_items: InvoiceLineItemInput[];
}

export interface InvoiceDraftResult {
  invoice_id: string;
  company_key: string;
  company_name: string;
  invoice_number: string;
  output_filename: string;
  sender_mailbox: string;
  recipient_email: string;
  cc_email?: string | null;
  subtotal: number;
  total: number;
  amount_due: number;
  currency: string;
  gmail_draft_id: string;
  download_url: string;
  created_at: string;
}
