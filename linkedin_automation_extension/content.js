const getRandomDelay = (minSeconds, maxSeconds) => {
    return new Promise(resolve => setTimeout(resolve, Math.floor(Math.random() * (maxSeconds - minSeconds + 1) + minSeconds) * 1000));
};

// ============================================================
// FIX FOR HYDRATED REACT DEAD-CLICKS
// ============================================================

function triggerHumanClick(element) {
    if (!element) return;

    // Force focus the interactive wrapper layer
    element.focus();

    // STEP 1: Execute native prototypes directly on the element shell to trigger component event listeners
    try {
        if (typeof element.click === 'function') {
            element.click();
        }
    } catch(e) {
        console.log("Native prototype click event execution bypassed...");
    }

    // STEP 2: Simultaneous trusted coordinate mouse event sequence injection fallback
    const rect = element.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;

    ['mousedown', 'mouseup', 'click'].forEach(eventType => {
        const ev = new MouseEvent(eventType, {
            bubbles: true,
            cancelable: true,
            view: window,
            clientX: x,
            clientY: y,
            buttons: eventType === 'mousedown' ? 1 : 0
        });
        element.dispatchEvent(ev);
    });
}


function isElementInSidebar(element) {
    if (!element) return false;
    const sidebarContainer = element.closest('aside, .right-rail, [data-track-heading="recommendations"]');
    if (sidebarContainer) return true;

    let parent = element.parentElement;
    while (parent && parent !== document.body) {
        const text = (parent.innerText || "").toLowerCase();
        if (text.includes("more profiles for you") && (parent.classList.contains('artdeco-card') || parent.tagName === 'SECTION')) {
            return true;
        }
        parent = parent.parentElement;
    }
    return false;
}

function findMoreDropdownButton() {
    let moreBtn = document.querySelector('button[aria-label="More"]') ||
                  document.querySelector('button[aria-label="More actions"]');

    if (!moreBtn) {
        moreBtn = Array.from(document.querySelectorAll('button')).find(b => {
            const ariaLabel = (b.getAttribute('aria-label') || '').toLowerCase();
            const text = b.innerText.trim().toLowerCase();
            return ariaLabel === 'more' || ariaLabel === 'more actions' || text === 'more';
        });
    }
    return moreBtn;
}

function findDirectConnectButton() {
    // Collect all primary structural interactive components inside the header workspace
    const primaryTarget = Array.from(document.querySelectorAll("button, a, [role='button']")).find(element => {
        if (isElementInSidebar(element)) return false;

        const text = element.innerText.replace(/\s+/g, ' ').trim().toLowerCase();
        const componentKey = (element.getAttribute("componentkey") || "").toLowerCase();
        const ariaLabel = (element.getAttribute("aria-label") || "").toLowerCase();
        const href = (element.getAttribute("href") || "").toLowerCase();

        return text === "connect" ||
               text.startsWith("connect ") ||
               text.includes("connect to") ||
               componentKey.includes("connect") ||
               href.includes("/preload/custom-invite/") ||
               (ariaLabel.includes("invite") && ariaLabel.includes("connect"));
    });

    if (!primaryTarget) return null;

    // DRILL DOWN DOWNWARDS ONLY WHEN ENCOUNTERING ENCLOSED POP-UP OVERLAY ITEMS
    const isDropdownItem = primaryTarget.getAttribute('role') === 'menuitem' || primaryTarget.closest('.artdeco-dropdown__content');

    if (isDropdownItem && primaryTarget.tagName === "A") {
        const innerTextNode = primaryTarget.querySelector('span, div, p');
        if (innerTextNode) return innerTextNode;
    }

    // CRITICAL: Always return the outer container shell for standard profile card headers to protect click tracking pathways
    return primaryTarget;
}

function extractCustomInviteUrlViaDomString() {
    const pageHtmlSource = document.documentElement.innerHTML;
    const invitePathRegex = /\/preload\/custom-invite\/\?vanityName=[a-zA-Z0-9\-_%]+/g;
    const discoveredMatches = pageHtmlSource.match(invitePathRegex);

    if (discoveredMatches && discoveredMatches.length > 0) {
        const structuralPath = discoveredMatches[0];
        console.log("🎯 Dynamic Source Parsing Success! Captured target route parameters: " + structuralPath);
        return "https://linkedin.com" + structuralPath;
    }
    return null;
}

function findSendWithoutNoteButton() {
    let btn = document.querySelector('button[aria-label="Send without a note"]') ||
              document.querySelector('button[aria-label="Send"]') ||
              Array.from(document.querySelectorAll('button')).find(b => {
                  const text = b.textContent.replace(/\s+/g, ' ').trim().toLowerCase();
                  return text.includes("send without a note") || text === "send";
              });

    if (btn) return btn;

    function searchShadows(root) {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
        let node;
        while (node = walker.nextNode()) {
            if (node.shadowRoot) {
                const shadowBtn = node.shadowRoot.querySelector('button[aria-label="Send without a note"]') ||
                                  node.shadowRoot.querySelector('button[aria-label="Send"]') ||
                                  Array.from(node.shadowRoot.querySelectorAll('button')).find(b => {
                                      const text = b.textContent.replace(/\s+/g, ' ').trim().toLowerCase();
                                      return text.includes("send without a note") || text === "send";
                                      });
                if (shadowBtn) return shadowBtn;
                const deepMatch = searchShadows(node.shadowRoot);
                if (deepMatch) return deepMatch;
            }
        }
        return null;
    }
    return searchShadows(document);
}


function isAlreadyConnected() {
    const candidates = [
        ...document.querySelectorAll(
            '[aria-label="Remove connection"]'
        )
    ];

    return candidates.some(element => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 &&
               rect.height > 0 &&
               element.getClientRects().length > 0;
    });
}


async function getConnectionStatusFromPage() {
    // 1. Check visible profile controls first.
    if (isAlreadyConnected()) {
        return "CONNECTED";
    }

    const getVisibleLabels = () =>
        Array.from(
            document.querySelectorAll(
                "button, a, [role='button'], [role='menuitem']"
            )
        )
        .filter(element => {
            const rect = element.getBoundingClientRect();
            return rect.width > 0 &&
                   rect.height > 0 &&
                   element.getClientRects().length > 0;
        })
        .map(element => (
            element.getAttribute("aria-label") ||
            element.innerText ||
            element.textContent ||
            ""
        ).replace(/\s+/g, " ").trim().toLowerCase());

    const detectStatus = () => {
        const labels = getVisibleLabels();

        if (labels.some(label =>
            label.includes("remove connection")
        )) {
            return "CONNECTED";
        }

        if (labels.some(label =>
            label === "pending" ||
            label.includes("invitation sent") ||
            label.includes("withdraw invitation")
        )) {
            return "REQUESTED";
        }

        return null;
    };

    let status = detectStatus();

    if (status) {
        return status;
    }

    // 2. Inspect the More dropdown if no clear status was found.
    const moreButton = findMoreDropdownButton();

    if (moreButton) {
        triggerHumanClick(moreButton);
        await getRandomDelay(1, 2);

        status = detectStatus();

        if (status) {
            return status;
        }
    }

    // 3. Never guess when LinkedIn provides insufficient evidence.
    return "UNKNOWN";
}


function waitForSendModalElement(maxWaitMs = 5000) {
    return new Promise((resolve) => {
        const checkIntervalMs = 500;
        let elapsedMs = 0;

        const intervalTracker = setInterval(() => {
            const discoveredButton = findSendWithoutNoteButton();
            if (discoveredButton) {
                clearInterval(intervalTracker);
                resolve(discoveredButton);
                return;
            }

            elapsedMs += checkIntervalMs;
            if (elapsedMs >= maxWaitMs) {
                clearInterval(intervalTracker);
                resolve(null);
            }
        }, checkIntervalMs);
    });
}

function querySelectorDeep(selector, root = document) {
    const directMatch = root.querySelector(selector);

    if (directMatch) {
        return directMatch;
    }

    for (const element of root.querySelectorAll("*")) {
        if (element.shadowRoot) {
            const match = querySelectorDeep(selector, element.shadowRoot);

            if (match) {
                return match;
            }
        }
    }

    return null;
}

function querySelectorAllDeep(selector, root = document, results = []) {
    results.push(...root.querySelectorAll(selector));

    for (const element of root.querySelectorAll("*")) {
        if (element.shadowRoot) {
            querySelectorAllDeep(selector, element.shadowRoot, results);
        }
    }

    return results;
}

async function sendCareerMessage(messageText) {
    const messageLink = Array.from(
        document.querySelectorAll('a[href*="/messaging/compose/"]')
    ).find(element => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 &&
            rect.height > 0 &&
            element.getClientRects().length > 0;
    });

    if (!messageLink) {
        return {
            status: "FAILED",
            reason: "Message button not found"
        };
    }

    triggerHumanClick(messageLink);
    await getRandomDelay(2, 4);

    const textboxSelector =
        '[contenteditable="true"][role="textbox"][aria-label="Write a message…"]';

    let textbox = null;

// LinkedIn may render the composer asynchronously.
    for (let attempt = 0; attempt < 10; attempt++) {
        textbox = querySelectorDeep(textboxSelector);

        if (textbox && textbox.getClientRects().length > 0) {
            break;
        }

        await getRandomDelay(0.5, 1);
    }

    if (!textbox || textbox.getClientRects().length === 0) {
        return {
            status: "FAILED",
            reason: "Visible message textbox not found after waiting"
        };
    }

    textbox.focus();

    // Use the editor's insertion mechanism rather than inserting a
    // text node directly, which may not update LinkedIn's internal state.
    textbox.dispatchEvent(new InputEvent("beforeinput", {
        bubbles: true,
        cancelable: true,
        inputType: "insertText",
        data: messageText
    }));

    const inserted = document.execCommand(
        "insertText",
        false,
        messageText
    );

    await getRandomDelay(1, 2);

    textbox = querySelectorDeep(textboxSelector);

    const actualText = textbox
        ? textbox.innerText.trim()
        : "";

    if (!inserted || actualText !== messageText.trim()) {
        return {
            status: "FAILED",
            reason: "Message text could not be verified in the editor"
        };
    }

    const sendButton = querySelectorDeep("button.msg-form__send-button");

    if (!sendButton || sendButton.disabled) {
        return {
            status: "FAILED",
            reason: "Send button unavailable"
        };
    }


// Click Send only after verifying the composed text.
    triggerHumanClick(sendButton);

    await getRandomDelay(2, 3);

// Check whether the message appears in the conversation.
// A missing confirmation does not necessarily mean it failed.

    const messageBodies = querySelectorAllDeep(
        ".msg-s-event-listitem__body"
    );

    const matchingMessage = messageBodies.find(
        element => element.innerText.trim() === messageText.trim()
    );

    if (matchingMessage) {
        const messageContainer = matchingMessage.closest(
            ".msg-s-event-listitem__message-bubble"
        );

        const sentIndicator = messageContainer?.querySelector(
            '[data-test-msg-cross-pillar-message-sending-indicator-presenter__sending-indicator--sent]'
        );

        if (sentIndicator) {
            return {
                status: "SENT",
                reason: "Matching message and LinkedIn sent indicator verified"
            };
        }
    }

    return {
        status: "UNKNOWN",
        reason: "Message sent indicator could not be verified"
    };
}

async function closeMessagingPanel() {
    const closeButton = querySelectorAllDeep(
    "button.msg-overlay-bubble-header__control"
).find(button =>
    button.querySelector('use[href="#close-small"]') ||
    button.innerText.includes("Close your draft conversation")
);

if (!closeButton) {
    console.log("❌ Draft conversation close button not found.");
    return;
}

console.log("✅ Correct X button found:", closeButton);
triggerHumanClick(closeButton);
await getRandomDelay(1, 2);
console.log("✅ Close button clicked.");
}


// ============================================================
// CORE PIPELINE FLUID CONTROL RUNTIME
// ============================================================
async function runExtensionPipeline() {
    const currentUrl = window.location.href.toLowerCase();
    console.log("🚀 Extension engine active on URL: " + currentUrl);

    const sendBtn = findSendWithoutNoteButton();
    if (currentUrl.includes("/custom-invite") && sendBtn) {
        console.log("⚡ Verified custom invite landing space! Resolving task completion...");

        const targetResponse = await new Promise((resolve) => {
            chrome.runtime.sendMessage({ action: "FETCH_NEXT_TARGET_REQUEST" }, (res) => resolve(res));
        });

        if (targetResponse && targetResponse.status === "success" && targetResponse.command.action !== "IDLE") {
            const target = targetResponse.command.target;
            console.log("🚀 Clicking final transmission button for: " + target.name);

            triggerHumanClick(sendBtn);
            await getRandomDelay(2, 4);

            console.log("📡 Writing success confirmation status parameters to Flask...");
            chrome.runtime.sendMessage({ action: "PROFILE_PROCESS_SUCCESS", id: target.id });
            return;
        }
    }

    if (!currentUrl.includes("/in/")) {
        console.log("⏳ Not on a target profile workspace. Standing by...");
        return;
    }

    const targetResponse = await new Promise((resolve) => {
        chrome.runtime.sendMessage({ action: "FETCH_NEXT_TARGET_REQUEST" }, (res) => resolve(res));
    });

    if (!targetResponse || targetResponse.status !== "success" || targetResponse.command.action === "IDLE") {
        console.log("⏳ AI Agent is currently idle or background unavailable. Re-checking in 5 seconds...");
        setTimeout(runExtensionPipeline, 5000);
        return;
    }

    const target = targetResponse.command.target;
    const targetUrl = (target.profile_url || target.url || "").toLowerCase();

    if (!currentUrl.includes(targetUrl.replace(/\/\(/, "")) && !targetUrl.includes(currentUrl.replace(/\/\)/, ""))) {
        console.log(`⚠️ Route divergence caught. Navigating tab frame straight onto: ${targetUrl}`);
        chrome.runtime.sendMessage({ action: "TRIGGER_NEXT_JUMP" });
        return;
    }

    console.log(`🎯 Context locked onto profile target: ${target.name}`);
    await getRandomDelay(4, 7)

    if (targetResponse.command.action === "CHECK_STATUS") {
    console.log(`🔎 Checking connection status for ${target.name}`);

    const result = await getConnectionStatusFromPage();

    console.log(`📋 Detected status: ${result}`);

    chrome.runtime.sendMessage({
        action: "REPORT_MONITORING_RESULT",
        id: target.id,
        result: result
    });

    return;
}


if (targetResponse.command.action === "SEND_MESSAGE") {
    const messageText = targetResponse.command.target.message;

    if (!messageText) {
        console.error("❌ No message text supplied for this contact.");
        return;
    }


    const result = await sendCareerMessage(messageText);

    console.log("📨 Message composition result:", result);

    // Close the conversation before reporting completion.
    await closeMessagingPanel();

    chrome.runtime.sendMessage({
        action: "REPORT_MESSAGE_RESULT",
        id: target.id,
        result: result.status,
        reason: result.reason
    });

    return;
}


    if (isAlreadyConnected()) {
            console.log(
                `Already connected: ${target.name}`
            );

            chrome.runtime.sendMessage({
                action: "UPDATE_CONTACT_STATUS",
                id: target.id,
                status: "CONNECTED"
            });

            return;
        }

    let connectBtn = findDirectConnectButton();

    console.log("⏳ Simulating human viewing delay parameters...");
    await getRandomDelay(4, 7);

    if (!connectBtn) {
        console.log("ℹ Direct targets absent. Searching for 'More' dropdown element...");
        const moreDropdown = findMoreDropdownButton();

        if (moreDropdown) {
            console.log("⚡ Found 'More' dropdown. Executing click interface...");
            triggerHumanClick(moreDropdown);
            await getRandomDelay(2, 3);

            connectBtn = findDirectConnectButton();
        }
    }

    if (connectBtn) {
        console.log("⚡ Executing connect button click event...");
        triggerHumanClick(connectBtn);

        console.log("⏳ Actively polling DOM tree for animation layers...");
        const normalSendBtn = await waitForSendModalElement(5000);
        if (normalSendBtn) {
            console.log("🎯 Target element matched overlay framework! Completing invitation transmission...");
            triggerHumanClick(normalSendBtn);
            await getRandomDelay(2, 4);
            chrome.runtime.sendMessage({ action: "PROFILE_PROCESS_SUCCESS", id: target.id });
        } else {
            console.log("❌ The connection modal overlay failed to inject within the allocation window.");
        }
    } else {
        console.log("ℹ Dropdown pathways absent. Bypassing layouts via raw string regex fallback...");
        const extractedInviteUrl = extractCustomInviteUrlViaDomString();
        if (extractedInviteUrl) {
console.log("⚡ Route discovered safely! Navigating to extracted workspace landing space...");
window.location.href = extractedInviteUrl;
} else {
console.log("❌ Target path parameters completely absent from page source code. Advancing queue...");
chrome.runtime.sendMessage({ action: "TRIGGER_NEXT_JUMP" });
}
}
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "CLOSE_MESSAGING_PANEL") {
        closeMessagingPanel()
            .then(() => sendResponse({ status: "success" }))
            .catch(error => {
                console.error("Failed to close messaging panel:", error);
                sendResponse({ status: "error" });
            });

        return true;
    }
});

if (document.readyState === "complete" || document.readyState === "interactive") {
runExtensionPipeline();
} else {
window.addEventListener("load", runExtensionPipeline);
}