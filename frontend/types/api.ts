export type Currency = 'USD' | 'EUR' | 'RUB' | 'USDT' | 'USDC'
export type AdSide = 'BUY' | 'SELL'
export type AdStatus = 'ACTIVE' | 'REVOKED' | 'HIDDEN' | 'EXPIRED' | 'COMPLETED'
export type ReportReason =
  | 'SCAM'
  | 'SPAM'
  | 'WRONG_RATE'
  | 'OFFENSIVE'
  | 'DUPLICATE'
  | 'FAKE_CONTACT'
  | 'OTHER'
export type ReportStatus = 'NEW' | 'IN_REVIEW' | 'RESOLVED' | 'REJECTED'

export interface UserResponse {
  id: number
  telegram_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  is_admin: boolean
  is_banned: boolean
}

export interface RequiredChannelResponse {
  chat_id: string
  title: string | null
  is_member: boolean
}

export interface AccessResponse {
  allowed: boolean
  required_channels: RequiredChannelResponse[]
  missing_channels: RequiredChannelResponse[]
}

export interface AuthResponse {
  user: UserResponse
  access: AccessResponse
  csrf_token: string
}

export interface AuthorResponse {
  id: number
  username: string | null
}

export interface AdResponse {
  id: number
  side: AdSide
  base_currency: Currency
  quote_currency: Currency
  amount: string
  min_amount: string | null
  max_amount: string | null
  rate: string
  payment_method: string | null
  location: string | null
  comment: string | null
  status: AdStatus
  expires_at: string
  created_at: string
  updated_at: string
  author?: AuthorResponse
  revoked_at?: string | null
  hidden_at?: string | null
  completed_at?: string | null
}

export interface PaginationResponse {
  limit: number
  offset: number
  total: number
}

export interface AdsBySideResponse {
  sell: AdResponse[]
  buy: AdResponse[]
  pagination: PaginationResponse
}

export interface MyAdsResponse {
  items: AdResponse[]
  pagination: PaginationResponse
}

export interface AdCreatePayload {
  side: AdSide
  base_currency: Currency
  quote_currency: Currency
  amount: string
  min_amount?: string | null
  max_amount?: string | null
  rate: string
  payment_method?: string | null
  location?: string | null
  comment?: string | null
}

export interface ContactAttemptResponse {
  contact_attempt_id: number
  telegram_url: string
}

export interface RateItem {
  pair: string
  rate: string
}

export interface RatesResponse {
  date: string
  source: string
  is_stale: boolean
  updated_at: string
  rates: RateItem[]
}

export interface ReportCreatePayload {
  ad_id: number | null
  target_user_id: number
  reason: ReportReason
  comment?: string | null
}

export interface ReportResponse {
  id: number
  status: ReportStatus
}

export interface AdminUserSummaryResponse {
  id: number
  username: string | null
}

export interface AdminReportResponse {
  id: number
  reporter: AdminUserSummaryResponse
  target: AdminUserSummaryResponse
  ad_id: number | null
  reason: ReportReason
  comment: string | null
  status: ReportStatus
  resolved_by_user_id: number | null
  resolved_at: string | null
  created_at: string
  updated_at: string
}

export interface AdminReportListResponse {
  items: AdminReportResponse[]
  pagination: PaginationResponse
}

export interface AdminDashboardResponse {
  users_total: number
  users_banned: number
  ads_active: number
  ads_hidden: number
  reports_new: number
  rates: {
    status: 'missing' | 'fresh' | 'stale'
    latest_date: string | null
    last_updated_at: string | null
  }
}
