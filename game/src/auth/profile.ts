// M9: [P] profile chip (next to the Almanac button) + parchment account modal.
// GUEST-FIRST: with no VITE_SUPABASE_* env config the game behaves exactly as
// before — guest session, local saves, no network calls, no console errors; the
// modal simply explains that cloud sync is not configured on this deployment.
// With config set: email magic-link sign-in, newer-year-wins save sync on
// sign-in, and a debounced (30 s) cloud push while signed in. saveLocal keeps
// running unconditionally in main.ts — the cloud is a second copy, never the
// only one.
import type { Simulation } from "../game/state";
import type { Session } from "./session";
import { isCloudConfigured, loadLocal, saveLocal } from "./session";
import { CloudClient, initialSync } from "./cloud";

const PUSH_INTERVAL_MS = 30_000;
const ADOPT_FLAG = "mildura.cloudAdopted"; // sessionStorage reload guard

const PROFILE_CSS = `
  .profile-btn {
    position: absolute; top: 14px; left: 468px;
    font-family: Georgia, serif; font-size: 11px; letter-spacing: 1px;
    font-variant: small-caps; color: #efe2bd; cursor: pointer; padding: 8px 12px;
    background: linear-gradient(#4a3820, #2a1d0f 60%, #1c130b);
    border: 2px solid #191009; outline: 1px solid #6b5636; border-radius: 5px;
    text-shadow: 0 1px 1px #000; box-shadow: 0 4px 12px #0008;
  }
  .profile-btn:hover { outline-color: #c9b26a; color: #ffd; }
  .profile-btn .key { color: #b8912f; margin-right: 5px; }
  .profile-panel {
    left: 50%; top: 50%; transform: translate(-50%, -50%);
    width: 420px; max-width: calc(100vw - 40px); z-index: 32;
  }
  .profile-panel.hidden { display: none; }
  .profile-body { padding: 10px 16px 14px; font-size: 13px; line-height: 1.45; }
  .profile-body p { margin: 0 0 10px; }
  .profile-row { display: flex; gap: 8px; margin: 8px 0 10px; }
  .profile-row input[type="email"] {
    flex: 1; font-family: Georgia, serif; font-size: 13px; padding: 7px 9px;
    color: #2b2013; background: #f4e9c6; border: 1px solid #6b5410;
    border-radius: 4px; outline: none;
  }
  .profile-row input[type="email"]:focus { border-color: #b8912f; box-shadow: 0 0 6px #b8912f66; }
  .profile-panel button.pf {
    font-family: Georgia, serif; font-size: 11px; letter-spacing: 0.6px;
    font-variant: small-caps; color: #efe2bd; cursor: pointer; padding: 7px 12px;
    background: linear-gradient(#4a3820, #2a1d0f 60%, #1c130b);
    border: 1px solid #0d0805; outline: 1px solid #6b5636; border-radius: 5px;
    text-shadow: 0 1px 1px #000;
  }
  .profile-panel button.pf:hover { outline-color: #c9b26a; color: #ffd; }
  .profile-panel button.pf.danger { background: linear-gradient(#6b2318, #3d120b 60%, #260a06); outline-color: #8a4536; }
  .profile-panel button.pf.danger:hover { outline-color: #e07a5a; }
  .profile-sync { font-style: italic; color: #6b5410; font-size: 12px; margin: 6px 0 10px; }
  .profile-small { font-size: 11px; color: #7a6a45; line-height: 1.4; border-top: 1px dashed #8a6a1c55; padding-top: 8px; margin-top: 10px; }
  .profile-name { font-weight: 700; color: #46351c; font-variant: small-caps; letter-spacing: 0.5px; }
  .profile-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
`;

export interface ProfileRefs {
  toggle(): void;
  /** Per-frame: debounced cloud push while signed in (no-op as guest). */
  update(): void;
}

export function installProfile(opts: { sim: Simulation; session: Session }): ProfileRefs {
  const { sim, session } = opts;
  const root = document.getElementById("ui")!;

  if (!document.getElementById("profile-style")) {
    const style = document.createElement("style");
    style.id = "profile-style";
    style.textContent = PROFILE_CSS;
    document.head.appendChild(style);
  }

  const env = import.meta.env;
  const client: CloudClient | null = isCloudConfigured()
    ? new CloudClient({ url: env.VITE_SUPABASE_URL as string, anonKey: env.VITE_SUPABASE_ANON_KEY as string })
    : null;

  // --- state ------------------------------------------------------------------
  let open = false;
  let sentTo: string | null = null; // magic link dispatched to this address
  let sending = false;
  let syncNote = "";
  let lastSyncAt = 0; // ms epoch of last successful cloud write/read
  let bootSynced = false; // initial sign-in sync finished — pushes allowed
  let lastPushAt = Date.now();
  let pushInFlight = false;

  // --- DOM ----------------------------------------------------------------------
  const btn = document.createElement("button");
  btn.className = "profile-btn";
  root.appendChild(btn);

  const panel = document.createElement("div");
  panel.className = "panel parchment profile-panel hidden";
  root.appendChild(panel);

  function chipLabel(): string {
    if (client && client.getSession()) return "Profile";
    return client ? "Sign in" : "Profile";
  }

  function hhmm(t: number): string {
    const d = new Date(t);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  function render(): void {
    btn.innerHTML = `<span class="key">[P]</span>${chipLabel()}`;
    const sess = client ? client.getSession() : null;
    let inner = `<h1>Colonist's Ledger</h1><div class="profile-body">`;
    if (!client) {
      inner += `
        <p>Playing as <span class="profile-name">${session.displayName}</span> — free, no account needed.
        Your colony autosaves to this browser.</p>
        <p>Cloud sign-in is not configured on this deployment. To enable it, the site
        operator sets <b>VITE_SUPABASE_URL</b> and <b>VITE_SUPABASE_ANON_KEY</b>
        (see <b>game/SUPABASE.md</b>).</p>
        <div class="profile-actions"><button class="pf" data-act="close">Close</button></div>`;
    } else if (!sess) {
      inner += `
        <p>Playing as <span class="profile-name">${session.displayName}</span>.
        Sign in with an email magic link to keep your colony in the cloud and
        carry it across devices. Free — accounts only store saves.</p>`;
      if (sentTo) {
        inner += `<p class="profile-sync">Magic link sent to <b>${sentTo}</b> — open it on this
          device and you will return here signed in.</p>
          <div class="profile-actions">
            <button class="pf" data-act="resend">Send again</button>
            <button class="pf" data-act="close">Close</button>
          </div>`;
      } else {
        inner += `
          <div class="profile-row">
            <input id="profile-email" type="email" placeholder="you@example.com" autocomplete="email" />
            <button class="pf" data-act="send"${sending ? " disabled" : ""}>${sending ? "Sending…" : "Send magic link"}</button>
          </div>`;
        if (syncNote) inner += `<div class="profile-sync">${syncNote}</div>`;
        inner += `<div class="profile-actions"><button class="pf" data-act="close">Close</button></div>`;
      }
      inner += `<div class="profile-small">Local saves keep working either way; signing in adds a
        cloud copy protected by row-level security (only you can read it).</div>`;
    } else {
      inner += `
        <p>Signed in as <span class="profile-name">${sess.email || "colonist"}</span></p>
        <p class="profile-sync">Cloud save: ${lastSyncAt ? `synced ${hhmm(lastSyncAt)}` : "waiting for first sync…"}</p>`;
      if (syncNote) inner += `<div class="profile-sync">${syncNote}</div>`;
      inner += `
        <div class="profile-actions">
          <button class="pf" data-act="signout">Sign out</button>
          <button class="pf danger" data-act="delete">Delete my data</button>
          <button class="pf" data-act="close">Close</button>
        </div>
        <div class="profile-small">"Delete my data" removes your cloud save rows and signs you
        out; the save in this browser is kept. Honest small print: the anon key cannot delete
        the auth user record itself — full account deletion is done from the Supabase
        dashboard (or with the service key). Email the operator to request it.</div>`;
    }
    inner += `</div>`;
    panel.innerHTML = inner;
  }

  function setNote(msg: string): void {
    syncNote = msg;
    if (open) render();
  }

  // --- cloud flows -----------------------------------------------------------------
  async function bootSync(): Promise<void> {
    if (!client) return;
    try {
      const sess = await client.refreshIfNeeded();
      if (!sess) {
        bootSynced = true;
        render();
        return;
      }
      const { decision, adopted } = await initialSync(client, loadLocal());
      syncNote = decision.message;
      lastSyncAt = Date.now();
      if (adopted) {
        saveLocal(adopted);
        // Placed buildings restore on the normal boot path; reload once (guarded
        // by sessionStorage so a same-year cloud copy can never loop).
        if (sessionStorage.getItem(ADOPT_FLAG) !== String(adopted.year)) {
          sessionStorage.setItem(ADOPT_FLAG, String(adopted.year));
          window.location.reload();
          return;
        }
        sim.load(adopted);
      }
      bootSynced = true;
      render();
    } catch (err) {
      bootSynced = true; // fall back to guest behaviour; local saves unaffected
      setNote("Cloud sync unavailable — playing on the local save.");
      console.warn("[mildura] cloud sync failed:", err);
    }
  }

  async function sendLink(email: string): Promise<void> {
    if (!client || sending) return;
    sending = true;
    render();
    try {
      await client.sendMagicLink(email, window.location.origin + window.location.pathname);
      sentTo = email;
    } catch (err) {
      setNote("Could not send the link — check the address and try again.");
      console.warn("[mildura] magic link failed:", err);
    } finally {
      sending = false;
      render();
    }
  }

  // --- events ----------------------------------------------------------------------
  panel.addEventListener("keydown", (e) => {
    // Keep typing in the email field from firing global hotkeys (C, 1-5, space, WASD).
    e.stopPropagation();
    if (e.code === "Escape") refs.toggle();
    if (e.code === "Enter") {
      const input = panel.querySelector<HTMLInputElement>("#profile-email");
      if (input && input.value.includes("@")) void sendLink(input.value.trim());
    }
  });
  panel.addEventListener("click", (e) => {
    const act = (e.target as HTMLElement).closest<HTMLElement>("[data-act]")?.dataset.act;
    if (!act) return;
    if (act === "close") refs.toggle();
    else if (act === "send") {
      const input = panel.querySelector<HTMLInputElement>("#profile-email");
      const email = input ? input.value.trim() : "";
      if (email.includes("@")) void sendLink(email);
      else setNote("Enter a valid email address first.");
    } else if (act === "resend") {
      const email = sentTo;
      sentTo = null;
      if (email) void sendLink(email);
      else render();
    } else if (act === "signout" && client) {
      void client.signOut().then(() => {
        sentTo = null;
        setNote("Signed out — back to guest saves in this browser.");
        render();
      });
    } else if (act === "delete" && client) {
      if (!window.confirm("Delete your cloud save data and sign out?")) return;
      void (async () => {
        try {
          await client.refreshIfNeeded();
          await client.deleteCloudSaves();
          await client.signOut();
          sentTo = null;
          setNote("Cloud save data deleted; signed out. Your local browser save is untouched.");
        } catch (err) {
          setNote("Delete failed — please try again.");
          console.warn("[mildura] delete failed:", err);
        }
        render();
      })();
    }
  });
  btn.addEventListener("click", () => refs.toggle());
  window.addEventListener("keydown", (e) => {
    const t = e.target as HTMLElement | null;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
    if (e.code === "KeyP") refs.toggle();
    else if (e.code === "Escape" && open) refs.toggle();
  });

  const refs: ProfileRefs = {
    toggle() {
      open = !open;
      panel.classList.toggle("hidden", !open);
      if (open) render();
    },
    update() {
      if (!client || !bootSynced || pushInFlight) return;
      if (!client.getSession()) return;
      const now = Date.now();
      if (now - lastPushAt < PUSH_INTERVAL_MS) return;
      lastPushAt = now;
      pushInFlight = true;
      void (async () => {
        try {
          const sess = await client.refreshIfNeeded();
          if (sess) {
            await client.upsertCloudSave(sim.snapshot());
            lastSyncAt = Date.now();
            if (open) render();
          }
        } catch {
          /* transient network failure — next 30 s window retries; local save is safe */
        } finally {
          pushInFlight = false;
        }
      })();
    },
  };

  // --- boot -----------------------------------------------------------------------
  if (client) {
    const fromLink = client.consumeAuthRedirect(window.location.hash);
    if (fromLink) {
      history.replaceState(null, "", window.location.pathname + window.location.search);
      open = true; // show the "which save won" line right after the redirect
      panel.classList.remove("hidden");
    }
    void bootSync();
  } else {
    bootSynced = true;
  }
  render();

  return refs;
}
