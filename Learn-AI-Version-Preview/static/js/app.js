const versionList = document.getElementById("version-list");
const restartButton = document.getElementById("restart-button");
const emptyState = document.getElementById("empty-state");
const detailHead = document.getElementById("detail-head");
const detailStats = document.getElementById("detail-stats");
const previewShell = document.getElementById("preview-shell");
const logSection = document.getElementById("log-section");

let currentDetail = window.__INITIAL_VERSION__ || null;
let autoRefreshHandle = null;

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function setActiveCard(versionName) {
    document.querySelectorAll(".version-tile").forEach((card) => {
        card.classList.toggle("active", !!versionName && card.dataset.versionName === versionName);
    });
}

function renderMainPreview(detail) {
    const frameWrap = document.getElementById("live-preview-frame");
    if (!frameWrap) return;

    if (detail.running && detail.iframe_url) {
        frameWrap.innerHTML = `<iframe src="${detail.iframe_url}" title="${escapeHtml(detail.name)}"></iframe>`;
        return;
    }

    frameWrap.innerHTML = `
        <div class="preview-error">
            <span class="material-symbols-outlined">warning</span>
            <h3>Diese Version konnte noch nicht gestartet werden</h3>
            <p id="error-message">${escapeHtml(detail.last_error || "Bitte kurz warten oder neu starten.")}</p>
        </div>
    `;
}

function updateLogView(detail) {
    const logView = document.getElementById("log-view");
    if (!logView) return;

    const nextText = detail.logs && detail.logs.length
        ? detail.logs.join("\n")
        : "Noch keine Logs vorhanden.";
    const stickToBottom = logView.scrollTop + logView.clientHeight >= logView.scrollHeight - 20;

    logView.textContent = nextText;
    if (stickToBottom) {
        logView.scrollTop = logView.scrollHeight;
    }
}

function setSelectedState(selected) {
    emptyState?.classList.toggle("hidden", selected);
    detailHead?.classList.toggle("hidden", !selected);
    detailStats?.classList.toggle("hidden", !selected);
    previewShell?.classList.toggle("hidden", !selected);
    logSection?.classList.toggle("hidden", !selected);
}

function updateStaticInfo(detail) {
    setSelectedState(true);
    document.getElementById("detail-title").textContent = detail.name;
    document.getElementById("detail-stats").innerHTML = `
        <div class="metric-card"><span>Dateien</span><strong>${detail.file_count}</strong></div>
        <div class="metric-card"><span>Ordner</span><strong>${detail.dir_count}</strong></div>
        <div class="metric-card"><span>Port</span><strong>${detail.port || "-"}</strong></div>
    `;

    if (restartButton) {
        restartButton.dataset.versionName = detail.name;
    }

    updateLogView(detail);
}

function updatePreview(detail, restartTimer = true) {
    const previousUrl = currentDetail?.iframe_url || null;
    currentDetail = detail;
    setActiveCard(detail.name);
    updateStaticInfo(detail);

    if (detail.iframe_url !== previousUrl || !detail.running) {
        renderMainPreview(detail);
    }

    if (restartTimer) {
        scheduleAutoRefresh();
    }
}

async function fetchVersionDetail(versionName) {
    const response = await fetch(`/api/versions/${encodeURIComponent(versionName)}`);
    if (!response.ok) {
        throw new Error("Version konnte nicht geladen werden.");
    }
    return response.json();
}

async function restartVersion(versionName) {
    const response = await fetch(`/api/versions/${encodeURIComponent(versionName)}/restart`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || "Version konnte nicht neu gestartet werden.");
    }
    return payload;
}

function scheduleAutoRefresh() {
    if (autoRefreshHandle) {
        clearInterval(autoRefreshHandle);
    }

    autoRefreshHandle = setInterval(async () => {
        if (!currentDetail) return;
        try {
            const previousUrl = currentDetail?.iframe_url || null;
            const refreshed = await fetchVersionDetail(currentDetail.name);
            currentDetail = refreshed;
            updateStaticInfo(refreshed);
            if (refreshed.iframe_url !== previousUrl || !refreshed.running) {
                renderMainPreview(refreshed);
            }
        } catch (error) {
            console.error(error);
        }
    }, 5000);
}

if (versionList) {
    versionList.addEventListener("click", async (event) => {
        const tile = event.target.closest(".version-tile");
        if (!tile) return;

        try {
            const detail = await fetchVersionDetail(tile.dataset.versionName);
            updatePreview(detail);
            window.scrollTo({ top: 0, behavior: "smooth" });
        } catch (error) {
            console.error(error);
        }
    });
}

if (restartButton) {
    restartButton.addEventListener("click", async () => {
        if (!restartButton.dataset.versionName) return;

        restartButton.disabled = true;
        try {
            updatePreview(await restartVersion(restartButton.dataset.versionName));
        } catch (error) {
            alert(error.message);
        } finally {
            restartButton.disabled = false;
        }
    });
}

setSelectedState(false);
setActiveCard(null);

window.addEventListener("beforeunload", () => {
    if (autoRefreshHandle) {
        clearInterval(autoRefreshHandle);
    }
});
