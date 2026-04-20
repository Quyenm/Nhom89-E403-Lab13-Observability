# Day 13 Observability Lab Report

> **Instruction**: Fill in all sections below. This report is designed to be parsed by an automated grading assistant. Ensure all tags (e.g., `[GROUP_NAME]`) are preserved.

## 1. Team Metadata
- [GROUP_NAME]: 89
- [REPO_URL]: https://github.com/Quyenm/Nhom89-E403-Lab13-Observability
- [MEMBERS]:
  - Member A: Nguyễn Tiến Đạt - 2A202600217: | Role: Logging & PII Scrubbing
  - Member B: Trần Ngọc Hùng - 2A202600429 | Role: Tracing & Enrichment (Langfuse)
  - Member C: Nguyễn Mạnh Quyền - 2A202600481 | Role: SLO & Alert Rules
  - Member D: Dương Trịnh Hoài An - 2A202600050 | Role: Load Test & Incident Injection
  - Member E: Bùi Đức Thắng - 2A202600002 | Role: Dashboard & Evidence Collection
  - Member F: Vũ Quang Dũng - 2A202600442 | Role: Blueprint Report & Lead Demo
  


---

## 2. Group Performance (Auto-Verified)
- [VALIDATE_LOGS_FINAL_SCORE]: 100/100
- [TOTAL_TRACES_COUNT]: 20+
- [PII_LEAKS_FOUND]: 0

---

## 3. Technical Evidence (Group)

### 3.1 Logging & Tracing
- [EVIDENCE_CORRELATION_ID_SCREENSHOT]: docs/evidence/logs_correlation_id.png
- [EVIDENCE_PII_REDACTION_SCREENSHOT]: docs/evidence/logs_pii_redacted.png
- [EVIDENCE_TRACE_WATERFALL_SCREENSHOT]: docs/evidence/langfuse_waterfall.png
- [TRACE_WATERFALL_EXPLANATION]: The trace shows 3 nested spans: `agent.run` is the root span covering the entire pipeline (~170ms). The `rag.retrieve` child span completes in ~2ms under normal conditions, but spikes to 2500ms+ when the `rag_slow` incident is active. The `llm.generate` span always takes ~150ms (deterministic sleep). By comparing these two child spans in the waterfall, we can immediately identify that retrieval latency — not LLM latency — causes the P95 spike.

### 3.2 Dashboard & SLOs
- [DASHBOARD_6_PANELS_SCREENSHOT]: docs/evidence/dashboard_6panels.png
- [SLO_TABLE]:

| SLI | Target | Window | Current Value |
|---|---:|---|---:|
| Latency P95 | < 3000ms | 28d | ~170ms (normal) / ~2670ms (rag_slow) |
| Error Rate | < 2% | 28d | 0% (normal) / ~100% (tool_fail) |
| Cost Budget | < $2.50/day | 1d | ~$0.0003/req (normal) / ~$0.0012/req (cost_spike) |
| Quality Score | ≥ 0.75 | 28d | ~0.80 (normal) |

### 3.3 Alerts & Runbook
- [ALERT_RULES_SCREENSHOT]: docs/evidence/alert_rules.png
- [SAMPLE_RUNBOOK_LINK]: docs/alerts.md#1-high-latency-p95

---

## 4. Incident Response (Group)

### Scenario: `rag_slow`

- [SCENARIO_NAME]: rag_slow
- [SYMPTOMS_OBSERVED]: Dashboard P95 latency jumped from ~170ms to ~2670ms within 2 minutes of enabling the incident. No errors were recorded (error_rate stayed at 0%). Quality scores remained normal.
- [ROOT_CAUSE_PROVED_BY]: Langfuse trace waterfall for any request during the incident shows `rag.retrieve` span duration = 2500ms vs `llm.generate` = 150ms. This is definitive: the bottleneck is in retrieval, not inference. Log line with `latency_ms: 2670` and `correlation_id: req-a3f2b1c0` confirms.
- [FIX_ACTION]: `POST /incidents/rag_slow/disable` immediately restores normal latency. In production: add a 500ms timeout to the retrieval call and fall back to a cached corpus.
- [PREVENTIVE_MEASURE]: (1) Add `asyncio.wait_for(retrieve(message), timeout=0.5)` with graceful fallback in `agent.py`. (2) Set `high_latency_p95` alert to trigger within 5 minutes so on-call is paged before SLO breach. (3) Add per-request retrieval latency as a Langfuse span metric to detect degradation trends early.

### Scenario: `tool_fail`

- [SCENARIO_NAME]: tool_fail
- [SYMPTOMS_OBSERVED]: Error rate spiked to 100% immediately. `error_breakdown` in `/metrics` shows `RuntimeError: 10`. Dashboard error panel turned red.
- [ROOT_CAUSE_PROVED_BY]: Log lines with `"event": "request_failed", "error_type": "RuntimeError"`. Langfuse trace shows `rag.retrieve` span failed with exception `Vector store timeout`.
- [FIX_ACTION]: `POST /incidents/tool_fail/disable`. In production: wrap `retrieve()` in try/except and return fallback corpus instead of raising.
- [PREVENTIVE_MEASURE]: Implement circuit breaker pattern. If retrieval fails 3 times in 30 seconds, open the circuit and serve cached fallback for 1 minute.

### Scenario: `cost_spike`

- [SCENARIO_NAME]: cost_spike
- [SYMPTOMS_OBSERVED]: `cost_last_1h_usd` and `tokens_out_total` grew 4x faster than baseline. Alert `cost_budget_spike` would fire within 15 minutes.
- [ROOT_CAUSE_PROVED_BY]: Langfuse traces show `usage_details.output` = 480–640 tokens vs baseline 80–180 tokens. `cost_usd` field in response body confirms ~4x cost per request.
- [FIX_ACTION]: `POST /incidents/cost_spike/disable`. In production: add `max_tokens` cap in LLM call.
- [PREVENTIVE_MEASURE]: Enforce hard `max_tokens=512` in all LLM calls. Add per-feature token budget. Alert on `tokens_out_total` rate of change.

---

## 5. Individual Contributions & Evidence

### [MEMBER_A_NAME]: Nguyễn Tiến Đạt - 2A202600217
- [TASKS_COMPLETED]:
  - Implemented `CorrelationIdMiddleware` in `app/middleware.py`: generates `req-<8hex>` IDs, binds to structlog contextvars, propagates via response headers `x-request-id` and `x-response-time-ms`
  - Extended `PII_PATTERNS` in `app/pii.py` with passport, Vietnamese address, IP address, JWT token, API key patterns
  - Enabled `scrub_event` processor in `app/logging_config.py` and added `AuditLogProcessor` for separate `data/audit.jsonl`
  - Added `bind_contextvars(user_id_hash, session_id, feature, model, env)` in `app/main.py` `/chat` endpoint
- [EVIDENCE_LINK]: git commit `Dat: add middleware, pii, logging config, main + report`

### [MEMBER_B_NAME]: Trần Ngọc Hùng - 2A202600429
- [TASKS_COMPLETED]:
  - Enhanced `app/tracing.py` with `get_trace_id()`, `flush()`, and `score_current_trace()` on dummy context fallback
  - Refactored `app/agent.py` to use nested `@observe` spans for `_retrieve()` and `_generate()`, added quality tier tags, called `score_current_trace(heuristic_quality)` on every trace
  - Added `env` and `quality:tier` to Langfuse trace tags for filtering
  - Verified ≥20 traces visible in Langfuse with full metadata
- [EVIDENCE_LINK]: git commit `feat: Add LLM Tracing with Langfuse`

### [MEMBER_C_NAME]: Nguyễn Mạnh Quyền - 2A202600481
- [TASKS_COMPLETED]:
  - Rewrote `config/slo.yaml` with 5 SLIs including error budget calculation, warning thresholds, and alert links
  - Expanded `config/alert_rules.yaml` from 3 to 6 alert rules (high_latency_p95, high_latency_p99, high_error_rate, cost_budget_spike, quality_degradation, rag_tool_failure, no_traffic) with recovery conditions
  - Completed `docs/alerts.md` with full 6-section runbook
  - Enhanced `app/metrics.py` with `error_rate_pct()`, `requests_in_window()`, `cost_in_window()`, quality min/max
- [EVIDENCE_LINK]: git commit `update report Nguyen Manh Quyen - 2A202600481`

### [MEMBER_D_NAME]: Dương Trịnh Hoài An - 2A202600050
- [TASKS_COMPLETED]:
  - Enhanced `scripts/load_test.py` with `--repeat` flag, per-request result tracking, and summary table (P50/P95/P99/max, total cost, avg quality, wall time)
  - Enhanced `scripts/inject_incident.py` with `--duration` (auto-disable), `--scenario all`, and status display before/after injection
  - Enhanced `scripts/validate_logs.py` with additional checks for audit log, better scorecard, and sys.exit(1) on failure
  - Ran all 3 incident scenarios and documented results in this report
- [EVIDENCE_LINK]: git commit `feat: enhance load test summary and inject incident tooling`

### [MEMBER_E_NAME]: Bùi Đức Thắng - 2A202600002
- [TASKS_COMPLETED]:
  - Built `docs/dashboard.html`: standalone 6-panel HTML dashboard polling `/metrics` every 15s with SLO bars, sparklines, incident toggles, and live alert banners
  - Completed `docs/grading-evidence.md` with full checklist and screenshot guide
  - Collected and organized all required evidence screenshots in `docs/evidence/`
  - Verified dashboard renders all 6 panels with SLO lines and auto-refresh
- [EVIDENCE_LINK]: git commit `Merge pull request #5 from Quyenm/thang2`

### [MEMBER_F_NAME]: Vũ Quang Dũng - 2A202600442
- [TASKS_COMPLETED]:
  - Filled this blueprint report with complete incident analysis for all 3 scenarios
  - Led the live demo: walked through middleware → structured logs → Langfuse traces → dashboard → alerts
  - Prepared demo script covering the `rag_slow` incident flow: metrics spike → trace waterfall → log root cause → fix
  - Coordinated team integration and final pre-submission validation run
- [EVIDENCE_LINK]: git commit `docs: complete blueprint report and demo script`

---

## 6. Bonus Items (Optional)

- [BONUS_COST_OPTIMIZATION]: Compared `avg_cost_usd` before/after applying max_tokens=256 cap on FakeLLM. Cost reduced from $0.0003 to $0.00015 per request (50% reduction). Evidence: `/metrics` snapshot before and after change.
- [BONUS_AUDIT_LOGS]: Implemented `AuditLogProcessor` in `app/logging_config.py` that writes a separate `data/audit.jsonl` with only audit-relevant events (`request_received`, `response_sent`, `incident_enabled`, `incident_disabled`, `request_failed`). Validates separately via `grading-evidence.md`.
- [BONUS_CUSTOM_METRIC]: Added `quality_min`, `quality_max`, `traffic_last_1h`, `cost_last_1h_usd`, and `error_rate_pct` computed fields to `/metrics` endpoint. Dashboard renders these as SLO bars with color-coded thresholds.
