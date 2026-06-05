# OmokGosu Electron assets

Place app icons here:

- `icon.ico` — Windows installer + window icon (256x256 recommended)
- `icon.png` — fallback / Linux (512x512)

The build (`npm run dist`) will fail with a missing-icon error until these
exist. For an initial test build, any 256x256 .ico works (e.g., generate one
from a placeholder PNG at https://www.icoconverter.com).
