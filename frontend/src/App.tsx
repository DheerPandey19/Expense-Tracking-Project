import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  createExpense,
  deleteExpense,
  getCategories,
  getExpenses,
  getSummary,
} from "./api";
import type { Category, Expense, Summary } from "./api";
import "./App.css";

function formatMoney(n: number) {
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export default function App() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [categoryId, setCategoryId] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [date, setDate] = useState("");

  const refresh = useCallback(async () => {
    const [cats, exps, sum] = await Promise.all([
      getCategories(),
      getExpenses(),
      getSummary(),
    ]);
    setCategories(cats);
    setExpenses(exps);
    setSummary(sum);
    setCategoryId((prev) => prev || (cats[0] ? String(cats[0].id) : ""));
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setError(null);
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
        category_id: Number(categoryId),
        amount: parsedAmount,
        note: note.trim(),
        date: date || null,
      });
      setAmount("");
      setNote("");
      setDate("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create expense");
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(id: number) {
    setError(null);
    try {
      await deleteExpense(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete expense");
    }
  }

  if (loading) {
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
        <h2>Summary</h2>
        {summary ? (
          <>
            <p className="total">Total: {formatMoney(summary.total_spend)}</p>
            <ul className="plain">
              {summary.by_category.map((c) => (
                <li key={c.category_id}>
                  {c.name}: {formatMoney(c.total)}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p>No summary yet.</p>
        )}
      </section>

      <section>
        <h2>Add expense</h2>
        <form className="form" onSubmit={onSubmit}>
          <label>
            Category
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              required
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
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
          <p>No expenses yet.</p>
        ) : (
          <ul className="expenses">
            {expenses.map((e) => (
              <li key={e.id}>
                <span>
                  {e.date} · {e.category_name ?? "?"} · {formatMoney(e.amount)}
                  {e.note ? ` — ${e.note}` : ""}
                </span>
                <button type="button" onClick={() => onDelete(e.id)}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
