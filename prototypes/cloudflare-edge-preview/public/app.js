async function renderHealth() {
  const healthOutput = document.querySelector("#health-result");
  if (!(healthOutput instanceof HTMLElement)) return;

  try {
    const response = await fetch("/healthz", {
      headers: { accept: "application/json" },
    });
    const result = await response.json();

    if (!response.ok || result.backendConnected !== false) {
      throw new Error("Unexpected preview health response");
    }

    healthOutput.textContent = "Worker responds; KI backend remains disconnected.";
  } catch {
    healthOutput.textContent = "Worker health check unavailable; no backend is configured.";
  }
}

void renderHealth();
