// app.js – Axio demo UI logic (vanilla JS)
const BASE_URL = "http://127.0.0.1:8000";

// DOM elements
const healthEl = document.getElementById("health");
const previewBtn = document.getElementById("previewBtn");
const executeBtn = document.getElementById("executeBtn");
const instructionEl = document.getElementById("instruction");
const loadingEl = document.getElementById("loading");
const errorEl = document.getElementById("error");
const planSection = document.getElementById("planSection");
const planList = document.getElementById("planList");
const finalSummary = document.getElementById("finalSummary");

/** Utility: show/hide loading indicator */
function setLoading(on) {
  loadingEl.classList.toggle("hidden", !on);
}
/** Utility: display error message */
function showError(msg) {
  errorEl.textContent = msg;
  errorEl.classList.toggle("hidden", !msg);
}
/** Reset plan UI */
function resetPlanUI() {
  planList.innerHTML = "";
  finalSummary.textContent = "";
  errorEl.classList.add("hidden");
  planSection.classList.remove("hidden");
}
/** Render plan and step results */
function renderResponse(data) {
  resetPlanUI();
  // steps
  data.plan.forEach((step, idx) => {
    const li = document.createElement("li");
    const nameSpan = document.createElement("span");
    nameSpan.textContent = step.name;
    const statusSpan = document.createElement("span");
    const result = data.step_results[idx] || {};
    const status = result.status || "unknown";
    statusSpan.textContent = status;
    statusSpan.className = `status ${status}`;
    li.append(nameSpan, statusSpan);
    planList.appendChild(li);
  });
  finalSummary.textContent = data.final_summary || "";
}
/** Perform health check */
async function checkHealth() {
  try {
    const r = await fetch(`${BASE_URL}/health`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    healthEl.textContent = "✅ Healthy";
    healthEl.className = "health healthy";
  } catch (e) {
    healthEl.textContent = "❌ Unavailable";
    healthEl.className = "health unhealthy";
  }
}
checkHealth();
instructionEl.addEventListener("input", () => {
  if (
    window._lastPreviewInstruction &&
    instructionEl.value.trim() !== window._lastPreviewInstruction
  ) {
    executeBtn.disabled = true;
  }
});
/** Preview (dry‑run) */
previewBtn.addEventListener("click", async () => {
  // disable both buttons while request is in flight
  previewBtn.disabled = true;
  executeBtn.disabled = true;
  setLoading(true);
  showError("");
  const payload = {
    instruction: instructionEl.value.trim(),
    dry_run: true,
    approve: false,
  };
  if (!payload.instruction) {
    showError("Instruction cannot be empty.");
    setLoading(false);
    previewBtn.disabled = false;
    return;
  }
  try {
    const r = await fetch(`${BASE_URL}/api/agent/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const resp = await r.json();
    if (!r.ok) throw new Error(resp.detail || `HTTP ${r.status}`);
    renderResponse(resp);
    // Enable Execute only if any step requires approval
    const needsApproval = resp.plan.some(step => step.requires_approval);
    executeBtn.disabled = !needsApproval;
    // Store the last preview response for later confirmation display
    window._lastPreview = resp;
    window._lastPreviewInstruction = payload.instruction;
  } catch (e) {
    showError(e.message);
  } finally {
    setLoading(false);
    previewBtn.disabled = false;
  }
});
/** Execute (approved) */
executeBtn.addEventListener("click", async () => {
  if (!window._lastPreview) return; // safety guard
  // Show a confirmation dialog containing the actions that will be performed
  const actionableSteps = window._lastPreview.plan
    .filter(step => step.requires_approval)
    .map(step => `- ${step.name}: ${JSON.stringify(step.arguments)}`)
    .join("\n");
  const confirmMsg = `The following actions will be performed:\n${actionableSteps}\n\nProceed?`;
  if (!window.confirm(confirmMsg)) return;

  previewBtn.disabled = true;
  executeBtn.disabled = true;
  setLoading(true);
  showError("");
  const payload = {
    instruction: window._lastPreviewInstruction,
    dry_run: false,
    approve: true,
  };
  try {
    const r = await fetch(`${BASE_URL}/api/agent/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const resp = await r.json();
    if (!r.ok) throw new Error(resp.detail || `HTTP ${r.status}`);
    renderResponse(resp);
  } catch (e) {
    showError(e.message);
  } finally {
    setLoading(false);
    previewBtn.disabled = false;
    // after execution, re‑run preview to refresh approval status
    executeBtn.disabled = true;
  }
});
