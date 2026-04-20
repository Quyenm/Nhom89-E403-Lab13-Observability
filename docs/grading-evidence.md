# Evidence Collection Sheet

## Checklist trước khi nộp

| # | Hạng mục | Trạng thái | File / Path |
|---|---|---|---|
| 1 | validate_logs.py đạt ≥ 80/100 | ✅ | Run: `python scripts/validate_logs.py` |
| 2 | Ít nhất 10 traces trong Langfuse | ✅ | Langfuse Cloud UI → Traces |
| 3 | Dashboard 6 panels | ✅ | `docs/dashboard.html` |
| 4 | Blueprint report đầy đủ | ✅ | `docs/blueprint-template.md` |
| 5 | Alert rules ≥ 3 | ✅ | `config/alert_rules.yaml` (6 rules) |
| 6 | PII không lộ trong logs | ✅ | `app/pii.py` + `app/logging_config.py` |
| 7 | Audit log riêng biệt | ✅ | `data/audit.jsonl` |
| 8 | Correlation ID xuyên suốt | ✅ | `app/middleware.py` |
| 9 | SLO YAML hợp lý | ✅ | `config/slo.yaml` |
| 10 | Load test chạy được | ✅ | `scripts/load_test.py` |

---

## Required Screenshots

### 1. Langfuse — Trace list (≥ 10 traces)
- **Đường dẫn ảnh**: `docs/evidence/langfuse_traces.png`
- **Ghi chú**: Chạy `python scripts/load_test.py --concurrency 2 --repeat 2` để tạo đủ traces

### 2. Langfuse — Full trace waterfall (1 trace)
- **Đường dẫn ảnh**: `docs/evidence/langfuse_waterfall.png`
- **Ghi chú**: Click vào 1 trace, chụp cả 3 spans: `agent.run`, `rag.retrieve`, `llm.generate`

### 3. JSON logs — Có correlation_id
- **Đường dẫn ảnh**: `docs/evidence/logs_correlation_id.png`
- **Lệnh gợi ý**: `cat data/logs.jsonl | python -m json.tool | grep correlation_id`

### 4. JSON logs — PII đã được redact
- **Đường dẫn ảnh**: `docs/evidence/logs_pii_redacted.png`
- **Lệnh gợi ý**: `grep "REDACTED" data/logs.jsonl | head -5`
- **Ghi chú**: Gửi request chứa email và phone để kiểm tra (queries u01, u05, u09 trong `sample_queries.jsonl`)

### 5. Dashboard — 6 panels
- **Đường dẫn ảnh**: `docs/evidence/dashboard_6panels.png`
- **Hướng dẫn**: Mở `docs/dashboard.html` trong trình duyệt, chờ auto-refresh, chụp toàn bộ 6 panels

### 6. Alert rules — Screenshot
- **Đường dẫn ảnh**: `docs/evidence/alert_rules.png`
- **Hướng dẫn**: Mở `config/alert_rules.yaml` hoặc Grafana Alerting panel

---

## Optional Screenshots (Bonus)

### Bonus: Incident trước và sau khi fix
- **Ảnh trước**: `docs/evidence/incident_rag_slow_before.png`
  - Lệnh: `python scripts/inject_incident.py --scenario rag_slow`
  - Chụp dashboard với P95 latency tăng cao
- **Ảnh sau**: `docs/evidence/incident_rag_slow_after.png`
  - Lệnh: `python scripts/inject_incident.py --scenario rag_slow --disable`
  - Chụp dashboard sau khi latency trở về bình thường

### Bonus: Cost spike
- **Ảnh trước**: `docs/evidence/incident_cost_spike_before.png`
  - Lệnh: `python scripts/inject_incident.py --scenario cost_spike`
- **Ảnh sau**: `docs/evidence/incident_cost_spike_after.png`

### Bonus: Audit log riêng biệt
- **Lệnh**: `cat data/audit.jsonl | python -m json.tool | head -20`
- **Ghi chú**: AuditLogProcessor ghi các sự kiện `request_received`, `response_sent`, `incident_enabled`

---

## Cách chạy đầy đủ từ đầu

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Mở terminal thứ 2:

```bash
python scripts/load_test.py --concurrency 2 --repeat 2
python scripts/validate_logs.py
```

Mở trình duyệt: `docs/dashboard.html`

Test incident:

```bash
python scripts/inject_incident.py --scenario rag_slow
python scripts/load_test.py
python scripts/inject_incident.py --scenario rag_slow --disable

python scripts/inject_incident.py --scenario cost_spike
python scripts/load_test.py
python scripts/inject_incident.py --scenario cost_spike --disable
```
