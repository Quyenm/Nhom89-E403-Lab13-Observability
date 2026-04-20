# BÁO CÁO CÁ NHÂN — MEMBER E

**Họ tên**: Bùi Đức Thắng - 2A202600002  
**Vai trò**: Dashboard + Thu thập bằng chứng  
**Lab**: Day 13 — Observability  
**Ngày nộp**: 20/04/2026  

---

## 1. Tóm tắt công việc đảm nhận

Member E chịu trách nhiệm **trực quan hóa dữ liệu observability** qua dashboard 6 panels và **đảm bảo có đủ bằng chứng** cho phần chấm điểm. Đây là phần "mặt tiền" — giảng viên nhìn vào dashboard trong 30 giây đầu demo.

---

## 2. Chi tiết kỹ thuật đã triển khai

### 2.1 Dashboard HTML (`docs/dashboard.html`)

**Thiết kế kỹ thuật**: Dashboard là file HTML thuần, không cần server riêng, không cần Grafana hay Prometheus. Chỉ cần mở trình duyệt và trỏ vào `/metrics` endpoint của app.

**Cơ chế hoạt động**:
```javascript
async function fetchAll() {
    const [mRes, hRes] = await Promise.all([
        fetch(`${base}/metrics`),      // metrics endpoint
        fetchHealth(base),             // /health endpoint (incidents)
    ]);
    // Cập nhật 6 panels + alert banners
}

fetchAll();
setInterval(fetchAll, 15000);   // Auto-refresh mỗi 15 giây
```

**6 Panels được implement**:

| Panel | Dữ liệu nguồn | Thành phần visual |
|---|---|---|
| ⏱ Latency | `latency_p50/p95/p99` | Số lớn + SLO bar đổi màu |
| 📊 Traffic | `traffic`, `traffic_last_1h` | Counter + SVG sparkline |
| 🚨 Error Rate | `error_rate_pct`, `error_breakdown` | % đổi màu + breakdown table |
| 💰 Cost | `cost_last_1h_usd`, `avg_cost_usd` | USD + daily budget bar |
| 🔢 Tokens | `tokens_in/out_total` | Count + ratio + sparkline |
| ⭐ Quality | `quality_avg/min/max` + incidents | Score + SLO bar + toggle badges |

**SLO bars đổi màu**:
```javascript
function barColor(pct) {
    if (pct > 90) return 'var(--red)';     // Nguy hiểm
    if (pct > 70) return 'var(--yellow)';  // Cảnh báo
    return 'var(--green)';                 // Ổn
}
```

**Alert banners tự động** (không cần cấu hình thêm):
```javascript
if (d.error_rate_pct > 5)
    alerts.push({ cls: 'p1', msg: '🚨 P1 ALERT: Error rate > 5%...' });
if (d.latency_p95 > 3000)
    alerts.push({ cls: 'p2', msg: '⚠️ P2 ALERT: Latency P95 > 3000ms...' });
```

**Sparklines** (không dùng Chart.js, implement thuần SVG):
```javascript
function drawSparkline(svgId, data, color) {
    const pts = data.map((v, i) => {
        const x = pad + (i / (data.length - 1)) * (W - pad * 2);
        const y = H - pad - ((v - mn) / range) * (H - pad * 2);
        return `${x},${y}`;
    });
    svg.innerHTML = `<polyline points="${pts.join(' ')}"
                     stroke="${color}" fill="none" stroke-width="2"/>`;
}
```

---

### 2.2 Evidence Collection Guide (`docs/grading-evidence.md`)

Viết checklist 10 hạng mục với trạng thái, đường dẫn file, và lệnh CLI cụ thể.

Hướng dẫn chi tiết từng screenshot cần chụp:
```
1. Langfuse trace list (≥10 traces)
   → Lệnh tạo: python scripts/load_test.py --concurrency 2 --repeat 2

2. Trace waterfall (1 trace đầy đủ 3 spans)
   → Click vào 1 trace, chụp agent.run → rag.retrieve + llm.generate

3. Logs với correlation_id
   → cat data/logs.jsonl | python -m json.tool | grep correlation_id

4. Logs với PII redacted
   → grep "REDACTED" data/logs.jsonl | head -5

5. Dashboard 6 panels
   → Mở docs/dashboard.html, chờ 15s, chụp full screen

6. Alert rules screenshot
   → Mở config/alert_rules.yaml
```

---

## 3. Demo flow cho phần Dashboard

**Bước 1**: Mở dashboard, tất cả panels hiển thị `—` (chưa có traffic)

**Bước 2**: Chạy load test:
```bash
python scripts/load_test.py --concurrency 2 --repeat 2
```
Panels bắt đầu hiển thị số liệu sau lần refresh đầu tiên.

**Bước 3**: Inject incident để demo alert:
```bash
python scripts/inject_incident.py --scenario rag_slow --duration 60
```
Sau 2-3 refresh: P95 latency panel chuyển vàng/đỏ, alert banner xuất hiện.

**Bước 4**: Dashboard tự recover sau 60 giây khi incident auto-disable.

---

## 4. Bài học rút ra

1. **Dashboard không cần Grafana cho lab demo**: File HTML thuần đủ để demo mọi tính năng yêu cầu, không phụ thuộc infrastructure.
2. **Auto-refresh quan trọng hơn manual refresh**: Trong demo 5 phút, không có thời gian nhớ ấn F5.
3. **Alert banner trực tiếp trên dashboard** = giảm thời gian phát hiện sự cố từ "check sau vài phút" xuống "thấy ngay khi mở dashboard".
4. **Color coding SLO bars**: Người xem không cần đọc số — nhìn màu là biết hệ thống có vấn đề không.
5. **Evidence checklist trước demo**: Đảm bảo không quên screenshot quan trọng trong lúc làm demo.
