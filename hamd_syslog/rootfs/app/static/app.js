"use strict";

const PAGE_SIZE = 100;
const EVENT_REFRESH_INTERVAL_MS = 5000;
const state = { offset: 0, total: 0, query: new URLSearchParams() };
const form = document.querySelector("#filters");
const rows = document.querySelector("#event-rows");
const errorBox = document.querySelector("#error");
let eventRequestSequence = 0;

function endpoint(path) {
  return new URL(path, window.location.href);
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.toggle("hidden", !message);
}

function displayTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}

function textCell(value, className = "") {
  const cell = document.createElement("td");
  cell.textContent = value || "—";
  if (className) cell.className = className;
  return cell;
}

function badgeCell(value, className = "") {
  const cell = document.createElement("td");
  const badge = document.createElement("span");
  badge.className = `badge ${className}`.trim();
  badge.textContent = value || "—";
  cell.append(badge);
  return cell;
}

function renderEvents(events) {
  rows.replaceChildren();
  for (const event of events) {
    const row = document.createElement("tr");
    const time = textCell(displayTime(event.event_time || event.received_at));
    const received = document.createElement("small");
    received.className = "secondary-line";
    received.textContent = `Received ${displayTime(event.received_at)}`;
    time.append(received);
    row.append(time);
    row.append(textCell(event.hostname || event.peer));
    const source = badgeCell(event.source);
    const app = document.createElement("small");
    app.className = "secondary-line";
    app.textContent = event.app_name || "unknown app";
    source.append(app);
    row.append(source);
    row.append(badgeCell(event.severity_name, `severity-${event.severity}`));
    row.append(badgeCell(event.transport));
    row.append(textCell(event.message || event.raw, "message"));
    rows.append(row);
  }
  document.querySelector("#empty").classList.toggle("hidden", events.length !== 0);
}

async function loadEvents() {
  const requestSequence = ++eventRequestSequence;
  showError("");
  const url = endpoint("api/events");
  for (const [key, value] of state.query) url.searchParams.set(key, value);
  url.searchParams.set("limit", PAGE_SIZE);
  url.searchParams.set("offset", state.offset);
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(await response.text() || response.statusText);
    const result = await response.json();
    if (requestSequence !== eventRequestSequence) return;
    state.total = result.total;
    renderEvents(result.events);
    const first = result.total ? state.offset + 1 : 0;
    const last = Math.min(state.offset + result.events.length, result.total);
    document.querySelector("#result-count").textContent = `${first}–${last} of ${result.total.toLocaleString()}`;
    document.querySelector("#page").textContent = `Page ${Math.floor(state.offset / PAGE_SIZE) + 1}`;
    document.querySelector("#previous").disabled = state.offset === 0;
    document.querySelector("#next").disabled = state.offset + PAGE_SIZE >= state.total;
    document.querySelector("#refresh-state").textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    if (requestSequence !== eventRequestSequence) return;
    showError(`Could not load events: ${error.message}`);
    document.querySelector("#refresh-state").textContent = "Refresh failed";
  }
}

function refreshVisibleEvents() {
  if (document.visibilityState === "visible") loadEvents();
}

function addOptions(id, values) {
  const select = document.querySelector(id);
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
}

async function loadSummary() {
  try {
    const [facetsResponse, statusResponse] = await Promise.all([
      fetch(endpoint("api/facets")), fetch(endpoint("api/status")),
    ]);
    if (!facetsResponse.ok || !statusResponse.ok) throw new Error("status request failed");
    const facets = await facetsResponse.json();
    const status = await statusResponse.json();
    addOptions("#hostname", facets.hostnames);
    addOptions("#app", facets.applications);
    addOptions("#transport", facets.transports);
    document.querySelector("#stored-count").textContent = facets.count.toLocaleString();
    document.querySelector("#retention").textContent = `${status.retention_days} days`;
    document.querySelector("#tls-state").textContent = status.tls ? "Enabled" : "Disabled";
    document.querySelector("#dropped-count").textContent = status.dropped.toLocaleString();
    document.querySelector("#ca-download").classList.toggle("hidden", !status.ca_download);
    if (status.tls) {
      const details = document.querySelector("#tls-details");
      const mode = status.tls_generated ? "A dedicated local CA generated by this app is active." : "A custom server certificate is active.";
      const fingerprint = status.tls_ca_sha256 ? ` CA SHA-256: ${status.tls_ca_sha256}.` : "";
      details.textContent = `${mode} Configure each HAMD device with one of these exact server names: ${status.tls_server_names.join(", ")}.${fingerprint}`;
      details.classList.remove("hidden");
    }
  } catch (error) {
    showError(`Could not load receiver status: ${error.message}`);
  }
}

async function refreshStatus() {
  try {
    const response = await fetch(endpoint("api/status"));
    if (!response.ok) return;
    const status = await response.json();
    document.querySelector("#stored-count").textContent = status.stored.toLocaleString();
    document.querySelector("#dropped-count").textContent = status.dropped.toLocaleString();
  } catch (_error) {
    // The next refresh or user query will report a persistent connection problem.
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  state.query = new URLSearchParams();
  for (const [key, value] of new FormData(form)) {
    if (!value) continue;
    if (key === "start" || key === "end") state.query.set(key, new Date(value).toISOString());
    else state.query.set(key, value);
  }
  state.offset = 0;
  loadEvents();
});

document.querySelector("#reset").addEventListener("click", () => {
  form.reset(); state.query = new URLSearchParams(); state.offset = 0; loadEvents();
});
document.querySelector("#previous").addEventListener("click", () => {
  state.offset = Math.max(0, state.offset - PAGE_SIZE); loadEvents();
});
document.querySelector("#next").addEventListener("click", () => {
  state.offset += PAGE_SIZE; loadEvents();
});
document.querySelector("#export").addEventListener("click", () => {
  const url = endpoint("api/export.csv");
  for (const [key, value] of state.query) url.searchParams.set(key, value);
  window.location.assign(url);
});

loadSummary();
loadEvents();
window.setInterval(refreshStatus, 30000);
window.setInterval(refreshVisibleEvents, EVENT_REFRESH_INTERVAL_MS);
document.addEventListener("visibilitychange", refreshVisibleEvents);
