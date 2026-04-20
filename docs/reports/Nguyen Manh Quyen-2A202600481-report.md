# BÁO CÁO CÁ NHÂN — MEMBER C

**Họ tên**: Nguyễn Mạnh Quyền - 2A202600481  
**Vai trò**: SLO + Alert Rules  
**Lab**: Day 13 — Observability  
**Ngày nộp**: 20/04/2026  

---

## 1. Tóm tắt công việc đảm nhận

Member C thiết kế toàn bộ tầng **reliability engineering**: định nghĩa SLO (Service Level Objectives), cấu hình alert rules với runbook, và mở rộng metrics endpoint. Đây là phần quyết định khi nào system được coi là "broken" và ai cần được gọi dậy lúc 3 giờ sáng.

---

## 2. Chi tiết kỹ thuật đã triển khai

### 2.1 SLO Definitions (`config/slo.yaml`)

Định nghĩa 5 SLI với đầy đủ thông tin vận hành:

```yaml
slis:
  latency_p95_ms:
    objective: 3000        # ngưỡng vi phạm
    target: 99.5           # % thời gian phải đáp ứng
    warning_threshold: 2500
    alert: high_latency_p95

  error_rate_pct:
    objective: 2
    target: 99.0
    warning_threshold: 1
    alert: high_error_rate

  daily_cost_usd:
    objective: 2.5
    target: 100.0
    warning_threshold: 2.0
    alert: cost_budget_spike

  quality_score_avg:
    objective: 0.75
    target: 95.0
    warning_threshold: 0.80
    alert: quality_degradation
```

**Lý do chọn latency P95 thay vì P99**: P99 bị ảnh hưởng mạnh bởi outlier (ví dụ 1 request debug 30 giây). P95 phản ánh trải nghiệm của phần lớn người dùng cuối tốt hơn. P99 vẫn được định nghĩa riêng nhưng với threshold cao hơn.

**Error budget tính toán**:
```yaml
error_budget:
  latency_p95_ms:
    window_minutes: 40320    # 28 ngày
    allowed_violation_minutes: 201.6   # 0.5% × 40320
```

---

### 2.2 Alert Rules (`config/alert_rules.yaml`)

Mở rộng từ 3 lên 6 rules, mỗi rule có `recovery_condition`:

**Nguyên tắc thiết kế**:
- **P1** (page ngay): Error rate > 2%, RAG tool failure — ảnh hưởng trực tiếp người dùng
- **P2** (notify trong 5 phút): Latency cao, cost spike, no traffic — ảnh hưởng gián tiếp
- **P3** (investigate trong giờ làm việc): Latency P99, quality degradation — degraded but not broken

**Symptom-based vs Cause-based**:
- `high_error_rate`: symptom-based (alert khi thấy kết quả xấu)
- `cost_budget_spike`: cause-based (alert khi biết nguyên nhân — token abuse)
- `rag_tool_failure`: cause-based (alert khi biết component nào hỏng)

**Recovery condition** (thường bị bỏ qua): Quan trọng để tránh alert flapping. Ví dụ: alert fire khi `error_rate > 2% for 2m`, resolve khi `error_rate < 1% for 5m` — ngưỡng resolve thấp hơn và thời gian dài hơn ngưỡng trigger.

---

### 2.3 Enhanced Metrics (`app/metrics.py`)

Thêm 5 computed metrics vào `snapshot()`:

```python
def error_rate_pct() -> float:
    if TRAFFIC == 0: return 0.0
    return round(sum(ERRORS.values()) / TRAFFIC * 100, 2)

def requests_in_window(window_seconds: int = 3600) -> int:
    cutoff = time.time() - window_seconds
    return sum(1 for ts in REQUEST_TIMESTAMPS if ts >= cutoff)

def cost_in_window(window_seconds: int = 3600) -> float:
    cutoff = time.time() - window_seconds
    pairs = list(zip(REQUEST_TIMESTAMPS, REQUEST_COSTS))
    return round(sum(cost for ts, cost in pairs if ts >= cutoff), 6)
```

**Tại sao cần timestamp-based window**: `/metrics` endpoint trả về tổng cộng dồn từ khi app start. Để detect `cost_budget_spike` cần chi phí trong **1 giờ gần nhất**, không phải tổng từ đầu. `REQUEST_TIMESTAMPS` lưu thời điểm mỗi request để tính window chính xác.

---

### 2.4 Runbook (`docs/alerts.md`)

Viết 6 runbook sections, mỗi section có:
- **Impact**: Ảnh hưởng gì đến người dùng
- **Investigation steps**: Từng bước cụ thể, không mơ hồ
- **Mitigation actions**: Hành động tức thì + hành động dài hạn

Ví dụ investigation steps cho `high_latency_p95`:
```
1. Check /metrics → latency_p95 và latency_p99
2. Mở Langfuse trace list, sort by duration giảm dần
3. So sánh rag.retrieve span vs llm.generate span
4. Check GET /health → incidents.rag_slow
5. Tìm log lines với latency_ms > 2000
```

---

## 3. Kết quả SLO so với thực tế

| SLI | SLO Target | Đo được (normal) | Đo được (rag_slow) |
|---|---|---|---|
| Latency P95 | < 3000ms | ~170ms ✅ | ~2670ms ✅ (chưa breach) |
| Error Rate | < 2% | 0% ✅ | 0% ✅ |
| Error Rate | < 2% | 0% ✅ | 100% ❌ (tool_fail) |
| Quality | ≥ 0.75 | ~0.80 ✅ | ~0.80 ✅ |

---

## 4. Bài học rút ra

1. **SLO phải có warning threshold**: Alert P2 khi gần breach, không đợi đến lúc đã breach mới alert.
2. **Recovery condition ngăn alert flapping**: Không có nó, alert sẽ liên tục bật/tắt quanh ngưỡng.
3. **Symptom-based alert cho P1, cause-based cho P2/P3**: Alert P1 phải kích hoạt dù không biết nguyên nhân (người dùng đang bị ảnh hưởng ngay).
4. **Timestamp window tốt hơn counter tích lũy**: Counter tích lũy từ khi start app không phản ánh tình trạng **hiện tại**.
