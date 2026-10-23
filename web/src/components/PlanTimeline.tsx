"use client";

import { formatDue, priorityLabel, relativeDue, statusLabel } from "@/lib/format";
import { argumentEntries, snapshotTasks, stepResult } from "@/lib/plan";
import type { PlanResponse } from "@/lib/types";

interface PlanTimelineProps {
  response: PlanResponse;
  mode: "preview" | "execute";
}

function pill(stepRequiresApproval: boolean, status: string | undefined, mode: "preview" | "execute") {
  if (status === "success") return { label: "Done", className: "bg-good/15 text-good" };
  if (status === "failed") return { label: "Failed", className: "bg-bad/15 text-bad" };
  if (status === "skipped" && stepRequiresApproval && mode === "preview") {
    return { label: "Needs approval", className: "bg-warn/15 text-warn" };
  }
  if (status === "skipped") return { label: "Skipped", className: "bg-warn/15 text-warn" };
  return { label: "Pending", className: "bg-white/10 text-mute" };
}

export function PlanTimeline({ response, mode }: PlanTimelineProps) {
  const banner =
    mode === "preview"
      ? "Preview only. No tasks were created or edited."
      : response.plan.some((_, index) => stepResult(response, index)?.status === "failed")
        ? "The backend reported a failure. Nothing below is inferred."
        : "Executed. Every status below came back from the backend.";

  const frame = mode === "preview" ? "border-warn/25" : "border-good/30";

  return (
    <section aria-label="Plan" className={`rounded-[28px] border bg-panel/95 p-5 shadow-panel backdrop-blur md:p-6 ${frame}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-faint">{mode === "preview" ? "Proposal" : "Backend report"}</p>
          <h2 className="mt-2 text-2xl font-medium tracking-[-0.03em]">{mode === "preview" ? "Proposed plan" : "Verified result"}</h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-mute">{banner}</p>
          <p className="mt-3 break-all font-mono text-[11px] text-faint">Request {response.request_id}</p>
        </div>
      </div>

      <p className="mt-4 rounded-2xl border border-white/10 bg-black/25 px-4 py-3 text-sm leading-6">
        <span className="text-faint">Intent · </span>
        {response.interpreted_intent}
      </p>

      <ol className="relative mt-6 space-y-3 before:absolute before:bottom-6 before:left-[15px] before:top-4 before:w-px before:bg-white/10">
        {response.plan.map((step, index) => {
          const result = stepResult(response, index);
          const badge = pill(step.requires_approval, result?.status, mode);
          const snapshots = snapshotTasks(result?.output);
          const showOrder = Boolean(snapshots && (snapshots.ordered || step.name.startsWith("Propose")));
          const entries = argumentEntries(step.arguments);
          return (
            <li key={`${step.name}-${index}`} className="grid grid-cols-[32px_minmax(0,1fr)] gap-3">
              <span className="relative z-10 mt-1 grid h-8 w-8 place-items-center rounded-full border border-white/15 bg-ink text-xs text-white">
                {index + 1}
              </span>
              <article className="rounded-2xl border border-white/10 bg-black/25 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-medium">{step.name}</h3>
                    <p className="mt-1 font-mono text-[11px] uppercase tracking-wide text-faint">
                      {step.tool}
                      {step.requires_approval ? " · approval required" : " · read only"}
                    </p>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${badge.className}`}>{badge.label}</span>
                </div>
                <p className="mt-3 text-sm leading-6 text-mute">{step.expected_result}</p>
                {result?.detail ? (
                  <p className="mt-2 text-sm text-white/90">
                    <span className="text-faint">{result.status} · </span>
                    {result.detail}
                  </p>
                ) : null}
                {entries.length > 0 ? (
                  <dl className="mt-3 grid gap-1 text-sm">
                    {entries.map(([key, value]) => (
                      <div key={key} className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
                        <dt className="text-faint">{key}</dt>
                        <dd className="break-words">{value}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
                {showOrder && snapshots ? (
                  snapshots.tasks.length === 0 ? (
                    <p className="mt-3 text-sm text-mute">No unfinished tasks to order.</p>
                  ) : (
                    <ol className="mt-4 space-y-2">
                      {snapshots.tasks.map((task, taskIndex) => (
                        <li key={`${task.id ?? task.title}-${taskIndex}`} className="flex items-start justify-between gap-3 rounded-xl bg-white/[0.04] px-3 py-2">
                          <div className="min-w-0">
                            <p className="break-words text-sm">
                              <span className="mr-2 text-faint">{taskIndex + 1}</span>
                              {task.title}
                            </p>
                            <p className="mt-1 text-xs text-faint">
                              {task.priority ? priorityLabel(task.priority) : "Unset"}
                              {task.status ? ` · ${statusLabel(task.status)}` : ""}
                              {task.due_date ? ` · ${formatDue(task.due_date)}` : " · No deadline"}
                              {relativeDue(task.due_date) ? ` · ${relativeDue(task.due_date)}` : ""}
                            </p>
                          </div>
                        </li>
                      ))}
                    </ol>
                  )
                ) : null}
                {!showOrder && snapshots ? (
                  <p className="mt-3 text-sm text-mute">
                    Read {snapshots.tasks.length} unfinished {snapshots.tasks.length === 1 ? "task" : "tasks"}.
                  </p>
                ) : null}
              </article>
            </li>
          );
        })}
      </ol>

      <p className="mt-5 rounded-2xl bg-white/[0.04] px-4 py-3 text-sm leading-6">{response.final_summary}</p>
    </section>
  );
}
