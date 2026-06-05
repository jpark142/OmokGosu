// OmokGosu desktop client — thin Electron shell.
//
// Loads the deployed web app in a Chromium BrowserWindow. The actual UI /
// game logic lives in the React bundle served by Fly.io; this shell just
// provides a desktop window, app icon, and standalone process.
//
// Default URL is `https://omokgosu.fly.dev`. Override via env var for local
// dev (`OMOKGOSU_URL=http://localhost:8000 npm start`).

const { app, BrowserWindow, Menu, shell } = require("electron");
const path = require("path");

const APP_URL = process.env.OMOKGOSU_URL || "https://omokgosu.fly.dev";

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: "OmokGosu",
    icon: path.join(__dirname, "assets", "icon.ico"),
    backgroundColor: "#0f172a",  // dark slate to avoid the white flash on load
    autoHideMenuBar: true,
    webPreferences: {
      // Security defaults: no Node in renderer, isolated context.
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Hide the default Alt menu entirely (we don't ship custom menu items).
  Menu.setApplicationMenu(null);

  win.loadURL(APP_URL);

  // External links (e.g., <a href="https://...">) open in the user's real
  // browser instead of hijacking this window.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  // Same for direct navigation away from APP_URL's origin.
  win.webContents.on("will-navigate", (event, url) => {
    try {
      const target = new URL(url);
      const home = new URL(APP_URL);
      if (target.origin !== home.origin) {
        event.preventDefault();
        shell.openExternal(url);
      }
    } catch {
      event.preventDefault();
    }
  });
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
