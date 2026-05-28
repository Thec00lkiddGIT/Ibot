const API = "";
let lastEventId = 0;
let lastEventSession = "";
let lastActivityLine = 0;
let activeScriptId = "";
let hubScripts = [];

function el(id) {
  return document.getElementById(id);
}

function initials(name) {
  return (name || "IB")
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function timeAgo(iso) {
  const t = new Date(iso).getTime();
  const sec = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (sec < 60) return `${sec} seconds ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} minute${min === 1 ? "" : "s"} ago`;
  const hr = Math.floor(min / 60);
  return `${hr} hour${hr === 1 ? "" : "s"} ago`;
}

function setRing(id, value, max) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  const ring = el(id);
  if (!ring) return;
  const fg = ring.querySelector(".fg");
  if (fg) fg.setAttribute("stroke-dasharray", `${pct}, 100`);
}

async function api(path, options) {
  const res = await fetch(API + path, options);
  const data = await res.json();
  if (!res.ok && data && data.error) {
    throw new Error(data.error);
  }
  return data;
}

function renderEvent(ev) {
  const card = document.createElement("article");
  card.className = `notify-card ${ev.kind}`;
  card.dataset.id = ev.id;
  card.innerHTML = `
    <h4>${escapeHtml(ev.title)}</h4>
    <p>${escapeHtml(ev.body)}</p>
    <div class="notify-meta">
      <span>${escapeHtml(ev.source)}</span>
      <span>${timeAgo(ev.ts)}</span>
    </div>
  `;
  return card;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function prependEvents(events) {
  const list = el("notify-list");
  if (!list || !events.length) return;
  const existing = new Set(
    [...list.querySelectorAll(".notify-card")].map((n) => n.dataset.id)
  );
  for (const ev of events) {
    if (existing.has(String(ev.id))) continue;
    list.prepend(renderEvent(ev));
    lastEventId = Math.max(lastEventId, ev.id);
  }
  while (list.children.length > 40) {
    list.removeChild(list.lastChild);
  }
}

function prependActivity(entry) {
  const list = el("notify-list");
  if (!list) return;
  const key = `log-${entry.line}`;
  if (list.querySelector(`[data-id="${key}"]`)) return;
  const card = document.createElement("article");
  card.className = `notify-card ${entry.kind || "info"} activity-log`;
  card.dataset.id = key;
  card.innerHTML = `
    <h4>Activity</h4>
    <p>${escapeHtml(entry.text || "")}</p>
  `;
  list.prepend(card);
  while (list.children.length > 60) {
    list.removeChild(list.lastChild);
  }
}

async function pollEvents() {
  try {
    const data = await api(`/api/events?after=${lastEventId}`);
    const session = data.session || "";
    const latestId = data.latest_id ?? 0;
    if (session && session !== lastEventSession) {
      lastEventSession = session;
      lastEventId = 0;
    } else if (latestId > 0 && latestId < lastEventId) {
      lastEventId = 0;
    }
    prependEvents(data.events || []);
  } catch (_) {
    /* server down */
  }
}

async function pollActivityLog() {
  try {
    const data = await api(`/api/activity-log?after=${lastActivityLine}`);
    for (const entry of data.entries || []) {
      prependActivity(entry);
      lastActivityLine = Math.max(lastActivityLine, entry.line || 0);
    }
  } catch (_) {
    /* server down */
  }
}

function copyText(text) {
  if (navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(text);
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
  return Promise.resolve();
}

function renderFdaCard(s) {
  if (s.fda_ok) {
    return `<div class="perm-card ok"><h4>Full Disk Access</h4><p>chat.db is readable.</p></div>`;
  }
  if (s.fda_bundle) {
    const path = s.fda_python_path || s.python || "";
    return `<div class="perm-card bad">
      <h4>Full Disk Access</h4>
      <p class="fda-steps">Ibot.app runs Python inside the app. Add <strong>this exact file</strong> (not a partial path):</p>
      <ol class="fda-step-list">
        <li>System Settings → Privacy &amp; Security → Full Disk Access</li>
        <li>Click <strong>+</strong>, then press <strong>Cmd+Shift+G</strong></li>
        <li>Paste the full path (starts with <code>/Applications</code>), press Go, select <code>python3</code></li>
        <li>Quit Ibot (Cmd+Q) and reopen</li>
      </ol>
      <div class="fda-path-row">
        <input type="text" class="fda-path" readonly value="${escapeHtml(path)}" aria-label="Full Disk Access path" />
        <button type="button" class="btn ghost fda-copy" data-path="${escapeHtml(path)}">Copy path</button>
        <button type="button" class="btn ghost fda-open">Open Settings</button>
      </div>
    </div>`;
  }
  return `<div class="perm-card bad">
    <h4>Full Disk Access</h4>
    <p>Can't read chat.db. Add ${escapeHtml(s.fda_target || s.fda_host || "this app")} in System Settings → Privacy &amp; Security → Full Disk Access, then quit and reopen that app.${s.python ? " Python: " + escapeHtml(s.python) : ""}</p>
  </div>`;
}

function renderConfigCard(s) {
  const envPath = s.env_path || "";
  const support = s.app_support || "";
  if (!envPath && !support) return "";
  return `<div class="perm-card ok">
    <h4>Config &amp; data</h4>
    <p>API keys and saved data live in Application Support (created automatically on first launch).</p>
    <div class="fda-path-row">
      <input type="text" class="fda-path" readonly value="${escapeHtml(envPath)}" aria-label="Env file path" />
      <button type="button" class="btn ghost env-open">Edit config</button>
      <button type="button" class="btn ghost env-copy" data-path="${escapeHtml(envPath)}">Copy path</button>
    </div>
    <p class="muted small-path">${support ? "Folder: " + escapeHtml(support) : ""}</p>
  </div>`;
}

function setupFdaButtons(root) {
  root.querySelector(".fda-copy")?.addEventListener("click", async (e) => {
    const path = e.currentTarget.dataset.path || "";
    try {
      await copyText(path);
      e.currentTarget.textContent = "Copied!";
      setTimeout(() => {
        e.currentTarget.textContent = "Copy path";
      }, 1500);
    } catch (_) {
      /* ignore */
    }
  });
  root.querySelector(".fda-open")?.addEventListener("click", async () => {
    await postControl({ action: "open_fda" });
  });
  root.querySelector(".env-open")?.addEventListener("click", async () => {
    await postControl({ action: "open_env" });
  });
  root.querySelector(".env-copy")?.addEventListener("click", async (e) => {
    const path = e.currentTarget.dataset.path || "";
    try {
      await copyText(path);
      e.currentTarget.textContent = "Copied!";
      setTimeout(() => {
        e.currentTarget.textContent = "Copy path";
      }, 1500);
    } catch (_) {
      /* ignore */
    }
  });
}

function applyStatus(s) {
  const name = s.display_name || "Ibot";
  el("display-name").textContent = name;
  el("profile-name").textContent = name;
  el("profile-handle").textContent = "@" + (s.handle || "mac");
  el("version").textContent = "v" + (s.version || "1.0.0");
  el("last-rowid").textContent = String(s.last_rowid ?? "-");
  el("host-app").textContent = s.fda_host || "-";
  el("commands-count").textContent = s.commands_used ?? 0;
  el("messages-count").textContent = s.messages_seen ?? 0;
  el("commands-used-footer").textContent = s.commands_used ?? 0;
  setRing("ring-commands", s.commands_used || 0, 500);
  setRing("ring-messages", s.messages_seen || 0, 5000);

  const badge = el("status-badge");
  if (s.running) {
    badge.textContent = "Running";
    badge.className = "badge running";
  } else {
    badge.textContent = "Stopped";
    badge.className = "badge muted";
  }

  const fda = el("fda-badge");
  if (s.fda_ok) {
    fda.textContent = "FDA OK";
    fda.className = "badge";
  } else {
    fda.textContent = "FDA missing";
    fda.className = "badge bad";
  }

  el("btn-start").disabled = !!s.running;
  el("btn-stop").disabled = !s.running;

  el("toggle-self").checked = !!s.include_self;
  el("toggle-verbose").checked = !!s.verbose;
  el("toggle-catchup").checked = !!s.catch_up;

  const afkBtn = el("btn-afk");
  const afkMsg = el("afk-message");
  const afkNav = el("nav-afk");
  if (afkBtn) {
    afkBtn.classList.toggle("on", !!s.afk_enabled);
    afkBtn.textContent = s.afk_enabled ? "AFK ON" : "AFK";
  }
  if (afkNav) {
    afkNav.classList.toggle("afk-on", !!s.afk_enabled);
  }
  const afkBadge = el("afk-status-badge");
  const afkStatusText = el("afk-status-text");
  if (afkBadge) {
    afkBadge.textContent = s.afk_enabled ? "On" : "Off";
    afkBadge.className = "badge " + (s.afk_enabled ? "on" : "muted");
  }
  if (afkStatusText) {
    afkStatusText.textContent = s.afk_enabled
      ? "Sending your message to everyone who texts you."
      : "Turn on AFK to send your message automatically.";
  }
  if (afkMsg && document.activeElement !== afkMsg) {
    afkMsg.value = s.afk_message || "";
  }

  if (s.session && s.session !== lastEventSession) {
    lastEventSession = s.session;
    lastEventId = 0;
  }

  const banner = el("alert-banner");
  if (banner) {
    let msg = "";
    let kind = "error";
    if (!s.fda_ok) {
      if (s.fda_bundle) {
        msg = "Full Disk Access: copy the python3 path on the Permissions tab (must start with /Applications).";
      } else {
        msg =
          "Can't read Messages. Grant Full Disk Access to " +
          (s.fda_target || s.fda_host || "this app") +
          ", then quit and reopen it.";
      }
    } else if (s.error) {
      msg = s.error;
    } else if (!s.running) {
      msg = "Bot is stopped. Click Start bot (or relaunch the app).";
      kind = "warn";
    } else if (s.afk_enabled) {
      msg = "AFK is on — auto-replying to incoming messages only.";
      kind = "warn";
    } else if (!s.include_self) {
      msg =
        "Your own iMessages are ignored. Turn on \"React to my messages\" to test !commands from this Mac.";
      kind = "warn";
    }
    if (msg) {
      banner.textContent = msg;
      banner.className = "alert-banner " + kind;
    } else {
      banner.className = "alert-banner hidden";
    }
  }

  const cmdList = el("cmd-list");
  if (cmdList && s.commands) {
    cmdList.innerHTML = s.commands
      .map((c) => {
        const tag =
          c.source === "hub"
            ? `<span class="cmd-tag${c.enabled === false ? " off" : ""}">hub</span>`
            : "";
        return `<li><div><code>!${escapeHtml(c.name)}</code><span class="muted">${escapeHtml(c.help)}</span></div>${tag}</li>`;
      })
      .join("");
  }

  const perms = el("perm-cards");
  if (perms) {
    perms.innerHTML =
      renderFdaCard(s) +
      renderConfigCard(s) +
      `<div class="perm-card ${s.automation_ok ? "ok" : "bad"}">
        <h4>Automation (Messages)</h4>
        <p>${escapeHtml(s.automation_msg || "")}</p>
      </div>`;
    setupFdaButtons(perms);
  }
}

async function refreshStatus() {
  try {
    const s = await api("/api/status");
    applyStatus(s);
  } catch (_) {
    /* ignore */
  }
}

async function postControl(body) {
  await api("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await refreshStatus();
}

function setupNav() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const page = btn.dataset.page;
      el("page-" + page)?.classList.add("active");
    });
  });
}

function setupControls() {
  el("btn-start")?.addEventListener("click", () => postControl({ action: "start" }));
  el("btn-stop")?.addEventListener("click", () => postControl({ action: "stop" }));

  const bindToggle = (id, key) => {
    el(id)?.addEventListener("change", (e) => {
      postControl({ action: "settings", [key]: e.target.checked });
    });
  };
  bindToggle("toggle-self", "include_self");
  bindToggle("toggle-verbose", "verbose");
  bindToggle("toggle-catchup", "catch_up");

  el("btn-afk")?.addEventListener("click", async () => {
    try {
      const s = await api("/api/status");
      await postControl({ action: "settings", afk_enabled: !s.afk_enabled });
    } catch (_) {
      /* ignore */
    }
  });

  let afkSaveTimer = null;
  el("afk-message")?.addEventListener("input", (e) => {
    clearTimeout(afkSaveTimer);
    afkSaveTimer = setTimeout(() => {
      postControl({ action: "settings", afk_message: e.target.value });
    }, 400);
  });
}

function setScriptStatus(msg, isError) {
  const node = el("script-status");
  if (!node) return;
  node.textContent = msg || "";
  node.style.color = isError ? "var(--error)" : "";
}

function loadScriptIntoEditor(script) {
  activeScriptId = script?.id || "";
  el("script-name").value = script?.name || "";
  el("script-author").value = script?.author || "Ibot";
  el("script-description").value = script?.description || script?.help || "";
  el("script-usage").value = script?.usage || (script?.command ? "!" + script.command + " <args>" : "");
  el("script-command").value = script?.command || "";
  el("script-enabled").checked = script?.enabled !== false;
  el("script-code").value = script?.code || "";
  el("script-test-out").textContent = "";
  setScriptStatus("");
  document.querySelectorAll("#hub-script-list button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.id === activeScriptId);
  });
}

function renderHubList() {
  const list = el("hub-script-list");
  if (!list) return;
  if (!hubScripts.length) {
    list.innerHTML = '<li class="muted" style="padding:8px">No scripts yet. Click New script to get started.</li>';
    return;
  }
  list.innerHTML = hubScripts
    .map(
      (s) =>
        `<li><button type="button" data-id="${escapeHtml(s.id)}" class="${s.id === activeScriptId ? "active" : ""}">
          <span class="hub-item-name">${escapeHtml(s.name || s.command)}${s.enabled ? "" : " (off)"}</span>
          <span class="hub-item-help">${escapeHtml(s.description || s.help || "")} · ${escapeHtml((s.commands || [s.command]).filter(Boolean).map((c) => "!" + c).join(", "))}</span>
        </button></li>`
    )
    .join("");
  list.querySelectorAll("button[data-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const script = hubScripts.find((s) => s.id === btn.dataset.id);
      if (script) loadScriptIntoEditor(script);
    });
  });
}

async function refreshScripts() {
  try {
    const data = await api("/api/scripts");
    hubScripts = data.scripts || [];
    renderHubList();
    if (activeScriptId) {
      const current = hubScripts.find((s) => s.id === activeScriptId);
      if (current) loadScriptIntoEditor(current);
    } else if (hubScripts.length) {
      loadScriptIntoEditor(hubScripts[0]);
    }
    await refreshStatus();
  } catch (_) {
    setScriptStatus("Could not load Script Hub.", true);
  }
}

async function postScript(body) {
  const data = await api("/api/scripts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!data.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function setupScriptHub() {
  el("btn-script-new")?.addEventListener("click", async () => {
    try {
      const tpl = await api("/api/scripts/template?name=My+Script");
      activeScriptId = "";
      loadScriptIntoEditor(tpl);
      renderHubList();
      setScriptStatus("New script ready. Edit the details, add your commands, then save.");
    } catch (_) {
      setScriptStatus("Could not load template.", true);
    }
  });

  el("btn-script-save")?.addEventListener("click", async () => {
    try {
      const data = await postScript({
        action: "save",
        id: activeScriptId || undefined,
        name: el("script-name").value,
        author: el("script-author").value,
        description: el("script-description").value,
        usage: el("script-usage").value,
        command: el("script-command").value,
        help: el("script-description").value,
        code: el("script-code").value,
        enabled: el("script-enabled").checked,
      });
      activeScriptId = data.script?.id || activeScriptId;
      setScriptStatus("Saved to Script Hub.");
      await refreshScripts();
    } catch (err) {
      setScriptStatus(err.message || String(err), true);
    }
  });

  el("btn-script-test")?.addEventListener("click", async () => {
    el("script-test-out").textContent = "…";
    try {
      const data = await postScript({
        action: "test",
        id: activeScriptId || undefined,
        command: el("script-command").value,
        code: el("script-code").value,
        args: el("script-test-args").value,
      });
      const r = data.result;
      el("script-test-out").textContent = Array.isArray(r) ? r.join(" | ") : String(r);
      setScriptStatus("");
    } catch (err) {
      el("script-test-out").textContent = "";
      setScriptStatus(err.message || String(err), true);
    }
  });

  el("btn-script-delete")?.addEventListener("click", async () => {
    if (!activeScriptId) {
      setScriptStatus("Nothing to delete. Pick a script first, or clear the editor.", true);
      return;
    }
    if (!confirm("Delete this script from the hub?")) return;
    try {
      await postScript({ action: "delete", id: activeScriptId });
      activeScriptId = "";
      loadScriptIntoEditor({ name: "", author: "Ibot", command: "", description: "", usage: "", code: "", enabled: true });
      setScriptStatus("Deleted.");
      await refreshScripts();
    } catch (err) {
      setScriptStatus(err.message || String(err), true);
    }
  });

  el("script-enabled")?.addEventListener("change", async () => {
    if (!activeScriptId) return;
    try {
      await postScript({
        action: "toggle",
        id: activeScriptId,
        enabled: el("script-enabled").checked,
      });
      await refreshScripts();
    } catch (err) {
      setScriptStatus(err.message || String(err), true);
    }
  });
}

setupNav();
setupControls();
setupScriptHub();
refreshStatus();
refreshScripts();
setInterval(refreshStatus, 2000);
setInterval(pollEvents, 800);
setInterval(pollActivityLog, 800);
pollActivityLog();
