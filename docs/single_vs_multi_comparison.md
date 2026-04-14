# Single Agent vs Multi-Agent Comparison - Lab Day 09

**Nhóm:** Team 31  
**Ngày:** 2026-04-14

> Số liệu Day 08 lấy từ `lab08-team-31/docs/architecture.md` và `lab08-team-31/docs/tuning-log.md`.
> Số liệu Day 09 lấy từ `python eval_trace.py --analyze` và `artifacts/eval_report.json`.

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Faithfulness | 3.70 / 5 | N/A | N/A | Day 09 chưa có scorecard cùng thang đo |
| Answer Relevance | 3.70 / 5 | N/A | N/A | Chưa chấm cùng rubric Day 08 |
| Context Recall | 5.00 / 5 | N/A | N/A | Day 09 chưa có phép đo recall tương đương |
| Completeness | 3.90 / 5 | N/A | N/A | Chưa thể đo công bằng |
| Avg confidence | N/A | 0.411 | N/A | Từ 57 trace hiện có |
| Avg latency (ms) | N/A | 6853 | N/A | Từ 57 trace hiện có |
| MCP usage rate | N/A | 50% | N/A | `29/57` trace có MCP tool call |
| HITL rate | N/A | 40% | N/A | `23/57` trace có `hitl_triggered=true` |
| Routing visibility | x Không có | check Có route_reason | N/A | Khác biệt kiến trúc rõ nhất |
| Debug time (estimate) | 15-20 phút | 5-10 phút | giảm khoảng 10 phút | Ước lượng từ workflow debug thực tế |

> **Lưu ý:** Day 08 có scorecard chất lượng answer, còn Day 09 hiện đã chạy được với API và retrieval thật trong `.venv`, nhưng chưa có scorecard cùng rubric /5. Vì vậy file này chỉ so sánh trực tiếp những metric thật sự đo được từ trace.

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Khá tốt ở factoid trực tiếp | Tốt hơn trước, đã có answer thật ở nhiều câu nhưng chưa ổn định hoàn toàn |
| Latency | 1 flow retrieve-generate | Chậm hơn do thêm supervisor, worker và trace |
| Observation | Baseline dense đủ mạnh cho nhiều câu FAQ/SLA cơ bản | Day 09 xử lý đúng luồng, nhưng chất lượng còn phụ thuộc mạnh vào retrieval backend |

**Kết luận:** Với câu đơn giản, Day 08 vẫn là baseline gọn và hiệu quả. Tuy nhiên Day 09 đã tiến thêm một bước đáng kể so với lượt chạy trước: synthesis standalone đã trả được answer grounded và nhiều trace test có confidence quanh 0.5-0.6 thay vì luôn rơi về 0.1.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Dễ hụt ở reasoning liên tài liệu | Thiết kế phù hợp hơn và đã kích hoạt MCP thật |
| Routing visible? | x | check |
| Observation | Day 08 failure chủ yếu ở evidence selection và grounded generation | Day 09 trace cho thấy worker đã gọi `search_kb` và `get_ticket_info` riêng cho câu access + P1, nên orchestration multi-hop đang hoạt động thật |

**Kết luận:** Đây là nhóm câu Day 09 có tiềm năng vượt Day 08 rõ nhất. Kiến trúc đã đúng hướng, vì route và MCP orchestration đang hoạt động thật trong trace. Điểm cần cải thiện tiếp theo là chất lượng retrieval và một thang chấm answer tương đương Day 08 để chứng minh lợi ích bằng điểm số.

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | Không có số tổng hợp | Vẫn đáng kể, thể hiện qua confidence trung bình 0.411 và HITL 40% |
| Hallucination cases | Có nguy cơ suy diễn từ context gần đúng | An toàn hơn vì route sang HITL hoặc fallback |
| Observation | Day 08 biết abstain nhưng chưa luôn giải thích tốt | Day 09 route được case `ERR-403-AUTH` sang human review, là điểm cộng rõ ràng về safety |

**Kết luận:** Về safety, Day 09 tốt hơn Day 08 vì hệ thống có đường ra an toàn: HITL, route_reason và confidence. Điều này đặc biệt quan trọng với các câu mà docs không đủ dữ liệu.

---

## 3. Debuggability Analysis

### Day 08 - Debug workflow
```text
Khi answer sai -> phải đọc toàn bộ RAG pipeline code -> tìm lỗi ở indexing/retrieval/generation
Không có trace -> không biết bắt đầu từ đâu
Thời gian ước tính: 15-20 phút
```

### Day 09 - Debug workflow
```text
Khi answer sai -> đọc trace -> xem supervisor_route + route_reason
  -> Nếu route sai -> sửa supervisor logic
  -> Nếu retrieval sai -> test retrieval_worker độc lập
  -> Nếu policy sai -> test policy_tool_worker với cùng state
  -> Nếu synthesis sai -> test synthesis_worker độc lập
Thời gian ước tính: 5-10 phút
```

**Câu cụ thể nhóm đã debug:**  
Trong đợt test Sprint 4, `python eval_trace.py` ban đầu chạy xong 15 câu nhưng crash khi phân tích trace do `eval_trace.py` đọc file JSON bằng encoding mặc định của Windows. Vì Day 09 có trace riêng cho từng run, lỗi được khoanh vùng rất nhanh vào `analyze_traces()` thay vì nhầm sang worker logic. Sau khi sửa `open(..., encoding="utf-8")`, phần analyze/compare chạy lại bình thường.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa prompt hoặc pipeline chính | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Phải re-prompt hoặc đổi retrieval logic | Thêm worker mới hoặc mở rộng policy worker |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa retrieval worker độc lập |
| A/B test một phần | Khó vì pipeline dính chặt | Dễ hơn vì có thể thay từng worker |

**Nhận xét:** Day 09 vượt trội ở khả năng mở rộng. Ví dụ trong trace hiện tại, các câu về P1/access đã gọi `get_ticket_info` qua MCP mà không cần chỉnh toàn bộ prompt như Day 08.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 LLM call | 1 supervisor + retrieval + synthesis |
| Complex query | 1 LLM call | 1 supervisor + policy worker + 1-2 MCP calls + synthesis |
| MCP tool call | N/A | 0-2 tool calls tùy route |

**Nhận xét về cost-benefit:** Day 09 đắt và chậm hơn ở trạng thái hiện tại. `avg_latency_ms = 6853` và các câu policy/multi-hop thường mất `4-8s` hoặc hơn, trong khi lợi ích thu được là trace đầy đủ, MCP orchestration thật và khả năng tách lỗi theo worker. Vì vậy multi-agent đáng giá khi hệ thống cần debug sâu, tool orchestration hoặc xử lý multi-hop phức tạp.

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**

1. Dễ debug hơn rất nhiều nhờ có trace ở từng bước, `route_reason`, `workers_called`, `mcp_tools_used`, `hitl_triggered`.
2. Dễ mở rộng hơn nhờ tách retrieval, policy và MCP thành các thành phần riêng.

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. Chậm hơn và dễ lộ dependency issues hơn, nhất là khi retrieval hoặc synthesis phụ thuộc API/môi trường mạng.

> **Khi nào KHÔNG nên dùng multi-agent?**

Không nên dùng multi-agent khi bài toán chỉ là factoid retrieval đơn giản, domain nhỏ, và nhóm chưa cần trace/debug sâu. Trong trường hợp đó, single-agent như Day 08 ít overhead hơn.

> **Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

Nhóm sẽ ưu tiên hai việc: sửa retrieval để không còn trả `0 chunks` ở standalone test, và bổ sung scorecard/chấm answer cho Day 09 theo cùng rubric với Day 08 để so sánh faithfulness, completeness và relevance một cách công bằng.
