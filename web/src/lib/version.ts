// Version comparison utilities + soft/hard classification for the upgrade
// banner/modal. Mirrors server/omok_server/version.py logic so frontend
// classification matches what the server's middleware enforces.

export const CLIENT_VERSION: string = __OMOK_VERSION__;

export type VersionStatus = "ok" | "soft" | "hard";

export function parseSemver(s: string): [number, number, number] | null {
  const m = /^(\d+)\.(\d+)\.(\d+)$/.exec(s.trim());
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}

export function compareSemver(a: string, b: string): number {
  const pa = parseSemver(a);
  const pb = parseSemver(b);
  if (!pa || !pb) return 0;
  for (let i = 0; i < 3; i++) {
    if (pa[i] !== pb[i]) return pa[i] - pb[i];
  }
  return 0;
}

/**
 * Classify the relationship between server, server's required-floor, and us.
 *
 *   client < minClient                          → "hard"  (server would 426 us)
 *   server <= client                            → "ok"    (we're up to date)
 *   server > client and major/minor differ      → "hard"  (UX could be broken)
 *   server > client and only patch differs      → "soft"  (compat, just nag)
 */
export function classify(
  server: string,
  minClient: string,
  client: string,
): VersionStatus {
  const ps = parseSemver(server);
  const pm = parseSemver(minClient);
  const pc = parseSemver(client);
  if (!ps || !pm || !pc) return "ok"; // junk responses are non-actionable

  if (compareSemver(client, minClient) < 0) return "hard";
  if (compareSemver(server, client) <= 0) return "ok";

  // server > client. Compare major/minor.
  if (ps[0] !== pc[0] || ps[1] !== pc[1]) return "hard";
  return "soft";
}
