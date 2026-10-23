"use client";

import { useEffect, useState, type FormEvent } from "react";
import { errorMessage, formatDue, fromDateTimeLocal, parseApiDate, priorityLabel, relativeDue, statusLabel } from "@/lib/format";
import type { Task, TaskCreateInput, TaskFilters, TaskPriority, TaskStatus, TaskUpdateInput } from "@/lib/types";
import { PRIORITY_OPTIONS, STATUS_OPTIONS } from "@/lib/types";

interface TaskBoardProps {
  tasks: Task[];
  total: number;
  loading: boolean;
  error: string | null;
  notice: string | null;
  filters: TaskFilters;
  highlightedId: number | null;
  disabled: boolean;
  seeding: boolean;
  onFilters: (filters: TaskFilters) => void;
  onCreate: (input: TaskCreateInput) => Promise<void>;
  onUpdate: (id: number, patch: TaskUpdateInput) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  onSeed: () => Promise<void>;
}

const PRIORITY_RANK: Record<TaskPriority, number> = { urgent: 0, high: 1, medium: 2, low: 3 };

function compareForEvening(a: Task, b: Task): number {
  const rank = (PRIORITY_RANK[a.priority] ?? 9) - (PRIORITY_RANK[b.priority] ?? 9);
  if (rank !== 0) return rank;
  const aDue = a.due_date ? parseApiDate(a.due_date).getTime() : Number.POSITIVE_INFINITY;
  const bDue = b.due_date ? parseApiDate(b.due_date).getTime() : Number.POSITIVE_INFINITY;
  if (aDue !== bDue) return aDue - bDue;
  return a.id - b.id;
}

const PRIORITY_DOT: Record<TaskPriority, string> = {
  urgent: "bg-bad",
  high: "bg-warn",
  medium: "bg-glow",
  low: "bg-white/35",
};

const PRIORITY_EDGE: Record<TaskPriority, string> = {
  urgent: "border-l-bad",
  high: "border-l-warn",
  medium: "border-l-glow",
  low: "border-l-white/25",
};

const STATUS_TONE: Record<TaskStatus, string> = {
  pending: "text-mute",
  in_progress: "text-glow",
  completed: "text-good",
  cancelled: "text-faint",
};

export function TaskBoard({
  tasks,
  total,
  loading,
  error,
  notice,
  filters,
  highlightedId,
  disabled,
  seeding,
  onFilters,
  onCreate,
  onUpdate,
  onDelete,
  onSeed,
}: TaskBoardProps) {
  const [search, setSearch] = useState(filters.search);
  const [composerOpen, setComposerOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [due, setDue] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [showFinished, setShowFinished] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (search !== filters.search) onFilters({ ...filters, search });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [search, filters, onFilters]);

  useEffect(() => {
    if (highlightedId == null) return;
    document.getElementById(`task-${highlightedId}`)?.scrollIntoView({ block: "nearest" });
  }, [highlightedId, tasks]);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    const nextTitle = title.trim();
    if (!nextTitle) {
      setFormError("A task needs a title.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      await onCreate({
        title: nextTitle,
        description: description.trim() || null,
        priority,
        due_date: fromDateTimeLocal(due),
      });
      setTitle("");
      setDescription("");
      setDue("");
      setPriority("medium");
      setComposerOpen(false);
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function handleStatus(task: Task, status: TaskStatus) {
    if (status === task.status) return;
    setRowError(null);
    try {
      await onUpdate(task.id, { status });
    } catch (error) {
      setRowError(errorMessage(error));
    }
  }

  async function handleDelete(taskId: number) {
    setRowError(null);
    try {
      await onDelete(taskId);
      setPendingDeleteId(null);
    } catch (error) {
      setRowError(errorMessage(error));
    }
  }

  const focusingFinished = filters.status === "completed" || filters.status === "cancelled";
  const openTasks = tasks.filter((task) => task.status === "pending" || task.status === "in_progress").sort(compareForEvening);
  const finishedTasks = tasks.filter((task) => task.status === "completed" || task.status === "cancelled").sort(compareForEvening);
  const visibleTasks = focusingFinished ? finishedTasks : openTasks;
  const ledgerSummary = loading
    ? "Loading from the API…"
    : focusingFinished
      ? `${total} ${total === 1 ? "task" : "tasks"} in this view`
      : `${openTasks.length} open${finishedTasks.length ? ` · ${finishedTasks.length} finished` : ""}`;

  function renderTask(task: Task) {
    const relative = relativeDue(task.due_date);
    const highlighted = task.id === highlightedId;
    return (
      <article
        key={task.id}
        id={`task-${task.id}`}
        className={`rounded-2xl border border-l-2 px-3 py-3 ${PRIORITY_EDGE[task.priority] ?? "border-l-white/20"} ${highlighted ? "border-glow/70 bg-glow/10" : "border-white/10 bg-black/25"}`}
      >
        <div className="flex items-start gap-2">
          <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${PRIORITY_DOT[task.priority] ?? "bg-white/30"}`} />
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <h3 className="break-words text-sm font-medium leading-5">{task.title}</h3>
              {highlighted ? (
                <span className="shrink-0 rounded-full bg-glow/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-glow">
                  New
                </span>
              ) : null}
            </div>
            {task.description ? <p className="mt-1 break-words text-xs leading-5 text-mute">{task.description}</p> : null}
            <p className="mt-2 text-xs text-faint">
              <span className="text-white/80">{priorityLabel(task.priority)}</span>
              {" · "}
              {formatDue(task.due_date)}
              {relative ? ` · ${relative}` : ""}
            </p>
          </div>
        </div>
        <div className="mt-3 flex items-center justify-between gap-2">
          <label className="sr-only" htmlFor={`status-${task.id}`}>
            Status for {task.title}
          </label>
          <select
            id={`status-${task.id}`}
            value={task.status}
            disabled={disabled}
            onChange={(event) => void handleStatus(task, event.target.value as TaskStatus)}
            className={`rounded-lg border border-white/10 bg-ink px-2 py-1 text-xs outline-none ring-glow/60 focus:ring-2 disabled:opacity-40 ${STATUS_TONE[task.status]}`}
          >
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>
                {statusLabel(status)}
              </option>
            ))}
          </select>
          {pendingDeleteId === task.id ? (
            <div className="flex gap-2">
              <button type="button" onClick={() => void handleDelete(task.id)} className="text-xs text-bad">
                Confirm delete
              </button>
              <button type="button" onClick={() => setPendingDeleteId(null)} className="text-xs text-mute">
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              disabled={disabled}
              onClick={() => setPendingDeleteId(task.id)}
              className="text-xs text-faint hover:text-bad disabled:opacity-40"
            >
              Delete
            </button>
          )}
        </div>
      </article>
    );
  }

  return (
    <section aria-label="Tasks" className="flex h-full min-h-0 flex-col rounded-[28px] border border-white/10 bg-panel/95 shadow-panel backdrop-blur">
      <div className="border-b border-white/10 px-5 py-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-faint">Ledger</p>
            <h2 className="mt-1 text-xl font-medium tracking-[-0.03em]">Evening tasks</h2>
            <p className="mt-1 text-sm text-mute">{ledgerSummary}</p>
          </div>
          <button
            type="button"
            onClick={() => void onSeed()}
            disabled={disabled || seeding}
            className="rounded-full border border-glow/40 px-3 py-1.5 text-xs font-medium text-glow transition hover:bg-glow/10 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {seeding ? "Loading sample…" : "Load evening sample"}
          </button>
        </div>
        {notice ? <p className="mt-3 text-sm text-good">{notice}</p> : null}
        {error ? (
          <p role="alert" className="mt-3 text-sm text-bad">
            {error}
          </p>
        ) : null}
      </div>

      <div className="space-y-3 border-b border-white/10 px-5 py-4">
        <label className="block">
          <span className="sr-only">Search tasks</span>
          <input
            value={search}
            disabled={disabled}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search title or description"
            className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none ring-glow/60 placeholder:text-faint focus:ring-2"
          />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-xs text-mute">
            Status
            <select
              value={filters.status}
              disabled={disabled}
              onChange={(event) => onFilters({ ...filters, status: event.target.value as TaskFilters["status"] })}
              className="mt-1 w-full rounded-xl border border-white/10 bg-black/30 px-2 py-2 text-sm text-white outline-none ring-glow/60 focus:ring-2"
            >
              <option value="">All</option>
              {STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {statusLabel(status)}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-mute">
            Priority
            <select
              value={filters.priority}
              disabled={disabled}
              onChange={(event) => onFilters({ ...filters, priority: event.target.value as TaskFilters["priority"] })}
              className="mt-1 w-full rounded-xl border border-white/10 bg-black/30 px-2 py-2 text-sm text-white outline-none ring-glow/60 focus:ring-2"
            >
              <option value="">All</option>
              {PRIORITY_OPTIONS.map((item) => (
                <option key={item} value={item}>
                  {priorityLabel(item)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button
          type="button"
          onClick={() => setComposerOpen((open) => !open)}
          className="text-sm text-glow hover:underline"
        >
          {composerOpen ? "Close new task" : "New task"}
        </button>
        {composerOpen ? (
          <form onSubmit={handleCreate} className="space-y-2 rounded-2xl border border-white/10 bg-black/20 p-3">
            <label className="block text-xs text-mute">
              Title
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-ink px-3 py-2 text-sm text-white outline-none ring-glow/60 focus:ring-2"
              />
            </label>
            <label className="block text-xs text-mute">
              Description
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={2}
                className="mt-1 w-full resize-y rounded-xl border border-white/10 bg-ink px-3 py-2 text-sm text-white outline-none ring-glow/60 focus:ring-2"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs text-mute">
                Priority
                <select
                  value={priority}
                  onChange={(event) => setPriority(event.target.value as TaskPriority)}
                  className="mt-1 w-full rounded-xl border border-white/10 bg-ink px-2 py-2 text-sm text-white outline-none ring-glow/60 focus:ring-2"
                >
                  {PRIORITY_OPTIONS.map((item) => (
                    <option key={item} value={item}>
                      {priorityLabel(item)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs text-mute">
                Due
                <input
                  type="datetime-local"
                  value={due}
                  onChange={(event) => setDue(event.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/10 bg-ink px-2 py-2 text-sm text-white outline-none ring-glow/60 focus:ring-2"
                />
              </label>
            </div>
            {formError ? (
              <p role="alert" className="text-sm text-bad">
                {formError}
              </p>
            ) : null}
            <button
              type="submit"
              disabled={disabled || saving}
              className="rounded-full bg-white px-4 py-2 text-sm font-medium text-ink disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving ? "Saving…" : "Create task"}
            </button>
          </form>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-3">
        {rowError ? (
          <p role="alert" className="px-2 text-sm text-bad">
            {rowError}
          </p>
        ) : null}
        {loading && tasks.length === 0 ? (
          <div className="space-y-2 px-2" aria-hidden>
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-20 animate-pulse rounded-2xl bg-white/5" />
            ))}
          </div>
        ) : null}
        {!loading && tasks.length === 0 ? (
          <div className="mx-2 rounded-2xl border border-dashed border-white/15 px-4 py-8 text-sm leading-6 text-mute">
            <p className="text-base text-white">The ledger is clear.</p>
            <p className="mt-2">Load the evening sample to start the demo, or add a task. Completed work stays out of the evening order.</p>
          </div>
        ) : null}
        <div className="space-y-2">{visibleTasks.map((task) => renderTask(task))}</div>
        {!focusingFinished && finishedTasks.length > 0 ? (
          <div className="px-1 pt-2">
            <button
              type="button"
              onClick={() => setShowFinished((open) => !open)}
              className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-mute hover:text-white"
            >
              {showFinished ? "Hide" : "Show"} {finishedTasks.length} finished
            </button>
            {showFinished ? <div className="mt-2 space-y-2 opacity-80">{finishedTasks.map((task) => renderTask(task))}</div> : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
