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
 * Synthesize a short, crisp "딱" approximating a wooden stone striking a
 * board. Earlier revisions sounded either SF-beepy (pure tones) or too
 * dull (low-cutoff noise burst). This version uses a very short
 * band-passed noise transient centered in the 2-3kHz range with a near-
 * instantaneous attack — that's where the energy of a real wood-on-wood
 * tap lives. Pitch jitter keeps successive moves from sounding identical.
 */
export function playMoveSound(): void {
  if (!_enabled) return;
  const ctx = getContext();
  if (!ctx || ctx.state !== "running") return;

  const now = ctx.currentTime;
  const dur = 0.035;  // ~35ms — short and snappy

  // Noise source — a tiny buffer of white noise played once.
  const noiseLen = Math.ceil(ctx.sampleRate * dur);
  const buf = ctx.createBuffer(1, noiseLen, ctx.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < noiseLen; i++) data[i] = Math.random() * 2 - 1;
  const noise = ctx.createBufferSource();
  noise.buffer = buf;

  // Band-pass centered around 2.2kHz — woody-crisp territory. The Q gives
  // it a slight resonant ring so the click has identity instead of just
  // being a hiss.
  const bp = ctx.createBiquadFilter();
  bp.type = "bandpass";
  bp.frequency.value = 2200 + (Math.random() * 400 - 200);
  bp.Q.value = 3;

  // Sub-ms attack + fast exponential decay. No layered body tone this
  // time — adding a low sine just thickens the result into "tok" again.
  const env = ctx.createGain();
  env.gain.setValueAtTime(0, now);
  env.gain.linearRampToValueAtTime(0.7, now + 0.001);
  env.gain.exponentialRampToValueAtTime(0.001, now + dur);

  noise.connect(bp).connect(env).connect(ctx.destination);
  noise.start(now);
  noise.stop(now + dur + 0.01);
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
  if (ko.length === 0) {
    _cachedVoice = null;
    return null;
  }
  const lc = (s: string) => s.toLowerCase();

  // Priority tiers, best → worst. Edge's "Online (Natural)" voices and
  // macOS Yuna are markedly less robotic than the older Microsoft Heami
  // or Samsung default. Google's Chrome voice sits in the middle.
  const tiers: Array<(v: SpeechSynthesisVoice) => boolean> = [
    // Microsoft "Online (Natural)" neural voices on Edge — top tier.
    // Names look like "Microsoft SunHi Online (Natural) - Korean (Korea)".
    (v) => /natural|neural/i.test(v.name),
    // macOS / iOS Yuna — very natural female voice.
    (v) => lc(v.name).includes("yuna"),
    // Chrome's built-in Google 한국의 — reasonable, female by default.
    (v) => lc(v.name).includes("google"),
    // Other named female voices we know about.
    (v) => /heami|혜미|가현|kyuri|sora|seoyeon|sunhi|jimin/i.test(lc(v.name)),
    // Anything tagged female.
    (v) => /female|여성|woman/i.test(lc(v.name)),
    // Final fallback: any Korean voice.
    () => true,
  ];
  for (const tier of tiers) {
    const found = ko.find(tier);
    if (found) {
      _cachedVoice = found;
      return found;
    }
  }
  _cachedVoice = ko[0];
  return ko[0];
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
  u.rate = opts.rate ?? 1.0;
  u.pitch = opts.pitch ?? 1.0;
  const v = pickKoreanFemaleVoice();
  if (v) u.voice = v;
  // Cancel any pending utterance so what plays is always the freshest
  // game state. The previous "no-cancel" experiment was meant to stop
  // the v1.4.x bug where '십' clipped mid-word — but that bug actually
  // came from useGameSocket dropping timer_tick (fixed in v1.5.1), not
  // from cancel. With the tick now applied every 250ms, the speak()
  // path is the right place to enforce "spoken number must match the
  // clock"; without cancel, the queue would back up behind a 1s
  // announcement and the countdown would drift behind real time.
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}
