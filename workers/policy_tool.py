"""
workers/policy_tool.py — Policy & Tool Worker
Sprint 2+3: Kiểm tra policy dựa vào context, gọi MCP tools khi cần.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: context từ retrieval_worker
    - needs_tool: True nếu supervisor quyết định cần tool call

Output (vào AgentState):
    - policy_result: {"policy_applies", "policy_name", "exceptions_found", "source", "rule"}
    - mcp_tools_used: list of tool calls đã thực hiện
    - worker_io_log: log

Gọi độc lập để test:
    python workers/policy_tool.py
"""

import os
import re
import sys
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

WORKER_NAME = "policy_tool_worker"


# ─────────────────────────────────────────────
# MCP Client — Sprint 3: Thay bằng real MCP call
# ─────────────────────────────────────────────

def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Gọi MCP tool.

    Sprint 3 TODO: Implement bằng cách import mcp_server hoặc gọi HTTP.

    Hiện tại: Import trực tiếp từ mcp_server.py (trong-process mock).
    """
    from datetime import datetime

    try:
        # TODO Sprint 3: Thay bằng real MCP client nếu dùng HTTP server
        from mcp_server import dispatch_tool
        result = dispatch_tool(tool_name, tool_input)
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": result,
            "error": None,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": None,
            "error": {"code": "MCP_CALL_FAILED", "reason": str(e)},
            "timestamp": datetime.now().isoformat(),
        }


# ─────────────────────────────────────────────
# LLM-based Policy Analysis — Sprint 2
# ─────────────────────────────────────────────

_POLICY_SYSTEM_PROMPT = """Bạn là policy analyst nội bộ. Nhiệm vụ:
Dựa vào context tài liệu VÀ kết quả rule-based đã cung cấp, đưa ra explanation ngắn gọn 1-2 câu.
QUAN TRỌNG: Nếu rule-based đã xác định policy_applies=False, KHÔNG được kết luận ngược lại.
KHÔNG suy đoán ngoài context. Trả lời đúng 1-2 câu, dùng làm explanation."""


def _analyze_policy_with_llm(
    task: str,
    chunks: list,
    rule_exceptions: list,
    policy_version_note: str,
    policy_applies: bool = True,
) -> str:
    """
    Gọi LLM để phân tích policy phức tạp hơn rule-based.
    Trả về explanation string; không raise exception (có fallback).

    Args:
        task: câu hỏi gốc
        chunks: retrieved context chunks
        rule_exceptions: exceptions đã phát hiện bởi rule-based logic
        policy_version_note: ghi chú về version policy (v3/v4)
    """
    if not chunks:
        return "Không có context chunks — rule-based only."

    context_text = "\n".join(
        f"[{c.get('source', 'unknown')}] {c.get('text', '')}" for c in chunks
    )
    exception_notes = (
        "\n".join(f"- {ex['rule']}" for ex in rule_exceptions)
        if rule_exceptions
        else "Không có exception nào được phát hiện."
    )
    version_note = f"\nLưu ý version: {policy_version_note}" if policy_version_note else ""

    user_content = (
        f"Yêu cầu: {task}\n\n"
        f"=== Kết quả rule-based ===\n"
        f"policy_applies (rule-based): {policy_applies}\n\n"
        f"=== Context tài liệu ===\n{context_text}\n\n"
        f"=== Rule-based exceptions đã phát hiện ===\n{exception_notes}"
        f"{version_note}"
    )
    messages = [
        {"role": "system", "content": _POLICY_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    # Option A: OpenAI
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.1,
            max_tokens=80,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        # print debug
        print(f"LLM analysis failed: {e}")
        pass

    # Fallback: rule-based summary
    if rule_exceptions:
        rules = "; ".join(ex["rule"] for ex in rule_exceptions)
        return f"[Rule-based fallback] Exceptions phát hiện: {rules}"
    return "[Rule-based fallback] Không phát hiện exception nào. Policy v4 áp dụng bình thường."


# ─────────────────────────────────────────────
# Policy Analysis Logic
# ─────────────────────────────────────────────

def analyze_policy(task: str, chunks: list) -> dict:
    """
    Phân tích policy dựa trên context chunks.

    TODO Sprint 2: Implement logic này với LLM call hoặc rule-based check.

    Cần xử lý các exceptions:
    - Flash Sale → không được hoàn tiền
    - Digital product / license key / subscription → không được hoàn tiền
    - Sản phẩm đã kích hoạt → không được hoàn tiền
    - Đơn hàng trước 01/02/2026 → áp dụng policy v3 (không có trong docs)

    Returns:
        dict with: policy_applies, policy_name, exceptions_found, source, rule, explanation
    """
    task_lower = task.lower()
    context_text = " ".join([c.get("text", "") for c in chunks]).lower()

    # --- Rule-based exception detection ---
    exceptions_found = []

    # Exception 1: Flash Sale
    if "flash sale" in task_lower or "flash sale" in context_text:
        exceptions_found.append({
            "type": "flash_sale_exception",
            "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
            "source": "policy_refund_v4.txt",
        })

    # Exception 2: Digital product
    if any(kw in task_lower for kw in ["license key", "license", "subscription", "kỹ thuật số"]):
        exceptions_found.append({
            "type": "digital_product_exception",
            "rule": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    # Exception 3: Activated product
    if any(kw in task_lower for kw in ["đã kích hoạt", "đã đăng ký", "đã sử dụng"]):
        exceptions_found.append({
            "type": "activated_exception",
            "rule": "Sản phẩm đã kích hoạt hoặc đăng ký tài khoản không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    # Determine policy_applies
    policy_applies = len(exceptions_found) == 0

    # Determine which policy version applies (temporal scoping)
    # policy_refund_v4.txt — Điều 1: áp dụng cho đơn hàng từ 01/02/2026.
    # Đơn hàng đặt trước ngày đó → policy v3 (không có trong docs hiện tại → flag cho synthesis).
    policy_name = "refund_policy_v4"
    policy_version_note = ""

    # Detect date patterns that indicate an order placed before 01/02/2026
    _pre_v4_date_patterns = [
        r"\b(3[01]|[12]\d|0?\d)/01(/2026)?\b",   # any day in Jan 2026, e.g. 31/01, 15/01/2026
        r"\btrước\s+01/02(/2026)?\b",              # "trước 01/02" / "trước 01/02/2026"
        r"\btrước\s+1/2(/2026)?\b",                # "trước 1/2"
        r"\btháng\s*(1|01)\s*(năm\s*2026)?\b",     # "tháng 1 2026" / "tháng 01"
        r"\bjanuary\s*2026\b",                      # English form
        r"\bv3\b",                                  # explicit mention of v3
    ]
    _is_pre_v4 = any(re.search(p, task_lower) for p in _pre_v4_date_patterns)

    if _is_pre_v4:
        policy_name = "refund_policy_v3"
        policy_version_note = (
            "Đơn hàng đặt trước 01/02/2026 áp dụng chính sách hoàn tiền v3 "
            "(không có trong tài liệu hiện tại). "
            "Synthesis cần thông báo giới hạn này cho người dùng."
        )
        # v3 docs are unavailable → policy cannot be confirmed → flag as not applicable
        policy_applies = False
        exceptions_found.append({
            "type": "pre_v4_policy_version",
            "rule": (
                "Đơn hàng được đặt trước ngày 01/02/2026. "
                "Chính sách hoàn tiền v4 không áp dụng; "
                "v3 áp dụng nhưng không có trong tài liệu hiện tại (Điều 1, policy_refund_v4.txt)."
            ),
            "source": "policy_refund_v4.txt",
        })

    # Sprint 2: Gọi LLM để phân tích phức tạp hơn (nếu có chunks)
    llm_analysis = _analyze_policy_with_llm(
        task, chunks, exceptions_found, policy_version_note,
        policy_applies=policy_applies,
    )

    sources = list({c.get("source", "unknown") for c in chunks if c})

    # print llm_analysis for debugging
    print(f"LLM analysis:\n{llm_analysis}\n---")

    return {
        "policy_applies": policy_applies,
        "policy_name": policy_name,
        "exceptions_found": exceptions_found,
        "source": sources,
        "policy_version_note": policy_version_note,
        "explanation": llm_analysis,
    }


# ─────────────────────────────────────────────
# Worker Entry Point
# ─────────────────────────────────────────────

def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với policy_result và mcp_tools_used
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    needs_tool = state.get("needs_tool", False)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "needs_tool": needs_tool,
        },
        "output": None,
        "error": None,
    }

    try:
        # Step 1: Nếu chưa có chunks, gọi MCP search_kb
        if not chunks and needs_tool:
            mcp_result = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP search_kb")

            if mcp_result.get("output") and mcp_result["output"].get("chunks"):
                chunks = mcp_result["output"]["chunks"]
                state["retrieved_chunks"] = chunks

        # Step 2: Phân tích policy
        policy_result = analyze_policy(task, chunks)
        state["policy_result"] = policy_result

        # Step 3: Nếu cần thêm info từ MCP (e.g., ticket status), gọi get_ticket_info
        if needs_tool and any(kw in task.lower() for kw in ["ticket", "p1", "jira"]):
            mcp_result = _call_mcp_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP get_ticket_info")

        worker_io["output"] = {
            "policy_applies": policy_result["policy_applies"],
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
            "mcp_calls": len(state["mcp_tools_used"]),
        }
        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={policy_result['policy_applies']}, "
            f"exceptions={len(policy_result.get('exceptions_found', []))}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(e)}
        state["policy_result"] = {"error": str(e)}
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Policy Tool Worker — Standalone Test")
    print("=" * 50)

    test_cases = [
        {
            "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
            "retrieved_chunks": [
                {"text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.9}
            ],
        },
        {
            "task": "Khách hàng muốn hoàn tiền license key đã kích hoạt.",
            "retrieved_chunks": [
                {"text": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.88}
            ],
        },
        {
            "task": "Khách hàng yêu cầu hoàn tiền trong 5 ngày, sản phẩm lỗi, chưa kích hoạt.",
            "retrieved_chunks": [
                {"text": "Yêu cầu trong 7 ngày làm việc, sản phẩm lỗi nhà sản xuất, chưa dùng.", "source": "policy_refund_v4.txt", "score": 0.85}
            ],
        },
    ]

    for tc in test_cases:
        print(f"\n▶ Task: {tc['task']}")
        result = run(tc.copy())
        pr = result.get("policy_result", {})
        print(f"  policy_applies: {pr.get('policy_applies')}")
        if pr.get("exceptions_found"):
            for ex in pr["exceptions_found"]:
                print(f"  exception: {ex['type']} — {ex['rule'][:60]}...")
        print(f"  MCP calls: {len(result.get('mcp_tools_used', []))}")

    print("\n✅ policy_tool_worker test done.")
