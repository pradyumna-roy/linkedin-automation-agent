import os
import json
import time
import requests
from dotenv import load_dotenv
from groq import Groq
from database import get_not_requested_contacts, get_requested_contacts, get_connected_contacts
import traceback

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY is missing from your .env file.")

client = Groq(api_key=api_key)
MODEL = "openai/gpt-oss-20b"
BRIDGE_URL = "http://127.0.0.1:5000/agent"

TASK_TIMEOUT = 180
POLL_INTERVAL = 2

def build_career_message(name):
    return (
        f"Hello {name}, hope you're doing well! "  # Your pitch here...
    )


# ============================================================
# EXTENSION DISPATCH
# ============================================================


def dispatch_extension_task(action_type, contact_id, name, url, message=None):
    """Dispatch a task and wait for its actual result."""
    print(f"DEBUG: dispatch_extension_task called for {name}, action={action_type}")

    payload = {
        "action": action_type,
        "target": {
            "id": contact_id,
            "name": name,
            "url": url,
            "message": message
        }
    }

    response = requests.post(
        f"{BRIDGE_URL}/set-command",
        json=payload,
        timeout=10
    )
    response.raise_for_status()

    print(f"Dispatched {action_type}: {name}")

    deadline = time.monotonic() + TASK_TIMEOUT

    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL)

        response = requests.get(
            f"{BRIDGE_URL}/check-status",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        # Monitoring result is stored before Flask resets the queue.
        result = data.get("result")

        # Handle connection-monitoring results
        if (
                action_type == "CHECK_STATUS"
                and isinstance(result, dict)
                and str(result.get("id")) == str(contact_id)
        ):
            print(f"Monitoring result for {name}: {result['status']}")
            return {
                "status": result["status"],
                "contact_id": contact_id
            }

        # Handle message-sending results
        if (
                action_type == "SEND_MESSAGE"
                and isinstance(result, dict)
                and str(result.get("id")) == str(contact_id)
        ):
            message_status = result.get("status", "UNKNOWN")
            print(f"Message result for {name}: {message_status}")
            print(f"DEBUG: Returning from dispatch_extension_task for {name}")
            return {
                "status": message_status,
                "contact_id": contact_id,
                "reason": result.get("reason", "")
            }

        if data.get("queue_status") == "IDLE":
            if action_type in ("CHECK_STATUS", "SEND_MESSAGE"):
                raise RuntimeError(
                    f"{action_type} ended without a result for {name}"
                )

            return {
                "status": "queue_idle",
                "contact_id": contact_id,
                "message": "Queue is idle; action outcome is unverified."
            }


def run_send_messages_workflow():
    contacts = get_connected_contacts()

    if not contacts:
        print("No eligible contacts to message.")
        return

    print(f"Found {len(contacts)} eligible contacts.")

    sent_count = 0
    failed_count = 0

    for index, contact in enumerate(contacts):
        contact_id = contact[0]
        name = contact[1]
        profile_url = contact[2]

        print(f"\n[{index + 1}/{len(contacts)}] Preparing message for: {name}")

        message_text = build_career_message(name)

        try:
            result = dispatch_extension_task(
                action_type="SEND_MESSAGE",
                contact_id=contact_id,
                name=name,
                url=profile_url,
                message=message_text
            )

            status = result.get("status", "UNKNOWN")
            print(f"Message result for {name}: {status}")
            print(f"Reason: {result.get('reason', 'No reason provided')}")

            if status == "SENT":
                sent_count += 1
            else:
                failed_count += 1

        except Exception as exc:
            failed_count += 1
            print(f"Error processing {name}: {exc}")
            traceback.print_exc()

        # Pause between contacts to avoid rapid consecutive actions.
        if index < len(contacts) - 1:
            print("Waiting 15 seconds before the next contact...")
            time.sleep(15)

    print("\n========== MESSAGE WORKFLOW SUMMARY ==========")
    print(f"Total eligible: {len(contacts)}")
    print(f"Successfully sent: {sent_count}")
    print(f"Unconfirmed/failed: {failed_count}")


# ============================================================
# GROQ TOOLS
# ============================================================

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_not_requested_contacts",
            "description": (
                "Retrieve contacts whose database status is NOT_REQUESTED. "
                "Use only when the active workflow is sending invitations."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_requested_contacts",
            "description": (
                "Retrieve contacts whose database status is REQUESTED. "
                "Use only when the active workflow is monitoring acceptance."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_connection_sequence",
            "description": (
                "Ask the extension to process an eligible NOT_REQUESTED "
                "contact by sending a connection invitation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "integer"},
                    "name": {"type": "string"},
                    "profile_url": {"type": "string"}
                },
                "required": ["contact_id", "name", "profile_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_connection_status",
            "description": (
                "Ask the extension to inspect a REQUESTED contact for "
                "acceptance. This must only inspect status and must never "
                "send an invitation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "integer"},
                    "name": {"type": "string"},
                    "profile_url": {"type": "string"}
                },
                "required": ["contact_id", "name", "profile_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_connected_contacts",
            "description": (
                "Retrieve CONNECTED contacts whose msg_sent_date is NULL. "
                "Use only in the SEND_MESSAGES workflow."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_career_message",
            "description": (
                "Compose a career-networking message for an eligible "
                "CONNECTED contact using the Chrome extension. "
                "Use only contacts returned by get_connected_contacts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "integer"},
                    "name": {"type": "string"},
                    "profile_url": {"type": "string"}
                },
                "required": ["contact_id", "name", "profile_url"]
            }
        }
    }
]


# ============================================================
# AGENT PIPELINE
# ============================================================

def run_ai_agent_pipeline(workflow):
    workflows = {
        "SEND_CONNECTIONS": (
            "Send invitations to eligible NOT_REQUESTED contacts. "
            "First retrieve those contacts, then process them one at a time. "
            "Do not process contacts outside this list."
        ),
        "MONITOR_CONNECTIONS": (
            "Monitor REQUESTED contacts only for acceptance. "
            "First call get_requested_contacts to retrieve eligible contacts. "
            "Then call check_connection_status for each returned contact. "
            "Process contacts one at a time. Never query the database directly. "
            "Never open links who have their status as CONNECTED. "
            "Never send invitations during monitoring. "
            "Never claim acceptance without verified evidence."
        ),
        "SEND_MESSAGES": (
            "Call get_connected_contacts immediately to fetch profiles. "            
            "If the returned contacts list is empty, report that no contacts "
            "are eligible and stop."
            "For every contact returned in that list, execute send_career_message "
            "using their exact contact_id, name, and profile_url one by one."
        )
    }

    if workflow not in workflows:
        raise ValueError(f"Unsupported workflow: {workflow}")

    workflow_tools = {
        "SEND_CONNECTIONS": [
            "get_not_requested_contacts",
            "execute_connection_sequence"
        ],
        "MONITOR_CONNECTIONS": [
            "get_requested_contacts",
            "check_connection_status"
        ],
        "SEND_MESSAGES": [
            "get_connected_contacts",
            "send_career_message"
        ]
    }

    active_tools = [
        tool for tool in tools
        if tool["function"]["name"] in workflow_tools[workflow]
    ]

    print(f"Available tools: {[t['function']['name'] for t in active_tools]}")

    print(f"\nStarting workflow: {workflow}")

    messages = [
        {
            "role": "system",
            "content": (
                "You are an orchestrator for a LinkedIn workflow. "
                "Follow the active workflow instruction strictly. "
                "Use tools for real database and extension operations. "
                "Never invent contacts or outcomes. Do not claim that an "
                "invitation was sent or acceptance was verified merely "
                "because a command was dispatched. If a tool fails, report "
                "the failure. Do not modify database statuses directly.\n\n"
                "CRITICAL: When invoking tools, you must use the EXACT function name "
                "provided in the tools schema. Do not append punctuation, trailing dots (...), "
                "or modify the name string under any circumstances."
            )
        },
        {
            "role": "user",
            "content": workflows[workflow]
        }
    ]

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=active_tools,
            tool_choice="auto",
            temperature=0
        )

        message = response.choices[0].message

        if not message.tool_calls:
            print("\nAGENT SUMMARY")
            print(message.content or "Workflow finished.")
            return

        messages.append(message)

        for tool_call in message.tool_calls:
            function_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            try:
                if function_name == "get_not_requested_contacts":
                    if workflow != "SEND_CONNECTIONS":
                        raise ValueError("Wrong workflow for this tool.")

                    result = {
                        "contacts": get_not_requested_contacts()
                    }

                elif function_name == "get_requested_contacts":
                    if workflow != "MONITOR_CONNECTIONS":
                        raise ValueError("Wrong workflow for this tool.")

                    result = {
                        "contacts": get_requested_contacts()
                    }

                elif function_name == "execute_connection_sequence":
                    if workflow != "SEND_CONNECTIONS":
                        raise ValueError("Invitations are disabled in monitoring.")

                    result = dispatch_extension_task(
                        "PROCESS_CONNECTION",
                        args["contact_id"],
                        args["name"],
                        args["profile_url"]
                    )

                elif function_name == "check_connection_status":
                    if workflow != "MONITOR_CONNECTIONS":
                        raise ValueError("Status checks require monitoring workflow.")

                    result = dispatch_extension_task(
                        "CHECK_STATUS",
                        args["contact_id"],
                        args["name"],
                        args["profile_url"]
                    )

                elif function_name == "send_career_message":
                    if workflow != "SEND_MESSAGES":
                        raise ValueError("Messaging is disabled in this workflow.")

                    eligible_contacts = get_connected_contacts()
                    contact = next(
                        (
                            c for c in eligible_contacts
                            if str(c["id"]) == str(args["contact_id"])
                        ),
                        None
                    )

                    if contact is None:
                        raise ValueError("Contact is not eligible for messaging.")

                    message_text = build_career_message(contact["name"])

                    result = dispatch_extension_task(
                        "SEND_MESSAGE",
                        contact["id"],
                        contact["name"],
                        contact["linkedin_url"],
                        message=message_text
                    )



                else:
                    raise ValueError(f"Unknown tool: {function_name}")

            except Exception as exc:
                result = {
                    "status": "error",
                    "error": str(exc)
                }

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": json.dumps(result, default=str)
            })



SCHEDULER_INTERVAL_SECONDS = 6 * 60 * 60  # Every 6 hours


def run_automation_cycle():
    """Run all three workflows sequentially, isolating failures."""

    for workflow in (
        "SEND_CONNECTIONS",
        "MONITOR_CONNECTIONS",
        "SEND_MESSAGES",
    ):
        print(f"\n{'=' * 50}")
        print(f"Starting workflow: {workflow}")
        print(f"{'=' * 50}")

        try:
            run_ai_agent_pipeline(workflow)
        except Exception as exc:
            import traceback
            print(f"Workflow {workflow} failed: {exc}")
            traceback.print_exc()

    print("\nAutomation cycle completed.")


if __name__ == "__main__":
    print("LinkedIn automation scheduler started.")

    while True:
        try:
            run_automation_cycle()
        except Exception as exc:
            import traceback
            print(f"Automation cycle failed: {exc}")
            traceback.print_exc()

        print("Next cycle in 6 hours.")
        time.sleep(SCHEDULER_INTERVAL_SECONDS)