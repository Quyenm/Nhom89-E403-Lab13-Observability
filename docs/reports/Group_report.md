# BÁO CÁO NHÓM — DAY 13 OBSERVABILITY LAB

**Môn học**: AI Engineering / LLMOps  
**Lab số**: 13 — Monitoring, Logging & Observability  
**Nhóm**: 89
**Ngày nộp**: 20/04/2026  
**Repository**: https://github.com/Quyenm/Nhom89-E403-Lab13-Observability

---

## 1. Tổng quan dự án

Nhóm xây dựng một hệ thống observability hoàn chỉnh cho ứng dụng FastAPI "agent" mô phỏng pipeline RAG (Retrieval-Augmented Generation). Hệ thống bao gồm: structured JSON logging, PII scrubbing, distributed tracing qua Langfuse, định nghĩa SLO, cấu hình alert rules, load testing, dashboard trực tiếp, và báo cáo incident response.

---

## 2. Kiến trúc hệ thống

```
HTTP Request
    │
    ▼
CorrelationIdMiddleware          ← sinh req-<8hex>, bind structlog context
    │
    ▼
FastAPI /chat endpoint           ← bind user_id_hash, session_id, feature, model
    │
    ▼
LabAgent.run()  [@observe]       ← root Langfuse span
  ├── _retrieve() [@observe]     ← child span: rag.retrieve
  └── _generate() [@observe]     ← child span: llm.generate
    │
    ▼
structlog pipeline
  ├── merge_contextvars          ← gắn correlation_id tự động vào mọi log
  ├── add_log_level + timestamp
  ├── scrub_event()              ← xóa PII trước khi ghi
  ├── AuditLogProcessor()        ← ghi riêng data/audit.jsonl
  ├── JsonlFileProcessor()       ← ghi data/logs.jsonl
  └── JSONRenderer()             ← in ra console
```

---

## 3. Kết quả triển khai kỹ thuật

### 3.1 Logging & Correlation ID

- Mọi request đều có `correlation_id` định dạng `req-<8 ký tự hex>`, sinh từ UUID4.
- Header `x-request-id` trong request được ưu tiên (tái sử dụng nếu có).
- Header response trả về: `x-request-id` và `x-response-time-ms`.
- `clear_contextvars()` được gọi đầu mỗi request để tránh context leak giữa các request concurrent.
- Mỗi log record API đều có đủ 8 trường: `ts`, `level`, `event`, `service`, `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`.

**Kết quả validate_logs.py**:
```
+ [PASSED] Basic JSON schema
+ [PASSED] Correlation ID propagation
+ [PASSED] Log enrichment
+ [PASSED] PII scrubbing
+ [BONUS]  Audit log file found (+5)
Estimated Score: 100/100
```

### 3.2 PII Scrubbing

Hệ thống nhận diện và redact 9 loại PII:

| Pattern | Ví dụ | Kết quả |
|---|---|---|
| email | student@vinuni.edu.vn | `[REDACTED_EMAIL]` |
| phone_vn | 0987 654 321 | `[REDACTED_PHONE_VN]` |
| cccd | 012345678901 | `[REDACTED_CCCD]` |
| credit_card | 4111 1111 1111 1111 | `[REDACTED_CREDIT_CARD]` |
| passport | B1234567 | `[REDACTED_PASSPORT]` |
| ip_address | 192.168.1.100 | `[REDACTED_IP_ADDRESS]` |
| jwt_token | eyJ... | `[REDACTED_JWT_TOKEN]` |
| api_key | sk-abc123... | `[REDACTED_API_KEY]` |
| vn_address | Phường 5, Quận 3 | `[REDACTED_VN_ADDRESS]` |

**Lưu ý thiết kế**: Thứ tự pattern được sắp xếp để tránh conflict (CCCD 12 chữ số phải chạy trước phone_vn để tránh greedy match sai).

### 3.3 Tracing (Langfuse)

- 3 spans cho mỗi request: `agent.run` (root), `rag.retrieve` (child), `llm.generate` (child).
- Mỗi trace gắn tags: `["lab", feature, model, env, "quality:high/medium/low"]`.
- `score_current_trace(name="heuristic_quality", value=...)` được gọi tự động.
- `user_id` được hash SHA-256 trước khi đưa vào trace.
- Kết quả: >20 traces với đầy đủ metadata, waterfall rõ ràng phân biệt bottleneck RAG vs LLM.

### 3.4 SLO

| SLI | Mục tiêu | Window | Warning |
|---|---|---|---|
| Latency P95 | < 3000ms | 28 ngày | 2500ms |
| Latency P99 | < 8000ms | 28 ngày | 6000ms |
| Error Rate | < 2% | 28 ngày | 1% |
| Daily Cost | < $2.50 | 1 ngày | $2.00 |
| Quality Score | ≥ 0.75 | 28 ngày | 0.80 |

### 3.5 Alert Rules

6 alert rules được cấu hình:

| Tên | Severity | Điều kiện kích hoạt |
|---|---|---|
| high_latency_p95 | P2 | P95 > 3000ms trong 5 phút |
| high_latency_p99 | P3 | P99 > 8000ms trong 15 phút |
| high_error_rate | P1 | Error rate > 2% trong 2 phút |
| cost_budget_spike | P2 | Chi phí/giờ > 2x baseline trong 15 phút |
| quality_degradation | P3 | Quality avg < 0.70 trong 10 phút |
| rag_tool_failure | P1 | RuntimeError từ rag.retrieve > 3 lần/phút |
| no_traffic | P2 | 0 request trong 10 phút |

### 3.6 Dashboard

Dashboard HTML (`docs/dashboard.html`) có 6 panels, tự động refresh 15 giây:

1. **Latency P50/P95/P99** — bar SLO màu đỏ/vàng/xanh
2. **Traffic** — tổng request + sparkline lịch sử
3. **Error Rate** — % + breakdown theo loại lỗi
4. **Cost** — chi phí giờ + tổng + avg/request
5. **Tokens In/Out** — tổng + tỉ lệ + sparkline
6. **Quality Score** — avg/min/max + incident toggle status

---

## 4. Incident Response

### 4.1 Scenario: `rag_slow`

**Kích hoạt**: `python scripts/inject_incident.py --scenario rag_slow`

**Triệu chứng quan sát được**:
- Dashboard: P95 latency tăng từ ~312ms lên ~5318ms khi bật incident `rag_slow`.
- Error rate vẫn = 0% (không có lỗi, chỉ chậm).
- Quality score không đổi.

**Phân tích root cause (qua trace waterfall)**:
- Span `rag.retrieve`: 2500ms → **bottleneck**
- Span `llm.generate`: 150ms → bình thường
- Kết luận: Vector store bị chậm, KHÔNG phải LLM.

**Cách fix**: `POST /incidents/rag_slow/disable`  
**Preventive**: Thêm timeout 500ms cho retrieve + fallback corpus cache.

**Số liệu thực nghiệm (20/04/2026)**:
- BEFORE (`rag_slow` bật): P95 = 5317.9ms, P99 = 5317.9ms, max = 5319.5ms.
- AFTER (`rag_slow` tắt): P95 = 314.3ms, P99 = 314.3ms, max = 317.4ms.

---

### 4.2 Scenario: `tool_fail`

**Triệu chứng**: Error rate 100%, `error_breakdown: {RuntimeError: N}`.  
**Root cause**: `mock_rag.retrieve()` raise `RuntimeError("Vector store timeout")`.  
**Fix**: Disable incident + wrap retrieve trong try/except với fallback.

---

### 4.3 Scenario: `cost_spike`

**Triệu chứng**: `tokens_out_total` tăng mạnh, chi phí mỗi lượt test tăng xấp xỉ 4x.  
**Root cause**: `FakeLLM.generate()` nhân `output_tokens * 4` khi `cost_spike = True`.  
**Fix**: Disable incident + thêm `max_tokens=256` cap.

**Số liệu thực nghiệm (20/04/2026)**:
- BEFORE (`cost_spike` bật): total cost = $0.085860 (10 requests), P95 = 313.9ms.
- AFTER (`cost_spike` tắt): total cost = $0.020850 (10 requests), P95 = 316.5ms.

---

## 5. Điểm Bonus đạt được

- **Audit logs tách riêng** (+2đ): `AuditLogProcessor` ghi `data/audit.jsonl` chứa các event audit-relevant.
- **Dashboard đẹp, chuyên nghiệp** (+3đ): 6-panel HTML dashboard với SLO bars, sparklines, alert banners, incident toggles.
- **Custom metrics** (+2đ): Thêm `error_rate_pct`, `cost_in_window`, `quality_min/max`, `traffic_last_1h` vào `/metrics`.

---

## 6. Danh sách thành viên và phân công

| Thành viên | Vai trò | Files chính |
|---|---|---|
| Nguyễn Tiến Đạt | Logging + PII | app/middleware.py, app/pii.py, app/logging_config.py, app/main.py |
| Bùi Đức Thắng | Tracing + Langfuse | app/tracing.py, app/agent.py |
| Nguyễn Mạnh Quyền | SLO + Alerts | app/metrics.py, config/slo.yaml, config/alert_rules.yaml, docs/alerts.md |
| Dương Trịnh Hoài An | Load Test + Incidents | scripts/load_test.py, scripts/inject_incident.py, scripts/validate_logs.py |
| Trần Ngọc Hùng | Dashboard + Evidence | docs/dashboard.html, docs/grading-evidence.md |
| Vũ Quang Dũng | Blueprint + Demo Lead | docs/blueprint-template.md, docs/reports/Group_report.md |

---

## 7. Kết quả chạy thực tế trước khi nộp

### 7.1 Baseline load test

Chạy lệnh:

`python scripts/load_test.py --url http://127.0.0.1:8000 --concurrency 2 --repeat 2`

Kết quả:
- Total requests: 20
- Succeeded/Failed: 20/0
- Wall time: 3.25s
- Latency P50/P95/P99/max: 310.9ms / 313.8ms / 313.8ms / 314.4ms
- Total cost USD: $0.038205
- Avg quality: 0.880

### 7.2 Validate logs

Chạy lệnh:

`python scripts/validate_logs.py`

Kết quả:
- Total log records: 461
- Parse errors: 0
- Missing required fields: 0
- Missing enrichment fields: 0
- Missing/bad correlation ID: 0
- Potential PII leaks: 0
- Audit log present: YES
- Estimated Score: 100/100

### 7.3 Unit tests

Chạy lệnh:

`pytest -q`

Kết quả:
- 24 passed in 0.08s
