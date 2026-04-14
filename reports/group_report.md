# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** ___________  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| ___ | Supervisor Owner | ___ |
| ___ | Worker Owner | ___ |
| ___ | MCP Owner | ___ |
| ___ | Trace & Docs Owner | ___ |

**Ngày nộp:** ___________  
**Repo:** ___________  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Hướng dẫn nộp group report:**
> 
> - File này nộp tại: `reports/group_report.md`
> - Deadline: Được phép commit **sau 18:00** (xem SCORING.md)
> - Tập trung vào **quyết định kỹ thuật cấp nhóm** — không trùng lặp với individual reports
> - Phải có **bằng chứng từ code/trace** — không mô tả chung chung
> - Mỗi mục phải có ít nhất 1 ví dụ cụ thể từ code hoặc trace thực tế của nhóm

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

> Mô tả ngắn gọn hệ thống nhóm: bao nhiêu workers, routing logic hoạt động thế nào,
> MCP tools nào được tích hợp. Dùng kết quả từ `docs/system_architecture.md`.

**Hệ thống tổng quan:**

Nhóm xây dựng một pipeline multi-agent theo pattern supervisor-worker gồm 3 worker chính và 1 human-review node. `graph.py` đóng vai trò supervisor: đọc câu hỏi, gán `supervisor_route`, `route_reason`, `risk_high`, `needs_tool`, rồi chuyển task tới worker phù hợp. `retrieval_worker` truy vấn ChromaDB để lấy evidence; `policy_tool_worker` xử lý các câu hỏi về refund, access control, temporal scoping và gọi MCP tools khi cần; `synthesis_worker` tổng hợp answer grounded từ state và gắn confidence. Ngoài ra, hệ thống có `mcp_server.py` để expose các tools như `search_kb`, `get_ticket_info`, `check_access_permission` và `create_ticket`.

**Routing logic cốt lõi:**
> Mô tả logic supervisor dùng để quyết định route (keyword matching, LLM classifier, rule-based, v.v.)

Supervisor hiện dùng rule-based routing theo keyword thay vì LLM classifier. Các câu chứa tín hiệu như `hoàn tiền`, `refund`, `flash sale`, `license`, `access`, `level 2/3`, `contractor`, `P1` kết hợp với access/policy thường được đưa vào `policy_tool_worker`; các câu SLA, FAQ và HR thông thường được đưa vào `retrieval_worker`; các câu có mã lỗi không rõ kiểu `ERR-*` sẽ kích hoạt `human_review`. Lý do nhóm chọn hướng này là vì nó nhanh, dễ debug qua trace và phù hợp với phạm vi lab.

**MCP tools đã tích hợp:**
> Liệt kê tools đã implement và 1 ví dụ trace có gọi MCP tool.

- `search_kb`: ___________________
- `get_ticket_info`: ___________________
- ___________________: ___________________
- `search_kb`: semantic search vào knowledge base, được dùng ở nhiều câu policy khi state chưa có `retrieved_chunks`
- `get_ticket_info`: tra cứu metadata ticket P1 mock, được gọi ở các câu có `ticket` hoặc `P1`
- `check_access_permission`: đã implement trong MCP server để phục vụ mở rộng logic access control

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

> Chọn **1 quyết định thiết kế** mà nhóm thảo luận và đánh đổi nhiều nhất.
> Phải có: (a) vấn đề gặp phải, (b) các phương án cân nhắc, (c) lý do chọn phương án đã chọn.

**Quyết định:** Dùng supervisor rule-based kết hợp worker tách biệt thay vì giữ single-agent RAG như Day 08

**Bối cảnh vấn đề:**

Trong Day 08, nhóm thấy hệ thống có `Context Recall = 5.00/5` nhưng `Faithfulness = 3.70/5` và `Completeness = 3.90/5`. Điều này cho thấy việc retrieve đúng nguồn chưa đủ; khi answer sai, nhóm vẫn không biết rõ lỗi nằm ở retrieval, policy reasoning hay generation. Với Day 09, nhóm cần một cách tổ chức dễ trace hơn, có thể mở rộng thêm tool, và tách rõ trách nhiệm giữa từng phần.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Giữ single-agent RAG | Ít bước, nhanh hơn, đơn giản để demo | Khó debug, khó thêm tool, khó audit route |
| Supervisor + workers chuyên biệt | Trace rõ, dễ mở rộng, mỗi worker test độc lập được | Overhead cao hơn, cần quản lý state và route kỹ hơn |

**Phương án đã chọn và lý do:**

Nhóm chọn supervisor + workers chuyên biệt. Lý do chính không phải để làm hệ thống “thông minh hơn” ngay lập tức, mà để làm đường đi của answer trở nên quan sát được. Sau khi triển khai, trace Day 09 đã ghi được `supervisor_route`, `route_reason`, `workers_called`, `mcp_tools_used`, `hitl_triggered`. Đây là cải thiện rất lớn so với Day 08 vì giờ nhóm có thể chỉ ra chính xác query đi qua worker nào, khi nào gọi MCP, và khi nào bật HITL.

**Bằng chứng từ trace/code:**
> Dẫn chứng cụ thể (VD: route_reason trong trace, đoạn code, v.v.)

```text
Trace q15:
route_reason = "task contains policy/access keyword | risk_high flagged"
workers_called = ["policy_tool_worker", "synthesis_worker"]
mcp_tools_used = ["search_kb", "get_ticket_info"]

Trace metrics sau khi chạy bằng .venv:
avg_confidence = 0.411
avg_latency_ms = 6853
mcp_usage_rate = 29/57 (50%)
hitl_rate = 23/57 (40%)
```

---

## 3. Kết quả grading questions (150–200 từ)

> Sau khi chạy pipeline với grading_questions.json (public lúc 17:00):
> - Nhóm đạt bao nhiêu điểm raw?
> - Câu nào pipeline xử lý tốt nhất?
> - Câu nào pipeline fail hoặc gặp khó khăn?

**Tổng điểm raw ước tính:** Chưa chấm chính thức / 96

**Câu pipeline xử lý tốt nhất:**
- ID: `q01` hoặc `q03` — Lý do tốt: đây là các câu hỏi rõ domain, route ổn định, evidence tập trung và answer trả về sát tài liệu

**Câu pipeline fail hoặc partial:**
- ID: `q13` / `q15` — Fail ở đâu: policy reasoning và multi-hop access logic vẫn còn trả lời quá “thuận chiều”  
  Root cause: policy worker chưa đủ chặt để ràng buộc đúng SOP access control trong các tình huống emergency

**Câu gq07 (abstain):** Nhóm xử lý thế nào?

Nếu gặp một câu abstain như `gq07`, nhóm sẽ ưu tiên an toàn: route theo trace, nếu evidence không đủ thì để synthesis trả lời theo hướng “không đủ thông tin trong tài liệu nội bộ” thay vì bịa thêm. Cách làm này nhất quán với hướng đánh giá từ Day 08, nơi hallucination bị phạt nặng hơn trả lời thiếu.

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 2 workers không? Kết quả thế nào?

Với câu multi-hop khó nhất kiểu `gq09`, trace hiện tại của Day 09 cho thấy hệ thống có thể ghi rõ nhiều worker/tool steps, ví dụ `policy_tool_worker` cùng `search_kb` và `get_ticket_info`. Tuy nhiên để đạt full marks thực sự, nhóm vẫn cần siết chặt thêm policy logic để answer cuối không chỉ đúng route mà còn đúng đầy đủ nội dung của cả hai quy trình.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

> Dựa vào `docs/single_vs_multi_comparison.md` — trích kết quả thực tế.

**Metric thay đổi rõ nhất (có số liệu):**

Metric thay đổi rõ nhất không phải accuracy mà là khả năng quan sát pipeline. Day 08 có `Context Recall = 5.00/5` nhưng `Faithfulness = 3.70/5` và `Completeness = 3.90/5`, cho thấy answer sai nhưng khó biết sai ở bước nào. Day 09 sau khi chạy lại với API đã cấu hình trong `.venv` có `avg_confidence = 0.411`, `avg_latency_ms = 6853`, `mcp_usage_rate = 50%`, `hitl_rate = 40%`, cùng với `supervisor_route`, `route_reason`, `workers_called`, nên nhóm nhìn được toàn bộ đường đi của từng answer.

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**

Điều bất ngờ nhất là multi-agent không tự động làm answer tốt hơn. Sau khi bật API, chất lượng đã cải thiện rõ so với lượt chạy fallback trước đó, nhưng pipeline vẫn cho thấy một sự thật quan trọng: orchestration chỉ phát huy khi từng worker đủ tốt. Nếu retrieval chưa ổn định hoặc logic policy chưa đủ chặt, answer cuối vẫn chưa thể vượt baseline Day 08 một cách thuyết phục.

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**

Với các câu hỏi đơn giản một tài liệu, Day 08 vẫn thực dụng hơn vì chỉ cần một flow retrieve-generate. Trong Day 09 hiện tại, `avg_latency_ms = 6853` và các câu route vào `policy_tool_worker` thường mất 4-8 giây hoặc hơn, nên multi-agent chỉ thực sự đáng giá ở các câu multi-hop, cần MCP, hoặc cần trace để debug.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

> Đánh giá trung thực về quá trình làm việc nhóm.

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| ___ | ___________________ | ___ |
| ___ | ___________________ | ___ |
| ___ | ___________________ | ___ |
| ___ | ___________________ | ___ |

**Điều nhóm làm tốt:**

Nhóm làm tốt ở việc chuyển từ một pipeline khó quan sát sang một hệ thống có trace rõ ràng. Sau Sprint 4, nhóm đã chạy được evaluation end-to-end bằng `.venv`, tạo trace thật, đo được confidence, latency, MCP usage và HITL rate. Điều này giúp việc phân tích Day 08 vs Day 09 dựa trên bằng chứng cụ thể thay vì mô tả cảm tính.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**

Điểm chưa tốt là một số worker vẫn phụ thuộc mạnh vào môi trường chạy, đặc biệt retrieval và synthesis. Điều này khiến nhóm từng có lúc hiểu sai rằng logic worker có vấn đề, trong khi nguyên nhân thật lại đến từ sandbox/network. Ngoài ra, phần report và evaluation chỉ thật sự ổn định sau khi chạy lại bằng `.venv`, nghĩa là khâu chuẩn hóa môi trường và kiểm chứng số liệu nên được làm sớm hơn.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**

Nếu làm lại, nhóm sẽ dành thời gian sớm hơn để chốt môi trường chạy chuẩn và thống nhất quy trình test: worker standalone, graph, rồi mới đến eval/report. Cách này sẽ giúp giảm vòng lặp debug muộn và làm cho Sprint 4 bớt phụ thuộc vào việc sửa số liệu ở phút cuối.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

> 1–2 cải tiến cụ thể với lý do có bằng chứng từ trace/scorecard.

Nếu có thêm 1 ngày, nhóm sẽ làm hai việc. Thứ nhất, bổ sung một scorecard cho Day 09 theo cùng rubric với Day 08 để có thể so sánh `faithfulness`, `answer relevance` và `completeness` một cách công bằng. Thứ hai, siết chặt logic access-control trong `policy_tool_worker`, vì trace hiện cho thấy các câu multi-hop như `q13` và `q15` vẫn là nơi hệ thống dễ trả lời chưa đúng hoàn toàn dù route và MCP orchestration đã hoạt động.

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
