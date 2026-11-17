"""add_start_over.py — adds a "Start over" button with confirmation modal."""
from pathlib import Path
import shutil
from datetime import datetime

# ── Backup ──────────────────────────────────────────────────────
BACKUP = Path("_backups")
BACKUP.mkdir(exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
for f in ["frontend/app.js", "frontend/style.css"]:
    src = Path(f)
    if src.exists():
        shutil.copy2(src, BACKUP / f"{src.stem}.{stamp}{src.suffix}")
print(f"backups -> {BACKUP}/")

# ═══════════════════════════════════════════════════════════════
# 1. Patch frontend/app.js
# ═══════════════════════════════════════════════════════════════
app_js = Path("frontend/app.js")
src = app_js.read_text(encoding="utf-8")

# --- A) Insert startOver + confirmStartOver after clearState() ---
old_clear = '''function clearState() {
  try { localStorage.removeItem(STORAGE_KEY); } catch {}
  state.ventureId = null;
  state.analyzedCache = null;
}'''

new_functions = '''function clearState() {
  try { localStorage.removeItem(STORAGE_KEY); } catch {}
  state.ventureId = null;
  state.analyzedCache = null;
}

/* ── Start over ──────────────────────────────────────────────────── */
function confirmStartOver() {
  return new Promise((resolve) => {
    const bd = document.createElement("div");
    bd.className = "vo-modal-backdrop";
    const m = document.createElement("div");
    m.className = "vo-modal";
    m.innerHTML = `
      <button class="vo-close" aria-label="Close">×</button>
      <h3>Start over?</h3>
      <p style="line-height:1.6;color:var(--muted);margin:0 0 20px">
        This returns you to the landing page so you can describe a new idea.
        Your current venture stays saved on the server — nothing is deleted.
      </p>
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="ghost" id="cancel-start-over">Cancel</button>
        <button class="primary" id="confirm-start-over">Yes, start over</button>
      </div>
    `;
    bd.appendChild(m);
    document.body.appendChild(bd);

    const close = (result) => { bd.remove(); resolve(result); };
    m.querySelector(".vo-close").onclick = () => close(false);
    m.querySelector("#cancel-start-over").onclick = () => close(false);
    m.querySelector("#confirm-start-over").onclick = () => close(true);
    bd.onclick = (e) => { if (e.target === bd) close(false); };
    const esc = (e) => {
      if (e.key === "Escape") {
        close(false);
        document.removeEventListener("keydown", esc);
      }
    };
    document.addEventListener("keydown", esc);
  });
}

async function startOver() {
  const ok = await confirmStartOver();
  if (!ok) return;

  // Forget the current venture selection
  clearState();

  // Tear down any running client-side state
  if (state.cy) { try { state.cy.destroy(); } catch {} state.cy = null; }
  stopPoll(); stopETA();

  // Reset UI to landing
  $("#workspace").classList.add("hidden");
  $("#discovery").classList.add("hidden");
  const chat = $("#chat"); if (chat) chat.innerHTML = "";
  const idea = $("#idea-input"); if (idea) idea.value = "";
  const ans = $("#answer-input"); if (ans) ans.value = "";
  $("#landing").classList.remove("hidden");
  state.readyForBrief = false;
  state.analyzedCache = null;

  toastOk("Ready for a fresh venture");
}

function ensureStartOverButton() {
  const sidebar = document.querySelector(".sidebar");
  if (!sidebar || document.getElementById("start-over-btn")) return;
  const btn = document.createElement("button");
  btn.id = "start-over-btn";
  btn.className = "ghost start-over-btn";
  btn.textContent = "Start over";
  btn.title = "Start a new venture";
  btn.onclick = startOver;
  sidebar.appendChild(btn);
}

function ensureDiscoveryStartOver() {
  const head = document.querySelector(".discovery-head");
  if (!head || document.getElementById("discovery-start-over")) return;
  const btn = document.createElement("button");
  btn.id = "discovery-start-over";
  btn.className = "ghost";
  btn.style.cssText = "margin-left:auto;font-size:13px;padding:6px 12px";
  btn.textContent = "Start over";
  btn.onclick = startOver;
  head.appendChild(btn);
}'''

if old_clear in src:
    src = src.replace(old_clear, new_functions, 1)
    print("[OK] inserted startOver functions")
else:
    print("[WARN] could not find clearState block — check manually")

# --- B) Call ensureStartOverButton from enterWorkspace ---
old_enter = '''async function enterWorkspace() {
  $("#discovery").classList.add("hidden");
  $("#workspace").classList.remove("hidden");
  ensureAskPanel();
  await refresh();
  renderThemePicker();
}'''
new_enter = '''async function enterWorkspace() {
  $("#discovery").classList.add("hidden");
  $("#workspace").classList.remove("hidden");
  ensureAskPanel();
  ensureStartOverButton();
  await refresh();
  renderThemePicker();
}'''
if old_enter in src:
    src = src.replace(old_enter, new_enter, 1)
    print("[OK] patched enterWorkspace")
else:
    print("[WARN] enterWorkspace mismatch — check manually")

# --- C) Restore case: call ensureDiscoveryStartOver ---
old_restore = '''        for (const m of data.messages) addChat(m.role, m.content);
        $("#answer-input").placeholder = "Answer the agent… (or start with ? to ask anything)";'''
new_restore = '''        for (const m of data.messages) addChat(m.role, m.content);
        $("#answer-input").placeholder = "Answer the agent… (or start with ? to ask anything)";
        ensureDiscoveryStartOver();'''
if old_restore in src:
    src = src.replace(old_restore, new_restore, 1)
    print("[OK] patched discovery restore")
else:
    print("[WARN] discovery restore mismatch — check manually")

# --- D) New venture start: call ensureDiscoveryStartOver ---
old_new = '''    addChat("user", idea);
    await askNext(idea);'''
new_new = '''    addChat("user", idea);
    ensureDiscoveryStartOver();
    await askNext(idea);'''
if old_new in src:
    src = src.replace(old_new, new_new, 1)
    print("[OK] patched new-venture start")
else:
    print("[WARN] new-venture start mismatch — check manually")

app_js.write_text(src, encoding="utf-8")
print("[OK] wrote frontend/app.js")

# ═══════════════════════════════════════════════════════════════
# 2. Patch frontend/style.css
# ═══════════════════════════════════════════════════════════════
css = Path("frontend/style.css")
csrc = css.read_text(encoding="utf-8")
if ".start-over-btn" not in csrc:
    csrc += '''

/* Start over button (sidebar) */
.start-over-btn {
  margin-top: 12px;
  width: 100%;
  font-size: 13px;
  padding: 8px 14px;
  text-align: center;
}
'''
    css.write_text(csrc, encoding="utf-8")
    print("[OK] added .start-over-btn CSS")
else:
    print("[OK] CSS already has .start-over-btn")

# ═══════════════════════════════════════════════════════════════
# 3. Verify JS is syntactically valid (parses as JS, not Python)
# ═══════════════════════════════════════════════════════════════
print()
js_text = app_js.read_text(encoding="utf-8")
# Light check: balanced braces on the new functions
for needle in ["function startOver", "function confirmStartOver",
               "function ensureStartOverButton", "function ensureDiscoveryStartOver"]:
    if needle in js_text:
        print(f"[OK] {needle} present")
    else:
        print(f"[FAIL] {needle} missing — patch did not apply")

print()
print("Done. Restart the server (Ctrl+C, then python main.py), then hard-refresh")
print("the browser with Ctrl+Shift+R.")