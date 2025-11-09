const API_BASE = "http://localhost:8000/api";
const QUERY_ENDPOINT = `${API_BASE}/query`;

const chatHistory = [];
let chatBusy = false;

async function uploadUfdr(event) {
    event.preventDefault();
    const fileInput = document.getElementById("ufdr-file");
    const statusNode = document.getElementById("upload-status");

    if (!fileInput.files.length) {
        statusNode.textContent = "Please select a UFDR archive first.";
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append("file", file);

    statusNode.textContent = "Uploading and parsing...";

    try {
        const response = await fetch(`${API_BASE}/ingest/ufdr`, {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Upload failed");
        }

        const result = await response.json();
        statusNode.textContent = `Ingestion complete. Messages: ${result.summary.messages_ingested}, Contacts: ${result.summary.contacts_ingested}`;
        await Promise.all([refreshMessages(), refreshContacts(), refreshSystemInfo()]);
    } catch (error) {
        console.error(error);
        statusNode.textContent = `Error: ${error.message}`;
    }
}

async function fetchPaginated(endpoint, params = {}) {
    const url = new URL(`${API_BASE}/${endpoint}`);
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
            url.searchParams.append(key, value);
        }
    });

    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to fetch ${endpoint}`);
    }
    return response.json();
}

function truncate(text, len = 120) {
    if (!text) {
        return "";
    }
    return text.length > len ? `${text.slice(0, len)}…` : text;
}

async function refreshMessages() {
    const search = document.getElementById("message-search").value;
    const tableBody = document.querySelector("#messages-table tbody");
    tableBody.innerHTML = "";

    try {
        const data = await fetchPaginated("messages", { search, limit: 50 });
        data.items.forEach((item) => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${item.timestamp || ""}</td>
                <td>${item.sender || ""}</td>
                <td>${item.receiver || ""}</td>
                <td>${truncate(item.body)}</td>
            `;
            tableBody.appendChild(row);
        });
    } catch (error) {
        console.error(error);
    }
}

async function refreshContacts() {
    const search = document.getElementById("contact-search").value;
    const tableBody = document.querySelector("#contacts-table tbody");
    tableBody.innerHTML = "";

    try {
        const data = await fetchPaginated("contacts", { search, limit: 50 });
        data.items.forEach((item) => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${item.display_name || ""}</td>
                <td>${item.phone_number || ""}</td>
                <td>${item.email || ""}</td>
            `;
            tableBody.appendChild(row);
        });
    } catch (error) {
        console.error(error);
    }
}

async function refreshSystemInfo() {
    const tableBody = document.querySelector("#system-info-table tbody");
    tableBody.innerHTML = "";

    try {
        const data = await fetchPaginated("system-info", { limit: 100 });
        data.items.forEach((item) => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${item.info_key}</td>
                <td>${truncate(item.info_value, 200)}</td>
                <td>${item.category || ""}</td>
            `;
            tableBody.appendChild(row);
        });
    } catch (error) {
        console.error(error);
    }
}

function attachEventListeners() {
    document.getElementById("upload-form").addEventListener("submit", uploadUfdr);
    document.getElementById("message-refresh").addEventListener("click", refreshMessages);
    document.getElementById("contact-refresh").addEventListener("click", refreshContacts);
    document.getElementById("message-search").addEventListener("keyup", (event) => {
        if (event.key === "Enter") {
            refreshMessages();
        }
    });
    document.getElementById("contact-search").addEventListener("keyup", (event) => {
        if (event.key === "Enter") {
            refreshContacts();
        }
    });

    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const resetButton = document.getElementById("chat-reset");

    if (chatForm) {
        chatForm.addEventListener("submit", handleChatSubmit);
    }
    if (chatInput) {
        chatInput.addEventListener("keydown", handleChatKeydown);
    }
    if (resetButton) {
        resetButton.addEventListener("click", () => resetChat(true));
    }
}

attachEventListeners();
resetChat(true);
refreshMessages();
refreshContacts();
refreshSystemInfo();

function appendChatMessage(role, content, { pending = false } = {}) {
    const log = document.getElementById("chat-log");
    if (!log) {
        return null;
    }

    const wrapper = document.createElement("div");
    wrapper.className = `chat-message ${role}${pending ? " pending" : ""}`;

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";

    const label = document.createElement("div");
    label.className = "chat-label";
    label.textContent = role === "assistant" ? "Analyst" : "You";

    const body = document.createElement("div");
    body.className = "chat-content";
    body.textContent = content;

    bubble.appendChild(label);
    bubble.appendChild(body);
    wrapper.appendChild(bubble);
    log.appendChild(wrapper);
    log.scrollTop = log.scrollHeight;
    return wrapper;
}

function updateAssistantMessage(node, content) {
    if (!node) {
        return;
    }
    node.classList.remove("pending");
    const body = node.querySelector(".chat-content");
    if (body) {
        body.textContent = content;
    }
}

function setChatStatus(message, isError = false) {
    const statusNode = document.getElementById("chat-status");
    if (!statusNode) {
        return;
    }
    statusNode.textContent = message;
    statusNode.classList.toggle("error", Boolean(isError && message));
}

function toggleChatInputs(disabled) {
    const input = document.getElementById("chat-input");
    const sendButton = document.getElementById("chat-send");
    chatBusy = disabled;
    if (input) {
        input.disabled = disabled;
    }
    if (sendButton) {
        sendButton.disabled = disabled;
    }
}

function renderEvidence(evidence) {
    const list = document.getElementById("evidence-list");
    const emptyState = document.getElementById("evidence-empty");
    if (!list || !emptyState) {
        return;
    }

    list.innerHTML = "";

    if (!Array.isArray(evidence) || evidence.length === 0) {
        emptyState.style.display = "block";
        return;
    }

    emptyState.style.display = "none";

    evidence.forEach((item) => {
        const li = document.createElement("li");
        li.className = "evidence-item";

    const title = document.createElement("div");
    title.className = "evidence-id";
    const hasScore = Number.isFinite(item.score);
    const scoreText = hasScore ? ` (score ${item.score.toFixed(3)})` : "";
    title.textContent = `${item.id}${scoreText}`;

        const text = document.createElement("div");
        text.className = "evidence-text";
        text.textContent = item.text || "";

        li.appendChild(title);
        li.appendChild(text);

        const metadataEntries = item.metadata ? Object.entries(item.metadata) : [];
        if (metadataEntries.length) {
            const metadata = document.createElement("div");
            metadata.className = "evidence-meta";
            metadata.textContent = metadataEntries.map(([k, v]) => `${k}: ${v}`).join(", ");
            li.appendChild(metadata);
        }

        list.appendChild(li);
    });
}

function resetChat(showGreeting) {
    const log = document.getElementById("chat-log");
    const input = document.getElementById("chat-input");
    chatHistory.length = 0;
    if (log) {
        log.innerHTML = "";
    }
    if (showGreeting) {
        appendChatMessage("assistant", "I'm ready to help analyze the UFDR data.");
    }
    setChatStatus("");
    renderEvidence([]);
    if (input) {
        input.value = "";
        input.disabled = false;
        input.focus();
    }
    const sendButton = document.getElementById("chat-send");
    if (sendButton) {
        sendButton.disabled = false;
    }
    chatBusy = false;
}

async function handleChatSubmit(event) {
    event.preventDefault();
    if (chatBusy) {
        return;
    }

    const input = document.getElementById("chat-input");
    if (!input) {
        return;
    }

    const question = input.value.trim();
    if (!question) {
        return;
    }

    appendChatMessage("user", question);
    toggleChatInputs(true);
    setChatStatus("Consulting Gemini...", false);
    const placeholder = appendChatMessage("assistant", "Reviewing evidence...", { pending: true });

    try {
        const payload = {
            question,
            conversation: chatHistory.map((turn) => ({ role: turn.role, content: turn.content })),
        };

        const response = await fetch(QUERY_ENDPOINT, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            let detail = "Query failed.";
            try {
                const error = await response.json();
                detail = error.detail || detail;
            } catch (parseError) {
                // ignore JSON parse error
            }
            throw new Error(detail);
        }

        const data = await response.json();
        const answer = data.answer || "No answer returned.";
        updateAssistantMessage(placeholder, answer);
        renderEvidence(data.evidence || []);
        setChatStatus(data.model ? `Model: ${data.model}` : "Ready", false);

        chatHistory.push({ role: "user", content: question });
        chatHistory.push({ role: "assistant", content: answer });
    } catch (error) {
        if (placeholder && placeholder.remove) {
            placeholder.remove();
        }
        setChatStatus(error.message || "Query failed.", true);
        appendChatMessage("assistant", "I wasn't able to complete that request. Please try again.");
    } finally {
        toggleChatInputs(false);
        input.value = "";
        input.focus();
    }
}

function handleChatKeydown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        const chatForm = document.getElementById("chat-form");
        if (chatForm) {
            chatForm.requestSubmit();
        }
    }
}
