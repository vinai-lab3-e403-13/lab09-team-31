"""
mcp_server.py — Mock MCP Server
Sprint 3: Implement ít nhất 2 MCP tools.

Mô phỏng MCP (Model Context Protocol) interface trong Python.
Agent (MCP client) gọi dispatch_tool() thay vì hard-code từng API.

Tools available:
    1. search_kb(query, top_k)                    → tìm kiếm Knowledge Base (ChromaDB)
    2. get_ticket_info(ticket_id)                 → tra cứu thông tin ticket (mock data)
    3. check_access_permission(access_level, ...) → kiểm tra quyền theo Access Control SOP
    4. create_ticket(priority, title, description) → tạo ticket mới (mock)

Mock data căn chỉnh theo tài liệu thật:
    - access_control_sop.txt  (Level 1-4, emergency escalation Section 4)
    - sla_p1_2026.txt         (P1 notifications, escalation timeline)

Sử dụng:
    from mcp_server import dispatch_tool, list_tools

    result = dispatch_tool("search_kb", {"query": "SLA P1", "top_k": 3})
    result = dispatch_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})

Chạy thử:
    python mcp_server.py
"""

import os
from datetime import datetime


# ─────────────────────────────────────────────
# Tool Schemas (MCP Discovery)
# ─────────────────────────────────────────────

TOOL_SCHEMAS = {
    "search_kb": {
        "name": "search_kb",
        "description": "Tìm kiếm Knowledge Base nội bộ bằng semantic search. Trả về top-k chunks liên quan nhất.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Câu hỏi hoặc keyword cần tìm"},
                "top_k": {"type": "integer", "description": "Số chunks cần trả về", "default": 3},
            },
            "required": ["query"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "chunks": {"type": "array"},
                "sources": {"type": "array"},
                "total_found": {"type": "integer"},
            },
        },
    },
    "get_ticket_info": {
        "name": "get_ticket_info",
        "description": "Tra cứu thông tin ticket từ hệ thống Jira nội bộ.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "ID ticket (VD: IT-9847, P1-LATEST, P1-2AM)",
                },
            },
            "required": ["ticket_id"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "priority": {"type": "string"},
                "status": {"type": "string"},
                "assignee": {"type": "string"},
                "created_at": {"type": "string"},
                "sla_deadline": {"type": "string"},
                "notifications_sent": {"type": "array"},
            },
        },
    },
    "check_access_permission": {
        "name": "check_access_permission",
        "description": (
            "Kiểm tra điều kiện cấp quyền truy cập theo Access Control SOP. "
            "Hỗ trợ Level 1-4 và emergency escalation (Section 4 của SOP)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "access_level": {
                    "type": "integer",
                    "description": "Level cần cấp (1=Read Only, 2=Standard, 3=Elevated, 4=Admin)",
                },
                "requester_role": {
                    "type": "string",
                    "description": "Vai trò người yêu cầu (VD: contractor, employee, team_lead)",
                },
                "is_emergency": {
                    "type": "boolean",
                    "description": "True nếu cần cấp khẩn cấp trong sự cố P1",
                    "default": False,
                },
            },
            "required": ["access_level", "requester_role"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "can_grant": {"type": "boolean"},
                "required_approvers": {"type": "array"},
                "approver_count": {"type": "integer"},
                "final_approver": {"type": "string"},
                "emergency_override": {"type": "boolean"},
                "processing_days": {"type": "integer"},
                "notes": {"type": "array"},
                "source": {"type": "string"},
            },
        },
    },
    "create_ticket": {
        "name": "create_ticket",
        "description": "Tạo ticket mới trong hệ thống Jira (MOCK — không tạo thật trong lab).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["priority", "title"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "url": {"type": "string"},
                "created_at": {"type": "string"},
            },
        },
    },
}


# ─────────────────────────────────────────────
# Tool 1: search_kb
# Delegate sang retrieval worker (ChromaDB)
# ─────────────────────────────────────────────

def tool_search_kb(query: str, top_k: int = 3) -> dict:
    """
    Tìm kiếm Knowledge Base bằng semantic search qua ChromaDB.
    Delegate sang workers/retrieval.py để tái dùng logic.
    Có fallback nếu ChromaDB chưa setup.
    """
    try:
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from workers.retrieval import retrieve_dense
        chunks = retrieve_dense(query, top_k=top_k)
        sources = list({c["source"] for c in chunks})
        return {
            "chunks": chunks,
            "sources": sources,
            "total_found": len(chunks),
        }
    except Exception as e:
        return {
            "chunks": [
                {
                    "text": f"[MOCK fallback] Không thể query ChromaDB: {e}",
                    "source": "mock_data",
                    "score": 0.5,
                }
            ],
            "sources": ["mock_data"],
            "total_found": 1,
        }


# ─────────────────────────────────────────────
# Tool 2: get_ticket_info
# Mock data căn chỉnh với sla_p1_2026.txt:
#   - First response SLA: 15 phút
#   - Resolution SLA: 4 giờ
#   - Escalation: 10 phút không phản hồi → auto-escalate Senior Engineer
#   - Thông báo: Slack #incident-p1, email, PagerDuty
# ─────────────────────────────────────────────

MOCK_TICKETS = {
    # P1 tạo lúc 22:47 — grading question gq01
    "P1-LATEST": {
        "ticket_id": "IT-9847",
        "priority": "P1",
        "title": "API Gateway down — toàn bộ người dùng không đăng nhập được",
        "status": "in_progress",
        "assignee": "nguyen.van.a@company.internal",
        "created_at": "2026-04-13T22:47:00",
        "sla_deadline": "2026-04-14T02:47:00",        # +4h resolution
        "first_response_deadline": "2026-04-13T23:02:00",  # +15 phút
        "escalation_deadline": "2026-04-13T22:57:00",      # +10 phút → Senior Engineer
        "escalated": True,
        "escalated_to": "Senior Engineer on-call",
        "notifications_sent": [
            "slack:#incident-p1",
            "email:incident@company.internal",
            "pagerduty:oncall",
        ],
        "update_frequency": "Mỗi 30 phút cho đến khi resolve",
        "source": "sla_p1_2026.txt",
    },
    # P1 tạo lúc 2am — grading question gq09
    "P1-2AM": {
        "ticket_id": "IT-9901",
        "priority": "P1",
        "title": "Database replication lag — data inconsistency detected",
        "status": "in_progress",
        "assignee": "tran.thi.b@company.internal",
        "created_at": "2026-04-14T02:00:00",
        "sla_deadline": "2026-04-14T06:00:00",
        "first_response_deadline": "2026-04-14T02:15:00",
        "escalation_deadline": "2026-04-14T02:10:00",
        "escalated": True,
        "escalated_to": "Senior Engineer on-call",
        "notifications_sent": [
            "slack:#incident-p1",
            "email:incident@company.internal",
            "pagerduty:oncall",
        ],
        "update_frequency": "Mỗi 30 phút cho đến khi resolve",
        "source": "sla_p1_2026.txt",
    },
    # P2 thông thường
    "IT-1234": {
        "ticket_id": "IT-1234",
        "priority": "P2",
        "title": "Feature login chậm cho một số user",
        "status": "open",
        "assignee": None,
        "created_at": "2026-04-13T09:15:00",
        "sla_deadline": "2026-04-14T09:15:00",
        "escalated": False,
        "notifications_sent": ["slack:#incident-p2"],
        "source": "sla_p1_2026.txt",
    },
}


def tool_get_ticket_info(ticket_id: str) -> dict:
    """
    Tra cứu thông tin ticket từ mock database.
    Hỗ trợ: P1-LATEST, P1-2AM, IT-1234.
    """
    ticket = MOCK_TICKETS.get(ticket_id.upper())
    if ticket:
        return ticket
    return {
        "error": f"Ticket '{ticket_id}' không tìm thấy trong hệ thống.",
        "available_mock_ids": list(MOCK_TICKETS.keys()),
    }


# ─────────────────────────────────────────────
# Tool 3: check_access_permission
# Mock data căn chỉnh với access_control_sop.txt:
#
#   Level 1 — Read Only  : Line Manager (1 ngày làm việc)
#   Level 2 — Standard   : Line Manager + IT Admin (2 ngày)
#   Level 3 — Elevated   : Line Manager + IT Admin + IT Security (3 ngày)
#   Level 4 — Admin      : IT Manager + CISO (5 ngày, cần training)
#
# Emergency (Section 4 SOP):
#   On-call IT Admin cấp tạm thời tối đa 24h, điều kiện:
#     → Tech Lead phê duyệt bằng lời
#     → Ghi log vào Security Audit (Splunk)
#     → Sau 24h: có ticket chính thức hoặc tự động thu hồi
#   Level 4 KHÔNG có emergency bypass.
# ─────────────────────────────────────────────

ACCESS_RULES = {
    1: {
        "name": "Read Only",
        "applies_to": "Tất cả nhân viên mới trong 30 ngày đầu",
        "required_approvers": ["Line Manager"],
        "final_approver": "Line Manager",
        "processing_days": 1,
        "emergency_bypass": True,
    },
    2: {
        "name": "Standard Access",
        "applies_to": "Nhân viên chính thức đã qua thử việc",
        "required_approvers": ["Line Manager", "IT Admin"],
        "final_approver": "IT Admin",
        "processing_days": 2,
        "emergency_bypass": True,
    },
    3: {
        "name": "Elevated Access",
        "applies_to": "Team Lead, Senior Engineer, Manager",
        "required_approvers": ["Line Manager", "IT Admin", "IT Security"],
        "final_approver": "IT Security",
        "processing_days": 3,
        "emergency_bypass": True,
    },
    4: {
        "name": "Admin Access",
        "applies_to": "DevOps, SRE, IT Admin",
        "required_approvers": ["IT Manager", "CISO"],
        "final_approver": "CISO",
        "processing_days": 5,
        "emergency_bypass": False,
        "extra_requirement": "Training bắt buộc về security policy",
    },
}


def tool_check_access_permission(
    access_level: int,
    requester_role: str,
    is_emergency: bool = False,
) -> dict:
    """
    Kiểm tra quy trình cấp quyền theo Access Control SOP thực tế.
    """
    rule = ACCESS_RULES.get(access_level)
    if not rule:
        return {
            "error": f"Access level {access_level} không hợp lệ. Levels hợp lệ: 1, 2, 3, 4.",
        }

    notes = []
    emergency_override = False

    if is_emergency:
        if rule["emergency_bypass"]:
            emergency_override = True
            notes.append(
                f"EMERGENCY BYPASS áp dụng (Section 4, access_control_sop.txt): "
                f"On-call IT Admin có thể cấp Level {access_level} tạm thời tối đa 24 giờ "
                f"sau khi Tech Lead phê duyệt bằng lời."
            )
            notes.append(
                "Quyền tạm thời BẮT BUỘC ghi log vào Security Audit (Splunk)."
            )
            notes.append(
                "Sau 24 giờ: phải tạo ticket chính thức trên Jira (project IT-ACCESS) "
                "hoặc quyền bị thu hồi tự động."
            )
        else:
            notes.append(
                f"Level {access_level} ({rule['name']}) KHÔNG có emergency bypass. "
                "Phải follow quy trình chuẩn đầy đủ."
            )
            if rule.get("extra_requirement"):
                notes.append(f"Yêu cầu thêm: {rule['extra_requirement']}")
    else:
        notes.append(
            f"Quy trình chuẩn: Tạo Access Request ticket trên Jira (project IT-ACCESS). "
            f"Thời gian xử lý: {rule['processing_days']} ngày làm việc."
        )
        if rule.get("extra_requirement"):
            notes.append(f"Yêu cầu thêm: {rule['extra_requirement']}")

    return {
        "access_level": access_level,
        "level_name": rule["name"],
        "applies_to": rule["applies_to"],
        "can_grant": True,
        "required_approvers": rule["required_approvers"],
        "approver_count": len(rule["required_approvers"]),
        "final_approver": rule["final_approver"],
        "processing_days": rule["processing_days"],
        "emergency_override": emergency_override,
        "notes": notes,
        "source": "access_control_sop.txt",
    }


# ─────────────────────────────────────────────
# Tool 4: create_ticket (mock)
# ─────────────────────────────────────────────

def tool_create_ticket(priority: str, title: str, description: str = "") -> dict:
    """Tạo ticket mới (MOCK — in log, không tạo thật)."""
    mock_id = f"IT-{9900 + abs(hash(title)) % 99}"
    ticket = {
        "ticket_id": mock_id,
        "priority": priority,
        "title": title,
        "description": description[:200],
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "url": f"https://jira.company.internal/browse/{mock_id}",
        "note": "MOCK ticket — không tồn tại trong hệ thống thật",
    }
    print(f"  [MCP create_ticket] MOCK: {mock_id} | {priority} | {title[:50]}")
    return ticket


# ─────────────────────────────────────────────
# Dispatch Layer — MCP server interface
# ─────────────────────────────────────────────

TOOL_REGISTRY = {
    "search_kb": tool_search_kb,
    "get_ticket_info": tool_get_ticket_info,
    "check_access_permission": tool_check_access_permission,
    "create_ticket": tool_create_ticket,
}


def list_tools() -> list:
    """
    MCP discovery: trả về danh sách tools có sẵn.
    Tương đương với `tools/list` trong MCP protocol.
    """
    return list(TOOL_SCHEMAS.values())


def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    """
    MCP execution: nhận tool_name và input, gọi tool tương ứng.
    Tương đương với `tools/call` trong MCP protocol.

    KHÔNG raise exception ra ngoài — luôn trả về dict.

    Args:
        tool_name: tên tool (phải có trong TOOL_REGISTRY)
        tool_input: input dict

    Returns:
        Tool output dict, hoặc error dict nếu thất bại
    """
    if tool_name not in TOOL_REGISTRY:
        return {
            "error": f"Tool '{tool_name}' không tồn tại.",
            "available_tools": list(TOOL_REGISTRY.keys()),
        }

    tool_fn = TOOL_REGISTRY[tool_name]
    try:
        result = tool_fn(**tool_input)
        return result
    except TypeError as e:
        return {
            "error": f"Input không hợp lệ cho tool '{tool_name}': {e}",
            "schema": TOOL_SCHEMAS[tool_name]["inputSchema"],
        }
    except Exception as e:
        return {
            "error": f"Tool '{tool_name}' thực thi thất bại: {e}",
        }


# ─────────────────────────────────────────────
# Test & Demo
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("MCP Server — Sprint 3 Test")
    print("=" * 65)

    # 1. Discover tools
    print("\n📋 Available Tools:")
    for tool in list_tools():
        print(f"  • {tool['name']}: {tool['description'][:65]}")

    # 2. Test search_kb
    print("\n🔍 Test: search_kb('SLA P1 resolution time')")
    result = dispatch_tool("search_kb", {"query": "SLA P1 resolution time", "top_k": 2})
    if result.get("chunks"):
        for c in result["chunks"]:
            print(f"  [{c.get('score', '?')}] {c.get('source')}: {str(c.get('text', ''))[:70]}...")
    else:
        print(f"  Result: {result}")

    # 3. Test get_ticket_info — P1 lúc 22:47 (grading gq01)
    print("\n🎫 Test: get_ticket_info('P1-LATEST') — P1 tạo lúc 22:47")
    ticket = dispatch_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
    print(f"  Ticket   : {ticket.get('ticket_id')} | {ticket.get('priority')}")
    print(f"  Tạo lúc  : {ticket.get('created_at')}")
    print(f"  SLA dead : {ticket.get('sla_deadline')} (4h resolution)")
    print(f"  Escalate : {ticket.get('escalation_deadline')} (10 phút không phản hồi)")
    print(f"  Channels : {ticket.get('notifications_sent')}")

    # 4. Test check_access_permission — Level 3 chuẩn (grading gq03)
    print("\n🔐 Test: Level 3, không khẩn cấp")
    perm = dispatch_tool("check_access_permission", {
        "access_level": 3,
        "requester_role": "team_lead",
        "is_emergency": False,
    })
    print(f"  Level    : {perm.get('level_name')}")
    print(f"  Approvers: {perm.get('required_approvers')} ({perm.get('approver_count')} người)")
    print(f"  Cuối cùng: {perm.get('final_approver')}")

    # 5. Test emergency Level 2 contractor (grading gq09)
    print("\n🔐 Test: Level 2, contractor, emergency=True")
    perm2 = dispatch_tool("check_access_permission", {
        "access_level": 2,
        "requester_role": "contractor",
        "is_emergency": True,
    })
    print(f"  Emergency override: {perm2.get('emergency_override')}")
    for note in perm2.get("notes", []):
        print(f"  Note: {note}")

    # 6. Test Level 4 emergency (no bypass)
    print("\n🔐 Test: Level 4, emergency=True (no bypass)")
    perm3 = dispatch_tool("check_access_permission", {
        "access_level": 4,
        "requester_role": "devops",
        "is_emergency": True,
    })
    print(f"  Emergency override: {perm3.get('emergency_override')}")
    for note in perm3.get("notes", []):
        print(f"  Note: {note}")

    # 7. Test invalid tool
    print("\n❌ Test: invalid tool")
    err = dispatch_tool("nonexistent_tool", {})
    print(f"  Error: {err.get('error')}")

    print("\n✅ MCP server test done.")
