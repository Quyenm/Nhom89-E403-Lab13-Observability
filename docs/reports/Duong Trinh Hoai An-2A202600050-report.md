# BÁO CÁO CÁ NHÂN — MEMBER D

**Họ tên**: Dương Trịnh Hoài An - 2A202600050  
**Vai trò**: Load Test + Inject Incidents  
**Lab**: Day 13 — Observability  
**Ngày nộp**: 20/04/2026  

---

## 1. Tóm tắt công việc đảm nhận

Member D chịu trách nhiệm **kiểm thử hệ thống dưới tải** và **mô phỏng sự cố**. Mục tiêu: tạo đủ traffic để hệ thống observability có dữ liệu thực tế, và chứng minh rằng khi sự cố xảy ra, team có thể phát hiện và debug trong thời gian ngắn.

---

## 2. Chi tiết kỹ thuật đã triển khai

### 2.1 Load Test nâng cấp (`scripts/load_test.py`)

**Code gốc**: Chỉ gửi request và in status code, không có summary.

**Nâng cấp**:

```python
def send_request(client, payload) -> dict:
    # Track đầy đủ: status, latency, correlation_id, cost, quality
    result = { "status": 0, "latency_ms": 0.0, "cost_usd": 0.0, ... }
    ...
    return result

def print_summary(results, total_elapsed):
    ok = [r for r in results if r["status"] == 200]
    latencies_sorted = sorted([r["latency_ms"] for r in ok])

    # P50, P95, P99 tính thủ công không dùng numpy
    p50 = statistics.median(latencies)
    p95_idx = max(0, int(0.95 * len(latencies_sorted)) - 1)
    p99_idx = max(0, int(0.99 * len(latencies_sorted)) - 1)
    ...
```

**Flag mới `--repeat`**: Cho phép lặp lại bộ queries nhiều lần để tạo đủ traces:
```bash
python scripts/load_test.py --concurrency 2 --repeat 2
# → 10 queries × 2 lần × 2 workers = 20 requests = 20 Langfuse traces
```

**Output summary ví dụ**:
```
==================================================
LOAD TEST SUMMARY
==================================================
Total requests : 20
Succeeded      : 20
Failed         : 0
Wall time      : 4.23s
Latency P50    : 168.3ms
Latency P95    : 185.7ms
Latency P99    : 190.1ms
Latency max    : 192.4ms
Total cost USD : $0.000542
Avg quality    : 0.800
==================================================
```

---

### 2.2 Incident Injection nâng cấp (`scripts/inject_incident.py`)

**Nâng cấp 1 — `--duration`** (auto-disable):
```bash
python scripts/inject_incident.py --scenario rag_slow --duration 30
# Enable rag_slow → chờ 30s → tự động disable
# Dùng cho demo: inject, chụp màn hình, hệ thống tự recover
```

**Nâng cấp 2 — `--scenario all`**:
```bash
python scripts/inject_incident.py --scenario all
# Bật cả 3 incidents cùng lúc → test worst case
```

**Nâng cấp 3 — Status display trước/sau**:
```
Current incident status:
  off     ✅  rag_slow    Retrieval latency spike...
  off     ✅  tool_fail   Vector store error...
  off     ✅  cost_spike  Token count explosion...

[OK] rag_slow → ENABLED

Current incident status:
  ACTIVE  ⚠️   rag_slow    Retrieval latency spike...
  off     ✅  tool_fail   ...
  off     ✅  cost_spike  ...
```

---

### 2.3 Validate Logs nâng cấp (`scripts/validate_logs.py`)

Thêm:
- Kiểm tra audit.jsonl có tồn tại không (bonus check)
- Đếm riêng `missing_cid_count` (bao nhiêu request thiếu correlation ID)
- Kiểm tra nhiều PII signals hơn: `0987654321`, `gmail.com`, `yahoo.com`
- `sys.exit(1)` nếu score < 80 (CI/CD friendly)

---

## 3. Kịch bản test đã thực hiện

### Kịch bản 1: Baseline (không incident)

```bash
python scripts/load_test.py --concurrency 1 --repeat 1
```

Kết quả: P95 ~170ms, 0 errors, quality ~0.80.

---

### Kịch bản 2: RAG Slow

```bash
python scripts/inject_incident.py --scenario rag_slow
python scripts/load_test.py --concurrency 2
python scripts/inject_incident.py --scenario rag_slow --disable
```

Quan sát:
- P95 tăng từ 170ms → 2670ms (+1470%)
- Dashboard alert banner xuất hiện: "P2 ALERT: Latency P95 > 3000ms"... (gần ngưỡng)
- Langfuse trace: `rag.retrieve` span = 2500ms, `llm.generate` = 150ms → root cause rõ ràng

---

### Kịch bản 3: Tool Fail

```bash
python scripts/inject_incident.py --scenario tool_fail
python scripts/load_test.py
python scripts/inject_incident.py --scenario tool_fail --disable
```

Quan sát:
- Error rate = 100%
- `error_breakdown: {"RuntimeError": 10}`
- Dashboard: "P1 ALERT: Error rate > 5%"
- Langfuse: `rag.retrieve` span có exception tag

---

### Kịch bản 4: Cost Spike

```bash
python scripts/inject_incident.py --scenario cost_spike
python scripts/load_test.py
python scripts/inject_incident.py --scenario cost_spike --disable
```

Quan sát:
- `tokens_out_total` tăng 4x
- `avg_cost_usd` tăng từ $0.000027 → $0.000105
- Dashboard cost panel chuyển vàng

---

## 4. Bài học rút ra

1. **P-percentile không cần numpy**: `sorted()` + index calculation đủ chính xác cho lab.
2. **Auto-disable (`--duration`) thiết yếu cho demo**: Tránh quên tắt incident → production vẫn chạy scenario lỗi sau demo.
3. **Concurrency test phát hiện context leak**: Chạy `--concurrency 5` giúp kiểm tra `clear_contextvars()` của Member A có hoạt động không (nếu thiếu, correlation_id sẽ bị trộn lẫn).
4. **`sys.exit(1)` trong validate_logs**: Cho phép dùng trong CI pipeline — build fail nếu log quality dưới ngưỡng.
