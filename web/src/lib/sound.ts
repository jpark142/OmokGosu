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
 * Synthesize a short percussive "tok" approximating a wooden stone hitting
 * a board. We feed a short burst of low-pass filtered noise through a sharp
 * envelope; that's much closer to a physical click than the triangle-wave
 * tones the first version used (which read as "SF beep" per user
 * feedback). Some pitch jitter keeps successive moves from sounding
 * identical.
 */
export function playMoveSound(): void {
  if (!_enabled) return;
  const ctx = getContext();
  if (!ctx || ctx.state !== "running") return;

  const now = ctx.currentTime;
  const dur = 0.08;  // ~80ms total tail

  // Noise source — a short buffer of white noise played once.
  const noiseLen = Math.ceil(ctx.sampleRate * dur);
  const buf = ctx.createBuffer(1, noiseLen, ctx.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < noiseLen; i++) data[i] = Math.random() * 2 - 1;
  const noise = ctx.createBufferSource();
  noise.buffer = buf;

  // Low-pass filter so the noise sounds woody, not hissy. Jittered slightly.
  const cutoff = 750 + (Math.random() * 200 - 100);
  const lp = ctx.createBiquadFilter();
  lp.type = "lowpass";
  lp.frequency.value = cutoff;
  lp.Q.value = 1.4;

  // Sharp attack + exponential decay = percussive envelope.
  const env = ctx.createGain();
  env.gain.setValueAtTime(0, now);
  env.gain.linearRampToValueAtTime(0.55, now + 0.003);
  env.gain.exponentialRampToValueAtTime(0.001, now + dur);

  noise.connect(lp).connect(env).connect(ctx.destination);
  noise.start(now);
  noise.stop(now + dur + 0.02);

  // Tiny resonant body tone underneath — barely audible, just lends weight
  // so the click doesn't sound paper-thin on small speakers.
  const body = ctx.createOscillator();
  body.type = "sine";
  body.frequency.value = 180 + (Math.random() * 30 - 15);
  const bodyEnv = ctx.createGain();
  bodyEnv.gain.setValueAtTime(0, now);
  bodyEnv.gain.linearRampToValueAtTime(0.18, now + 0.002);
  bodyEnv.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
  body.connect(bodyEnv).connect(ctx.destination);
  body.start(now);
  body.stop(now + 0.06);
}

// ----- voice selection -----

let _cachedVoice: SpeechSynthesisVoice | null | undefined = undefined;

function pickKoreanFemaleVoice(): SpeechSynthesisVoice | null {
  if (_cachedVoice !== undefined) return _cachedVoice;
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    _cachedVoice = null;
    return null;
  }
  const all = window.speechSynthesis.getVoices();
  if (all.length === 0) {
    // Voices load asynchronously on some browsers. Leave the cache slot
    // unset so a later call retries.
    return null;
  }
  const ko = all.filter((v) => v.lang === "ko-KR" || v.lang.startsWith("ko"));
  // Known female voice names across Chrome/Edge/Safari. Anything with these
  // tokens is preferred; the literal token "female" is a Google fallback.
  const FEMALE_TOKENS = [
    "female",
    "여성",
    "yuna",       // macOS Korean
    "heami",      // Windows 헤미
    "혜미",
    "유나",
    "sora",       // Samsung
    "google",     // Chrome's Google 한국의 default is female
    "kyuri",
  ];
  const lc = (s: string) => s.toLowerCase();
  const female = ko.find((v) => FEMALE_TOKENS.some((t) => lc(v.name).includes(t)));
  const fallback = female ?? ko[0] ?? null;
  _cachedVoice = fallback;
  return fallback;
}

// Some browsers populate voices asynchronously — refresh the cache when
// the voiceschanged event fires.
if (typeof window !== "undefined" && "speechSynthesis" in window) {
  window.speechSynthesis.addEventListener("voiceschanged", () => {
    _cachedVoice = undefined;
  });
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
  const v = pickKoreanFemaleVoice();
  if (v) u.voice = v;
  // Cancel anything queued — countdowns benefit from the latest take
  // arriving promptly, and we don't want a backlog if the page was
  // backgrounded for a moment.
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}
