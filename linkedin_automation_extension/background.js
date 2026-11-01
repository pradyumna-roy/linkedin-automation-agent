const BACKEND_URL = "http://127.0.0.1:5000";

// This synchronous listener interface forces Chrome to keep the worker awake
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("📡 Background worker received action signal:", message.action);

    // 1. Proxy Fetch Routing (Bypasses secure context blocks completely)
    if (message.action === "FETCH_NEXT_TARGET_REQUEST") {
        fetch(BACKEND_URL + "/api/next-target")
            .then(res => {
                if (!res.ok) throw new Error("HTTP error " + res.status);
                return res.json();
            })
            .then(data => {
                console.log("✓ Successfully fetched target payload data:", data);
                sendResponse(data);
            })
            .catch(err => {
                console.error("❌ Failed to query Flask backend server:", err);
                sendResponse({ status: "error", message: err.message });
            });
        return true; // 🌟 CRITICAL: This forces the messaging channel to stay open asynchronously!
    }

    // 2. Success Record Handler
    if (message.action === "PROFILE_PROCESS_SUCCESS") {
        console.log("📡 Processing success database update sequence for ID:", message.id);
        fetch(BACKEND_URL + "/api/mark-requested", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: message.id })
        })
        .then(() => {
            navigateToNextProfile(sender.tab.id);
        })
        .catch(err => console.error("❌ Failed to write success update:", err));
        return true;
    }

    // 3. Redirection Fallback Trigger
    if (message.action === "TRIGGER_NEXT_JUMP") {
        navigateToNextProfile(sender.tab.id);
        return true;
    }


if (message.action === "REPORT_MONITORING_RESULT") {
    console.log(
        `📡 Reporting monitoring result for contact ${message.id}: ${message.result}`
    );

    fetch(`${BACKEND_URL}/agent/report-result`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            id: message.id,
            result: message.result
        })
    })
    .then(async response => {
    const data = await response.json();

    if (!response.ok || data.status !== "success") {
        throw new Error(data.message || "Monitoring report failed");
    }

    console.log("✅ Monitoring result accepted by Flask:", data);

    // Wait for the agent to queue the next task.
    navigateToNextProfile(sender.tab.id);
})
.catch(error => {
    console.error("❌ Failed to report monitoring result:", error);
});

    return true;
}


if (message.action === "CLOSE_MESSAGING_PANEL") {
    chrome.tabs.sendMessage(
        sender.tab.id,
        { action: "CLOSE_MESSAGING_PANEL" },
        response => {
            if (chrome.runtime.lastError) {
                console.error(
                    "Failed to close messaging panel:",
                    chrome.runtime.lastError.message
                );
                return;
            }

            console.log("Messaging panel close response:", response);
        }
    );

    return true;
}


if (message.action === "REPORT_MESSAGE_RESULT") {
    console.log(
        `📨 Reporting message result for contact ${message.id}: ${message.result}`
    );

    fetch(`${BACKEND_URL}/agent/report-message-result`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            id: message.id,
            result: message.result,
            reason: message.reason
        })
    })
    .then(async response => {
        const data = await response.json();

        if (!response.ok || data.status !== "success") {
            throw new Error(data.message || "Message result reporting failed");
        }

        console.log("✅ Message result received by Flask:", data);

        if (sender.tab?.id) {
    navigateToNextProfile(sender.tab.id);
}
    })
    .catch(error => {
        console.error("❌ Failed to report message result:", error);
    });

    return true;
}



    if (message.action === "UPDATE_CONTACT_STATUS") {
        fetch(BACKEND_URL + "/api/mark-requested", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                id: message.id,
                status: message.status
            })
        })
        .then(async response => {
            const data = await response.json();

            if (!response.ok || data.status !== "success") {
                throw new Error(
                    data.message || "Database update failed"
                );
            }

            console.log(
                `Database status updated: ${message.id} → ${message.status}`
            );
        })
        .catch(error => {
            console.error("Database status update failed:", error);
        });

        return true;
    }

});

// Navigation Engine Controller


async function navigateToNextProfile(tabId) {
    console.log("⏳ Waiting for the next queued task...");

    const deadline = Date.now() + 60000;

    function closePanelAndNavigate(url) {
        chrome.tabs.sendMessage(
            tabId,
            { action: "CLOSE_MESSAGING_PANEL" },
            response => {
                if (chrome.runtime.lastError) {
                    console.warn(
                        "Could not close messaging panel:",
                        chrome.runtime.lastError.message
                    );
                } else {
                    console.log("Messaging panel response:", response);
                }

                // Allow time for the panel to close before navigating.
                setTimeout(() => {
                    console.log("➡️ Navigating to:", url);
                    chrome.tabs.update(tabId, { url });
                }, 1500);
            }
        );
    }

    function checkForNextTarget() {
        fetch(BACKEND_URL + "/api/next-target")
            .then(res => {
                if (!res.ok) throw new Error("HTTP error " + res.status);
                return res.json();
            })
            .then(serverCheck => {
                const command = serverCheck?.command;

                if (
                    serverCheck?.status === "success" &&
                    command?.action !== "IDLE" &&
                    command?.target?.url
                ) {
                    closePanelAndNavigate(command.target.url);
                    return;
                }

                if (Date.now() < deadline) {
                    setTimeout(checkForNextTarget, 2000);
                } else {
                    console.log("🏁 No next task queued; standing by.");
                }
            })
            .catch(err => {
                console.error("❌ Error checking next target:", err);

                if (Date.now() < deadline) {
                    setTimeout(checkForNextTarget, 3000);
                }
            });
    }

    setTimeout(checkForNextTarget, 2000);
}