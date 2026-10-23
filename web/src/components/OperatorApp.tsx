"use client";

import { useCallback, useEffect, useState } from "react";
import { getHealth, getPreferences, listTasks, runAgent, createTask, updateTask, deleteTask } from "@/lib/api";
import { errorMessage, isAbortError, taskFingerprint } from "@/lib/format";
import { createOutcome } from "@/lib/plan";
import { loadEveningSample } from "@/lib/sample";
import { DEMO_INSTRUCTION, type HealthResponse, type PlanResponse, type Task, type TaskCreateInput, type TaskFilters, type TaskUpdateInput } from "@/lib/types";
import { PlanTimeline } from "./PlanTimeline";
import { TaskBoard } from "./TaskBoard";

type HealthState =
  | { state: "checking" }
  | { state: "up"; data: HealthResponse }
  | { state: "down"; message: string };

interface SavedRun {
  instruction: string;
  mode: "preview" | "execute";
  response: PlanResponse;
}

const EMPTY_FILTERS: TaskFilters = { status: "", priority: "", search: "" };

export function OperatorApp() {
  const [instruction, setInstruction] = useState(DEMO_INSTRUCTION);
  const [health, setHealth] = useState<HealthState>({ state: "checking" });
  const [policy, setPolicy] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<TaskFilters>(EMPTY_FILTERS);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [taskError, setTaskError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [run, setRun] = useState<SavedRun | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [drift, setDrift] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState<"preview" | "execute" | "seed" | null>(null);
  const [highlightedId, setHighlightedId] = useState<number | null>(null);
  const [mobileView, setMobileView] = useState<"operate" | "tasks">("operate");

  const refreshTasks = useCallback(async (nextFilters: TaskFilters = filters) => {
    const data = await listTasks(nextFilters);
    setTasks(data.tasks);
    setTotal(data.total);
    return data.tasks;
  }, [filters]);

  useEffect(() => {
    const controller = new AbortController();
    setTasksLoading(true);
    setTaskError(null);
    listTasks(filters, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setTasks(data.tasks);
        setTotal(data.total);
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) return;
        setTaskError(errorMessage(error));
        setTasks([]);
        setTotal(0);
      })
      .finally(() => {
        if (!controller.signal.aborted) setTasksLoading(false);
      });
    return () => controller.abort();
  }, [filters]);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const data = await getHealth(controller.signal);
        setHealth({ state: "up", data });
        try {
          const preferences = await getPreferences(controller.signal);
          setPolicy(preferences.preferences.confirm_consequential_actions ?? null);
        } catch (error) {
          if (!isAbortError(error)) setPolicy(null);
        }
      } catch (error) {
        if (isAbortError(error)) return;
        setHealth({ state: "down", message: errorMessage(error) });
      }
    }
    void load();
    const timer = window.setInterval(() => void load(), 15000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    setConfirmed(false);
  }, [run?.response.request_id]);

  const offline = health.state === "down";
  const locked = busy !== null || offline;
  const trimmed = instruction.trim();
  const previewReady = Boolean(run && run.mode === "preview" && run.instruction === trimmed);
  const approvalSteps = previewReady ? run!.response.plan.filter((step) => step.requires_approval) : [];
  const canExecute = previewReady && approvalSteps.length > 0 && confirmed && !locked && !drift;

  async function handlePreview() {
    if (!trimmed || locked) return;
    const before = taskFingerprint(tasks);
    const canCompare = !tasksLoading;
    setBusy("preview");
    setRunError(null);
    setDrift(false);
    setHighlightedId(null);
    try {
      const response = await runAgent(trimmed, true, false);
      setRun({ instruction: trimmed, mode: "preview", response });
      try {
        const after = await refreshTasks();
        if (canCompare) setDrift(taskFingerprint(after) !== before);
      } catch (error) {
        setTaskError(errorMessage(error));
      }
    } catch (error) {
      setRun(null);
      setRunError(errorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function handleExecute() {
    if (!run || !canExecute) return;
    setBusy("execute");
    setRunError(null);
    setDrift(false);
    try {
      const response = await runAgent(run.instruction, false, true);
      setRun({ instruction: run.instruction, mode: "execute", response });
      setHighlightedId(createOutcome(response)?.id ?? null);
      try {
        await refreshTasks();
      } catch (error) {
        setTaskError(errorMessage(error));
      }
    } catch (error) {
      setRunError(errorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function handleSeed() {
    if (locked) return;
    setBusy("seed");
    setNotice(null);
    setTaskError(null);
    try {
      const message = await loadEveningSample();
      setNotice(message);
      await refreshTasks();
    } catch (error) {
      setTaskError(errorMessage(error));
      try {
        await refreshTasks();
      } catch {
        // The original error is the one to show.
      }
    } finally {
      setBusy(null);
    }
  }

  async function handleCreate(input: TaskCreateInput) {
    await createTask(input);
    setNotice("Task created.");
    await refreshTasks();
  }

  async function handleUpdate(id: number, patch: TaskUpdateInput) {
    await updateTask(id, patch);
    await refreshTasks();
  }

  async function handleDelete(id: number) {
    await deleteTask(id);
    if (highlightedId === id) setHighlightedId(null);
    setNotice("Task deleted.");
    await refreshTasks();
  }

  const outcome = run?.mode === "execute" ? createOutcome(run.response) : null;
  const stage: StageId =
    !run || trimmed !== run.instruction ? "instruction" : run.mode === "execute" ? "result" : approvalSteps.length > 0 ? "approval" : "preview";
  const stageCaption =
    stage === "approval"
      ? "One write is waiting: the interview preparation block. The ledger stays unchanged until you approve."
      : stage === "result"
        ? "This report is the backend’s own result. Preview again to confirm the interview block is not duplicated."
        : stage === "preview"
          ? "Nothing in this plan needs a write. Running it again will not create a second interview task."
          : "State the evening. Preview is read-only. Axio writes only after you approve.";

  return (
    <div className="relative mx-auto flex min-h-screen max-w-[1360px] flex-col px-4 py-6 md:px-8 md:py-8">
      <header className="flex flex-wrap items-end justify-between gap-5 border-b border-white/10 pb-6">
        <div className="flex items-center gap-4">
          <span className="grid h-12 w-12 place-items-center rounded-2xl border border-glow/40 bg-gradient-to-br from-glow/20 to-transparent shadow-[0_0_32px_rgba(126,231,255,0.12)]" aria-hidden>
            <svg viewBox="0 0 24 24" className="h-5 w-5 text-glow" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M5 12h11" strokeLinecap="round" />
              <path d="M12 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-glow">Amazon AppDev · Alexa+</p>
            <h1 className="mt-1 text-[2rem] font-medium leading-none tracking-[-0.04em]">Axio</h1>
            <p className="mt-2 text-sm text-mute">Your intent. In action.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-mute">Human approval before every write</span>
          <HealthPill health={health} />
        </div>
      </header>

      <StageRail stage={stage} caption={stageCaption} />

      <div className="mt-4 grid grid-cols-2 gap-2 lg:hidden">
        {(["operate", "tasks"] as const).map((view) => (
          <button
            key={view}
            type="button"
            onClick={() => setMobileView(view)}
            className={`rounded-full px-3 py-2 text-sm ${mobileView === view ? "bg-white text-ink" : "border border-white/10 text-mute"}`}
          >
            {view === "operate" ? "Brief" : "Ledger"}
          </button>
        ))}
      </div>

      <div className="mt-5 grid min-h-0 flex-1 gap-5 lg:grid-cols-[minmax(0,1fr)_390px]">
        <main className={`space-y-4 ${mobileView === "tasks" ? "hidden lg:block" : ""}`}>
          {health.state === "down" ? (
            <div role="alert" className="rounded-2xl border border-bad/40 bg-bad/10 px-4 py-3 text-sm leading-6">
              <p>{health.message}</p>
              <code className="mt-2 block break-words font-mono text-xs text-white/80">
                .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
              </code>
            </div>
          ) : null}

          <section className="rounded-[28px] border border-white/10 bg-panel/95 p-5 shadow-panel backdrop-blur md:p-6">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-faint">Instruction</p>
                <h2 className="mt-2 text-2xl font-medium tracking-[-0.03em]">Organize the evening</h2>
                <p className="mt-2 max-w-xl text-sm leading-6 text-mute">
                  Axio reads unfinished work, proposes an order, and holds the interview block until you confirm it.
                </p>
              </div>
              <button type="button" onClick={() => setInstruction(DEMO_INSTRUCTION)} className="rounded-full border border-white/10 px-3 py-1.5 text-sm text-glow transition hover:border-glow/40">
                Restore demo line
              </button>
            </div>
            <label htmlFor="instruction" className="sr-only">
              Instruction for Axio
            </label>
            <textarea
              id="instruction"
              value={instruction}
              disabled={busy !== null}
              onChange={(event) => setInstruction(event.target.value)}
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                  event.preventDefault();
                  void handlePreview();
                }
              }}
              rows={4}
              className="mt-5 w-full resize-y rounded-2xl border border-white/10 border-l-glow/70 bg-black/40 px-4 py-4 text-lg leading-8 tracking-[-0.01em] outline-none ring-glow/50 focus:ring-2 disabled:opacity-60"
            />
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void handlePreview()}
                disabled={locked || !trimmed}
                className="rounded-full bg-glow px-5 py-2.5 text-sm font-semibold text-ink shadow-[0_0_24px_rgba(126,231,255,0.18)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
              >
                {busy === "preview" ? "Reading the ledger…" : "Preview plan"}
              </button>
              <p className="max-w-md text-xs leading-5 text-faint">⌘/Ctrl + Enter. This demonstration recognizes the evening instruction above.</p>
            </div>
          </section>

          {run && trimmed !== run.instruction ? (
            <p className="rounded-2xl border border-warn/30 bg-warn/10 px-4 py-3 text-sm text-warn">
              The instruction changed after the last plan. Preview again before approving anything.
            </p>
          ) : null}

          {runError ? (
            <div role="alert" className="rounded-2xl border border-bad/40 bg-bad/10 px-4 py-3 text-sm leading-6">
              <p>{runError}</p>
              {runError.includes("Unable to interpret") ? (
                <p className="mt-2 text-white/80">Use the demo instruction. Axio does not invent a plan for unsupported requests.</p>
              ) : null}
            </div>
          ) : null}

          {drift ? (
            <p role="alert" className="rounded-2xl border border-bad/40 bg-bad/10 px-4 py-3 text-sm">
              The task list changed during preview. Preview is supposed to be read-only, so approval stays disabled.
            </p>
          ) : null}

          {busy === "preview" || busy === "execute" ? (
            <div className="h-1 overflow-hidden rounded-full bg-white/10" aria-hidden>
              <div className="h-full w-1/3 animate-pulse bg-glow" />
            </div>
          ) : null}

          {run && run.instruction === trimmed ? <PlanTimeline response={run.response} mode={run.mode} /> : null}

          {previewReady && approvalSteps.length === 0 ? (
            <p className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm leading-6 text-mute">
              This preview has no writes. Nothing needs approval, and running it again will not create a duplicate interview task.
            </p>
          ) : null}

          {previewReady && approvalSteps.length > 0 ? (
            <section className="rounded-[28px] border border-warn/50 bg-gradient-to-b from-warn/15 to-warn/5 p-5 md:p-6">
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-warn">Approval required</p>
              <h2 className="mt-2 text-2xl font-medium tracking-[-0.03em]">Confirm the write</h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-white/80">
                The plan above is still a proposal. Axio rebuilds it on the server and creates the task only after this confirmation.
              </p>
              <ul className="mt-4 space-y-3">
                {approvalSteps.map((step) => (
                  <li key={step.name} className="rounded-2xl border border-white/10 bg-black/30 p-4">
                    <p className="text-sm font-medium">{step.name}</p>
                    <p className="mt-1 text-sm text-mute">{step.expected_result}</p>
                    <dl className="mt-3 grid gap-1 text-sm">
                      {Object.entries(step.arguments).map(([key, value]) => (
                        <div key={key} className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
                          <dt className="text-faint">{key}</dt>
                          <dd className="break-words">{value == null || value === "" ? "—" : String(value)}</dd>
                        </div>
                      ))}
                    </dl>
                  </li>
                ))}
              </ul>
              <label className="mt-4 flex items-start gap-3 text-sm leading-6">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                  className="mt-1 h-4 w-4 accent-glow"
                />
                <span>Apply these changes to my task list.</span>
              </label>
              <button
                type="button"
                onClick={() => void handleExecute()}
                disabled={!canExecute}
                className="mt-5 rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy === "execute" ? "Writing to the ledger…" : "Approve and execute"}
              </button>
            </section>
          ) : null}

          {outcome && !outcome.reused ? (
            <p className="text-sm text-mute">
              The new task is highlighted in the ledger. Preview again to see where interview preparation sits in the evening order.
            </p>
          ) : null}
          {outcome?.reused ? (
            <p className="text-sm text-mute">The backend reused the existing task. No duplicate was created.</p>
          ) : null}
        </main>

        <aside className={`lg:sticky lg:top-5 lg:h-[calc(100vh-7.5rem)] ${mobileView === "operate" ? "hidden lg:block" : ""}`}>
          <TaskBoard
            tasks={tasks}
            total={total}
            loading={tasksLoading}
            error={taskError}
            notice={notice}
            filters={filters}
            highlightedId={highlightedId}
            disabled={locked}
            seeding={busy === "seed"}
            onFilters={setFilters}
            onCreate={handleCreate}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
            onSeed={() => handleSeed()}
          />
        </aside>
      </div>

      <footer className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4 font-mono text-[11px] text-faint">
        <p>
          {health.state === "up"
            ? `${health.data.app} ${health.data.version} · ${health.data.environment} · MCP ${health.data.mcp_endpoint}`
            : "Axio · waiting for the API"}
          {policy ? ` · confirm_consequential_actions=${policy}` : ""}
        </p>
        <p>Preview does not mutate tasks.</p>
      </footer>
    </div>
  );
}

const STAGES = [
  { id: "instruction", label: "Instruction" },
  { id: "preview", label: "Preview" },
  { id: "approval", label: "Approval" },
  { id: "result", label: "Verified" },
] as const;

type StageId = (typeof STAGES)[number]["id"];

function StageRail({ stage, caption }: { stage: StageId; caption: string }) {
  const current = STAGES.findIndex((item) => item.id === stage);
  return (
    <section className="mt-6" aria-label="Demo progress">
      <ol className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {STAGES.map((item, index) => {
          const state = index < current ? "done" : index === current ? "current" : "upcoming";
          const tone =
            state === "done"
              ? "border-good/30 bg-good/10 text-good"
              : state === "current"
                ? "border-glow/50 bg-glow/10 text-white shadow-[0_0_24px_rgba(126,231,255,0.08)]"
                : "border-white/10 bg-white/[0.02] text-faint";
          return (
            <li key={item.id} aria-current={state === "current" ? "step" : undefined} className={`rounded-2xl border px-4 py-3 ${tone}`}>
              <p className="font-mono text-[11px] tracking-[0.14em]">{String(index + 1).padStart(2, "0")}</p>
              <p className="mt-1 text-sm font-medium text-white">{item.label}</p>
              <p className="mt-1 text-xs opacity-80">{state === "done" ? "Complete" : state === "current" ? "Now" : "Waiting"}</p>
            </li>
          );
        })}
      </ol>
      <p className="mt-3 text-sm leading-6 text-mute">{caption}</p>
    </section>
  );
}

function HealthPill({ health }: { health: HealthState }) {
  if (health.state === "checking") {
    return <span className="rounded-full bg-white/10 px-3 py-1.5 text-xs text-mute">Connecting</span>;
  }
  if (health.state === "down") {
    return <span className="rounded-full bg-bad/15 px-3 py-1.5 text-xs text-bad">API offline</span>;
  }
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-good/15 px-3 py-1.5 text-xs text-good">
      <span className="h-1.5 w-1.5 rounded-full bg-good motion-safe:animate-pulse" />
      Operator live
    </span>
  );
}
