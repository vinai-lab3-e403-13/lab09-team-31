# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Trịnh Ngọc Tú
**Vai trò trong nhóm:** Worker owner
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

> Mô tả cụ thể module, worker, contract, hoặc phần trace bạn trực tiếp làm.
> Không chỉ nói "tôi làm Sprint X" — nói rõ file nào, function nào, quyết định nào.

**Module/file tôi chịu trách nhiệm:**
- File chính: `workers/synthesis.py`
- Functions tôi implement: `_call_llm`, `_build_context`, `_estimate_confidence`, `_has_citation`, `_ensure_citations`, `synthesize`, `run`

**Cách công việc của tôi kết nối với phần của thành viên khác:** Công việc của tôi ở workers/synthesis.py nhận retrieved_chunks từ retrieval_worker và policy_result từ policy_tool_worker, sau đó tổng hợp thành final_answer, sources, confidence để trả về cho graph.py và pipeline chung.

_________________

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):** 721214448204da2ea2fc483dda88ba6f5c03b0c9

_________________

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
> - Quyết định là gì?
> - Các lựa chọn thay thế là gì?
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:** Tôi chọn “abstain sớm” trong synthesize() — nếu retrieved_chunks rỗng thì trả ngay "Không đủ thông tin trong tài liệu nội bộ." thay vì gọi LLM.

**Ví dụ:**
> "Tôi chọn không gọi LLM khi chunks rỗng trong workers/synthesis.py.
>  Lý do: tránh hallucination và giảm latency/chi phí.
>  Bằng chứng: đoạn if not chunks: return {"answer": "...", "sources": [], "confidence": 0.1} trong hàm synthesize()."

**Lý do:**
> Đảm bảo tuân thủ quy tắc “chỉ trả lời dựa trên context”.
> Giảm rủi ro trả lời sai khi retrieval thất bại.
> Tiết kiệm chi phí gọi LLM và thời gian xử lý.

_________________

**Trade-off đã chấp nhận:**
> Chấp nhận khả năng bỏ lỡ câu trả lời khi retrieval tạm thời lỗi hoặc thiếu chunk; đổi lại đảm bảo an toàn, không hallucinate và giữ đúng nguyên tắc “chỉ trả lời dựa trên context”.
_________________

**Bằng chứng từ trace/code:**

```
if not chunks:
    # Không có evidence -> abstain ngay, không gọi LLM
    answer = "Không đủ thông tin trong tài liệu nội bộ."
    return {"answer": answer, "sources": [], "confidence": 0.1}
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** Output cuối không có citation dù có evidence.

**Symptom (pipeline làm gì sai?):**

Synthesis trả câu trả lời trơn, thiếu [source], vi phạm rule “trích dẫn nguồn cuối mỗi câu quan trọng”.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

Worker logic ở workers/synthesis.py: sau khi gọi LLM, output không được cưỡng chế thêm citation nếu model không tự chèn.

**Cách sửa:**

Thêm hàm _ensure_citations() và gọi nó trước khi trả kết quả để auto gắn Nguồn: [source] khi chưa có citation.

**Bằng chứng trước/sau:**
> Dán trace/log/output trước khi sửa và sau khi sửa.

Trước: answer không có [source].
Sau: answer được append Nguồn: [sla_p1_2026.txt] nếu thiếu citation.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**

Tôi làm tốt ở việc thiết kế logic “abstain sớm” và cưỡng chế citation trong workers/synthesis.py, giúp câu trả lời an toàn và đúng chuẩn policy.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi chưa kiểm thử đủ các trường hợp edge-case khi LLM trả về định dạng lạ, nên đôi lúc phải xử lý thủ công.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_

Pipeline tổng hợp câu trả lời bị block nếu synthesis chưa ổn định, vì đây là bước cuối để ra final_answer và confidence.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_

Tôi cần retrieval trả đúng retrieved_chunks và policy worker trả policy_result rõ ràng để synthesis tổng hợp đúng.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.
> Không phải "làm tốt hơn chung chung" — phải là:
> *"Tôi sẽ thử X vì trace của câu gq___ cho thấy Y."*

Tôi sẽ thử cải tiến cách ước lượng confidence trong workers/synthesis.py vì trace ở các câu gq có score cao nhưng vẫn bị hitl_triggered cho thấy công thức hiện tại hơi bảo thủ. Cụ thể, tôi sẽ cân lại exception_penalty và đưa thêm tín hiệu độ dài answer để tránh hạ confidence quá mức khi evidence mạnh.

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*  
*Ví dụ: `reports/individual/nguyen_van_a.md`*
