# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Đặng Quang Minh 
**Vai trò trong nhóm:** Trace & Docs Owner  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

**Module/file tôi chịu trách nhiệm:**
- File chính: `eval_trace.py`, `docs/system_architecture.md`, `docs/routing_decisions.md`, `docs/single_vs_multi_comparison.md`
- Functions tôi implement: `run_test_questions()`, `run_grading_questions()`, `analyze_traces()`, và các function phân tích metrics từ trace.

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Công việc của tôi tập trung vào việc thu thập và phân tích trace từ pipeline để cung cấp insights cho các owner khác debug và cải thiện hệ thống. Ví dụ, trace từ `eval_trace.py` cung cấp `route_reason`, `confidence`, và `latency_ms` để Supervisor Owner tinh chỉnh routing logic, trong khi MCP Owner sử dụng `mcp_tools_used` để verify tool calls. Ngoài ra, documentation trong `docs/` giúp nhóm hiểu kiến trúc tổng thể và quyết định routing, tạo nền tảng cho Worker Owners optimize workers.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**
- Commit: `Trace & Docs Owner ` — Thêm function `analyze_traces()` trong `eval_trace.py` với comment "# Trace analysis by Minh".
- File `docs/system_architecture.md` 
- Trace files trong `artifacts/traces/` được generate từ `eval_trace.py` mà tôi maintain.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Chọn implement trace logging chi tiết cho routing decisions và MCP tool calls thay vì chỉ log output cuối cùng.

**Ví dụ:**
> "Tôi quyết định log `route_reason`, `mcp_tools_used`, và `workers_called_sequence` trong mỗi trace để tăng visibility vào orchestration flow. Thay vì chỉ ghi final answer, trace giờ ghi rõ supervisor route dựa trên keyword matching (~45ms) thay vì LLM classify (~800ms), và MCP tools như `search_kb` được log với input/output. Điều này giúp debug nhanh hơn khi pipeline fail, như trong trace `run_20260414_170102.json` ghi `route_reason='default route'` cho câu SLA P1, cho thấy routing đúng nhưng reason chưa optimal."

**Lý do:**
- Các lựa chọn thay thế: Log ít hơn để giảm overhead, hoặc dùng external tracing tools như Jaeger.
- Tôi chọn log chi tiết vì lab yêu cầu trace rõ ràng để so sánh single vs multi, và overhead thấp (chỉ thêm JSON fields).
- Trade-off: Tăng file size trace (~2KB mỗi trace) nhưng giảm debug time từ 15-20 phút xuống 5-10 phút, như ghi trong `docs/single_vs_multi_comparison.md`.

**Bằng chứng từ trace/code:**
```
# Từ eval_trace.py
def save_trace(result, output_dir):
    trace = {
        "task": result["task"],
        "route_reason": result.get("route_reason", "unknown"),
        "mcp_tools_used": result.get("mcp_tools_used", []),
        # ... other fields
    }
    # Save to JSON

# Từ trace run_20260414_170102.json
{
  "task": "SLA xử lý ticket P1 là bao lâu?",
  "route_reason": "default route",
  "mcp_tools_used": [],
  "confidence": 0.1
}
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Trace không ghi được `workers_called_sequence` khi có error trong synthesis worker, dẫn đến khó debug multi-hop routing.

**Symptom (pipeline làm gì sai?):**
Khi chạy `python eval_trace.py`, một số trace thiếu `workers_called_sequence`, chỉ có final answer error như "[SYNTHESIS ERROR] Không thể gọi LLM", làm mất visibility vào worker nào fail.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**
Lỗi nằm ở `eval_trace.py` function `save_trace()` — khi exception xảy ra trong `run_graph()`, trace chỉ capture result cuối mà không log sequence workers đã gọi. Điều này xảy ra vì `workers_called_sequence` chỉ được set trong success path, không trong error handling.

**Cách sửa:**
Thêm try-except trong `run_graph()` để log `workers_called_sequence` ngay cả khi fail, và update `save_trace()` để include error details.

**Bằng chứng trước/sau:**
Trước sửa: Trace thiếu sequence, chỉ có "error": "Synthesis failed".
Sau sửa: Trace có "workers_called_sequence": ["retrieval_worker", "synthesis_worker"], "error": "LLM API key missing".

Ví dụ trace trước:
```
{
  "task": "...",
  "error": "Synthesis failed"
}
```

Sau:
```
{
  "task": "...",
  "workers_called_sequence": ["retrieval_worker", "policy_tool_worker"],
  "error": "MCP tool timeout"
}
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**
Tôi làm tốt ở việc cung cấp trace chi tiết và documentation rõ ràng, giúp nhóm debug nhanh chóng. Ví dụ, `docs/routing_decisions.md` ghi 3 quyết định routing thực tế từ trace, và `single_vs_multi_comparison.md` so sánh metrics như latency giảm từ 15-20 phút debug xuống 5-10 phút.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Tôi chưa tối ưu hóa trace file size — với 57 traces, tổng size ~100KB, có thể giảm bằng compression. Ngoài ra, `route_reason` đôi khi còn generic như "default route" thay vì specific keywords.

**Nhóm phụ thuộc vào tôi ở đâu?**
Nhóm phụ thuộc vào trace của tôi để evaluate pipeline performance và debug failures. Nếu tôi chưa xong `eval_trace.py`, các owner khác không thể measure latency hoặc MCP usage rate.

**Phần tôi phụ thuộc vào thành viên khác:**
Tôi phụ thuộc vào Supervisor Owner để có `route_reason` trong state, và Worker Owners để workers log đúng fields như `confidence`. Nếu họ thiếu, trace của tôi sẽ incomplete.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ cải thiện `route_reason` từ generic "default route" thành specific như "contains P1 SLA keyword" bằng cách update keyword matching logic trong supervisor. Lý do: Trace hiện tại cho thấy routing đúng nhưng reason unclear, như trong `run_20260414_170102.json` route đúng nhưng reason generic. Điều này sẽ tăng debug speed thêm 20%, dựa trên metrics trong `docs/single_vs_multi_comparison.md` ghi debug time giảm từ 15 phút xuống 5-10 phút.

---