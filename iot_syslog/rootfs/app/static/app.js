"use strict";

const PAGE_SIZE = 100;
const EVENT_REFRESH_INTERVAL_MS = 5000;
const state = { offset: 0, total: 0, query: new URLSearchParams() };
const form = document.querySelector("#filters");
const rows = document.querySelector("#event-rows");
const errorBox = document.querySelector("#error");
const searchButton = document.querySelector("#search");
const exportButton = document.querySelector("#export");
const exportCSVButton = document.querySelector("#export-csv");
let eventRequestSequence = 0;
let eventRequestInFlight = false;

const activePage = document.body.dataset.page || "overview";
for (const section of document.querySelectorAll("[data-page]")) section.classList.toggle("hidden", section.dataset.page !== activePage);
for (const link of document.querySelectorAll("[data-page-link]")) {
  const active = link.dataset.pageLink === activePage;
  link.classList.toggle("active", active);
  if (active) link.setAttribute("aria-current", "page");
}

function endpoint(path) {
  return new URL(path, window.location.href);
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.toggle("hidden", !message);
}

function setPortalStatus(element, stateName, message) {
  if (!element) return;
  delete element.dataset.refreshError;
  element.className = `portal-status${stateName ? ` ${stateName}` : ""}`;
  element.setAttribute('role', stateName === 'error' ? 'alert' : 'status');
  element.textContent = message || "";
}

function setSummaryStatus(stateName, message) {
  for (const element of document.querySelectorAll("[data-summary-status]")) {
    setPortalStatus(element, stateName, message);
  }
}

function statusRefreshNotices() {
  return activePage === 'events' ? [document.querySelector('#filter-status')].filter(Boolean) :
    [...document.querySelectorAll('[data-summary-status]')];
}

function setBusy(button, busy, label) {
  if (!button) return;
  if (busy) {
    button.dataset.idleLabel = button.textContent;
    button.textContent = label;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  } else {
    button.textContent = button.dataset.idleLabel || button.textContent;
    button.disabled = false;
    button.removeAttribute("aria-busy");
  }
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

async function loadEvents({ force = false, trigger = null, feedback = "" } = {}) {
  if (eventRequestInFlight && !force) return;
  const requestSequence = ++eventRequestSequence;
  eventRequestInFlight = true;
  showError("");
  setBusy(trigger, true, trigger === searchButton ? "Searching…" : "Refreshing…");
  document.querySelector("#refresh-state").textContent = "Refreshing…";
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
    exportButton.disabled = state.total === 0;
    exportCSVButton.disabled = state.total === 0;
    document.querySelector("#refresh-state").textContent = `Updated ${new Date().toLocaleTimeString()}`;
    if (feedback) {
      const count = `${result.total.toLocaleString()} event${result.total === 1 ? "" : "s"}`;
      setPortalStatus(document.querySelector("#filter-status"), "success", `${feedback} — ${count}`);
    }
  } catch (error) {
    if (requestSequence !== eventRequestSequence) return;
    showError(`Could not load events: ${error.message}`);
    document.querySelector("#refresh-state").textContent = "Refresh failed";
    if (feedback) setPortalStatus(document.querySelector("#filter-status"), "error", "Could not update results.");
  } finally {
    setBusy(trigger, false);
    if (requestSequence === eventRequestSequence) eventRequestInFlight = false;
  }
}

function refreshVisibleEvents() {
  if (activePage === "events" && document.visibilityState === "visible") loadEvents();
}

function replaceOptions(id, values) {
  const select = document.querySelector(id);
  const selected = select.value;
  while (select.options.length > 1) select.remove(1);
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
  if ([...select.options].some((option) => option.value === selected)) select.value = selected;
}

function applyStatus(status) {
  document.querySelector("#stored-count").textContent = status.stored.toLocaleString();
  document.querySelector("#retention").textContent = `${status.retention_days} days`;
  document.querySelector("#tls-state").textContent = status.tls ? "Enabled" : "Disabled";
  document.querySelector("#dropped-count").textContent = status.dropped.toLocaleString();
  document.querySelector("#settings-retention").textContent = `${status.retention_days} days`;
  document.querySelector("#settings-tls").textContent = status.tls ? "Enabled" : "Disabled";
  document.querySelector("#settings-server-names").textContent = status.tls_server_names.join(", ") || "Not configured";
  document.querySelector("#settings-stored").textContent = status.stored.toLocaleString();
  document.querySelector("#ca-download").classList.toggle("hidden", !status.ca_download);
  const details = document.querySelector("#tls-details");
  details.classList.toggle("hidden", !status.tls);
  if (status.tls) {
    const mode = status.tls_generated ? "A dedicated local CA generated by this app is active." : "A custom server certificate is active.";
    const fingerprint = status.tls_ca_sha256 ? ` CA SHA-256: ${status.tls_ca_sha256}.` : "";
    details.textContent = `${mode} Configure each sender with one of these exact server names: ${status.tls_server_names.join(", ")}.${fingerprint}`;
  }
}

async function loadSummary({ trigger = null, announce = false } = {}) {
  setBusy(trigger, true, "Refreshing…");
  if (announce) setSummaryStatus("", "Refreshing receiver status…");
  try {
    const [facetsResponse, statusResponse] = await Promise.all([
      fetch(endpoint("api/facets")), fetch(endpoint("api/status")),
    ]);
    if (!facetsResponse.ok || !statusResponse.ok) throw new Error("status request failed");
    const facets = await facetsResponse.json();
    const status = await statusResponse.json();
    replaceOptions("#hostname", facets.hostnames);
    replaceOptions("#app", facets.applications);
    replaceOptions("#transport", facets.transports);
    document.querySelector("#stored-count").textContent = facets.count.toLocaleString();
    applyStatus(status);
    if (announce) setSummaryStatus("success", `Receiver status updated at ${new Date().toLocaleTimeString()}.`);
  } catch (error) {
    if (activePage === "events") {
      setPortalStatus(document.querySelector("#filter-status"), "error", `Could not load filter options: ${error.message}`);
    }
    else setSummaryStatus("error", `Could not load receiver status: ${error.message}`);
  } finally {
    setBusy(trigger, false);
  }
}

async function refreshStatus() {
  try {
    const response = await fetch(endpoint("api/status"));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const status = await response.json();
    applyStatus(status);
    for (const element of statusRefreshNotices()) {
      if (element.dataset.refreshError === '1') { setPortalStatus(element, '', 'Receiver status refreshed.'); delete element.dataset.refreshError; }
    }
  } catch (error) {
    for (const element of statusRefreshNotices()) {
      setPortalStatus(element, "error", `Could not refresh receiver status: ${error.message}. Previously loaded data is retained.`);
      element.dataset.refreshError = '1';
    }
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
  loadEvents({ force: true, trigger: searchButton, feedback: "Filters applied" });
});

document.querySelector("#reset").addEventListener("click", () => {
  form.reset(); state.query = new URLSearchParams(); state.offset = 0;
  loadEvents({ force: true, trigger: document.querySelector("#reset"), feedback: "Filters cleared" });
});
document.querySelector("#previous").addEventListener("click", () => {
  state.offset = Math.max(0, state.offset - PAGE_SIZE); loadEvents({ force: true });
});
document.querySelector("#next").addEventListener("click", () => {
  state.offset += PAGE_SIZE; loadEvents({ force: true });
});
document.querySelector("#refresh-events").addEventListener("click", (event) => {
  loadEvents({ force: true, trigger: event.currentTarget });
});
function filteredDownloadURL(formatName) {
  const url = endpoint(formatName === "csv" ? "api/export.csv" : "api/export.txt");
  for (const [key, value] of state.query) url.searchParams.set(key, value);
  return url;
}
function downloadFilteredEvents(formatName) {
  const link = document.createElement("a");
  link.href = filteredDownloadURL(formatName);
  link.download = `iot-syslog-filtered.${formatName}`;
  document.body.append(link);
  link.click();
  link.remove();
  setPortalStatus(document.querySelector("#filter-status"), "", "Download requested for all events matching the applied filters.");
}
exportButton.addEventListener("click", () => downloadFilteredEvents("txt"));
exportCSVButton.addEventListener("click", () => downloadFilteredEvents("csv"));
for (const button of document.querySelectorAll("[data-summary-refresh]")) {
  button.addEventListener("click", () => loadSummary({ trigger: button, announce: true }));
}

loadSummary();
if (activePage === "events") loadEvents({ force: true });
if (activePage !== "events") window.setInterval(refreshStatus, 30000);
window.setInterval(refreshVisibleEvents, EVENT_REFRESH_INTERVAL_MS);
document.addEventListener("visibilitychange", refreshVisibleEvents);
