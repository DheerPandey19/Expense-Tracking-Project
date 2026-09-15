const API_BASE = "http://127.0.0.1:8000";

export type Category = {
  id: number;
  name: string;
  color: string;
};

export type Tag = {
  id: number;
  name: string;
};

export type Expense = {
  id: number;
  category_id: number;
  amount: number;
  date: string;
  note: string;
  category_name: string | null;
  categories: Category[];
  tags: string[];
};

export type ExpenseCreate = {
  category_id?: number;
  category_ids: number[];
  amount: number;
  date?: string | null;
  note?: string;
  tags?: string[];
};

export type ExpenseUpdate = {
  category_id?: number;
  category_ids?: number[];
  amount?: number;
  date?: string | null;
  note?: string;
  tags?: string[];
};

export type DateRange = {
  from?: string;
  to?: string;
};

export type CategoryTotal = {
  category_id: number;
  name: string;
  total: number;
  color?: string | null;
};

export type Summary = {
  total_spend: number;
  by_category: CategoryTotal[];
};

export type ExpenseDraft = {
  amount: number;
  category_id: number | null;
  category_ids?: number[];
  date: string | null;
  note: string;
  confidence: string;
  tags?: string[];
  /** Local-only raw input while editing a draft card */
  tag_text?: string;
};

export type ParseOut = {
  drafts: ExpenseDraft[];
};

export type BudgetProgress = {
  category_id: number;
  category_name: string;
  color: string;
  limit: number;
  spent: number;
  remaining: number;
  over: boolean;
  pct: number;
};

export type BudgetUpsert = {
  category_id: number;
  amount: number;
};

export function parseTagInput(raw: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of raw.split(",")) {
    const name = part.trim().toLowerCase().replace(/\s+/g, " ");
    if (!name || seen.has(name)) continue;
    seen.add(name);
    out.push(name);
  }
  return out;
}

export function formatTagInput(tags: string[] | undefined | null): string {
  return (tags ?? []).join(", ");
}

function rangeQuery(range?: DateRange): string {
  if (!range) return "";
  const params = new URLSearchParams();
  if (range.from) params.set("from", range.from);
  if (range.to) params.set("to", range.to);
  const q = params.toString();
  return q ? `?${q}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) {
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      /* ignore parse errors */
    }
    throw new Error(detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export function getCategories() {
  return request<Category[]>("/api/categories");
}

export function getTags() {
  return request<Tag[]>("/api/tags");
}

export function getExpenses(range?: DateRange) {
  return request<Expense[]>(`/api/expenses${rangeQuery(range)}`);
}

export function createExpense(body: ExpenseCreate) {
  return request<Expense>("/api/expenses", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateExpense(id: number, body: ExpenseUpdate) {
  return request<Expense>(`/api/expenses/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteExpense(id: number) {
  return request<{ ok: boolean }>(`/api/expenses/${id}`, { method: "DELETE" });
}

export function getSummary(range?: DateRange) {
  return request<Summary>(`/api/summary${rangeQuery(range)}`);
}

export function parseExpense(text: string) {
  return request<ParseOut>("/api/parse", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function getBudgets() {
  return request<BudgetProgress[]>("/api/budgets");
}

export function upsertBudget(body: BudgetUpsert) {
  return request<BudgetProgress>("/api/budgets", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function deleteBudget(categoryId: number) {
  return request<{ ok: boolean }>(`/api/budgets/${categoryId}`, {
    method: "DELETE",
  });
}
