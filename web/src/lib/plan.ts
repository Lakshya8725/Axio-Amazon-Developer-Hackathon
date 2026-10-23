import type { ExecutionResult, PlanResponse, TaskSnapshot } from "./types";

export function stepResult(response: PlanResponse, index: number): ExecutionResult | undefined {
  return response.step_results[String(index)];
}

export function snapshotTasks(output: unknown): { ordered: boolean; tasks: TaskSnapshot[] } | null {
  if (!output || typeof output !== "object") return null;
  const record = output as { tasks?: unknown; ordered?: unknown };
  if (!Array.isArray(record.tasks)) return null;
  const tasks = record.tasks.filter((item): item is TaskSnapshot => Boolean(item) && typeof item === "object");
  return { ordered: record.ordered === true, tasks };
}

export function createdTaskId(response: PlanResponse): number | null {
  return createOutcome(response)?.id ?? null;
}

export function createOutcome(response: PlanResponse): { id: number; reused: boolean } | null {
  for (let index = 0; index < response.plan.length; index += 1) {
    const step = response.plan[index];
    const result = stepResult(response, index);
    if (step.tool !== "create_task" || result?.status !== "success" || !result.output) continue;
    if (typeof result.output !== "object" || !("id" in result.output)) continue;
    const id = (result.output as { id?: unknown }).id;
    if (typeof id !== "number") continue;
    const detail = (result.detail ?? "").toLowerCase();
    return { id, reused: detail.includes("already exists") };
  }
  return null;
}

export function argumentEntries(args: Record<string, unknown>): Array<[string, string]> {
  return Object.entries(args).map(([key, value]) => {
    if (value == null || value === "") return [key, "—"];
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return [key, String(value)];
    }
    return [key, JSON.stringify(value)];
  });
}
