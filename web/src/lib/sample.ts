import { createTask, listTasks, updateTask } from "./api";
import type { TaskPriority, TaskStatus } from "./types";

interface SampleTask {
  title: string;
  description: string;
  priority: TaskPriority;
  dueInHours: number | null;
  status: TaskStatus;
}

const SAMPLES: SampleTask[] = [
  {
    title: "Confirm recruiter callback",
    description: "Lock the conversation before the evening block.",
    priority: "urgent",
    dueInHours: 3,
    status: "pending",
  },
  {
    title: "Draft hackathon demo outline",
    description: "Sequence the live path: intent, preview, approval, result.",
    priority: "high",
    dueInHours: 6,
    status: "in_progress",
  },
  {
    title: "Finish system design revision",
    description: "One focused pass on the last open questions.",
    priority: "high",
    dueInHours: 26,
    status: "pending",
  },
  {
    title: "Leave a 45-minute workout window",
    description: "Protect time so the evening plan stays realistic.",
    priority: "medium",
    dueInHours: null,
    status: "pending",
  },
  {
    title: "Reply to family about dinner",
    description: "A short message so it does not spill into focus time.",
    priority: "low",
    dueInHours: 30,
    status: "pending",
  },
  {
    title: "Send yesterday's standup notes",
    description: "Already done. Axio should leave this out of the evening order.",
    priority: "low",
    dueInHours: -20,
    status: "completed",
  },
];

export async function loadEveningSample(): Promise<string> {
  const now = Date.now();
  let created = 0;

  for (const sample of SAMPLES) {
    const existing = await listTasks({ status: "", priority: "", search: sample.title });
    if (existing.tasks.some((task) => task.title === sample.title)) continue;

    const task = await createTask({
      title: sample.title,
      description: sample.description,
      priority: sample.priority,
      due_date: sample.dueInHours == null ? null : new Date(now + sample.dueInHours * 3_600_000).toISOString(),
    });
    created += 1;
    if (sample.status !== "pending") {
      await updateTask(task.id, { status: sample.status });
    }
  }

  if (created === 0) return "Evening sample is already loaded.";
  return created === 1 ? "Added 1 sample task." : `Added ${created} sample tasks.`;
}
