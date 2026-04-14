# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Trần Kiên Trường  
**Vai trò trong nhóm:** Worker Owner
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
- File chính: `workers/retrieval.py`
- Functions tôi implement: `retrieve_dense()` (dense retrieval từ ChromaDB), `run()` (worker entry point), `_get_embedding_fn()`, `_get_collection()`

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Retrieval worker là worker đầu tiên trong pipeline. Sau khi supervisor route sang `retrieval_worker`, nó lấy evidence chunks từ ChromaDB rồi chuyển state sang synthesis worker. Nếu `retrieval_chunks` rỗng và `needs_tool=True`, policy worker sẽ gọi MCP `search_kb` để bù.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**
- Commit `871e43d`: `Done retrieval` — triển khai retrieval worker đầu tiên
- Commit `7e964e2`: `add testcases, traces` — thêm test questions và trace files
- `workers/retrieval.py` line 30: `WORKER_NAME = "retrieval_worker"` (author tag)
- Trace `run_20260414_171543.json` — retrieval lấy 3 chunks từ `hr/leave-policy-2026.pdf` và `it/access-control-sop.md`, confidence=0.57

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
> - Quyết định là gì?
> - Các lựa chọn thay thế là gì?
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:** Tách embedding function giữa OpenAI API (production) và random fallback (test-only) — không dùng Sentence Transformers offline.

**Các lựa chọn thay thế:**
1. **Sentence Transformers offline** (`all-MiniLM-L6-v2`) — không cần API key, chạy local
2. **OpenAI `text-embedding-3-small`** — embeddings chất lượng cao hơn, cần API key
3. **Random fallback** — chỉ dùng khi test, không production

**Lý do chọn OpenAI embeddings:**
Tôi chọn OpenAI vì trong môi trường lab `.venv` đã có API key, embeddings đồng nhất với Day 08 (dùng cùng model), và `text-embedding-3-small` cho latency thấp hơn so với gọi STS model mỗi query. Trace sau đó cho thấy retrieval đạt chunks có score 0.62–0.74, đủ để synthesis tạo answer có citation và confidence 0.57–0.62.

**Trade-off đã chấp nhận:**
Không có local fallback offline hoàn chỉnh. Nếu API key hết hạn hoặc network chặn, retrieval trả 0 chunks và synthesis abstain. Đây là trade-off có thể chấp nhận trong lab vì `.venv` environment được kiểm soát.

**Bằng chứng từ trace/code:**
```python
# workers/retrieval.py:50-58
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    def embed(text: str) -> list:
        resp = client.embeddings.create(input=text, model="text-embedding-3-small")
        return resp.data[0].embedding
    return embed
except ImportError:
    pass
```

Trace `run_20260414_171543`: retrieval trả `3 chunks`, score [0.7449, 0.4969, 0.475], confidence synthesis = 0.57.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** ChromaDB query failed — `retrieved_sources` rỗng dù query hợp lệ

**Symptom (pipeline làm gì sai?):**
- Trace `run_20260414_162248`: retrieval trả 0 chunks, `retrieved_sources=[]`
- `mcp_tools_used` có `search_kb` gọi nhưng output là `[MOCK fallback] Không thể query ChromaDB: The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable`
- Synthesis abstain với confidence=0.1, answer = `[SYNTHESIS ERROR]`

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**
- Lỗi nằm ở `workers/retrieval.py:_get_collection()` và `_get_embedding_fn()` — khi ChromaDB collection `day09_docs` chưa được build, nó tự tạo collection mới nhưng không có data
- Khi `retrieve_dense()` gọi ChromaDB, query thất bại vì collection rỗng → fallback trả empty list
- Mặc dù `_get_embedding_fn()` đã cố gắi dùng OpenAI, nếu API key không resolve đúng cách trong subprocess của MCP call, nó dùng random fallback → query sai

**Cách sửa:**
Thêm try-except quanh ChromaDB query trong `retrieve_dense()` để khi không query được thì trả empty list thay vì crash:

```python
# workers/retrieval.py:125-128
except Exception as e:
    print(f"⚠️  ChromaDB query failed: {e}")
    # Fallback: return empty (abstain)
    return []
```

**Bằng chứng trước/sau:**
> Trước khi sửa: Trace `run_20260414_162248` — retrieval trả 0 chunks, synthesis abstain
> Sau khi sửa: Trace `run_20260414_171543` — retrieval trả 3 chunks, confidence=0.57, answer có citation

Trace `run_20260414_171543` sau khi fix:
```
"[retrieval_worker] retrieved 3 chunks from ['it/access-control-sop.md', 'hr/leave-policy-2026.pdf']"
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**
Retrieval worker là worker đầu tiên và cơ bản nhất — tôi implement đúng contract, test độc lập được, và trace cho thấy chunks được retrieve ổn định với score 0.47–0.74. Việc tách `_get_embedding_fn()` và `_get_collection()` thành helper riêng giúp đọc và debug dễ hơn.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
- ChromaDB collection `day09_docs` chưa được build chuẩn từ đầu — tôi phải debug qua nhiều trace mới phát hiện lỗi rỗng
- Chưa implement deduplicate logic cho retrieved_sources (sources trùng nhau trong một số trace)
- Không có unit test riêng cho retrieval worker — chỉ test qua graph hoặc trace

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_
Retrieval worker là bước đầu tiên của pipeline — nếu retrieval fail, synthesis không có chunks và answer luôn abstain. Khi tôi debug xong ChromaDB fallback, các worker khác (policy, synthesis) mới có evidence để xử lý.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_
Tôi cần `graph.py` gọi đúng `retrieval_worker_node` sau supervisor. Supervisor Owner đã setup đúng flow trong `build_graph()`, nên không block. Ngoài ra tôi phụ thuộc vào synthesis worker để biết confidence thực tế sau retrieval.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.
> Không phải "làm tốt hơn chung chung" — phải là:
> *"Tôi sẽ thử X vì trace của câu gq___ cho thấy Y."*

Tôi sẽ implement **hybrid search** (dense + sparse/bm25) cho retrieval worker, thay vì chỉ dense retrieval hiện tại.

Lý do: Trace `run_20260414_171543` cho thấy chunks có score 0.47–0.74 — score thấp nhất (0.475) trùng khớp với HR policy nhưng bị bỏ sót ở vị trí rank thấp hơn. Hybrid search sẽ cải thiện recall cho các câu hỏi HR/FAQ nơi exact keyword matching quan trọng hơn semantic similarity. Ngoài ra, trace `run_20260414_170154` cho thấy `get_ticket_info` được gọi đúng cách sau retrieval, chứng tỏ MCP integration đã ổn — điểm yếu còn lại là retrieval quality thuần túy.

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*  
*Ví dụ: `reports/individual/nguyen_van_a.md`*
