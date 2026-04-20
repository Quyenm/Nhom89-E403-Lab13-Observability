# Dashboard Spec

Required Layer-2 panels (all implemented in `docs/dashboard.html`):

1. **Latency P50/P95/P99** — SLO bar at 3000ms, color-coded red/yellow/green
2. **Traffic (request count)** — Total + last-1h counter, sparkline history
3. **Error rate with breakdown** — % rate + per error_type count table
4. **Cost over time** — Last-1h USD, total, avg/req, daily budget bar
5. **Tokens in/out** — Total counts, out/in ratio, sparkline history
6. **Quality proxy** — Avg/min/max heuristic score, SLO bar at 0.75, incident toggle status

Quality bar:
- Default time range: live (polling every 15s)
- Auto refresh: every 15 seconds
- Visible threshold/SLO line: yes (SLO bar per panel)
- Units clearly labeled: yes (ms, %, USD, score)
- Alert banners: yes (P1/P2 visual alerts when thresholds exceeded)
- Incident toggles: visible in Quality panel

How to use:
- Open `docs/dashboard.html` in any browser
- Enter the app URL (default: http://127.0.0.1:8000)
- Click Refresh or wait 15s for auto-update
