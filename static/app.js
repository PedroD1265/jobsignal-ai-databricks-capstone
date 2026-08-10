const $ = (selector) => document.querySelector(selector);
let profileId = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `${response.status} ${response.statusText}`);
  return body;
}

function fmt(value, fallback = "—") {
  return value === null || value === undefined || value === "" ? fallback : value;
}

function chipList(values, prefix = "") {
  if (!values || !values.length) return "";
  return values.map((value) => `<span>${prefix}${escapeHtml(String(value))}</span>`).join("");
}

function escapeHtml(value) {
  const el = document.createElement("div");
  el.textContent = value;
  return el.innerHTML;
}

async function loadStats() {
  const status = $("#systemStatus");
  try {
    const stats = await api(`/api/stats?profile_id=${profileId}`);
    $("#metricJobs").textContent = fmt(stats.jobs, "0");
    $("#metricQuality").textContent = stats.avg_quality ? `${stats.avg_quality}/100` : "—";
    $("#metricEmbedded").textContent = fmt(stats.embedded_jobs, "0");
    $("#metricApps").textContent = fmt(stats.applications, "0");
    status.classList.toggle("ok", Boolean(stats.source_table_available));
    status.innerHTML = `<span class="dot"></span>${stats.source_table_available ? "Gold serving table online" : "Waiting for Gold synced table"}`;
  } catch (error) {
    status.innerHTML = `<span class="dot"></span>${escapeHtml(error.message)}`;
  }
}

async function loadProfile() {
  const box = $("#profileBox");
  try {
    const profile = await api(`/api/profile?profile_id=${profileId}`);
    if (!profile.profile_id) {
      box.innerHTML = `<div class="empty">No profile yet. Load the demo profile to start matching.</div>`;
      return;
    }
    box.innerHTML = `
      <div class="profile-name">${escapeHtml(profile.display_name)}</div>
      <div class="profile-headline">${escapeHtml(profile.headline || "")}</div>
      <div class="tags">${chipList(profile.skills || [])}</div>
    `;
  } catch (error) {
    box.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
  }
}

function renderResults(results) {
  const target = $("#results");
  target.innerHTML = "";
  if (!results.length) {
    target.innerHTML = `<div class="empty">No trusted semantic matches found yet.</div>`;
    return;
  }
  for (const job of results) {
    const node = $("#jobTemplate").content.cloneNode(true);
    node.querySelector(".company").textContent = job.company || "Unknown company";
    node.querySelector(".job-title").textContent = job.title || "Untitled role";
    const salary = job.salary_min ? ` · $${Number(job.salary_min).toLocaleString()}${job.salary_max ? `–$${Number(job.salary_max).toLocaleString()}` : "+"}` : "";
    node.querySelector(".meta").textContent = `${job.location || "Remote / unspecified"}${salary} · ${job.source || "source"}`;
    node.querySelector(".match-score").textContent = `${Number(job.match_score || 0).toFixed(0)}%`;
    node.querySelector(".quality").textContent = `quality ${job.quality_score || 0}/100`;
    node.querySelector(".similarity").textContent = `semantic ${Number(job.similarity || 0).toFixed(3)}`;
    node.querySelector(".matched").innerHTML = chipList(job.matched_skills || [], "✓ ");
    node.querySelector(".missing").innerHTML = chipList(job.missing_skills || [], "gap: ");
    node.querySelector(".description").textContent = (job.chunk_text || job.description_text || "").slice(0, 650);
    const link = node.querySelector(".source-link");
    link.href = job.source_url || job.apply_url || "#";
    node.querySelector(".save-button").addEventListener("click", async (event) => {
      event.currentTarget.disabled = true;
      try {
        await api(`/api/jobs/${encodeURIComponent(job.job_id)}/save`, { method: "POST", body: JSON.stringify({ profile_id: profileId }) });
        event.currentTarget.textContent = "Saved ✓";
        await loadStats();
      } catch (error) {
        event.currentTarget.textContent = "Save failed";
        event.currentTarget.title = error.message;
      }
    });
    node.querySelector(".track-button").addEventListener("click", async (event) => {
      event.currentTarget.disabled = true;
      try {
        await api(`/api/applications/${encodeURIComponent(job.job_id)}/stage`, { method: "POST", body: JSON.stringify({ profile_id: profileId, stage: "applied" }) });
        event.currentTarget.textContent = "Tracked ✓";
        await Promise.all([loadStats(), loadApplications()]);
      } catch (error) {
        event.currentTarget.textContent = "Track failed";
        event.currentTarget.title = error.message;
      }
    });
    target.appendChild(node);
  }
}

async function searchJobs(event) {
  event?.preventDefault();
  const query = $("#query").value.trim();
  const message = $("#searchMessage");
  if (!query) return;
  message.className = "inline-message";
  message.textContent = "Embedding query and searching pgvector…";
  try {
    const payload = await api("/api/jobs/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k: 8, profile_id: profileId }),
    });
    message.textContent = `${payload.results.length} explainable matches returned with ${payload.model.split("/").pop()}.`;
    renderResults(payload.results);
  } catch (error) {
    message.className = "inline-message error";
    message.textContent = error.message;
  }
}

async function loadApplications() {
  const target = $("#pipeline");
  try {
    const rows = await api(`/api/applications?profile_id=${profileId}`);
    const stages = ["saved", "applied", "interviewing", "offer"];
    target.innerHTML = stages.map((stage) => {
      const items = rows.filter((row) => row.stage === stage);
      return `<section class="stage"><h3>${stage} · ${items.length}</h3>${items.length ? items.map((row) => `<div class="stage-item"><b>${escapeHtml(row.company || "")}</b><br>${escapeHtml(row.title || row.job_id)}</div>`).join("") : `<div class="empty">No items</div>`}</section>`;
    }).join("");
  } catch (error) {
    target.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
  }
}

$("#searchForm").addEventListener("submit", searchJobs);
$("#refreshApplications").addEventListener("click", loadApplications);
$("#demoProfileButton").addEventListener("click", async () => {
  const button = $("#demoProfileButton");
  button.disabled = true;
  try {
    const profile = await api("/api/profile/demo", { method: "POST", body: "{}" });
    profileId = profile.profile_id;
    await Promise.all([loadProfile(), loadStats(), loadApplications()]);
    button.textContent = "Demo profile ready ✓";
  } catch (error) {
    button.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
$("#embedButton").addEventListener("click", async () => {
  const button = $("#embedButton");
  button.disabled = true;
  button.textContent = "Embedding…";
  try {
    const result = await api("/api/admin/embed-jobs", { method: "POST", body: JSON.stringify({ limit: 500 }) });
    button.textContent = `${result.jobs_processed} jobs embedded ✓`;
    await loadStats();
  } catch (error) {
    button.textContent = `Failed: ${error.message}`;
  } finally {
    button.disabled = false;
  }
});

async function bootstrap() {
  try {
    const profile = await api("/api/profile/demo", { method: "POST", body: "{}" });
    profileId = profile.profile_id;
    await Promise.all([loadStats(), loadProfile(), loadApplications()]);
  } catch (error) {
    $("#systemStatus").innerHTML = `<span class="dot"></span>${escapeHtml(error.message)}`;
  }
}

bootstrap();
