// Milestone narrator via the Web Speech API, with per-persona accents:
//   AU — the colony's own voice (default; Latji Latji-era and later milestones)
//   GB — Capt. Sturt and the Jamieson squatters (British)
//   US — the Chaffey era (W.B. & George came via Ontario and California)
// Degrades silently where speech synthesis is unavailable — the newspaper
// banner always carries the same words as captions.

export type Accent = "AU" | "GB" | "US";

let voices: SpeechSynthesisVoice[] = [];

function loadVoices(): void {
  if (!("speechSynthesis" in window)) return;
  const v = window.speechSynthesis.getVoices();
  if (v.length) voices = v;
}

function voiceFor(accent: Accent): SpeechSynthesisVoice | null {
  if (!voices.length) loadVoices();
  const lang = `en-${accent}`;
  return (
    voices.find((v) => v.lang === lang) ??
    voices.find((v) => v.lang.startsWith(lang)) ??
    (accent === "AU" ? voices.find((v) => /australi/i.test(v.name)) : undefined) ??
    // sensible fallback chain: any English rather than silence in the wrong tongue
    voices.find((v) => v.lang === "en-AU") ??
    voices.find((v) => v.lang === "en-GB") ??
    voices.find((v) => v.lang.startsWith("en")) ??
    null
  );
}

export function initNarrator(): void {
  if (!("speechSynthesis" in window)) return;
  loadVoices();
  window.speechSynthesis.addEventListener?.("voiceschanged", loadVoices);
}

export function narrate(text: string, accent: Accent = "AU"): void {
  if (!("speechSynthesis" in window)) return;
  try {
    const u = new SpeechSynthesisUtterance(text);
    const v = voiceFor(accent);
    if (v) u.voice = v;
    u.lang = v?.lang ?? `en-${accent}`;
    u.rate = 0.92; // unhurried, storyteller pace
    u.pitch = 0.9; // a touch lower — weathered
    u.volume = 1;
    window.speechSynthesis.cancel(); // a fresh milestone interrupts the last
    window.speechSynthesis.speak(u);
  } catch {
    // never let narration break the game
  }
}
