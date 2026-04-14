# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Đặng Thanh Tùng
**Vai trò trong nhóm:** Policy Tool Worker Owner
**Ngày nộp:** 14/04/2026
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

**Module/file tôi chịu trách nhiệm:**
- File chính: `workers/policy_tool.py`
- Functions tôi implement: `analyze_policy()`, `_analyze_policy_with_llm()`, `run()`
- File phụ: `graph.py` (wiring workers vào graph), `data/grading_questions.json` (bộ câu hỏi grading), ChromaDB indexing (`chroma_db/`)

Tôi phụ trách toàn bộ `policy_tool_worker` — worker kiểm tra chính sách hoàn tiền, xác định exception (Flash Sale, digital product, pre-v4 temporal scoping), gọi LLM để tạo explanation, và trả `policy_result` vào `AgentState`.

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`policy_result` do tôi tạo ra là đầu vào chính của `synthesis_worker` (cheeka13). Nếu `policy_applies=False` hoặc có exception, synthesis phải phản ánh điều đó vào `final_answer`. Tôi cũng wiring graph để gọi đúng `retrieval_run`, `policy_tool_run`, `synthesis_run` thay vì placeholder (commit `399e098`).

**Bằng chứng (commit hash):**

- `f73fc58` — ChromaDB indexing
- `871e43d` — Implement `policy_tool_worker` (+116 lines)
- `399e098` — Wire workers vào `graph.py`
- `0ca3e0a`, `7e964e2` — Generate traces
- `6a86ad1` — Grading questions + eval report

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Dùng regex-based temporal scoping để phát hiện đơn hàng trước 01/02/2026, thay vì để LLM tự suy luận về version policy.

Ban đầu code chỉ check chuỗi cứng `"31/01"`, `"30/01"`, `"trước 01/02"` bằng `in`. Cách này bỏ sót nhiều biến thể ngày tháng (VD: `15/01/2026`, `tháng 1 2026`, `january 2026`). Lựa chọn thay thế là để LLM tự phán đoán version từ context — nhưng LLM có thể bỏ qua điều kiện temporal nếu context chunk không đề cập ngày.

Tôi chọn dùng một danh sách regex patterns bao phủ 6 dạng biểu diễn ngày khác nhau:

```python
_pre_v4_date_patterns = [
    r"\b(3[01]|[12]\d|0?\d)/01(/2026)?\b",  # 31/01, 15/01/2026
    r"\btrước\s+01/02(/2026)?\b",
    r"\btháng\s*(1|01)\s*(năm\s*2026)?\b",
    r"\bjanuary\s*2026\b",
    r"\bv3\b",
]
```

Khi match, code set cứng `policy_applies=False` và `policy_name="refund_policy_v3"` — LLM không thể override.

**Trade-off đã chấp nhận:** Regex có thể false positive nếu task đề cập tháng 1 theo ngữ cảnh khác (VD: hỏi về SLA tháng 1). Nhưng đây là trade-off chấp nhận được vì false negative (bỏ sót v3 case) nguy hiểm hơn nhiều về mặt compliance.

**Bằng chứng từ trace:**

```
trace: run_20260414_171532.json
task: "Khách hàng đặt đơn ngày 31/01/2026..."
policy_name: refund_policy_v3
policy_applies: False
exception: pre_v4_policy_version
explanation: "Yêu cầu không được chấp thuận vì đơn hàng đặt trước 01/02/2026..."
hitl_triggered: True
latency_ms: 5474
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** LLM override rule-based `policy_applies=False` — bot trả lời "được hoàn tiền" dù đơn thuộc v3.

**Symptom:**

Với câu hỏi *"Khách hàng đặt đơn ngày 31/01/2026..."*, rule-based đặt `policy_applies=False` và append exception `pre_v4_policy_version`. Tuy nhiên `final_answer` vẫn xác nhận hoàn tiền vì LLM đọc chunk `"Yêu cầu trong 7 ngày làm việc, sản phẩm lỗi nhà sản xuất, chưa dùng"` và tự suy luận từ đó, không biết version context.

**Root cause:**

`_analyze_policy_with_llm()` không nhận `policy_applies` làm tham số — LLM chỉ thấy context chunk và exception list trong prompt, không thấy kết luận rule-based. System prompt cũ cũng không có ràng buộc cứng.

**Cách sửa:**

1. Thêm `policy_applies: bool = True` vào signature của `_analyze_policy_with_llm()`
2. Inject vào `user_content`: `"policy_applies (rule-based): {policy_applies}"`
3. Cập nhật system prompt: *"Nếu rule-based đã xác định `policy_applies=False`, KHÔNG được kết luận ngược lại."*
4. Truyền `policy_applies=policy_applies` tại nơi gọi hàm

**Bằng chứng trước/sau:**

```
TRƯỚC: explanation = "Khách hàng được hoàn tiền vì sản phẩm lỗi nhà sản xuất và chưa kích hoạt."
       policy_applies (return) = False  ← mâu thuẫn với explanation

SAU:   explanation = "Yêu cầu không được chấp thuận vì đơn hàng đặt trước 01/02/2026,
                      áp dụng chính sách v3 nhưng tài liệu v3 không có sẵn."
       policy_applies (return) = False  ← nhất quán
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Tôi implement hoàn chỉnh `analyze_policy()` với rule-based exception detection coverage tốt (Flash Sale, digital product, activated product, temporal v3/v4 scoping), kết hợp LLM explanation với fallback an toàn. Việc wiring graph từ placeholder sang real workers (commit `399e098`) giúp cả team unblock được end-to-end run sớm.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

`policy_tool_worker` gán `policy_name="refund_policy_v4"` cho tất cả câu hỏi không liên quan đến hoàn tiền (VD: câu hỏi về access control, SLA) — đây là false assignment cần fix. Ngoài ra tôi chưa viết unit test độc lập cho các regex pattern.

**Nhóm phụ thuộc vào tôi ở đâu?**

`synthesis_worker` phụ thuộc vào `policy_result` tôi tạo. Nếu `policy_applies` sai thì `final_answer` cũng sai theo. Việc wiring graph (commit `399e098`) là prerequisite để cả team chạy được pipeline thật.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi phụ thuộc vào `retrieval_worker` (tktrev) để có `retrieved_chunks` đủ chất lượng — nếu chunks không relevant, LLM explanation trong `_analyze_policy_with_llm` sẽ kém chính xác.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ fix việc `policy_name` bị gán nhầm thành `"refund_policy_v4"` cho các câu hỏi không liên quan hoàn tiền. Trace `run_20260414_171505.json` (câu hỏi về Level 3 access) cho thấy `policy_name: refund_policy_v4` dù task hoàn toàn không liên quan đến refund. Cách sửa: thêm keyword detection xác định domain trước khi gán `policy_name`, hoặc đổi default thành `"n/a"` nếu không có refund keyword trong task.

---
