
const API_BASE = "http://127.0.0.1:8000";

function getHeaders() {
    const headers = { "Content-Type": "application/json" };
    const session = JSON.parse(localStorage.getItem("twin_session") || "{}");
    if (session.token) {
        headers["Authorization"] = `Bearer ${session.token}`;
    }
    return headers;
}

async function login(username, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
    });
    if (!res.ok) throw new Error("Login failed");
    return await res.json();
}

async function fetchProfile() {
    const res = await fetch(`${API_BASE}/profile/me`, { headers: getHeaders() });
    if (!res.ok) throw new Error("Failed to fetch profile");
    return await res.json();
}

async function askTwin(message, sessionId = null, profileKey = "individual") {
    const res = await fetch(`${API_BASE}/twin/chat`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ message, session_id: sessionId, profile_key: profileKey })
    });
    if (!res.ok) throw new Error("Chat failed");
    return await res.json();
}

async function getChatSessions(profileKey = "individual") {
    const res = await fetch(`${API_BASE}/twin/chats?profile_key=${profileKey}`, { headers: getHeaders() });
    if (!res.ok) throw new Error("Failed to fetch chats");
    return await res.json();
}

async function getChatSession(sessionId, profileKey = "individual") {
    const res = await fetch(`${API_BASE}/twin/chats/${sessionId}?profile_key=${profileKey}`, { headers: getHeaders() });
    if (!res.ok) throw new Error("Failed to fetch chat session");
    return await res.json();
}

async function simulateDecision(decisionId, commitmentPct) {
    const res = await fetch(`${API_BASE}/twin/simulate`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ decision_id: decisionId, commitment_pct: commitmentPct })
    });
    if (!res.ok) throw new Error("Simulation failed");
    return await res.json();
}

async function simulateScenario(scenario, profileKey = "individual") {
    const res = await fetch(`${API_BASE}/twin/simulate-scenario`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ scenario, profile_key: profileKey })
    });
    if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error((detail && detail.detail) || "Simulation failed");
    }
    return await res.json();
}

async function parseStatement(file) {
    const formData = new FormData();
    formData.append("file", file);
    
    // We cannot use getHeaders directly because Content-Type must be unset for FormData
    const headers = {};
    const session = JSON.parse(localStorage.getItem("twin_session") || "{}");
    if (session.token) {
        headers["Authorization"] = `Bearer ${session.token}`;
    }
    
    const res = await fetch(`${API_BASE}/onboard/parse-statement`, {
        method: "POST",
        headers: headers,
        body: formData
    });
    if (!res.ok) throw new Error("Parse failed");
    return await res.json();
}

async function confirmProfile(userId, persona, metrics) {
    const res = await fetch(`${API_BASE}/onboard/confirm`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ user_id: userId, persona, metrics })
    });
    if (!res.ok) throw new Error("Confirm failed");
    return await res.json();
}

async function startupOnboard(payload) {
    const res = await fetch(`${API_BASE}/onboard/startup`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify(payload)
    });
    if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error((detail && detail.detail) || "Startup onboarding failed");
    }
    return await res.json();
}

async function fetchStartupOverview() {
    const res = await fetch(`${API_BASE}/startup/overview`, { headers: getHeaders() });
    if (!res.ok) throw new Error("Failed to fetch startup overview");
    return await res.json();
}

async function fetchStartupHisaab() {
    const res = await fetch(`${API_BASE}/startup/hisaab`, { headers: getHeaders() });
    if (!res.ok) throw new Error("Failed to fetch Hisaab");
    return await res.json();
}

async function addStartupTransaction(payload) {
    const res = await fetch(`${API_BASE}/startup/hisaab/transactions`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify(payload)
    });
    if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error((detail && detail.detail) || "Failed to add transaction");
    }
    return await res.json();
}

async function fetchWeeklyReport() {
    const res = await fetch(`${API_BASE}/startup/reports/weekly`, { headers: getHeaders() });
    if (!res.ok) throw new Error("Failed to fetch weekly report");
    return await res.json();
}

async function onboardingChat(messages) {
    const res = await fetch(`${API_BASE}/onboard/chat`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ messages })
    });
    if (!res.ok) throw new Error("Chat failed");
    return await res.json();
}

async function renameChatSession(sessionId, title, profileKey = "individual") {
    const res = await fetch(`${API_BASE}/twin/chats/${sessionId}?profile_key=${profileKey}`, {
        method: "PUT",
        headers: getHeaders(),
        body: JSON.stringify({ title })
    });
    if (!res.ok) throw new Error("Failed to rename chat");
    return await res.json();
}

async function deleteChatSession(sessionId, profileKey = "individual") {
    const res = await fetch(`${API_BASE}/twin/chats/${sessionId}?profile_key=${profileKey}`, {
        method: "DELETE",
        headers: getHeaders()
    });
    if (!res.ok) throw new Error("Failed to delete chat");
    return await res.json();
}

window.api = {
    login,
    fetchProfile,
    askTwin,
    getChatSessions,
    getChatSession,
    simulateDecision,
    simulateScenario,
    parseStatement,
    confirmProfile,
    onboardingChat,
    renameChatSession,
    deleteChatSession,
    startupOnboard,
    fetchStartupOverview,
    fetchStartupHisaab,
    addStartupTransaction,
    fetchWeeklyReport
};

