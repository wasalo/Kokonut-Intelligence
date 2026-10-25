"use strict";

const $ = (selector) => document.querySelector(selector);
const statusNode = $("#status");
const consentPanel = $("#consent");
const workspacePanel = $("#workspace");
const inviteStorageKey = "kokonut.delphi.pendingInvite";
const acceptanceStorageKey = "kokonut.delphi.pendingAcceptance";
const pendingContributions = new Map();
let workspaceOffset = 0;
let workspaceLimit = 50;

function setStatus(message, tone = "") {
  statusNode.textContent = message;
  statusNode.dataset.tone = tone;
  statusNode.hidden = !message;
}

function readCookie(name) {
  const prefix = `${name}=`;
  const item = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

function randomToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  let body = {};
  try { body = await response.json(); } catch (_error) { body = {}; }
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

function renderNotice(acceptance) {
  $("#study-title").textContent = acceptance.study_title;
  $("#notice-version").textContent = `Consent notice ${acceptance.notice_version}`;
  $("#notice-text").textContent = acceptance.notice_text;
  $("#consent-check").checked = false;
  $("#accept").disabled = true;
  consentPanel.hidden = false;
  workspacePanel.hidden = true;
  statusNode.hidden = true;
}

function storeInviteFromFragment() {
  const fragment = window.location.hash.slice(1);
  if (!fragment) return;
  window.history.replaceState(null, document.title, window.location.pathname);
  if (/^[0-9a-f]{64}$/.test(fragment)) {
    window.sessionStorage.setItem(inviteStorageKey, fragment);
  } else {
    setStatus("This participation link is not valid. Ask the study facilitator for a new invite.", "error");
  }
}

async function startConsent() {
  const pending = window.sessionStorage.getItem(acceptanceStorageKey);
  if (pending) {
    try {
      const saved = JSON.parse(pending);
      if (saved && saved.payload && saved.notice) {
        renderNotice(saved.notice);
        setStatus("A consent request is waiting to finish. Review the notice and retry to establish your private session.");
        return;
      }
    } catch (_error) {
      window.sessionStorage.removeItem(acceptanceStorageKey);
    }
  }

  const inviteToken = window.sessionStorage.getItem(inviteStorageKey);
  if (!inviteToken) return false;
  const preview = await request("/api/participation/delphi/preview", {
    method: "POST",
    body: JSON.stringify({ invite_token: inviteToken }),
  });
  renderNotice(preview);
  return true;
}

$("#consent-check").addEventListener("change", (event) => {
  $("#accept").disabled = !event.currentTarget.checked;
});

$("#accept").addEventListener("click", async () => {
  const savedPending = window.sessionStorage.getItem(acceptanceStorageKey);
  let pending;
  if (savedPending) {
    try { pending = JSON.parse(savedPending); } catch (_error) { pending = null; }
  }
  try {
    if (!pending || !pending.payload || !pending.notice) {
      const inviteToken = window.sessionStorage.getItem(inviteStorageKey);
      if (!inviteToken || !$("#consent-check").checked) {
        throw new Error("Open a valid invite and accept the displayed notice to continue.");
      }
      const preview = await request("/api/participation/delphi/preview", {
        method: "POST",
        body: JSON.stringify({ invite_token: inviteToken }),
      });
      const payload = {
        invite_token: inviteToken,
        notice_digest: preview.notice_digest,
        session_token: randomToken(),
        csrf_token: randomToken(),
        request_id: crypto.randomUUID(),
        accepted: true,
      };
      pending = { payload, notice: preview };
      window.sessionStorage.setItem(acceptanceStorageKey, JSON.stringify(pending));
    } else if (!$("#consent-check").checked) {
      throw new Error("Review the notice and confirm your consent before retrying.");
    }
    $("#accept").disabled = true;
    const accepted = await request("/api/participation/delphi/accept", {
      method: "POST",
      body: JSON.stringify(pending.payload),
    });
    window.sessionStorage.removeItem(acceptanceStorageKey);
    window.sessionStorage.removeItem(inviteStorageKey);
    consentPanel.hidden = true;
    setStatus(`Consent recorded for notice ${accepted.notice_version}.`, "success");
    await loadWorkspace(true);
  } catch (error) {
    $("#accept").disabled = !$("#consent-check").checked;
    setStatus(error.message, "error");
  }
});

function addText(parent, tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = text || "";
  parent.append(node);
  return node;
}

function renderItem(item) {
  const card = document.createElement("article");
  card.className = "question";
  addText(card, "p", "question-meta", `${item.item_type} · ${item.scale}`);
  addText(card, "h3", "", item.label);
  if (item.description) addText(card, "p", "", item.description);

  const form = document.createElement("form");
  const scoreLabel = addText(form, "label", "field", "Your score");
  const score = document.createElement("input");
  score.type = "number";
  score.min = String(item.minimum);
  score.max = String(item.maximum);
  score.step = "0.0001";
  score.required = true;
  if (item.my_score !== null && item.my_score !== undefined) score.value = String(item.my_score);
  scoreLabel.append(score);
  addText(scoreLabel, "span", "field-help", `Allowed range: ${item.minimum} to ${item.maximum}`);

  const reasoningLabel = addText(form, "label", "field", "Optional reasoning");
  const reasoning = document.createElement("textarea");
  reasoning.maxLength = 4000;
  reasoning.setAttribute("aria-label", `Optional reasoning for ${item.label}`);
  reasoning.value = item.my_reasoning || "";
  reasoningLabel.append(reasoning);

  const save = document.createElement("button");
  save.type = "submit";
  save.textContent = item.my_updated_at ? "Update my answer" : "Save my answer";
  form.append(save);
  const answerState = addText(form, "p", "answer-state", item.my_updated_at ? "Your current answer is saved." : "");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const body = {
      item_id: item.item_id,
      score: Number(score.value),
      reasoning: reasoning.value || null,
    };
    const prior = pendingContributions.get(item.item_id);
    const pending = prior && JSON.stringify(prior.body) === JSON.stringify(body)
      ? prior
      : { body, request_id: crypto.randomUUID() };
    pendingContributions.set(item.item_id, pending);
    save.disabled = true;
    answerState.textContent = "Saving your answer…";
    try {
      const csrf = readCookie("kokonut_delphi_participant_csrf");
      const result = await request("/api/participation/delphi/contributions", {
        method: "POST",
        headers: { "X-Kokonut-CSRF": csrf },
        body: JSON.stringify({ ...pending.body, request_id: pending.request_id }),
      });
      pendingContributions.delete(item.item_id);
      answerState.textContent = result.replayed ? "Your saved answer was confirmed." : "Your answer is saved.";
      setStatus("Your answer was saved to this study.", "success");
      await loadWorkspace(true);
    } catch (error) {
      answerState.textContent = error.message;
      setStatus("Your answer could not be confirmed. Retry this unchanged answer to safely check its status.", "error");
    } finally {
      save.disabled = false;
    }
  });
  card.append(form);
  return card;
}

async function loadWorkspace(reset = false) {
  if (reset) {
    workspaceOffset = 0;
    $("#questions").replaceChildren();
  }
  try {
    const result = await request(`/api/participation/delphi/workspace?limit=${workspaceLimit}&offset=${workspaceOffset}`);
    const study = result.study;
    $("#workspace-title").textContent = study.title;
    $("#study-status").textContent = study.status;
    workspacePanel.hidden = false;
    consentPanel.hidden = true;
    statusNode.hidden = true;
    const message = $("#study-message");
    message.hidden = false;
    message.dataset.tone = study.status === "open" ? "success" : "";
    message.textContent = study.status === "draft"
      ? "This consultation is being prepared. Questions will appear after the facilitator opens it."
      : study.status === "closed"
        ? "This consultation is closed. You can review your own answers, but new answers cannot be submitted."
        : "Your answers are private. You can update them while this consultation is open.";
    for (const item of result.items || []) $("#questions").append(renderItem(item));
    $("#more").hidden = !result.has_more;
    $("#more").disabled = false;
    if (!result.items?.length && study.status !== "draft") {
      addText($("#questions"), "p", "notice", "No questions are available on this page.");
    }
  } catch (error) {
    workspacePanel.hidden = true;
    setStatus(error.message, "error");
  }
}

$("#more").addEventListener("click", async () => {
  $("#more").disabled = true;
  workspaceOffset += workspaceLimit;
  try {
    const result = await request(`/api/participation/delphi/workspace?limit=${workspaceLimit}&offset=${workspaceOffset}`);
    for (const item of result.items || []) $("#questions").append(renderItem(item));
    $("#more").hidden = !result.has_more;
  } catch (error) {
    workspaceOffset = Math.max(0, workspaceOffset - workspaceLimit);
    setStatus(error.message, "error");
  } finally {
    $("#more").disabled = false;
  }
});

$("#withdraw").addEventListener("click", async () => {
  if (!window.confirm("Withdraw consent and revoke this Delphi session? Previously submitted answers will remain private pending the study owner's retention or erasure review.")) return;
  try {
    const csrf = readCookie("kokonut_delphi_participant_csrf");
    await request("/api/participation/delphi/withdraw", {
      method: "POST",
      headers: { "X-Kokonut-CSRF": csrf },
      body: JSON.stringify({ request_id: crypto.randomUUID() }),
    });
    workspacePanel.hidden = true;
    window.sessionStorage.removeItem(inviteStorageKey);
    window.sessionStorage.removeItem(acceptanceStorageKey);
    $("#questions").replaceChildren();
    setStatus("Your consent was withdrawn. This browser session has been revoked.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
});

async function initialize() {
  storeInviteFromFragment();
  try {
    if (await startConsent()) return;
  } catch (error) {
    setStatus(error.message, "error");
    return;
  }
  await loadWorkspace(true);
}

initialize();
