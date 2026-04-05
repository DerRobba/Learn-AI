const compareButton = document.getElementById("compare-button");
const resetButton = document.getElementById("reset-button");
const promptInput = document.getElementById("prompt-input");
const systemPromptInput = document.getElementById("system-prompt");
const statusBox = document.getElementById("status-box");
const emptyState = document.getElementById("empty-state");
const comparisonSummary = document.getElementById("comparison-summary");
const historyPanel = document.getElementById("history-panel");
const historyList = document.getElementById("history-list");
const originalMetrics = document.getElementById("original-metrics");
const tunedMetrics = document.getElementById("tuned-metrics");
const originalResponse = document.getElementById("original-response");
const tunedResponse = document.getElementById("tuned-response");

let sharedHistory = [];
let liveBuffers = { original: "", tuned: "" };

function escapeHtml(value) {
    return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatText(text) {
    const safe = escapeHtml(text || "");
    return safe
        .split(/\n{2,}/)
        .map((paragraph) => `<p>${paragraph.replaceAll("\n", "<br>")}</p>`)
        .join("");
}

function ensureLivePlaceholder(target, message) {
    target.innerHTML = `<p>${escapeHtml(message)}</p>`;
}

function updateLiveResponse(target, text) {
    target.innerHTML = formatText(text || "");
    target.scrollTop = target.scrollHeight;
}

function setStatus(message, type = "info") {
    statusBox.classList.remove("hidden", "bg-amber-50", "border-amber-100", "text-amber-800", "bg-red-50", "border-red-100", "text-red-700", "bg-emerald-50", "border-emerald-100", "text-emerald-700");

    if (type === "error") {
        statusBox.classList.add("bg-red-50", "border-red-100", "text-red-700");
    } else if (type === "success") {
        statusBox.classList.add("bg-emerald-50", "border-emerald-100", "text-emerald-700");
    } else {
        statusBox.classList.add("bg-amber-50", "border-amber-100", "text-amber-800");
    }

    statusBox.textContent = message;
}

function renderMetricCards(target, result, accent) {
    const metrics = [
        { label: "Laufzeit", value: `${result.duration_ms} ms` },
        { label: "Woerter", value: `${result.word_count}` },
        { label: "Zeichen", value: `${result.char_count}` },
        { label: "Tokens", value: result.total_tokens ?? "n/a" },
    ];

    target.innerHTML = metrics
        .map(
            (metric) => `
                <div class="rounded-2xl border px-4 py-3 ${accent}">
                    <p class="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">${metric.label}</p>
                    <p class="mt-2 text-lg font-bold text-slate-800">${metric.value}</p>
                </div>
            `
        )
        .join("");
    target.classList.remove("hidden");
}

function renderHistory() {
    if (!sharedHistory.length) {
        historyPanel.classList.add("hidden");
        historyList.innerHTML = "";
        return;
    }

    historyPanel.classList.remove("hidden");
    historyList.innerHTML = sharedHistory
        .map((item, index) => {
            const cardClass =
                item.role === "user"
                    ? "bg-slate-50 border-slate-200"
                    : item.variant === "original"
                    ? "bg-purple-50 border-purple-100"
                    : "bg-pink-50 border-pink-100";

            const label =
                item.role === "user"
                    ? "Prompt"
                    : item.variant === "original"
                    ? "Originalmodell"
                    : "Fine-Tune";

            return `
                <div class="rounded-3xl border ${cardClass} px-4 py-4">
                    <div class="flex items-center justify-between gap-4">
                        <p class="text-sm font-semibold text-slate-700">${label}</p>
                        <span class="text-xs text-slate-400">Eintrag ${index + 1}</span>
                    </div>
                    <div class="mt-3 text-sm text-slate-600 leading-7">${formatText(item.content)}</div>
                </div>
            `;
        })
        .join("");
}

function resetView() {
    sharedHistory = [];
    liveBuffers = { original: "", tuned: "" };
    promptInput.value = "";
    originalMetrics.innerHTML = "";
    tunedMetrics.innerHTML = "";
    originalMetrics.classList.add("hidden");
    tunedMetrics.classList.add("hidden");
    originalResponse.textContent = "Die Antwort des Originalmodells erscheint hier.";
    tunedResponse.textContent = "Die Antwort des Fine-Tunes erscheint hier.";
    comparisonSummary.classList.add("hidden");
    comparisonSummary.textContent = "";
    emptyState.classList.remove("hidden");
    statusBox.classList.add("hidden");
    renderHistory();
}

async function readEventStream(response, handlers) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { value, done } = await reader.read();
        if (done) {
            break;
        }

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const rawEvent of events) {
            const lines = rawEvent.split("\n");
            let eventName = "message";
            const dataLines = [];

            for (const line of lines) {
                if (line.startsWith("event:")) {
                    eventName = line.slice(6).trim();
                } else if (line.startsWith("data:")) {
                    dataLines.push(line.slice(5).trim());
                }
            }

            if (!dataLines.length) {
                continue;
            }

            const payload = JSON.parse(dataLines.join("\n"));
            const handler = handlers[eventName];
            if (handler) {
                await handler(payload);
            }
        }
    }
}

async function compareModels() {
    const prompt = promptInput.value.trim();
    const systemPrompt = systemPromptInput.value.trim();

    if (!window.__APP_CONFIG__.originalConfigured || !window.__APP_CONFIG__.tunedConfigured) {
        setStatus("Bitte trage zuerst beide Modelle inklusive API Keys in der .env ein.", "error");
        return;
    }

    if (!prompt) {
        setStatus("Bitte gib zuerst einen Prompt ein.", "error");
        return;
    }

    compareButton.disabled = true;
    compareButton.classList.add("opacity-70", "cursor-not-allowed");
    setStatus("Streaming laeuft. Beide Modelle werden parallel abgefragt.");
    emptyState.classList.add("hidden");
    comparisonSummary.classList.add("hidden");
    comparisonSummary.textContent = "";
    originalMetrics.classList.add("hidden");
    tunedMetrics.classList.add("hidden");
    originalMetrics.innerHTML = "";
    tunedMetrics.innerHTML = "";
    liveBuffers = { original: "", tuned: "" };
    ensureLivePlaceholder(originalResponse, "Originalmodell antwortet gerade ...");
    ensureLivePlaceholder(tunedResponse, "Fine-Tune antwortet gerade ...");

    try {
        const response = await fetch("/api/compare/stream", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                prompt,
                system_prompt: systemPrompt,
                history: sharedHistory
                    .filter((entry) => entry.role === "user")
                    .map((entry) => ({ role: entry.role, content: entry.content })),
            }),
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || "Unbekannter Fehler beim Vergleich.");
        }

        if (!response.body) {
            throw new Error("Der Browser konnte den Stream nicht lesen.");
        }

        let finalPayload = null;

        await readEventStream(response, {
            start: async () => {
                setStatus("Streaming gestartet. Antworten laufen live ein.");
            },
            chunk: async (payload) => {
                liveBuffers[payload.kind] += payload.text;
                if (payload.kind === "original") {
                    updateLiveResponse(originalResponse, liveBuffers.original);
                } else if (payload.kind === "tuned") {
                    updateLiveResponse(tunedResponse, liveBuffers.tuned);
                }
            },
            done: async (payload) => {
                const accent = payload.kind === "original" ? "border-purple-100 bg-purple-50" : "border-pink-100 bg-pink-50";
                const target = payload.kind === "original" ? originalMetrics : tunedMetrics;
                renderMetricCards(target, payload.result, accent);
            },
            complete: async (payload) => {
                finalPayload = payload;
            },
            error: async (payload) => {
                throw new Error(payload.message || "Streaming ist fehlgeschlagen.");
            },
        });

        if (!finalPayload) {
            throw new Error("Streaming wurde unerwartet beendet.");
        }

        const original = finalPayload.responses.original;
        const tuned = finalPayload.responses.tuned;

        originalResponse.innerHTML = formatText(original.text);
        tunedResponse.innerHTML = formatText(tuned.text);
        renderMetricCards(originalMetrics, original, "border-purple-100 bg-purple-50");
        renderMetricCards(tunedMetrics, tuned, "border-pink-100 bg-pink-50");

        comparisonSummary.textContent = `${finalPayload.comparison.summary} Schneller war: ${finalPayload.comparison.faster_model}.`;
        comparisonSummary.classList.remove("hidden");

        sharedHistory.push({ role: "user", content: prompt });
        sharedHistory.push({ role: "assistant", variant: "original", content: original.text });
        sharedHistory.push({ role: "assistant", variant: "tuned", content: tuned.text });
        renderHistory();

        promptInput.value = "";
        setStatus("Streaming erfolgreich abgeschlossen.", "success");
    } catch (error) {
        setStatus(error.message, "error");
    } finally {
        compareButton.disabled = false;
        compareButton.classList.remove("opacity-70", "cursor-not-allowed");
    }
}

compareButton.addEventListener("click", compareModels);

promptInput.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        compareModels();
    }
});

resetButton.addEventListener("click", resetView);

resetView();
