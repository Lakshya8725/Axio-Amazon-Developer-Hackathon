import type { Task, TaskPriority, TaskStatus } from "./types";

export function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return "Something went wrong.";
}

export function isAbortError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    (error as { name?: string }).name === "AbortError"
  );
}

export function formatApiError(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return null;
        })
        .filter((item): item is string => Boolean(item));
      if (messages.length) return messages.join(" ");
    }
  }
  if (status >= 500) return `The backend returned ${status}.`;
  return `Request failed (${status}).`;
}

export function parseApiDate(value: string): Date {
  const trimmed = value.trim();
  const hasZone = /(?:z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
  return new Date(hasZone ? trimmed : `${trimmed}Z`);
}

export function formatDue(value: string | null | undefined): string {
  if (!value) return "No deadline";
  const date = parseApiDate(value);
  if (Number.isNaN(date.getTime())) return "No deadline";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function relativeDue(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = parseApiDate(value);
  if (Number.isNaN(date.getTime())) return null;
  const hours = Math.round((date.getTime() - Date.now()) / 3_600_000);
  if (Math.abs(hours) < 48) {
    if (hours === 0) return "due now";
    return hours > 0 ? `due in ${hours}h` : `${Math.abs(hours)}h overdue`;
  }
  const days = Math.round(hours / 24);
  return days > 0 ? `due in ${days}d` : `${Math.abs(days)}d overdue`;
}

export function statusLabel(status: TaskStatus | string): string {
  switch (status) {
    case "in_progress":
      return "In progress";
    case "pending":
      return "Pending";
    case "completed":
      return "Completed";
    case "cancelled":
      return "Cancelled";
    default:
      return status;
  }
}

export function priorityLabel(priority: TaskPriority | string): string {
  if (!priority) return "Unset";
  return priority.charAt(0).toUpperCase() + priority.slice(1);
}

export function taskFingerprint(tasks: Task[]): string {
  return tasks
    .map((task) => [task.id, task.status, task.priority, task.title, task.updated_at, task.due_date ?? ""].join("~"))
    .sort()
    .join("|");
}

export function fromDateTimeLocal(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}
