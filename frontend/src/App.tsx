import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
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
import "./App.css";

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
    <fieldset className="category-extras">
      <legend>Also categories</legend>
      <div className="checkbox-row">
        {options.map((c) => (
          <label key={c.id} className="check-label">
            <input
              type="checkbox"
              checked={extraIds.includes(c.id)}
              onChange={() => toggle(c.id)}
            />
            <span className="swatch" style={{ background: c.color }} aria-hidden />
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
      <main className="page">
        <p>Loading…</p>
      </main>
    );
  }

  return (
    <main className="page">
      <h1>Expense Tracker</h1>

      {error && <p className="error">{error}</p>}

      <section>
        <h2>Period</h2>
        <div className="presets" role="group" aria-label="Date range">
          {(
            [
              ["all", "All time"],
              ["week", "This week"],
              ["month", "This month"],
              ["custom", "Custom"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={preset === value ? "preset active" : "preset"}
              onClick={() => setPreset(value)}
            >
              {label}
            </button>
          ))}
        </div>
        {preset === "custom" && (
          <div className="range-inputs">
            <label>
              From
              <input
                type="date"
                value={customFrom}
                onChange={(e) => setCustomFrom(e.target.value)}
              />
            </label>
            <label>
              To
              <input
                type="date"
                value={customTo}
                onChange={(e) => setCustomTo(e.target.value)}
              />
            </label>
          </div>
        )}
      </section>

      <section>
        <h2>Summary</h2>
        {summary ? (
          <>
            <p className="total">Total: {formatMoney(summary.total_spend)}</p>
            <CategoryPieChart categories={summary.by_category} />
            <ul className="plain category-totals">
              {summary.by_category.map((c) => {
                const color = c.color ?? colorById.get(c.category_id) ?? "#888";
                return (
                  <li key={c.category_id}>
                    <span className="swatch" style={{ background: color }} aria-hidden />
                    {c.name}: {formatMoney(c.total)}
                  </li>
                );
              })}
            </ul>
          </>
        ) : (
          <p>No summary yet.</p>
        )}
      </section>

      <section>
        <h2>Monthly budgets</h2>
        <p className="hint">Limits apply to the current calendar month.</p>
        {budgets.length > 0 && (
          <ul className="budget-progress">
            {budgets.map((b) => (
              <li key={b.category_id} className={b.over ? "over" : undefined}>
                <div className="budget-head">
                  <span className="swatch" style={{ background: b.color }} aria-hidden />
                  <span>
                    {b.category_name}: {formatMoney(b.spent)} / {formatMoney(b.limit)}
                    {b.over ? " — over" : ` · ${formatMoney(b.remaining)} left`}
                  </span>
                </div>
                <div className="bar" role="progressbar" aria-valuenow={Math.min(b.pct, 100)} aria-valuemin={0} aria-valuemax={100}>
                  <div
                    className="bar-fill"
                    style={{ width: `${Math.min(b.pct, 100)}%`, background: b.color }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
        <ul className="budget-edit">
          {categories.map((c) => (
            <li key={c.id}>
              <span className="budget-label">
                <span className="swatch" style={{ background: c.color }} aria-hidden />
                {c.name}
              </span>
              <input
                type="number"
                min="0.01"
                step="0.01"
                placeholder="limit"
                value={budgetDrafts[c.id] ?? ""}
                onChange={(e) =>
                  setBudgetDrafts((prev) => ({ ...prev, [c.id]: e.target.value }))
                }
              />
              <button
                type="button"
                disabled={savingBudgetId === c.id}
                onClick={() => saveBudget(c.id)}
              >
                {savingBudgetId === c.id ? "…" : "Save"}
              </button>
              <button
                type="button"
                disabled={savingBudgetId === c.id || !(budgetDrafts[c.id] || budgets.some((b) => b.category_id === c.id))}
                onClick={() => clearBudget(c.id)}
              >
                Clear
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Chat</h2>
        <form className="form" onSubmit={onParse}>
          <label>
            What did you spend?
            <input
              type="text"
              value={chatText}
              onChange={(e) => setChatText(e.target.value)}
              placeholder="e.g. swiggy 450 yesterday"
            />
          </label>
          <button type="submit" disabled={parsing}>
            {parsing ? "Parsing…" : "Parse"}
          </button>
        </form>

        {drafts.map((d, i) => (
          <div key={i} className="draft">
            <strong>Review before saving</strong>
            {(d.confidence === "low" || d.category_id == null) && (
              <p className="error">Check category before approving</p>
            )}
            <label>
              Amount
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={d.amount}
                onChange={(e) => updateDraft(i, { amount: Number(e.target.value) })}
              />
            </label>
            <label>
              Category
              <select
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
              </select>
            </label>
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
            <label>
              Date
              <input
                type="date"
                value={d.date ?? ""}
                onChange={(e) => updateDraft(i, { date: e.target.value || null })}
              />
            </label>
            <label>
              Note
              <input
                type="text"
                value={d.note}
                onChange={(e) => updateDraft(i, { note: e.target.value })}
              />
            </label>
            <label>
              Tags
              <input
                type="text"
                value={d.tag_text ?? formatTagInput(d.tags)}
                onChange={(e) => updateDraft(i, { tag_text: e.target.value })}
                placeholder="comma-separated, e.g. gift, travel"
              />
            </label>
            <button type="button" onClick={() => approveDraft(i)}>
              Approve
            </button>
            <button type="button" onClick={() => rejectDraft(i)}>
              Reject
            </button>
          </div>
        ))}
      </section>

      <section>
        <h2>Add expense</h2>
        <form className="form" onSubmit={onSubmit}>
          <label>
            Category
            <select
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
            </select>
          </label>
          <CategoryExtras
            categories={categories}
            primaryId={categoryId ? Number(categoryId) : null}
            extraIds={extraCategoryIds}
            onChange={setExtraCategoryIds}
          />
          <label>
            Amount
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
            />
          </label>
          <label>
            Note
            <input
              type="text"
              maxLength={240}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="optional"
            />
          </label>
          <label>
            Tags
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="comma-separated, e.g. gift, mom"
            />
          </label>
          <label>
            Date
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? "Saving…" : "Add"}
          </button>
        </form>
      </section>

      <section>
        <h2>Expenses</h2>
        {expenses.length === 0 ? (
          <p>No expenses in this period.</p>
        ) : (
          <ul className="expenses">
            {expenses.map((e) => {
              const color = colorById.get(e.category_id) ?? "#888";
              if (editingId === e.id) {
                return (
                  <li key={e.id} className="expense-edit">
                    <form className="form edit-form" onSubmit={saveEdit}>
                      <label>
                        Category
                        <select
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
                        </select>
                      </label>
                      <CategoryExtras
                        categories={categories}
                        primaryId={editCategoryId ? Number(editCategoryId) : null}
                        extraIds={editExtraCategoryIds}
                        onChange={setEditExtraCategoryIds}
                      />
                      <label>
                        Amount
                        <input
                          type="number"
                          min="0.01"
                          step="0.01"
                          value={editAmount}
                          onChange={(ev) => setEditAmount(ev.target.value)}
                          required
                        />
                      </label>
                      <label>
                        Date
                        <input
                          type="date"
                          value={editDate}
                          onChange={(ev) => setEditDate(ev.target.value)}
                          required
                        />
                      </label>
                      <label>
                        Note
                        <input
                          type="text"
                          maxLength={240}
                          value={editNote}
                          onChange={(ev) => setEditNote(ev.target.value)}
                        />
                      </label>
                      <label>
                        Tags
                        <input
                          type="text"
                          value={editTagsInput}
                          onChange={(ev) => setEditTagsInput(ev.target.value)}
                          placeholder="comma-separated"
                        />
                      </label>
                      <div className="row-actions">
                        <button type="submit" disabled={savingEdit}>
                          {savingEdit ? "Saving…" : "Save"}
                        </button>
                        <button type="button" onClick={cancelEdit}>
                          Cancel
                        </button>
                      </div>
                    </form>
                  </li>
                );
              }
              return (
                <li key={e.id}>
                  <span className="expense-main">
                    <span className="swatch" style={{ background: color }} aria-hidden />
                    <span>
                      {e.date} ·{" "}
                      {(e.categories?.length
                        ? e.categories.map((c) => c.name).join(" · ")
                        : e.category_name) ?? "?"}{" "}
                      · {formatMoney(e.amount)}
                      {e.note ? ` — ${e.note}` : ""}
                      {e.tags.length > 0 && (
                        <span className="tag-list">
                          {e.tags.map((t) => (
                            <span key={t} className="tag">
                              {t}
                            </span>
                          ))}
                        </span>
                      )}
                    </span>
                  </span>
                  <span className="row-actions">
                    <button type="button" onClick={() => startEdit(e)}>
                      Edit
                    </button>
                    <button type="button" onClick={() => onDelete(e.id)}>
                      Delete
                    </button>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
