export type TaskStatus = "pending" | "in_progress" | "completed" | "cancelled";
export type TaskPriority = "low" | "medium" | "high" | "urgent";

export interface Task {
  id: number;
  title: string;
  description: string | null;
  priority: TaskPriority;
  status: TaskStatus;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskListResponse {
  tasks: Task[];
  total: number;
  filters: {
    status: string | null;
    priority: string | null;
    search: string | null;
    limit: number;
    offset: number;
  };
}

export interface TaskCreateInput {
  title: string;
  description?: string | null;
  priority?: TaskPriority;
  due_date?: string | null;
}

export interface TaskUpdateInput {
  title?: string;
  description?: string | null;
  priority?: TaskPriority;
  status?: TaskStatus;
  due_date?: string | null;
}

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  environment: string;
  mcp_endpoint: string;
}

export interface PreferencesResponse {
  preferences: Record<string, string>;
  category: string | null;
}

export interface PlanStep {
  name: string;
  tool: "get_tasks" | "create_task" | "update_task_status" | "get_user_preferences";
  arguments: Record<string, unknown>;
  requires_approval: boolean;
  expected_result: string;
}

export interface ExecutionResult {
  status: "success" | "failed" | "skipped";
  detail?: string | null;
  output?: unknown;
}

export interface PlanResponse {
  request_id: string;
  interpreted_intent: string;
  plan: PlanStep[];
  step_results: Record<string, ExecutionResult>;
  final_summary: string;
}

export interface TaskFilters {
  status: "" | TaskStatus;
  priority: "" | TaskPriority;
  search: string;
}

export interface TaskSnapshot {
  id?: number;
  title?: string;
  description?: string | null;
  priority?: string;
  status?: string;
  due_date?: string | null;
}

export const DEMO_INSTRUCTION =
  "Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation.";

export const STATUS_OPTIONS: TaskStatus[] = ["pending", "in_progress", "completed", "cancelled"];
export const PRIORITY_OPTIONS: TaskPriority[] = ["urgent", "high", "medium", "low"];
