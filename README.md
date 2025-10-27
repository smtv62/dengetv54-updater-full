# dengetv54-updater-full
Automated updater for Dengetv54 m3u playlist.

Features:
- Discovers changing `zirvedesin*.sbs` hosts via crt.sh (Certificate Transparency) and validates `/yayinzirve.m3u8`.
- Scans dengetv hosts starting from dengetv67.live and increments upward until a working host is found.
- Caches discovered base URL in `cache.json` for 12 hours to avoid frequent crt.sh queries.
- GitHub Actions workflow that runs hourly, generates `output/dengetv54.m3u`, and force-pushes updates.

Notes:
- crt.sh JSON endpoint is used: `https://crt.sh/?q=%zirvedesin%&output=json` (respect rate limits).
- If no host is found, falls back to `https://tible.zirvedesin13.sbs/` and `https://dengetv58.live/`.
