# BÁO CÁO CÁ NHÂN — MEMBER B

**Họ tên**: Trần Ngọc Hùng - 2A202600429  
**Vai trò**: Tracing + Tags (Langfuse)  
**Lab**: Day 13 — Observability  
**Ngày nộp**: 20/04/2026  

---

## 1. Tóm tắt công việc đảm nhận

Tôi chịu trách nhiệm toàn bộ tầng **distributed tracing** qua Langfuse. Mục tiêu: mỗi request tạo ra một trace tree đầy đủ để team có thể nhìn vào Langfuse và biết ngay: request đó mất bao lâu ở từng bước, tốn bao nhiêu token, quality score bao nhiêu, do user nào gửi.

---

## 2. Chi tiết kỹ thuật đã triển khai

### 2.1 Nested Span Architecture (`app/agent.py`)

**Code gốc**: Chỉ có 1 span `agent.run`, không tách sub-spans.

**Giải pháp**: Tách pipeline thành 3 spans lồng nhau:

```python
class LabAgent:

    @observe(name="agent.run")        # ROOT span
    def run(self, ...):
        docs = self._retrieve(message)    # → tạo child span tự động
        response = self._generate(prompt) # → tạo child span tự động
        ...

    @observe(name="rag.retrieve")     # CHILD span 1
    def _retrieve(self, message):
        return retrieve(message)

    @observe(name="llm.generate")     # CHILD span 2
    def _generate(self, prompt):
        return self.llm.generate(prompt)
```

**Tại sao thiết kế này quan trọng**: Trong incident `rag_slow`, nếu chỉ có 1 span ta thấy tổng latency = 2670ms nhưng không biết nguyên nhân. Với 3 spans:
- `rag.retrieve`: 2500ms → **đây là vấn đề**
- `llm.generate`: 150ms → bình thường

Root cause được xác định ngay từ trace waterfall, không cần đọc log.

---

### 2.2 Enrichment — Tags và Metadata

```python
langfuse_context.update_current_trace(
    user_id=hash_user_id(user_id),    # Privacy: hash trước khi gửi
    session_id=session_id,
    tags=["lab", feature, self.model, env,
          f"quality:{self._quality_tier(quality_score)}"],
)
langfuse_context.update_current_observation(
    name="agent.run",
    metadata={
        "doc_count": len(docs),
        "query_preview": summarize_text(message),   # PII đã scrub
        "latency_ms": latency_ms,
        "quality_score": quality_score,
        "env": env,
    },
    usage_details={
        "input": response.usage.input_tokens,
        "output": response.usage.output_tokens,
    },
)
```

**Tag `quality:high/medium/low`**: Cho phép filter trong Langfuse theo tier chất lượng mà không cần viết query phức tạp.

**Tag `env`**: Phân tách trace dev/staging/prod.

---

### 2.3 Automatic Quality Scoring

```python
langfuse_context.score_current_trace(
    name="heuristic_quality",
    value=quality_score,     # 0.0 – 1.0
    comment=f"feature={feature} docs={len(docs)}",
)
```

Mỗi trace tự động được gán score trong Langfuse. Điều này cho phép:
- Lọc trace chất lượng thấp (`score < 0.6`) để debug
- Theo dõi trend quality theo thời gian
- Phát hiện feature nào cho chất lượng kém

---

### 2.4 Graceful Fallback (`app/tracing.py`)

Khi không có Langfuse credentials (local dev không có `.env`), toàn bộ decorator `@observe` vẫn hoạt động bình thường — chỉ là không gửi dữ liệu đi. Dummy context được mở rộng:

```python
class _DummyContext:
    def update_current_trace(self, **kwargs): return None
    def update_current_observation(self, **kwargs): return None
    def get_current_trace_id(self) -> str | None: return None
    def score_current_trace(self, **kwargs): return None
    def flush(self) -> None: return None
```

---

## 3. Kết quả trên Langfuse

Sau khi chạy `python scripts/load_test.py --concurrency 2 --repeat 2`:

- **Tổng traces**: 20 traces
- **Spans/trace**: 3 (agent.run, rag.retrieve, llm.generate)
- **Tags gắn đúng**: lab, qa/summary, claude-sonnet-4-5, dev, quality:medium
- **Score được ghi**: heuristic_quality ~0.80 (normal), ~0.50 (tool_fail)
- **user_id**: hiển thị dạng hash 12 ký tự, không lộ raw user_id

---

## 4. Phân tích trace waterfall — Ví dụ thực tế

**Request bình thường**:
```
agent.run          ████████████████████  170ms
  rag.retrieve     ██  8ms
  llm.generate     █████████████████  155ms
```
→ Bottleneck: LLM generation (bình thường, deterministic 150ms sleep)

**Request khi `rag_slow` active**:
```
agent.run          ████████████████████████████████████████████  2670ms
  rag.retrieve     ████████████████████████████████████  2500ms  ← VẤN ĐỀ
  llm.generate     █████  155ms
```
→ Nhìn vào waterfall: ngay lập tức biết RAG là bottleneck.

---

## 5. Bài học rút ra

1. **Span granularity quyết định tốc độ debug**: Quá ít span → không biết bước nào chậm. Quá nhiều span → noise. 3 spans cho pipeline này là vừa đủ.
2. **Hash user_id trước khi gửi lên external service**: Langfuse là cloud service — không được phép gửi raw PII.
3. **Quality scoring tự động tạo feedback loop**: Team ML có thể dùng Langfuse scores để cải thiện model mà không cần human labeling.
4. **`@observe` decorator pattern**: Non-invasive, code logic không thay đổi, dễ bật/tắt.
