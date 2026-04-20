# Alert Rules and Runbooks

## 1. High Latency P95
- **Alert name**: `high_latency_p95`
- **Severity**: P2
- **Trigger**: `latency_p95_ms > 3000 for 5m` (warning) / `> 5000 for 30m` (critical)
- **Impact**: Tail latency breaches SLO; users experience slow responses
- **SLO link**: config/slo.yaml → latency_p95_ms (target 99.5% requests < 3000ms)

### Investigation steps
1. Check `/metrics` endpoint for current `latency_p95` and `latency_p99` values
2. Open Langfuse trace list filtered to `last_30m` — sort by duration descending
3. Inspect the slowest trace: compare `rag.retrieve` span vs `llm.generate` span duration
4. Check if incident toggle `rag_slow` is enabled: `GET /health` → incidents field
5. Look at logs for `latency_ms > 2000` log lines to identify which sessions are affected

### Mitigation actions
- If `rag.retrieve` span is slow: disable `rag_slow` via `POST /incidents/rag_slow/disable`, or reduce corpus size
- If `llm.generate` span is slow: reduce prompt length, apply prompt caching
- Immediately: serve cached fallback answers for repeat queries
- Long-term: add timeout + fallback logic in `mock_rag.py` retrieve function

---

## 2. High Error Rate
- **Alert name**: `high_error_rate`
- **Severity**: P1
- **Trigger**: `error_rate_pct > 2 for 2m` (warning) / `> 5 for 5m` (critical)
- **Impact**: Users receive HTTP 500; service unavailable for affected sessions
- **SLO link**: config/slo.yaml → error_rate_pct (target 99.0% success)

### Investigation steps
1. Check `/metrics` endpoint for `error_breakdown` and `error_rate_pct`
2. Filter logs for `"level": "error"` and group by `error_type`
3. If `error_type: RuntimeError` → likely `tool_fail` incident active
4. Inspect failed trace in Langfuse: find the span that produced the error
5. Check `GET /health` → incidents for active toggles

### Mitigation actions
- If `tool_fail` is active: `POST /incidents/tool_fail/disable`
- If schema validation error: check `ChatRequest` field constraints in schemas.py
- Immediate rollback: revert last code deployment
- Retry circuit: add exponential backoff around RAG call in agent.py

---

## 3. Cost Budget Spike
- **Alert name**: `cost_budget_spike`
- **Severity**: P2
- **Trigger**: `hourly_cost_usd > 2x_baseline for 15m`
- **Impact**: Daily budget exhausted prematurely; financial risk
- **SLO link**: config/slo.yaml → daily_cost_usd (target < $2.50/day)

### Investigation steps
1. Check `/metrics` → `cost_last_1h_usd` and `tokens_out_total`
2. Compare `tokens_in_total` vs `tokens_out_total` — spike in output means verbose answers
3. Check Langfuse traces filtered by `tags: cost_spike` or `tags: cost-spike`
4. Check if `cost_spike` incident toggle is active: `GET /health`
5. Identify feature or session_id generating most tokens via trace metadata

### Mitigation actions
- If `cost_spike` incident active: `POST /incidents/cost_spike/disable`
- Apply max_tokens constraint in `FakeLLM.generate()` → output_tokens cap
- Route cheap/simple queries to a less expensive model
- Add per-session token budget enforcement

---

## 4. Quality Degradation
- **Alert name**: `quality_degradation`
- **Severity**: P3
- **Trigger**: `quality_score_avg < 0.7 for 10m`
- **Impact**: Users receive low-quality, unhelpful answers

### Investigation steps
1. Check `/metrics` → `quality_avg`, `quality_min`, `quality_max`
2. Filter Langfuse traces by score `heuristic_quality < 0.7`
3. Check if RAG docs matched for recent queries: look at trace metadata `doc_count`
4. Review log lines for `[REDACTED` in answer_preview (over-scrubbing degrades quality score)

### Mitigation actions
- Expand RAG corpus in `mock_rag.py` with more relevant documents
- Tune PII scrubber to not redact legitimate domain terms
- Adjust `_heuristic_quality` thresholds if baseline has shifted

---

## 5. RAG Tool Failure
- **Alert name**: `rag_tool_failure`
- **Severity**: P1
- **Trigger**: `error_type=RuntimeError AND tool_name=rag.retrieve count > 3 for 1m`
- **Impact**: All responses fall back to generic answers; quality drops to zero

### Investigation steps
1. Check `GET /health` → `incidents.tool_fail`
2. Filter logs for `"event": "request_failed"` with `"error_type": "RuntimeError"`
3. Inspect Langfuse `rag.retrieve` span for the exception message

### Mitigation actions
- Disable `tool_fail` incident: `POST /incidents/tool_fail/disable`
- Add try/except fallback in `mock_rag.retrieve()` to return generic corpus on error
- Alert the vector-store infra team if happening in production

---

## 6. No Traffic
- **Alert name**: `no_traffic`
- **Severity**: P2
- **Trigger**: `request_count == 0 for 10m`
- **Impact**: Service may be down or routing is broken; users cannot reach the API

### Investigation steps
1. Check if the app process is running: `ps aux | grep uvicorn`
2. Curl `GET /health` — if it responds, routing upstream is the issue
3. Check middleware logs for `app_started` event (restart may have wiped metrics counter)

### Mitigation actions
- Restart app: `uvicorn app.main:app --reload`
- Check load balancer / reverse-proxy configuration
- Verify `.env` is correct and app started without import errors
