# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Trần Tiến Long
**Vai trò trong nhóm:** MCP Owner
**Ngày nộp:** 2026-04-14
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

**Module/file tôi chịu trách nhiệm:**
- File chính: `mcp_server.py`
- Functions tôi implement: `tool_search_kb`, `tool_get_ticket_info`, `tool_check_access_permission`, `tool_create_ticket`, `dispatch_tool`, `list_tools`

Tôi implement toàn bộ Mock MCP Server cho nhóm, bao gồm 4 tools và dispatch layer. Nhiệm vụ cụ thể là xây dựng interface trung gian để `policy_tool.py` (do Đặng Thanh Tùng phụ trách) gọi vào thay vì truy cập ChromaDB trực tiếp.

`tool_search_kb` delegate sang `workers/retrieval.py` để tái dùng ChromaDB logic, có fallback nếu chưa setup. `tool_get_ticket_info` và `tool_check_access_permission` dùng mock data được căn chỉnh với tài liệu thật (`access_control_sop.txt`, `sla_p1_2026.txt`). `dispatch_tool` là entry point duy nhất — không raise exception ra ngoài, luôn trả về dict.

**Kết nối với thành viên khác:** `policy_tool.py` import `dispatch_tool` từ file của tôi. Nếu `dispatch_tool` raise exception, toàn bộ `mcp_tools_used` trong trace sẽ trống và nhóm mất điểm trace.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Căn chỉnh mock data của `check_access_permission` theo đúng nội dung `access_control_sop.txt`, thay vì giữ placeholder tổng quát.

Khi nhận file gốc `mcp_server.py`, `ACCESS_RULES` chỉ định nghĩa Level 1, 2, 3 — thiếu hoàn toàn Level 4 (Admin Access). Quan trọng hơn, Level 3 được gán `emergency_can_bypass = False`, nhưng đọc kỹ **Section 4** của `access_control_sop.txt`:

> *"On-call IT Admin có thể cấp quyền tạm thời (max 24 giờ) sau khi được Tech Lead phê duyệt bằng lời."*

Section 4 không giới hạn theo level — chỉ ngoại lệ duy nhất là Level 4 (Admin Access) do độ rủi ro cao và yêu cầu training bắt buộc. Vì vậy Level 3 emergency bypass phải là `True`.

Lựa chọn thay thế tôi cân nhắc: giữ nguyên placeholder và để synthesis worker tự xử lý. Tuy nhiên nếu làm vậy, câu grading **gq09** ("contractor cần Level 2 tạm thời để fix P1") sẽ không có đủ thông tin từ MCP để synthesis trả lời đúng — vì policy_worker phụ thuộc vào output của `check_access_permission` để biết điều kiện emergency bypass.

**Trade-off chấp nhận:** Mock data chi tiết hơn đồng nghĩa với việc phải đọc kỹ tài liệu và có nguy cơ sai nếu tài liệu không rõ ràng. Tuy nhiên grading dựa trên tài liệu nội bộ, nên đây là trade-off đáng làm.

**Bằng chứng từ code:**

```python
# TRƯỚC (file gốc) — sai với SOP thực tế
3: {
    "required_approvers": ["Line Manager", "IT Admin", "IT Security"],
    "emergency_can_bypass": False,  # ← SAI: SOP Section 4 cho phép
}

# SAU (file của tôi) — khớp với access_control_sop.txt Section 4
3: {
    "name": "Elevated Access",
    "required_approvers": ["Line Manager", "IT Admin", "IT Security"],
    "final_approver": "IT Security",
    "processing_days": 3,
    "emergency_bypass": True,  # ← ĐÚNG theo Section 4 SOP
}
```

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** File gốc `mcp_server.py` thiếu Level 4 và có `emergency_bypass` sai cho Level 3.

**Symptom:** Khi `policy_tool.py` gọi `dispatch_tool("check_access_permission", {"access_level": 3, "is_emergency": True})`, kết quả trả về `emergency_override: False` — không khớp với quy định trong `access_control_sop.txt`. Câu trả lời tổng hợp cuối cùng sẽ nói contractor *không thể* được cấp quyền tạm thời, trong khi thực tế SOP cho phép.

**Root cause:** Mock data được viết theo phỏng đoán, không đối chiếu với tài liệu thật. Level 4 bị bỏ qua hoàn toàn.

**Cách sửa:** Đọc toàn bộ `access_control_sop.txt`, đặc biệt Section 2 (4 levels) và Section 4 (emergency escalation), sau đó viết lại `ACCESS_RULES` với đủ 4 levels và logic emergency đúng.

**Bằng chứng trước/sau:**

```
# TRƯỚC khi sửa:
dispatch_tool("check_access_permission", {"access_level": 3, "requester_role": "contractor", "is_emergency": True})
→ { "emergency_override": False, "notes": ["Level 3 KHÔNG có emergency bypass"] }

# SAU khi sửa:
→ {
    "emergency_override": True,
    "notes": [
      "EMERGENCY BYPASS áp dụng (Section 4, access_control_sop.txt): On-call IT Admin có thể
       cấp Level 3 tạm thời tối đa 24 giờ sau khi Tech Lead phê duyệt bằng lời.",
      "Quyền tạm thời BẮT BUỘC ghi log vào Security Audit (Splunk).",
      "Sau 24 giờ: phải tạo ticket chính thức trên Jira (project IT-ACCESS)..."
    ]
  }
```

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**
Đọc kỹ tài liệu thật trước khi viết mock data. Việc này giúp `check_access_permission` phản ánh đúng quy trình thực tế, đặc biệt quan trọng cho câu grading gq03 và gq09. Ngoài ra `dispatch_tool` được implement đúng contract — không raise exception, luôn trả về error dict — giúp `policy_tool.py` không bị crash khi gọi tool sai.

**Tôi làm chưa tốt ở điểm nào?**
`tool_search_kb` hoàn toàn phụ thuộc vào `retrieve_dense` từ `workers/retrieval.py`. Nếu retrieval worker chưa build ChromaDB index, `search_kb` trả về empty — ảnh hưởng đến toàn bộ flow khi `policy_worker` cần tìm chunks qua MCP.

**Nhóm phụ thuộc vào tôi ở đâu?**
`policy_tool.py` gọi `dispatch_tool` ở mọi bước có `needs_tool=True`. Nếu MCP server thiếu tool hoặc raise exception, field `mcp_tools_used` trong trace sẽ trống và nhóm mất điểm trace (−20% mỗi câu thiếu `mcp_tool_called`).

**Tôi phụ thuộc vào ai?**
Phụ thuộc vào Đặng Thanh Tùng (policy_tool.py) để xác nhận interface gọi đúng — cụ thể là `_call_mcp_tool` có import `dispatch_tool` từ file của tôi không.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Nhìn vào trace `run_20260414_144909.json`, câu hỏi *"Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp"* được route đúng sang `policy_tool_worker` với `needs_tool=True`, nhưng field `mcp_tools_used` trong trace vẫn là `[]` — MCP không được gọi thực tế.

Nếu có thêm 2 giờ, tôi sẽ debug và đảm bảo `policy_tool.py` gọi `check_access_permission` tự động khi task chứa keyword "cấp quyền" hoặc "access level", thay vì chỉ gọi `search_kb`. Điều này trực tiếp ảnh hưởng đến grading câu gq03 và gq09 — hai câu có tổng 26 điểm raw.
