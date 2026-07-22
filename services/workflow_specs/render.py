"""Deterministic workflow documentation renderers."""

from .model import WorkflowSpec


def render_markdown(spec: WorkflowSpec) -> str:
    """Render a stable decision table."""
    lines = [
        f"# {spec.title}",
        "",
        f"Spec: `{spec.id}`",
        "",
        "## Invariants",
        "",
        *[f"- {item}" for item in spec.invariants],
        "",
        "## Decision Table",
        "",
        "| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for step in sorted(spec.steps, key=lambda item: item.id):
        controls = _controls(step)
        if step.terminal:
            lines.append(
                f"| {step.id} | {step.actor} | {step.current_state} | {step.action} | - | terminal | - | - | {controls} |"
            )
        for transition in sorted(
            step.transitions,
            key=lambda item: (item.target, item.guard, item.outcome, item.next_state),
        ):
            lines.append(
                f"| {step.id} | {step.actor} | {step.current_state} | {step.action} | {transition.guard} | {transition.outcome} | {transition.next_state} | {transition.target} | {controls} |"
            )
    if spec.source_refs:
        lines.extend(("", "## Sources", "", *[f"- `{item}`" for item in spec.source_refs]))
    metadata = spec.metadata
    if metadata.governance_controls:
        lines.extend(("", "## Governance Controls", "", *[f"- {item}" for item in metadata.governance_controls]))
    if metadata.data_sources:
        lines.extend(("", "## Data and Persistence", "", *[f"- {item}" for item in metadata.data_sources]))
    if metadata.audit_controls:
        lines.extend(("", "## Audit Controls", "", *[f"- {item}" for item in metadata.audit_controls]))
    if metadata.test_refs:
        lines.extend(("", "## Tests", "", *[f"- `{item}`" for item in metadata.test_refs]))
    return "\n".join(lines) + "\n"


def render_mermaid(spec: WorkflowSpec) -> str:
    """Render a stable Mermaid flowchart."""
    lines = ["flowchart TD"]
    for step in sorted(spec.steps, key=lambda item: item.id):
        label = _escape(f"{step.id}: {step.action} [{step.actor}]")
        shape = f"(({label}))" if step.terminal else f"[{label}]"
        lines.append(f"    {step.id}{shape}")
    for step in sorted(spec.steps, key=lambda item: item.id):
        for transition in sorted(
            step.transitions,
            key=lambda item: (item.target, item.guard, item.outcome, item.next_state),
        ):
            label = _escape(
                f"{transition.guard} / {transition.outcome} -> {transition.next_state}"
            )
            lines.append(f"    {step.id} -->|{label}| {transition.target}")
    return "\n".join(lines) + "\n"


def _controls(step) -> str:
    names = []
    for enabled, name in (
        (step.entry, "entry"),
        (step.transaction_boundary, "transaction"),
        (step.external_side_effect, "external-side-effect"),
        (step.human_approval, "human-approval"),
        (step.retry_safe, "retry-safe"),
        (step.high_risk, "high-risk"),
        (step.terminal, "terminal"),
    ):
        if enabled:
            names.append(name)
    return ", ".join(names) or "-"


def _escape(value: str) -> str:
    return value.replace('"', "'").replace("|", "/")
