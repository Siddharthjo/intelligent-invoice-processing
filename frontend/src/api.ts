export interface User {
  username: string;
  role: string;
}

export interface StatusCount {
  decision_status: string | null;
  count: number;
}

export interface ExceptionReason {
  step: string;
  rule_code: string;
  count: number;
}

export interface DailyUsage {
  date: string;
  investigations: number;
  total_tokens: number;
  estimated_cost_usd: string;
}

export interface AnalyticsSummary {
  status_counts: StatusCount[];
  exception_reasons: ExceptionReason[];
  usage_by_day: DailyUsage[];
}

async function parseErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    return body.detail || fallback;
  } catch {
    return fallback;
  }
}

export async function login(username: string, password: string): Promise<User> {
  const response = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) throw new Error(await parseErrorDetail(response, "Login failed."));
  return response.json();
}

export async function fetchAnalyticsSummary(): Promise<AnalyticsSummary> {
  const response = await fetch("/analytics/summary");
  if (!response.ok) throw new Error(await parseErrorDetail(response, "Failed to load analytics."));
  return response.json();
}
