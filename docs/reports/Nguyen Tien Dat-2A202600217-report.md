# BÁO CÁO CÁ NHÂN — MEMBER A

**Họ tên**: Nguyễn Tiến Đạt - 2A202600217  
**Vai trò**: Logging + PII Scrubbing  
**Lab**: Day 13 — Observability  
**Ngày nộp**: 20/04/2026  

---

## 1. Tóm tắt công việc đảm nhận

Member A chịu trách nhiệm toàn bộ tầng **logging pipeline** và **PII protection**. Đây là nền tảng của toàn bộ hệ thống observability: nếu log sai format hoặc lộ PII, mọi phần còn lại (tracing, dashboard, alert) đều không có giá trị.

---

## 2. Chi tiết kỹ thuật đã triển khai

### 2.1 Correlation ID Middleware (`app/middleware.py`)

**Vấn đề ban đầu**: File gốc để `correlation_id = "MISSING"` và comment toàn bộ logic.

**Giải pháp triển khai**:

```python
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        clear_contextvars()   # Xóa context cũ, tránh leak giữa requests concurrent

        incoming = request.headers.get("x-request-id", "").strip()
        if incoming:
            correlation_id = incoming          # Tái sử dụng ID từ upstream
        else:
            correlation_id = "req-" + uuid.uuid4().hex[:8]   # Sinh mới

        bind_contextvars(correlation_id=correlation_id)   # Gắn vào mọi log tự động
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["x-request-id"] = correlation_id       # Trả về client
        response.headers["x-response-time-ms"] = str(elapsed_ms)
        return response
```

**Tại sao `clear_contextvars()` quan trọng**: Starlette/uvicorn tái sử dụng thread workers. Nếu không clear, context của request trước (user_id, session_id...) sẽ "rò rỉ" sang request sau — đây là bug khó debug vì chỉ xảy ra dưới tải cao.

**Tại sao format `req-<8hex>`**: Ngắn gọn (11 ký tự), unique đủ dùng (16^8 = 4 tỉ khả năng), dễ grep trong log.

---

### 2.2 PII Scrubbing (`app/pii.py`)

**Mở rộng từ 4 lên 9 patterns**, với thứ tự được thiết kế cẩn thận:

```python
PII_PATTERNS: dict[str, str] = {
    "jwt_token": r"\beyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\b",
    "api_key": r"\b(?:sk|pk|rk|ak)[_\-][A-Za-z0-9]{16,}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "cccd": r"\b\d{12}\b",           # PHẢI trước phone_vn
    "passport": r"\b[A-Z]{1,2}\d{6,9}\b",
    "email": r"[\w\.\+\-]+@[\w\.\-]+\.\w{2,}",
    "phone_vn": r"(?:\+84|0)[ \.\-]?\d{3}[ \.\-]?\d{3}[ \.\-]?\d{3,4}",
    "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "vn_address": r"(?i)\b(?:số\s*\d+|phường|quận|...)...",
}
```

**Bug phát hiện và fix**: CCCD (12 chữ số) và phone VN (10-11 chữ số) có thể overlap. Nếu chạy phone_vn trước, chuỗi `012345678901` sẽ bị match 11 ký tự đầu thành `[REDACTED_PHONE_VN]` và còn sót `1` ở cuối — CCCD không được scrub. Fix: đặt `cccd` **trước** `phone_vn` trong dict.

---

### 2.3 Logging Pipeline (`app/logging_config.py`)

**Bật `scrub_event` processor** (bị comment trong code gốc):

```python
structlog.configure(
    processors=[
        merge_contextvars,       # Tự động gắn correlation_id từ middleware
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
        scrub_event,             # ← ĐÃ BẬT: scrub PII trong mọi log field
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        AuditLogProcessor(),     # ← MỚI: ghi riêng audit.jsonl
        JsonlFileProcessor(),    # ghi logs.jsonl
        structlog.processors.JSONRenderer(),
    ],
    ...
)
```

**Thêm `AuditLogProcessor`** (bonus): Chỉ ghi các event audit-relevant (`request_received`, `response_sent`, `incident_enabled`, `incident_disabled`, `request_failed`) ra `data/audit.jsonl` riêng biệt. Thiết kế này tuân theo nguyên tắc separation of concerns: log đầy đủ cho debug, audit log gọn nhẹ cho compliance.

---

### 2.4 Context Enrichment (`app/main.py`)

```python
bind_contextvars(
    user_id_hash=hash_user_id(body.user_id),   # Hash SHA-256, 12 ký tự hex
    session_id=body.session_id,
    feature=body.feature,
    model=agent.model,
    env=os.getenv("APP_ENV", "dev"),
)
```

Nhờ `merge_contextvars` trong structlog pipeline, 5 trường này tự động xuất hiện trong **mọi** log record được tạo trong suốt lifecycle của request — kể cả log từ `agent.py`, không cần truyền thủ công.

---

## 3. Kiểm thử

Viết 13 test cases trong `tests/test_pii.py`:

| Test | Kết quả |
|---|---|
| test_scrub_email | PASSED |
| test_scrub_phone_vn | PASSED |
| test_scrub_credit_card | PASSED |
| test_scrub_cccd | PASSED (sau khi fix ordering) |
| test_scrub_passport | PASSED |
| test_scrub_ip_address | PASSED |
| test_scrub_multiple_pii | PASSED |
| test_scrub_clean_text | PASSED |
| test_summarize_truncates | PASSED |
| test_summarize_scrubs | PASSED |
| test_hash_user_id_length | PASSED |
| test_hash_user_id_deterministic | PASSED |
| test_hash_user_id_different | PASSED |

---

## 4. Kết quả validate_logs.py sau khi triển khai

```
+ [PASSED] Basic JSON schema (ts, level, event, correlation_id)
+ [PASSED] Correlation ID propagation (>10 unique IDs)
+ [PASSED] Log enrichment (user_id_hash, session_id, feature, model)
+ [PASSED] PII scrubbing (no raw emails or credit card numbers)
+ [BONUS]  Audit log file found (+5)
Estimated Score: 100/100
```

---

## 5. Bài học rút ra

1. **Thứ tự regex quan trọng**: Pattern ngắn hơn có thể "cướp" match của pattern dài hơn. Luôn test trường hợp biên.
2. **`clear_contextvars()` bắt buộc**: Trong async framework, thread reuse là thực tế — context leak là bug production nguy hiểm.
3. **PII scrubbing phải nằm trong pipeline, không trong application code**: Nếu để developer tự nhớ gọi `scrub_text()`, sẽ có lúc quên. Đặt trong structlog processor đảm bảo 100% coverage.
4. **Audit log tách riêng giúp compliance**: Không cần grep toàn bộ log để tìm ai đã làm gì.
