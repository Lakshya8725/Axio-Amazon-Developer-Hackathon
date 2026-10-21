"""Schemas for the agent orchestration layer.

The request body contains a free‑form natural‑language instruction and optional flags.
The response returns a deterministic plan, step‑by‑step status, and any generated results.
"""

from __future__ import annotations

from typing import List, Optional, Literal, Dict

from pydantic import BaseModel, Field, validator

# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------
class AgentRunRequest(BaseModel):
    """Incoming request to run the orchestration agent.

    * ``instruction`` – free‑form user request.
    * ``dry_run`` – when ``True`` the plan is only previewed, no state‑changing
      actions are executed.
    * ``approve`` – explicit approval flag for any consequential actions
      (e.g., task creation). If ``False`` those steps are marked as
      ``requires_approval`` and are not executed.
    """

    instruction: str = Field(..., description="User natural‑language request")
    dry_run: bool = Field(False, description="Preview only, do not perform actions")
    approve: bool = Field(False, description="Approve consequential actions when previewing")

    @validator("instruction")
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("instruction must not be empty")
        return v.strip()

# ---------------------------------------------------------------------------
# Plan and step definitions
# ---------------------------------------------------------------------------
class PlanStep(BaseModel):
    """A single step in the generated plan.

    * ``name`` – human readable label.
    * ``tool`` – which backend tool will be called (e.g. ``get_tasks``).
    * ``arguments`` – validated arguments passed to the tool.
    * ``requires_approval`` – whether the step must be approved before execution.
    * ``expected_result`` – description of what the step should return.
    """

    name: str = Field(..., description="Descriptive name of the step")
    tool: Literal["get_tasks", "create_task", "update_task_status", "get_user_preferences"]
    arguments: Dict[str, object] = Field(default_factory=dict)
    requires_approval: bool = Field(False)
    expected_result: str = Field(...)

class ExecutionResult(BaseModel):
    """Result of executing a single step.

    * ``status`` – ``success``, ``failed`` or ``skipped``.
    * ``detail`` – any error message or useful information.
    * ``output`` – raw tool output when applicable (e.g. created task dict).
    """

    status: Literal["success", "failed", "skipped"]
    detail: Optional[str] = None
    output: Optional[object] = None

class PlanResponse(BaseModel):
    """Full response returned by the ``/api/agent/run`` endpoint.

    * ``request_id`` – unique identifier for this run (UUID string).
    * ``interpreted_intent`` – concise summary of the parsed user intent.
    * ``plan`` – ordered list of steps.
    * ``step_results`` – results keyed by step index.
    * ``final_summary`` – human‑readable outcome.
    """

    request_id: str = Field(..., description="UUID of this orchestration request")
    interpreted_intent: str = Field(..., description="Brief summary of the user's goal")
    plan: List[PlanStep]
    step_results: Dict[int, ExecutionResult] = Field(default_factory=dict)
    final_summary: str = Field(..., description="Overall result of the orchestration run")
