import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { NotebookPen, PiggyBank, Wallet, X } from "lucide-react";
import {
  createExpense,
  deleteBudget,
  deleteExpense,
  formatTagInput,
  getBudgets,
  getCategories,
  getExpenses,
  getSummary,
  parseExpense,
  parseTagInput,
  updateExpense,
  upsertBudget,
} from "./api";
import type {
  BudgetProgress,
  Category,
  DateRange,
  Expense,
  ExpenseDraft,
  Summary,
} from "./api";
import CategoryPieChart from "./CategoryPieChart";
import Button from "./ui/Button";
import Card from "./ui/Card";
import Input from "./ui/Input";
import Select from "./ui/Select";
import { wobblySm } from "./ui/tokens";

type Preset = "all" | "week" | "month" | "custom";

function formatMoney(n: number) {
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function toISODate(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function startOfWeek(d: Date) {
  const out = new Date(d);
  const day = out.getDay();
  const diff = day === 0 ? 6 : day - 1;
  out.setDate(out.getDate() - diff);
  return out;
}

function startOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function rangeForPreset(preset: Preset, customFrom: string, customTo: string): DateRange {
  const today = new Date();
  if (preset === "week") {
    return { from: toISODate(startOfWeek(today)), to: toISODate(today) };
  }
  if (preset === "month") {
    return { from: toISODate(startOfMonth(today)), to: toISODate(today) };
  }
  if (preset === "custom") {
    return {
      from: customFrom || undefined,
      to: customTo || undefined,
    };
  }
  return {};
}

function mergeCategoryIds(primaryId: number, extraIds: number[]): number[] {
  const seen = new Set<number>();
  const out: number[] = [];
  for (const id of [primaryId, ...extraIds]) {
    if (seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

function Swatch({ color }: { color: string }) {
  return (
    <span
      className="mt-0.5 inline-block h-3 w-3 shrink-0 border-2 border-ink"
      style={{ background: color, borderRadius: wobblySm }}
      aria-hidden
    />
  );
}

function CategoryExtras({
  categories,
  primaryId,
  extraIds,
  onChange,
}: {
  categories: Category[];
  primaryId: number | null;
  extraIds: number[];
  onChange: (ids: number[]) => void;
}) {
  const options = categories.filter((c) => c.id !== primaryId);
  if (options.length === 0) return null;

  function toggle(id: number) {
    if (extraIds.includes(id)) onChange(extraIds.filter((x) => x !== id));
    else onChange([...extraIds, id]);
  }

  return (
    <fieldset
      className="border-2 border-dashed border-ink p-3"
      style={{ borderRadius: wobblySm }}
    >
      <legend className="px-1 font-heading text-lg">Also categories</legend>
      <div className="flex flex-wrap gap-3">
        {options.map((c) => (
          <label key={c.id} className="inline-flex items-center gap-2 text-base">
            <input
              type="checkbox"
              className="h-4 w-4 accent-pen"
              checked={extraIds.includes(c.id)}
              onChange={() => toggle(c.id)}
            />
            <Swatch color={c.color} />
            {c.name}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export default function App() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [preset, setPreset] = useState<Preset>("month");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");

  const [categoryId, setCategoryId] = useState("");
  const [extraCategoryIds, setExtraCategoryIds] = useState<number[]>([]);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [date, setDate] = useState("");
  const [tagsInput, setTagsInput] = useState("");

  const [chatText, setChatText] = useState("");
  const [drafts, setDrafts] = useState<ExpenseDraft[]>([]);
  const [parsing, setParsing] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editCategoryId, setEditCategoryId] = useState("");
  const [editExtraCategoryIds, setEditExtraCategoryIds] = useState<number[]>([]);
  const [editAmount, setEditAmount] = useState("");
  const [editNote, setEditNote] = useState("");
  const [editDate, setEditDate] = useState("");
  const [editTagsInput, setEditTagsInput] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);

  const [budgets, setBudgets] = useState<BudgetProgress[]>([]);
  const [budgetDrafts, setBudgetDrafts] = useState<Record<number, string>>({});
  const [savingBudgetId, setSavingBudgetId] = useState<number | null>(null);
  const [budgetsOpen, setBudgetsOpen] = useState(false);

  useEffect(() => {
    if (!budgetsOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setBudgetsOpen(false);
    }
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [budgetsOpen]);

  const dateRange = useMemo(
    () => rangeForPreset(preset, customFrom, customTo),
    [preset, customFrom, customTo],
  );

  const colorById = useMemo(() => {
    const map = new Map<number, string>();
    for (const c of categories) map.set(c.id, c.color);
    return map;
  }, [categories]);

  const refresh = useCallback(async () => {
    const [cats, exps, sum, buds] = await Promise.all([
      getCategories(),
      getExpenses(dateRange),
      getSummary(dateRange),
      getBudgets(),
    ]);
    setCategories(cats);
    setExpenses(exps);
    setSummary(sum);
    setBudgets(buds);
    const limits: Record<number, string> = {};
    for (const c of cats) {
      const b = buds.find((x) => x.category_id === c.id);
      limits[c.id] = b ? String(b.limit) : "";
    }
    setBudgetDrafts(limits);
    setCategoryId((prev) => prev || (cats[0] ? String(cats[0].id) : ""));
  }, [dateRange]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setError(null);
        setLoading(true);
        await refresh();
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load data");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  async function onParse(e: FormEvent) {
    e.preventDefault();
    if (!chatText.trim()) return;
    setParsing(true);
    setError(null);
    try {
      const res = await parseExpense(chatText.trim());
      if (res.drafts.length === 0) {
        setError("Could not find an amount in that message.");
        setDrafts([]);
      } else {
        setDrafts(res.drafts);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Parse failed");
    } finally {
      setParsing(false);
    }
  }

  function updateDraft(index: number, patch: Partial<ExpenseDraft>) {
    setDrafts((prev) =>
      prev.map((d, i) => {
        if (i !== index) return d;
        const next = { ...d, ...patch };
        if (patch.category_id !== undefined) {
          const primary = patch.category_id;
          const extras = (next.category_ids ?? []).filter((id) => id !== primary);
          next.category_ids =
            primary == null ? extras : mergeCategoryIds(primary, extras);
        }
        return next;
      }),
    );
  }

  function draftExtraIds(d: ExpenseDraft): number[] {
    const primary = d.category_id;
    return (d.category_ids ?? []).filter((id) => id !== primary);
  }

  async function approveDraft(index: number) {
    const d = drafts[index];
    if (!d || d.category_id == null) {
      setError("Pick a category before approving.");
      return;
    }
    setError(null);
    try {
      await createExpense({
        category_ids: mergeCategoryIds(d.category_id, draftExtraIds(d)),
        amount: d.amount,
        note: d.note,
        date: d.date,
        tags: parseTagInput(d.tag_text ?? formatTagInput(d.tags)),
      });
      setDrafts((prev) => prev.filter((_, i) => i !== index));
      setChatText("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    }
  }

  function rejectDraft(index: number) {
    setDrafts((prev) => prev.filter((_, i) => i !== index));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const parsedAmount = Number(amount);
    if (!categoryId || !Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      setError("Pick a category and enter an amount greater than 0.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await createExpense({
        category_ids: mergeCategoryIds(Number(categoryId), extraCategoryIds),
        amount: parsedAmount,
        note: note.trim(),
        date: date || null,
        tags: parseTagInput(tagsInput),
      });
      setAmount("");
      setNote("");
      setDate("");
      setTagsInput("");
      setExtraCategoryIds([]);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create expense");
    } finally {
      setSubmitting(false);
    }
  }

  function startEdit(e: Expense) {
    setEditingId(e.id);
    setEditCategoryId(String(e.category_id));
    setEditExtraCategoryIds(
      (e.categories ?? []).map((c) => c.id).filter((id) => id !== e.category_id),
    );
    setEditAmount(String(e.amount));
    setEditNote(e.note);
    setEditDate(e.date);
    setEditTagsInput(formatTagInput(e.tags));
  }

  function cancelEdit() {
    setEditingId(null);
  }

  async function saveEdit(e: FormEvent) {
    e.preventDefault();
    if (editingId == null) return;
    const parsedAmount = Number(editAmount);
    if (!editCategoryId || !Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      setError("Pick a category and enter an amount greater than 0.");
      return;
    }
    setSavingEdit(true);
    setError(null);
    try {
      await updateExpense(editingId, {
        category_ids: mergeCategoryIds(Number(editCategoryId), editExtraCategoryIds),
        amount: parsedAmount,
        note: editNote.trim(),
        date: editDate || null,
        tags: parseTagInput(editTagsInput),
      });
      setEditingId(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update expense");
    } finally {
      setSavingEdit(false);
    }
  }

  async function onDelete(id: number) {
    setError(null);
    try {
      await deleteExpense(id);
      if (editingId === id) setEditingId(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete expense");
    }
  }

  async function saveBudget(categoryIdNum: number) {
    const raw = budgetDrafts[categoryIdNum]?.trim() ?? "";
    if (!raw) {
      setError("Enter a monthly limit greater than 0, or clear to remove.");
      return;
    }
    const value = Number(raw);
    if (!Number.isFinite(value) || value <= 0) {
      setError("Budget must be greater than 0.");
      return;
    }
    setSavingBudgetId(categoryIdNum);
    setError(null);
    try {
      await upsertBudget({ category_id: categoryIdNum, amount: value });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save budget");
    } finally {
      setSavingBudgetId(null);
    }
  }

  async function clearBudget(categoryIdNum: number) {
    setSavingBudgetId(categoryIdNum);
    setError(null);
    try {
      const exists = budgets.some((b) => b.category_id === categoryIdNum);
      if (exists) await deleteBudget(categoryIdNum);
      setBudgetDrafts((prev) => ({ ...prev, [categoryIdNum]: "" }));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear budget");
    } finally {
      setSavingBudgetId(null);
    }
  }

  if (loading && !summary) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-10 md:px-6">
        <p className="font-heading text-2xl">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl space-y-8 px-4 py-8 md:px-6 md:py-12">
      <header className="relative">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
          <p
            className="inline-block rotate-[-2deg] bg-postit px-3 py-1 text-sm border-2 border-ink"
            style={{ borderRadius: wobblySm }}
          >
            sketchbook ledger
          </p>
          <Button
            type="button"
            variant="secondary"
            aria-expanded={budgetsOpen}
            aria-controls="budgets-sidebar"
            onClick={() => setBudgetsOpen(true)}
          >
            <PiggyBank strokeWidth={2.5} className="h-5 w-5" aria-hidden />
            Budgets
          </Button>
        </div>
        <h1 className="font-heading text-4xl md:text-6xl">
          Expense Tracker
          <span className="ml-1 inline-block rotate-12 text-accent" aria-hidden>
            !
          </span>
        </h1>
        <p className="mt-2 max-w-xl text-lg text-ink/80 md:text-xl">
          Scribble spends from the web or Telegram — same notebook, same totals.
        </p>
        <Wallet
          className="absolute -right-1 top-16 hidden h-14 w-14 rotate-6 text-pen md:block"
          strokeWidth={2.5}
          aria-hidden
        />
      </header>

      {error && (
        <p
          role="alert"
          className="border-[3px] border-ink bg-accent/15 px-4 py-3 text-ink shadow-[4px_4px_0px_0px_#2d2d2d]"
          style={{ borderRadius: wobblySm }}
        >
          {error}
        </p>
      )}

      <Card title="Period" decoration="tape" rotate="left">
        <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Date range">
          {(
            [
              ["all", "All time"],
              ["week", "This week"],
              ["month", "This month"],
              ["custom", "Custom"],
            ] as const
          ).map(([value, label]) => (
            <Button
              key={value}
              type="button"
              variant={preset === value ? "secondary" : "ghost"}
              className={preset === value ? "bg-pen text-white hover:bg-pen" : ""}
              onClick={() => setPreset(value)}
            >
              {label}
            </Button>
          ))}
        </div>
        {preset === "custom" && (
          <div className="flex flex-wrap gap-4">
            <Input
              label="From"
              type="date"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
            />
            <Input
              label="To"
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
            />
          </div>
        )}
      </Card>

      <Card title="Summary" decoration="tack">
        {summary ? (
          <>
            <p className="mb-4 font-heading text-2xl md:text-3xl">
              Total: {formatMoney(summary.total_spend)}
            </p>
            <div className="grid items-start gap-6 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] md:gap-8">
              <CategoryPieChart categories={summary.by_category} />
              <ul className="columns-1 gap-x-6 space-y-2 sm:columns-2 md:columns-1 lg:columns-2">
                {summary.by_category.map((c) => {
                  const color = c.color ?? colorById.get(c.category_id) ?? "#888";
                  return (
                    <li
                      key={c.category_id}
                      className="mb-2 flex break-inside-avoid items-center gap-2"
                    >
                      <Swatch color={color} />
                      {c.name}: {formatMoney(c.total)}
                    </li>
                  );
                })}
              </ul>
            </div>
          </>
        ) : (
          <p>No summary yet.</p>
        )}
      </Card>

      {budgetsOpen && (
        <div className="fixed inset-0 z-40 flex justify-end">
          <button
            type="button"
            className="absolute inset-0 bg-ink/30"
            aria-label="Close budgets sidebar"
            onClick={() => setBudgetsOpen(false)}
          />
          <aside
            id="budgets-sidebar"
            role="dialog"
            aria-modal="true"
            aria-labelledby="budgets-sidebar-title"
            className="relative z-50 flex h-full w-full max-w-md flex-col border-l-[3px] border-ink bg-card shadow-[-8px_0_0_0_#2d2d2d]"
          >
            <div className="flex items-start justify-between gap-3 border-b-2 border-dashed border-ink/30 p-4 md:p-5">
              <div>
                <h2
                  id="budgets-sidebar-title"
                  className="font-heading text-2xl md:text-3xl"
                >
                  Monthly budgets
                </h2>
                <p className="mt-1 text-base text-ink/70">
                  Limits apply to the current calendar month.
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                className="min-h-10 shrink-0 px-3"
                aria-label="Close"
                onClick={() => setBudgetsOpen(false)}
              >
                <X strokeWidth={3} className="h-5 w-5" aria-hidden />
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 md:p-5">
              {budgets.length > 0 && (
                <ul className="mb-6 space-y-4">
                  {budgets.map((b) => (
                    <li key={b.category_id}>
                      <div className="mb-1 flex items-center gap-2">
                        <Swatch color={b.color} />
                        <span>
                          {b.category_name}: {formatMoney(b.spent)} /{" "}
                          {formatMoney(b.limit)}
                          {b.over ? (
                            <span className="text-accent"> — over</span>
                          ) : (
                            ` · ${formatMoney(b.remaining)} left`
                          )}
                        </span>
                      </div>
                      <div
                        className={`h-4 overflow-hidden border-2 border-ink bg-muted ${b.over ? "ring-2 ring-accent" : ""}`}
                        style={{ borderRadius: wobblySm }}
                        role="progressbar"
                        aria-valuenow={Math.min(b.pct, 100)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      >
                        <div
                          className="h-full"
                          style={{
                            width: `${Math.min(b.pct, 100)}%`,
                            background: b.color,
                          }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              <ul className="space-y-3">
                {categories.map((c) => (
                  <li
                    key={c.id}
                    className="flex flex-wrap items-center gap-2 border-b border-dashed border-ink/30 pb-3"
                  >
                    <span className="inline-flex min-w-[6.5rem] items-center gap-2">
                      <Swatch color={c.color} />
                      {c.name}
                    </span>
                    <Input
                      type="number"
                      min="0.01"
                      step="0.01"
                      placeholder="limit"
                      className="max-w-[7.5rem]"
                      value={budgetDrafts[c.id] ?? ""}
                      onChange={(e) =>
                        setBudgetDrafts((prev) => ({
                          ...prev,
                          [c.id]: e.target.value,
                        }))
                      }
                    />
                    <Button
                      type="button"
                      disabled={savingBudgetId === c.id}
                      onClick={() => saveBudget(c.id)}
                    >
                      {savingBudgetId === c.id ? "…" : "Save"}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      disabled={
                        savingBudgetId === c.id ||
                        !(
                          budgetDrafts[c.id] ||
                          budgets.some((b) => b.category_id === c.id)
                        )
                      }
                      onClick={() => clearBudget(c.id)}
                    >
                      Clear
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        </div>
      )}

      <Card title="Chat" decoration="tape">
        <form className="grid gap-3" onSubmit={onParse}>
          <Input
            label="What did you spend?"
            type="text"
            value={chatText}
            onChange={(e) => setChatText(e.target.value)}
            placeholder="e.g. swiggy 450 yesterday"
          />
          <div>
            <Button type="submit" disabled={parsing}>
              <NotebookPen strokeWidth={2.5} className="h-5 w-5" aria-hidden />
              {parsing ? "Parsing…" : "Parse"}
            </Button>
          </div>
        </form>

        {drafts.map((d, i) => (
          <div
            key={i}
            className="mt-5 border-[3px] border-ink bg-postit p-4 shadow-[3px_3px_0px_0px_rgba(45,45,45,0.15)]"
            style={{ borderRadius: wobblySm }}
          >
            <strong className="font-heading text-xl">Review before saving</strong>
            {(d.confidence === "low" || d.category_id == null) && (
              <p className="mt-1 text-accent">Check category before approving</p>
            )}
            <div className="mt-3 grid gap-3">
              <Input
                label="Amount"
                type="number"
                min="0.01"
                step="0.01"
                value={d.amount}
                onChange={(e) => updateDraft(i, { amount: Number(e.target.value) })}
              />
              <Select
                label="Category"
                value={d.category_id ?? ""}
                onChange={(e) =>
                  updateDraft(i, {
                    category_id: e.target.value ? Number(e.target.value) : null,
                  })
                }
              >
                <option value="">Select…</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
              <CategoryExtras
                categories={categories}
                primaryId={d.category_id}
                extraIds={draftExtraIds(d)}
                onChange={(ids) =>
                  updateDraft(i, {
                    category_ids:
                      d.category_id == null
                        ? ids
                        : mergeCategoryIds(d.category_id, ids),
                  })
                }
              />
              <Input
                label="Date"
                type="date"
                value={d.date ?? ""}
                onChange={(e) => updateDraft(i, { date: e.target.value || null })}
              />
              <Input
                label="Note"
                type="text"
                value={d.note}
                onChange={(e) => updateDraft(i, { note: e.target.value })}
              />
              <Input
                label="Tags"
                type="text"
                value={d.tag_text ?? formatTagInput(d.tags)}
                onChange={(e) => updateDraft(i, { tag_text: e.target.value })}
                placeholder="comma-separated, e.g. gift, travel"
              />
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={() => approveDraft(i)}>
                  Approve
                </Button>
                <Button type="button" variant="ghost" onClick={() => rejectDraft(i)}>
                  Reject
                </Button>
              </div>
            </div>
          </div>
        ))}
      </Card>

      <Card title="Add expense" rotate="left">
        <form className="grid gap-3" onSubmit={onSubmit}>
          <Select
            label="Category"
            value={categoryId}
            onChange={(e) => {
              const next = e.target.value;
              setCategoryId(next);
              const primary = Number(next);
              setExtraCategoryIds((prev) => prev.filter((id) => id !== primary));
            }}
            required
          >
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <CategoryExtras
            categories={categories}
            primaryId={categoryId ? Number(categoryId) : null}
            extraIds={extraCategoryIds}
            onChange={setExtraCategoryIds}
          />
          <Input
            label="Amount"
            type="number"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
          <Input
            label="Note"
            type="text"
            maxLength={240}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="optional"
          />
          <Input
            label="Tags"
            type="text"
            value={tagsInput}
            onChange={(e) => setTagsInput(e.target.value)}
            placeholder="comma-separated, e.g. gift, mom"
          />
          <Input
            label="Date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <div>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving…" : "Add"}
            </Button>
          </div>
        </form>
      </Card>

      <Card title="Expenses" decoration="tack">
        {expenses.length === 0 ? (
          <p>No expenses in this period.</p>
        ) : (
          <ul className="space-y-3">
            {expenses.map((e) => {
              const color = colorById.get(e.category_id) ?? "#888";
              if (editingId === e.id) {
                return (
                  <li
                    key={e.id}
                    className="border-[3px] border-ink bg-muted/40 p-4"
                    style={{ borderRadius: wobblySm }}
                  >
                    <form className="grid gap-3" onSubmit={saveEdit}>
                      <Select
                        label="Category"
                        value={editCategoryId}
                        onChange={(ev) => {
                          const next = ev.target.value;
                          setEditCategoryId(next);
                          const primary = Number(next);
                          setEditExtraCategoryIds((prev) =>
                            prev.filter((id) => id !== primary),
                          );
                        }}
                        required
                      >
                        {categories.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </Select>
                      <CategoryExtras
                        categories={categories}
                        primaryId={editCategoryId ? Number(editCategoryId) : null}
                        extraIds={editExtraCategoryIds}
                        onChange={setEditExtraCategoryIds}
                      />
                      <Input
                        label="Amount"
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={editAmount}
                        onChange={(ev) => setEditAmount(ev.target.value)}
                        required
                      />
                      <Input
                        label="Date"
                        type="date"
                        value={editDate}
                        onChange={(ev) => setEditDate(ev.target.value)}
                        required
                      />
                      <Input
                        label="Note"
                        type="text"
                        maxLength={240}
                        value={editNote}
                        onChange={(ev) => setEditNote(ev.target.value)}
                      />
                      <Input
                        label="Tags"
                        type="text"
                        value={editTagsInput}
                        onChange={(ev) => setEditTagsInput(ev.target.value)}
                        placeholder="comma-separated"
                      />
                      <div className="flex flex-wrap gap-2">
                        <Button type="submit" disabled={savingEdit}>
                          {savingEdit ? "Saving…" : "Save"}
                        </Button>
                        <Button type="button" variant="ghost" onClick={cancelEdit}>
                          Cancel
                        </Button>
                      </div>
                    </form>
                  </li>
                );
              }
              return (
                <li
                  key={e.id}
                  className="flex flex-wrap items-start justify-between gap-3 border-b-2 border-dashed border-ink/25 pb-3"
                >
                  <span className="flex min-w-0 items-start gap-2">
                    <Swatch color={color} />
                    <span>
                      {e.date} ·{" "}
                      {(e.categories?.length
                        ? e.categories.map((c) => c.name).join(" · ")
                        : e.category_name) ?? "?"}{" "}
                      · {formatMoney(e.amount)}
                      {e.note ? ` — ${e.note}` : ""}
                      {e.tags.length > 0 && (
                        <span className="mt-1 flex flex-wrap gap-1">
                          {e.tags.map((t) => (
                            <span
                              key={t}
                              className="inline-block border-2 border-ink bg-postit px-2 text-sm"
                              style={{ borderRadius: wobblySm }}
                            >
                              {t}
                            </span>
                          ))}
                        </span>
                      )}
                    </span>
                  </span>
                  <span className="flex shrink-0 gap-2">
                    <Button type="button" variant="secondary" onClick={() => startEdit(e)}>
                      Edit
                    </Button>
                    <Button type="button" variant="danger" onClick={() => onDelete(e.id)}>
                      Delete
                    </Button>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </main>
  );
}
