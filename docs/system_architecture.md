# System Architecture - Lab Day 09

**Nhóm:** Team 31  
**Ngày:** 2026-04-14  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

**Pattern đã chọn:** Supervisor-Worker

**Lý do chọn pattern này (thay vì single agent):**

Day 08 dùng single-agent RAG theo flow retrieve -> generate, nên khi câu trả lời sai rất khó tách lỗi nằm ở retrieval, policy reasoning hay generation. Hai file đánh giá của Day 08 cho thấy baseline có `Context Recall = 5.00/5` nhưng `Faithfulness = 3.70/5` và `Completeness = 3.90/5`, nghĩa là vấn đề không còn chủ yếu nằm ở việc tìm được tài liệu, mà nằm ở khâu chọn evidence đúng trọng tâm và trả lời grounded. Vì vậy Day 09 chuyển sang pattern supervisor-worker để chia pipeline thành các bước rõ ràng: supervisor chịu trách nhiệm route, retrieval worker chịu trách nhiệm lấy bằng chứng, policy/tool worker xử lý rule và gọi MCP, còn synthesis worker chỉ tổng hợp câu trả lời từ state.

---

## 2. Sơ đồ Pipeline

```text
User Question
    |
    v
Supervisor (graph.py)
    |- phân tích task
    |- gán supervisor_route
    |- ghi route_reason / risk_high / needs_tool
    |
    +--> retrieval_worker
    |       |- dense retrieval qua ChromaDB
    |       |- trả retrieved_chunks + retrieved_sources
    |
    +--> policy_tool_worker
    |       |- gọi search_kb / get_ticket_info qua MCP
    |       |- phát hiện exception cases
    |       |- trả policy_result + mcp_tools_used
    |
    +--> human_review
            |- bật HITL cho case mã lỗi không rõ hoặc risk cao
            |- sau đó quay lại retrieval nếu được approve
    |
    v
synthesis_worker
    |- tổng hợp answer từ chunks + policy_result
    |- gán confidence, sources, final_answer
    |
    v
Trace / Output
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích câu hỏi và chọn worker phù hợp |
| **Input** | `task` từ người dùng |
| **Output** | `supervisor_route`, `route_reason`, `risk_high`, `needs_tool` |
| **Routing logic** | Rule-based theo keyword: refund/access/level -> policy worker; P1/SLA/ticket -> retrieval; `ERR-` + risk cao -> human review |
| **HITL condition** | Hiện được kích hoạt với mã lỗi không rõ (`ERR-*`) hoặc confidence thấp sau synthesis |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Query vector store để lấy bằng chứng |
| **Embedding model** | `text-embedding-3-small` qua OpenAI; fallback random/test nếu thiếu môi trường |
| **Top-k** | Mặc định 3 |
| **Stateless?** | Yes |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Kiểm tra policy và xử lý ngoại lệ trước khi synthesis |
| **MCP tools gọi** | `search_kb`, `get_ticket_info`; có thể mở rộng `check_access_permission` |
| **Exception cases xử lý** | `flash_sale_exception`, `digital_product_exception`, `activated_exception`, `pre_v4_policy_version` |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | `gpt-4o-mini` hoặc Gemini fallback |
| **Temperature** | `0.1` |
| **Grounding strategy** | Chỉ dùng `retrieved_chunks` và `policy_result`, có cơ chế gắn citation nếu answer chưa có |
| **Abstain condition** | Không có chunks hoặc không gọi được model -> trả answer an toàn / synthesis error fallback |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| search_kb | query, top_k | chunks, sources |
| get_ticket_info | ticket_id | ticket details |
| check_access_permission | access_level, requester_role, is_emergency | can_grant, approvers, emergency_override |
| create_ticket | priority, title, description | ticket_id, url, created_at |

---

## 4. Shared State Schema

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| task | str | Câu hỏi đầu vào | supervisor đọc |
| supervisor_route | str | Worker được chọn | supervisor ghi |
| route_reason | str | Lý do route | supervisor ghi |
| risk_high | bool | Đánh dấu tình huống rủi ro cao | supervisor ghi |
| needs_tool | bool | Cho phép worker gọi MCP | supervisor ghi |
| hitl_triggered | bool | Có bật human review hay không | human_review / synthesis ghi |
| retrieved_chunks | list | Evidence lấy được | retrieval hoặc policy worker ghi |
| retrieved_sources | list | Danh sách nguồn retrieve | retrieval ghi |
| policy_result | dict | Kết quả phân tích policy | policy worker ghi |
| mcp_tools_used | list | Nhật ký tool calls | policy worker ghi |
| workers_called | list | Chuỗi worker đã chạy | graph và workers ghi |
| history | list | Log từng bước | toàn pipeline ghi |
| final_answer | str | Câu trả lời cuối | synthesis ghi |
| sources | list | Sources dùng để trả lời | synthesis ghi |
| confidence | float | Độ tin cậy | synthesis ghi |
| latency_ms | int | Tổng thời gian chạy | graph ghi |
| run_id | str | ID trace | graph ghi |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó, vì retrieve và generate nằm trong một flow | Dễ hơn, có thể đọc trace và test từng worker độc lập |
| Thêm capability mới | Phải sửa prompt hoặc pipeline chính | Thêm worker hoặc MCP tool riêng |
| Routing visibility | Không có | Có `supervisor_route` và `route_reason` |
| Xử lý multi-hop | Dễ lẫn evidence giữa nhiều ý | Có thể tách policy/tool và synthesis thành các bước riêng |
| Safety / HITL | Khó cắm vào flow cũ | Có node `human_review` và `hitl_triggered` trong trace |

**Nhóm điền thêm quan sát từ thực tế lab:**

Kết quả Day 08 cho thấy recall đã đủ cao, nên Day 09 không cần tối ưu retrieval đơn thuần trước. Điều quan trọng hơn là thêm quan sát và kiểm soát luồng xử lý. Trong trace hiện tại của Day 09, nhóm đã đo được `mcp_usage_rate = 54%` và `hitl_rate = 58%`, tức là kiến trúc mới đã thực sự tạo thêm các nhánh xử lý mà Day 08 không có.

---

## 6. Giới hạn và điểm cần cải tiến

1. Retrieval hiện phụ thuộc API key OpenAI nên khi thiếu key, `search_kb` rơi về mock fallback và làm chất lượng answer giảm mạnh.
2. Synthesis worker vẫn cần API key để tạo answer thật; khi không có key, hệ thống chỉ trả `[SYNTHESIS ERROR]` hoặc abstain fallback nên chưa thể so sánh accuracy công bằng với Day 08.
3. `route_reason` ở một số case còn mơ hồ như `default route`, nên dù trace tốt hơn Day 08, format giải thích route vẫn cần chuẩn hóa hơn.
