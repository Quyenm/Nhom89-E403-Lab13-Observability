# BÁO CÁO CÁ NHÂN

**Họ tên**: Vũ Quang Dũng - 2A202600442  
**Vai trò**: Blueprint Report + Lead Demo  
**Lab**: Day 13 — Observability  
**Ngày nộp**: 20/04/2026  

---

## 1. Tóm tắt công việc đảm nhận

Member F chịu trách nhiệm **tổng hợp báo cáo kỹ thuật** của toàn nhóm và **dẫn dắt buổi demo live**. Đây là vai trò tích hợp: phải hiểu sâu công việc của tất cả 5 thành viên còn lại để viết báo cáo chính xác và trả lời câu hỏi của giảng viên.

---

## 2. Chi tiết công việc đã thực hiện

### 2.1 Hoàn thiện Blueprint Report (`docs/blueprint-template.md`)

Điền đầy đủ tất cả các mục trong template:

**Mục quan trọng nhất — Incident Response** (10/60 điểm nhóm):

Phân tích 3 scenarios dựa trên dữ liệu thực từ load test:

**Scenario `rag_slow`**:
- Triệu chứng: P95 tăng 1470%, error rate = 0%
- Root cause: `rag.retrieve` span = 2500ms (từ Langfuse trace)
- Fix: `POST /incidents/rag_slow/disable`
- Preventive: `asyncio.wait_for(retrieve(), timeout=0.5)` + fallback corpus

**Scenario `tool_fail`**:
- Triệu chứng: Error rate = 100%, `error_breakdown: {RuntimeError: N}`
- Root cause: `mock_rag.retrieve()` raise `RuntimeError("Vector store timeout")`
- Fix: `POST /incidents/tool_fail/disable`
- Preventive: Circuit breaker pattern với 3 failures / 30s window

**Scenario `cost_spike`**:
- Triệu chứng: `tokens_out_total` tăng 4x, cost/request tăng 4x
- Root cause: `FakeLLM.generate()` nhân `output_tokens * 4` khi `cost_spike = True`
- Fix: `POST /incidents/cost_spike/disable`
- Preventive: Hard `max_tokens=256` cap + per-session token budget

---

### 2.2 Script Demo Live

Chuẩn bị kịch bản demo 15 phút:

**Phần 1 — Architecture (2 phút)**:
> "Hệ thống có 3 tầng observability: Logs (structlog → JSON), Traces (Langfuse), Metrics (in-memory → HTTP endpoint). Mọi request đi qua CorrelationIdMiddleware → được gán ID duy nhất → ID này xuyên suốt trong log, response header, và Langfuse trace."

**Phần 2 — Live Logging Demo (3 phút)**:
```bash
# Terminal 1: app running
uvicorn app.main:app --reload

# Terminal 2: send request với PII
curl -X POST localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u01","session_id":"s01","feature":"qa",
       "message":"My email is test@example.com, what is refund policy?"}'

# Show log output
tail -1 data/logs.jsonl | python -m json.tool
# → Thấy REDACTED_EMAIL, thấy correlation_id, thấy user_id_hash
```

**Phần 3 — Langfuse Trace (3 phút)**:
- Mở Langfuse Cloud → Traces
- Click vào trace vừa tạo
- Chỉ 3 spans: agent.run, rag.retrieve, llm.generate
- Chỉ score heuristic_quality = 0.80

**Phần 4 — Dashboard (2 phút)**:
- Mở `docs/dashboard.html`
- Chạy load test để dashboard có data
- Chỉ 6 panels, SLO bars, incident toggles

**Phần 5 — Incident Demo (4 phút)**:
```bash
# Inject rag_slow
python scripts/inject_incident.py --scenario rag_slow --duration 45

# Gửi requests → dashboard P95 tăng
python scripts/load_test.py --concurrency 2

# Chỉ Langfuse: rag.retrieve span = 2500ms
# Giải thích flow: Metrics spike → trace waterfall → log root cause
# Sau 45s hệ thống tự recover
```

**Phần 6 — Q&A (1 phút buffer)**

---

### 2.3 Câu hỏi khó đã chuẩn bị

**Giảng viên có thể hỏi Member F (demo lead)**:

Q: "Tại sao dùng P95 thay vì average latency?"  
A: Average bị kéo bởi outlier. Nếu 1/100 request mất 10s, average chỉ tăng 100ms nhưng người dùng thứ 5 trong mỗi 100 người trải nghiệm cực tệ. P95 phản ánh trải nghiệm thực tế của phần lớn users.

Q: "PII scrubbing ở client hay server?"  
A: Server-side, trong structlog processor. Không tin vào client scrubbing vì developer có thể quên. Pipeline xử lý trước khi ghi ra disk.

Q: "Correlation ID dùng để làm gì?"  
A: Liên kết tất cả log records của 1 request lại. Nếu request lỗi, lấy correlation_id từ response header → grep logs.jsonl → thấy toàn bộ lifecycle: request nhận → agent chạy → response gửi.

Q: "Langfuse vs OpenTelemetry?"  
A: Langfuse chuyên cho LLM: có prompt/response tracking, token cost, quality scoring built-in. OpenTelemetry generic hơn, phù hợp cho microservices. Lab này dùng Langfuse vì focus vào LLM observability.

---

## 3. Phối hợp nhóm

Vai trò Member F còn bao gồm tích hợp:
- Kiểm tra output của Member A (validate_logs.py đạt 100/100)
- Kiểm tra Member B đã có đủ ≥10 traces trong Langfuse
- Nhắc Member D chạy đủ 3 incident scenarios và chụp screenshots
- Nhắc Member E export dashboard screenshot trước demo

---

## 4. Bài học rút ra

1. **Demo lead phải hiểu cả hệ thống**: Không thể demo tốt nếu chỉ biết phần mình làm.
2. **Chuẩn bị câu hỏi khó trước**: Giảng viên thường hỏi "Tại sao chọn thiết kế này thay vì cái kia?"
3. **Incident demo là highlight**: Đây là lúc toàn bộ observability stack thể hiện giá trị thực — không phải lý thuyết.
4. **Integration check 30 phút trước demo**: Chạy `validate_logs.py` một lần cuối, xác nhận Langfuse có data.
