// Milestone narrator: reads era milestones aloud via the Web Speech API,
// preferring an Australian-English voice (with a measured, period delivery).
// Degrades silently where speech synthesis is unavailable — the newspaper
// banner always carries the same words as captions.

let voice: SpeechSynthesisVoice | null = null;
let ready = false;

function pickVoice(): void {
  if (!("speechSynthesis" in window)) return;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return;
  // Strong preference for Australian English; then any English.
  voice =
    voices.find((v) => v.lang === "en-AU") ??
    voices.find((v) => v.lang.startsWith("en-AU")) ??
    voices.find((v) => /australi/i.test(v.name)) ??
    voices.find((v) => v.lang === "en-GB") ??
    voices.find((v) => v.lang.startsWith("en")) ??
    null;
  ready = true;
}

export function initNarrator(): void {
  if (!("speechSynthesis" in window)) return;
  pickVoice();
  window.speechSynthesis.addEventListener?.("voiceschanged", pickVoice);
}

export function narrate(text: string): void {
  if (!("speechSynthesis" in window)) return;
  if (!ready) pickVoice();
  try {
    const u = new SpeechSynthesisUtterance(text);
    if (voice) u.voice = voice;
    u.lang = voice?.lang ?? "en-AU";
    u.rate = 0.92; // unhurried, storyteller pace
    u.pitch = 0.9; // a touch lower — weathered
    u.volume = 1;
    window.speechSynthesis.cancel(); // a fresh milestone interrupts the last
    window.speechSynthesis.speak(u);
  } catch {
    // never let narration break the game
  }
}
