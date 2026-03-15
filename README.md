# Rebate Tracker Executive Dashboard

Standalone HTML executive dashboard for the ClickUp Rebate Tracker.

## Open the Dashboard

Double-click `index.html` — no server, no install required.

## Refresh with Live ClickUp Data

1. Get your ClickUp API token from ClickUp → Settings → Apps
2. Run:

```bash
pip install requests
CLICKUP_API_TOKEN=your_token_here python fetch_clickup.py
```

This rewrites `index.html` with live data from the ClickUp board.

## Files

- `index.html` — full self-contained dashboard
- `fetch_clickup.py` — ClickUp data refresh script
- `ref/` — original spec documents
