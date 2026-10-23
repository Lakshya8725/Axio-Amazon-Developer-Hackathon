import { formatApiError } from "./format";
import type {
  HealthResponse,
  PlanResponse,
  PreferencesResponse,
  Task,
  TaskCreateInput,
  TaskFilters,
  TaskListResponse,
  TaskUpdateInput,
} from "./types";

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "/axio-api").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    if (typeof error === "object" && error !== null && "name" in error && (error as { name: string }).name === "AbortError") {
      throw error;
    }
    throw new Error(
      "Cannot reach Axio. Start the backend with: .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000",
    );
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text.slice(0, 180) };
    }
  }

  if (!response.ok) {
    const message = formatApiError(body, response.status);
    if (response.status >= 500) {
      throw new Error(`${message} Confirm FastAPI is running on http://127.0.0.1:8000.`);
    }
    throw new Error(message);
  }

  return body as T;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { signal });
}

export function getPreferences(signal?: AbortSignal): Promise<PreferencesResponse> {
  return request<PreferencesResponse>("/api/preferences", { signal });
}

export function listTasks(filters: TaskFilters = { status: "", priority: "", search: "" }, signal?: AbortSignal) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.priority) params.set("priority", filters.priority);
  if (filters.search.trim()) params.set("search", filters.search.trim());
  params.set("limit", "100");
  const query = params.toString();
  return request<TaskListResponse>(`/api/tasks${query ? `?${query}` : ""}`, { signal });
}

export function createTask(input: TaskCreateInput): Promise<Task> {
  return request<Task>("/api/tasks", { method: "POST", body: JSON.stringify(input) });
}

export function updateTask(taskId: number, patch: TaskUpdateInput): Promise<Task> {
  return request<Task>(`/api/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(patch) });
}

export function deleteTask(taskId: number): Promise<void> {
  return request<void>(`/api/tasks/${taskId}`, { method: "DELETE" });
}

export function runAgent(instruction: string, dryRun: boolean, approve: boolean): Promise<PlanResponse> {
  return request<PlanResponse>("/api/agent/run", {
    method: "POST",
    body: JSON.stringify({ instruction, dry_run: dryRun, approve }),
  });
}
