import os
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from database import create_database, get_not_requested_contacts, get_requested_contacts, add_contact, get_all_contacts

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "linkedin_contacts.db")

# 🧠 THE AGENT COMMAND QUEUE
# Holds the current active instruction sent down from the Groq Agent, so as for the extension to process the requests
AGENT_COMMAND_QUEUE = {
    "action": "IDLE",  # IDLE, PROCESS_CONNECTION, CHECK_STATUS
    "target": None,
    "result": None
}


def get_connection():
    return sqlite3.connect(DB_NAME)


# ============================================================
# API ENDPOINT FOR THE CHROME EXTENSION
# ============================================================
@app.route('/api/next-target', methods=['GET'])
def get_next_target():
    # Returns the active live command pushed by the AI Agent
    return jsonify({
        "status": "success",
        "command": AGENT_COMMAND_QUEUE
    })


@app.route('/api/mark-requested', methods=['POST'])
def api_mark_requested():
    payload = request.get_json()
    contact_id = payload.get("id")
    final_status = payload.get("status", "REQUESTED")  # Can be REQUESTED or CONNECTED

    if not contact_id:
        return jsonify({"status": "error", "message": "Missing ID"}), 400

    if final_status not in {"REQUESTED", "CONNECTED"}:
        return jsonify({
            "status": "error",
            "message": "Invalid connection status"
        }), 400

    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")

    if final_status == "REQUESTED":
        cursor.execute("""
                       UPDATE linkedin_contacts
                       SET connection_status = 'REQUESTED',
                           request_sent_date = ?
                       WHERE id = ?
                       """, (now, contact_id))
    elif final_status == "CONNECTED":
        cursor.execute("""
                       UPDATE linkedin_contacts
                       SET connection_status = ?
                       WHERE id = ?
                       """, (final_status, contact_id))

    conn.commit()
    conn.close()

    # Task executed successfully, clear the active agent queue
    AGENT_COMMAND_QUEUE["action"] = "IDLE"
    AGENT_COMMAND_QUEUE["target"] = None

    print(f"📡 DB Sync: Contact {contact_id} marked as {final_status}")
    return jsonify({"status": "success", "message": "Database updated successfully."})


@app.route('/api/report-skip', methods=['POST'])
def api_report_skip():
    # If the extension detects a profile is already connected or pending, it reports back
    payload = request.get_json()
    contact_id = payload.get("id")
    detected_state = payload.get("reason")  # "ALREADY_CONNECTED" or "PENDING"

    if contact_id:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       UPDATE linkedin_contacts
                       SET connection_status = ?
                       WHERE id = ?
                       """, (detected_state, contact_id))
        conn.commit()
        conn.close()

    AGENT_COMMAND_QUEUE["action"] = "IDLE"
    AGENT_COMMAND_QUEUE["target"] = None
    return jsonify({"status": "success"})


# ============================================================
# PRIVATE CONTROL ENDPOINTS FOR THE PYTHON AI AGENT
# ============================================================
@app.route('/agent/set-command', methods=['POST'])
def agent_set_command():
    global AGENT_COMMAND_QUEUE

    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    target = payload.get("target")

    if action not in {"PROCESS_CONNECTION", "CHECK_STATUS", "SEND_MESSAGE"}:
        return jsonify({
            "status": "error",
            "message": "Invalid action"
        }), 400

    if not isinstance(target, dict) or not target.get("id") or not target.get("url"):
        return jsonify({
            "status": "error",
            "message": "Target must include id and url"
        }), 400

    if action == "SEND_MESSAGE" and not isinstance(target.get("message"), str):
        return jsonify({
            "status": "error",
            "message": "SEND_MESSAGE requires message text"
        }), 400

    if action == "SEND_MESSAGE" and not target["message"].strip():
        return jsonify({
            "status": "error",
            "message": "Message text cannot be empty"
        }), 400

    if AGENT_COMMAND_QUEUE["action"] != "IDLE":
        return jsonify({
            "status": "error",
            "message": "Another task is already running"
        }), 409

    AGENT_COMMAND_QUEUE = {
        "action": action,
        "target": target,
        "result": None
    }

    print(f"Agent command queued: {action} -> {target.get('name')}")
    return jsonify({
        "status": "command_set",
        "queue": AGENT_COMMAND_QUEUE
    })


@app.route('/agent/check-status', methods=['GET'])
def agent_check_status():
    return jsonify({
        "queue_status": AGENT_COMMAND_QUEUE["action"],
        "result": AGENT_COMMAND_QUEUE["result"]
    })


@app.route('/agent/report-message-result', methods=['POST'])
def agent_report_message_result():
    global AGENT_COMMAND_QUEUE

    payload = request.get_json(silent=True) or {}
    contact_id = payload.get("id")
    result = payload.get("result")
    reason = payload.get("reason", "")

    if AGENT_COMMAND_QUEUE["action"] != "SEND_MESSAGE":
        return jsonify({
            "status": "error",
            "message": "No message task is active"
        }), 409

    target = AGENT_COMMAND_QUEUE.get("target") or {}

    if str(contact_id) != str(target.get("id")):
        return jsonify({
            "status": "error",
            "message": "Contact ID does not match active task"
        }), 409

    if result not in {"SENT", "FAILED", "READY_TO_SEND", "UNKNOWN"}:
        return jsonify({
            "status": "error",
            "message": "Invalid message result"
        }), 400

    # Do not mark a message as sent merely because it was composed.
    if result == "SENT":
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE linkedin_contacts
            SET msg_sent_date = ?
            WHERE id = ?
              AND connection_status = 'CONNECTED'
              AND msg_sent_date IS NULL
        """, (datetime.now().isoformat(timespec="seconds"), contact_id))

        updated = cursor.rowcount
        conn.commit()
        conn.close()

        if not updated:
            return jsonify({
                "status": "error",
                "message": "Contact was not eligible or was already messaged"
            }), 409

#    if result == "SENT":
#        print(f"✅ Message verified as SENT for contact {contact_id} (Database timestamp bypassed)")

#    AGENT_COMMAND_QUEUE["result"] = {
#        "id": contact_id,
#        "status": result,
#        "reason": reason
#    }
#    AGENT_COMMAND_QUEUE["action"] = "IDLE"
#    AGENT_COMMAND_QUEUE["target"] = None

#    print(f"Message result: contact {contact_id} -> {result}")

    AGENT_COMMAND_QUEUE["result"] = {
        "id": contact_id,
        "status": result,
        "reason": reason
    }
    AGENT_COMMAND_QUEUE["action"] = "IDLE"
    AGENT_COMMAND_QUEUE["target"] = None

    return jsonify({
        "status": "success",
        "result": result
    })


@app.route('/agent/report-result', methods=['POST'])
def agent_report_result():
    global AGENT_COMMAND_QUEUE

    payload = request.get_json(silent=True) or {}
    contact_id = payload.get("id")
    result = payload.get("result")

    if AGENT_COMMAND_QUEUE["action"] != "CHECK_STATUS":
        return jsonify({
            "status": "error",
            "message": "No status-check task is active"
        }), 409

    target = AGENT_COMMAND_QUEUE.get("target") or {}

    if contact_id != target.get("id"):
        return jsonify({
            "status": "error",
            "message": "Contact ID does not match active task"
        }), 409

    if result not in {"CONNECTED", "REQUESTED", "UNKNOWN"}:
        return jsonify({
            "status": "error",
            "message": "Invalid monitoring result"
        }), 400

    if result == "CONNECTED":
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE linkedin_contacts
            SET connection_status = 'CONNECTED'
            WHERE id = ? AND connection_status = 'REQUESTED'
        """, (contact_id,))
        updated = cursor.rowcount
        conn.commit()
        conn.close()

        if not updated:
            result = "UNKNOWN"

    AGENT_COMMAND_QUEUE["result"] = {
        "id": contact_id,
        "status": result
    }
    AGENT_COMMAND_QUEUE["action"] = "IDLE"
    AGENT_COMMAND_QUEUE["target"] = None

    print(f"Monitoring result: contact {contact_id} -> {result}")

    return jsonify({
        "status": "success",
        "result": result
    })

if __name__ == "__main__":
    print("🚀 Initializing layout table structures...")

    print("\nALL CONTACTS:")

    contacts = get_all_contacts()

    for contact in contacts:
        print(contact)

    print("\nNOT REQUESTED:")

    contacts = get_not_requested_contacts()

    for contact in contacts:
        print(contact)

    print("\nREQUESTED:")
    contacts = get_requested_contacts()
    for contact in contacts:
        print(contact)

    app.run(host="127.0.0.1", port=5000, debug=False)