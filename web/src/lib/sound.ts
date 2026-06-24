// Game audio: a short "click" tone for moves + Korean TTS for byo-yomi
// countdown / period transitions. Two design choices worth noting:
//
//  1. Zero asset files. The click is synthesized via Web Audio API; speech
//     is delivered through the browser's built-in speechSynthesis. This
//     keeps the bundle slim and avoids hosting/copyright questions.
//
//  2. Toggle state lives in localStorage and is broadcast via a custom
//     window event so multiple components (the toggle button, hook
//     readers) can stay in sync without a Context wrapper.

const STORAGE_KEY = "omok:sound-enabled";
const EVENT_NAME = "omok:sound-changed";

// Browsers block AudioContext + speechSynthesis until the page sees a
// user gesture. We lazily resume on the first click anywhere in the app
// (see hookAutoUnlock below).
let _ctx: AudioContext | null = null;
let _unlocked = false;

function getContext(): AudioContext | null {
  if (_ctx !== null) return _ctx;
  if (typeof window === "undefined") return null;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  _ctx = new Ctor();
  return _ctx;
}

// ----- toggle state -----

function readEnabled(): boolean {
  if (typeof window === "undefined") return true;
  const v = window.localStorage.getItem(STORAGE_KEY);
  // Default ON. First-time users hear the game; if they hate it they
  // can mute via the toggle button.
  return v === null ? true : v === "1";
}

let _enabled = readEnabled();

export function isSoundEnabled(): boolean {
  return _enabled;
}

export function setSoundEnabled(value: boolean): void {
  _enabled = value;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
    window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: value }));
  }
}

/**
 * Subscribe to enabled-state changes. Returns an unsubscribe function.
 * Useful for the toggle button + any component that wants to reflect
 * the current state in its UI.
 */
export function subscribeSoundEnabled(cb: (enabled: boolean) => void): () => void {
  const handler = (e: Event) => {
    const detail = (e as CustomEvent<boolean>).detail;
    cb(detail);
  };
  window.addEventListener(EVENT_NAME, handler);
  return () => window.removeEventListener(EVENT_NAME, handler);
}

// ----- audio unlock -----

/**
 * Install a one-shot listener that resumes the AudioContext and primes
 * speechSynthesis the first time the user clicks anywhere. Browser
 * autoplay policies block both APIs until a user gesture, so we piggyback
 * on the very first interaction.
 */
export function hookAutoUnlock(): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = () => {
    if (_unlocked) return;
    _unlocked = true;
    const ctx = getContext();
    if (ctx && ctx.state === "suspended") {
      void ctx.resume().catch(() => {});
    }
    // Prime speechSynthesis: a single near-silent utterance lets later
    // speak() calls fire without the engine warming up mid-countdown.
    if ("speechSynthesis" in window) {
      const u = new SpeechSynthesisUtterance(" ");
      u.volume = 0;
      window.speechSynthesis.speak(u);
    }
    window.removeEventListener("pointerdown", handler);
    window.removeEventListener("keydown", handler);
  };
  window.addEventListener("pointerdown", handler, { once: false });
  window.addEventListener("keydown", handler, { once: false });
  return () => {
    window.removeEventListener("pointerdown", handler);
    window.removeEventListener("keydown", handler);
  };
}

// ----- effects -----

/**
 * Short percussive "click" approximating the sound of a stone landing on
 * a wooden board. Synthesized so we don't ship a sample file. Pitch is
 * randomized slightly per call so successive moves don't sound identical.
 */
export function playMoveSound(): void {
  if (!_enabled) return;
  const ctx = getContext();
  if (!ctx || ctx.state !== "running") return;

  const now = ctx.currentTime;
  // Two layered tones make it sound less "beep" and more "thock".
  // Frequencies tuned by ear; jitter keeps it from being robotic.
  const baseHz = 380 + (Math.random() * 40 - 20);
  const overHz = baseHz * 2.7;

  for (const [freq, gain, dur] of [
    [baseHz, 0.25, 0.09],
    [overHz, 0.08, 0.06],
  ] as const) {
    const osc = ctx.createOscillator();
    const env = ctx.createGain();
    osc.type = "triangle";
    osc.frequency.value = freq;
    env.gain.setValueAtTime(0, now);
    env.gain.linearRampToValueAtTime(gain, now + 0.005);
    env.gain.exponentialRampToValueAtTime(0.001, now + dur);
    osc.connect(env).connect(ctx.destination);
    osc.start(now);
    osc.stop(now + dur + 0.02);
  }
}

/**
 * Speak a short Korean phrase. Cancels any in-flight utterance so a fresh
 * countdown number takes precedence over a stale one (e.g. switching from
 * "10" to "9" mid-second).
 */
export function speak(text: string, opts: { rate?: number; pitch?: number } = {}): void {
  if (!_enabled) return;
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "ko-KR";
  u.rate = opts.rate ?? 1.25;
  u.pitch = opts.pitch ?? 1.0;
  // Cancel anything queued — countdowns benefit from the latest take
  // arriving promptly, and we don't want a backlog if the page was
  // backgrounded for a moment.
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}
