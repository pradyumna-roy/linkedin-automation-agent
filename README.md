# LinkedIn Automation Agent (POC)

An experimental LinkedIn automation system built using Python, Playwright/Chrome extension technologies, SQLite, and Groq LLMs. The project aims to automate parts of the outreach workflow, including connection requests, connection monitoring, and personalized follow-up messages.

> **Note:** This is a proof of concept, not a production-ready automation platform.

## Features

- **Connection requests:** Identifies contacts whose connection status is `NOT_REQUESTED` and initiates connection requests.
- **Connection monitoring:** Checks profiles with a `REQUESTED` status to identify accepted connection requests.
- **Personalized messaging:** Sends messages to contacts whose status is `CONNECTED`.
- **Message verification:** Checks LinkedIn's interface for confirmation that a message was sent.
- **Database management:** Uses SQLite to maintain contact information and workflow statuses.
- **AI agent orchestration:** Uses Groq LLMs to coordinate outreach workflows and tool execution.

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python, Flask, Flask-CORS |
| AI agent | Groq API |
| Browser automation | Chrome Extension (Manifest V3) |
| Database | SQLite |
| Environment management | uv |
| Frontend automation | JavaScript |

## Project Structure

```text
Linkedin agent PoC/
│
├── backend/
│   ├── database.py
│   ├── database_bridge.py
│   └── groq_agent.py
│
├── linkedin_automation_extension/
│   ├── manifest.json
│   ├── background.js
│   └── content.js
│
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
└── README.md
```

## Architecture

The system consists of three main components:

1. **Python backend:** Manages contact records, database operations, workflow coordination, and communication with the browser extension.
2. **Chrome extension:** Interacts with LinkedIn's web interface to perform browser actions and report execution results.
3. **Groq-powered agent:** Coordinates outreach workflows and invokes the relevant tools based on the current workflow.

### Workflow

The project uses three primary workflows:

**1. Send Connection Requests**
- Retrieves contacts with `NOT_REQUESTED` status from the database.
- Navigates to the corresponding LinkedIn profiles.
- Initiates connection requests.
- Updates the database to `REQUESTED`.

**2. Monitor Connection Requests**
- Retrieves contacts with `REQUESTED` status from the database.
- Navigates to the corresponding LinkedIn profiles.
- Checks whether connection requests have been accepted.
- Updates accepted contacts to `CONNECTED`, or else keeps them as `REQUESTED`.

**3. Send Follow-up Messages**
- Retrieves contacts with `CONNECTED` status from database, where `msg_sent_date` is empty.
- Sends a pre-defined personal pitch message.
- Verifies successful delivery via the LinkedIn interface.
- Updates the `msg_sent_date` timestamp in the database.

## Database Statuses

| Status | Description |
|---|---|
| `NOT_REQUESTED` | No connection request has been sent. |
| `REQUESTED` | A connection request has been sent and is awaiting acceptance. |
| `CONNECTED` | The connection request has been accepted. |

## Prerequisites

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/)
- Google Chrome
- A Groq API key

## Installation

**1. Clone the repository**

```bash
git clone <repository-url>
cd <repository-folder>
```

**2. Install dependencies**

```bash
uv sync
```

**3. Configure environment variables**

Create a `.env` file in the project root using `.env.example` as a template.

```dotenv
GROQ_API_KEY=your_groq_api_key
```

**4. Load the Chrome extension**

1. Open `chrome://extensions/` in Google Chrome.
2. Enable Developer mode.
3. Select **Load unpacked**.
4. Select the `linkedin_automation_extension` folder.

## Running the Project

The application requires two Python processes running simultaneously.

**1. Start the database bridge**

Open a terminal in the project root:

```bash
uv run python backend/database_bridge.py
```

This starts the Flask server at:

```text
http://127.0.0.1:5000
```

**2. Start the automation scheduler**

Open a second terminal in the project root:

```bash
uv run python backend/groq_agent.py
```

The scheduler executes an automation cycle and waits for the defined period before starting the next cycle.

**3. Keep Chrome running**

Ensure the Chrome extension is loaded and the browser session is authenticated before running the automation workflows.


## Important Notes

- This project is an experimental proof of concept.
- A logged-in LinkedIn browser session is required.
- This project relies entirely on a **DOM-based automation approach**, where elements are interacted with and clicked based on their `Inspect Element` structural selectors (attributes, classes, or text content). 
- Because LinkedIn frequently updates its frontend interface, structural elements or layouts may change without notice. **If LinkedIn updates its UI, selector paths may break, requiring updates to the selectors within the DOM script.**