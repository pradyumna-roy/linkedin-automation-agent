import sqlite3
from datetime import datetime


DB_NAME = "linkedin_contacts.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def create_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS linkedin_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            linkedin_url TEXT NOT NULL UNIQUE,

            connection_status TEXT NOT NULL
                DEFAULT 'NOT_REQUESTED',

            request_sent_date TEXT,

            msg_sent_date TEXT,

            followup_required INTEGER
                DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()

    print("✓ Database initialized.")

def drop_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""drop table if exists linkedin_contacts""")

    conn.commit()
    conn.close()

# ============================================================
# ADD CONTACT
# ============================================================

def add_contact(name, linkedin_url, status='NOT_REQUESTED'):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO linkedin_contacts
        (
            name,
            linkedin_url,
            connection_status
        )
        VALUES (?, ?, ?)
    """, (
        name,
        linkedin_url,
        status  # Uses the variable passed into the function
    ))

    conn.commit()
    conn.close()

    print(f"✓ Contact added: {name} Status: {status}")



# ============================================================
# DELETE SPECIFIC CONTACTS
# ============================================================

def drop_contacts(contact_ids):
    """
    Removes specific contacts from the database.
    Accepts a single ID (int) or a list/tuple of IDs (e.g., [1, 2]).
    """
    # If a single integer is passed, turn it into a list
    if isinstance(contact_ids, int):
        contact_ids = [contact_ids]

    if not contact_ids:
        print("✗ No IDs provided.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Creates the appropriate number of placeholders: (?, ?, ?)
    placeholders = ",".join("?" for _ in contact_ids)

    cursor.execute(f"""
        DELETE FROM linkedin_contacts 
        WHERE id IN ({placeholders})
    """, tuple(contact_ids))

    conn.commit()

    print(f"✓ Command executed. Rows affected: {cursor.rowcount}")
    conn.close()


# ============================================================
# GET ALL CONTACTS
# ============================================================

def get_all_contacts():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            linkedin_url,
            connection_status,
            request_sent_date,
            msg_sent_date,
            followup_required
        FROM linkedin_contacts
        ORDER BY id
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows



# ============================================================
# UPDATE CONNECTION STATUS
# ============================================================

def mark_request_sent(contact_id):

    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute("""
        UPDATE linkedin_contacts
        SET
            connection_status = 'REQUESTED',
            request_sent_date = ?
        WHERE id = ?
    """, (
        now,
        contact_id
    ))

    conn.commit()
    conn.close()

    print(
        f"✓ Contact {contact_id} → REQUESTED"
    )


# ============================================================
# GET REQUESTED CONTACTS
# ============================================================

def get_requested_contacts():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            linkedin_url,
            connection_status,
            request_sent_date
        FROM linkedin_contacts
        WHERE connection_status = 'REQUESTED'
        ORDER BY id
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows

# ============================================================
# GET NOT REQUESTED CONTACTS
# ============================================================

def get_not_requested_contacts():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            linkedin_url,
            connection_status
        FROM linkedin_contacts
        WHERE connection_status = 'NOT_REQUESTED'
        ORDER BY id
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


# ============================================================
# UPDATE CONNECTED
# ============================================================

def mark_connected(contact_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE linkedin_contacts
        SET connection_status = 'CONNECTED'
        WHERE id = ?
    """, (contact_id,))

    conn.commit()
    conn.close()

    print(
        f"✓ Contact {contact_id} → CONNECTED"
    )

def get_connected_contacts():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
                   SELECT 
                       id, 
                       name, 
                       linkedin_url,
                       connection_status
                   FROM linkedin_contacts
                   WHERE connection_status = 'CONNECTED'
                     AND msg_sent_date IS NULL
                   """)

    contacts = cursor.fetchall()
    conn.close()

    return contacts

# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    create_database()

    # You can manually add contacts here
    #add_contact("name", "linkedin_url")

    print("\nALL CONTACTS:")

    contacts = get_all_contacts()

    for contact in contacts:

        print(contact)