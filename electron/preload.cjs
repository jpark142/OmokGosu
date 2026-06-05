// Preload script — currently a no-op. Reserved for future IPC bridges
// (e.g., native notifications, OS-level "is the game window focused" hooks)
// if/when we need to escape the renderer sandbox.
//
// Kept as an empty file so electron-builder ships it; main.cjs may opt into
// loading it later by setting webPreferences.preload.
