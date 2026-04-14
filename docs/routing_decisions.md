# Routing Decisions Log - Lab Day 09

**Nhóm:** Team 31  
**Ngày:** 2026-04-14

> Các quyết định dưới đây được rút từ trace thật trong `artifacts/traces/` sau khi chạy `python graph.py` và `python eval_trace.py`.

---

## Routing Decision #1

**Task đầu vào:**
> "SLA xử lý ticket P1 là bao lâu?"

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `default route`  
**MCP tools được gọi:** không có  
**Workers called sequence:** `retrieval_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): `Không đủ thông tin trong tài liệu nội bộ.`
- confidence: `0.10`
- Correct routing? Yes

**Nhận xét:**  
Routing đúng vì đây là câu retrieval trực tiếp về SLA/P1. Tuy nhiên `route_reason` chưa tốt, vì thay vì nêu tín hiệu `ticket` hoặc `P1`, hệ thống chỉ ghi `default route`. Đây là ví dụ cho thấy Day 09 đã có trace nhưng vẫn cần cải tiến chất lượng trace.

---

## Routing Decision #2

**Task đầu vào:**
> "Khách hàng đặt đơn ngày 31/01/2026 và yêu cầu hoàn tiền ngày 07/02/2026... Được hoàn tiền không?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains policy/access keyword`  
**MCP tools được gọi:** `search_kb`  
**Workers called sequence:** `policy_tool_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): `[SYNTHESIS ERROR] Không thể gọi LLM. Kiểm tra API key trong .env.`
- confidence: `0.10`
- Correct routing? Yes

**Nhận xét:**  
Routing đúng vì đây là câu policy temporal scoping. Policy worker còn phát hiện được `pre_v4_policy_version`, tức là logic Sprint 2-3 hoạt động đúng hướng. Điểm yếu nằm ở retrieval/MCP fallback và synthesis, không nằm ở route.

---

## Routing Decision #3

**Task đầu vào:**
> "Contractor cần Admin Access (Level 3) để khắc phục sự cố P1 đang active. Quy trình cấp quyền tạm thời như thế nào?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains policy/access keyword`  
**MCP tools được gọi:** `search_kb`, `get_ticket_info`  
**Workers called sequence:** `policy_tool_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): `[SYNTHESIS ERROR] Không thể gọi LLM. Kiểm tra API key trong .env.`
- confidence: `0.10`
- Correct routing? Yes

**Nhận xét:**  
Đây là ví dụ tốt nhất cho lợi ích của kiến trúc multi-agent. Câu hỏi vừa cần access policy vừa cần context P1 ticket, và trace cho thấy worker đã gọi hai MCP tools riêng biệt. Dù answer cuối chưa tốt, trace đủ rõ để chứng minh route và tool orchestration đang hoạt động.

---

## Routing Decision #4 (tuỳ chọn - bonus)

**Task đầu vào:**
> "ERR-403-AUTH là lỗi gì và cách xử lý?"

**Worker được chọn:** `human_review`  
**Route reason:** `unknown error code + risk_high → human review`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**

Đây là case cần abstain hoặc escalation vì trong docs không có mã lỗi tương ứng. Day 08 cũng từng gặp khó với loại câu này. Ở Day 09, supervisor đã route sang human review và trace ghi rõ `hitl_triggered`, nên đây là ví dụ rõ nhất cho phần safety và observability mà single-agent không có.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 23 | 40% |
| policy_tool_worker | 34 | 59% |
| human_review | 0 trong final route thống kê | 0% |

### Routing Accuracy

- Câu route đúng: `15 / 15` trên bộ test hiện tại theo expected route ở mức coarse-grained
- Câu route sai (đã sửa bằng cách nào?): Chưa thấy route sai rõ ràng, nhưng có câu `route_reason` chưa đủ cụ thể để debug tốt
- Câu trigger HITL: `23 / 57` trace hiện có

### Lesson Learned về Routing

1. Rule-based routing là đủ nhanh và minh bạch cho lab, nhất là khi cần đối chiếu trace.
2. Route đúng chưa đủ; để answer tốt còn cần retrieval và synthesis ổn định, đặc biệt ở các case policy multi-hop.

### Route Reason Quality

`route_reason` hiện hữu ích hơn Day 08 vì ít nhất đã có giải thích route, nhưng chưa đồng đều. Ví dụ tốt là `task contains policy/access keyword | risk_high flagged`; ví dụ chưa tốt là `default route`. Bản tiếp theo nên chuẩn hóa format như `matched_keywords=[P1,ticket]; risk_high=false; route=retrieval_worker`.
