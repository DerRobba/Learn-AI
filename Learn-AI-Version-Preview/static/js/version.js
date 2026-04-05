const restartButton = document.getElementById("restart-button");
const startButton = document.getElementById("start-button");
const interactionToggle = document.getElementById("interaction-toggle");
const previewWidth = document.getElementById("preview-width");
const previewHeight = document.getElementById("preview-height");
const previewHeightValue = document.getElementById("preview-height-value");

let currentDetail = window.__INITIAL_DETAIL__ || null;
let autoRefreshHandle = null;
let previewInteractive = false;

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function syncPreviewControls() {
    const width = previewWidth?.value || "100";
    const height = previewHeight?.value || "704";
    document.documentElement.style.setProperty("--preview-width", `${width}%`);
    document.documentElement.style.setProperty("--preview-height", `${height}px`);
    if (previewHeightValue) {
        previewHeightValue.textContent = `${height} px`;
    }
}

function setPreviewInteraction(enabled) {
    previewInteractive = enabled;
    const frameWrap = document.getElementById("live-preview-frame");
    frameWrap?.classList.toggle("is-interactive", enabled);

    if (interactionToggle) {
        interactionToggle.classList.toggle("hidden", !currentDetail?.running);
        interactionToggle.innerHTML = enabled
            ? '<span class="material-symbols-outlined">swipe_down</span>Seitenmodus aktiv'
            : '<span class="material-symbols-outlined">touch_app</span>Interaktion aktivieren';
    }
}

function renderMainPreview(detail) {
    const frameWrap = document.getElementById("live-preview-frame");
    if (!frameWrap) return;

    if (detail.running && detail.iframe_url) {
        frameWrap.innerHTML = `
            <div class="preview-note">
                <span class="material-symbols-outlined">mouse</span>
                <span>Mausrad scrollt die Launcher-Seite. Wenn du direkt in der Version klicken oder dort scrollen willst, aktiviere die Interaktion.</span>
            </div>
            <div class="preview-canvas">
                <iframe src="${detail.iframe_url}" title="${escapeHtml(detail.name)}" allow="microphone *"></iframe>
            </div>
        `;
        syncPreviewControls();
        setPreviewInteraction(previewInteractive);
        return;
    }

    frameWrap.innerHTML = `
        <div class="preview-error">
            <span class="material-symbols-outlined">warning</span>
            <h3>Diese Version läuft gerade nicht</h3>
            <p>${escapeHtml(detail.last_error || "Die Version konnte noch nicht gestartet werden.")}</p>
        </div>
    `;
}

function updateLogView(detail) {
    const logView = document.getElementById("log-view");
    if (!logView) return;
    const nextText = detail.logs && detail.logs.length ? detail.logs.join("\n") : "Noch keine Logs vorhanden.";
    const stickToBottom = logView.scrollTop + logView.clientHeight >= logView.scrollHeight - 20;
    logView.textContent = nextText;
    if (stickToBottom) {
        logView.scrollTop = logView.scrollHeight;
    }
}

function updateStaticInfo(detail) {
    document.getElementById("detail-title").textContent = detail.name;
    document.getElementById("detail-path").textContent = detail.path;
    document.getElementById("detail-stats").innerHTML = `
        <div class="metric-card"><span>Dateien</span><strong>${detail.file_count}</strong></div>
        <div class="metric-card"><span>Ordner</span><strong>${detail.dir_count}</strong></div>
        <div class="metric-card"><span>Port</span><strong>${detail.port || "-"}</strong></div>
    `;

    if (restartButton) {
        restartButton.dataset.versionName = detail.path;
    }
    if (startButton) {
        startButton.dataset.versionName = detail.path;
        startButton.classList.toggle("hidden", !!detail.running);
    }
    if (interactionToggle) {
        interactionToggle.classList.toggle("hidden", !detail.running);
    }

    updateLogView(detail);
}

function updatePreview(detail, restartTimer = true) {
    const frameWrap = document.getElementById("live-preview-frame");
    const previousUrl = currentDetail?.iframe_url || null;
    previewInteractive = false;
    currentDetail = detail;
    updateStaticInfo(detail);
    if (!frameWrap?.hasChildNodes() || detail.iframe_url !== previousUrl || !detail.running) {
        renderMainPreview(detail);
    }
    if (restartTimer) {
        scheduleAutoRefresh();
    }
}

async function fetchVersionDetail(versionPath) {
    const response = await fetch(`/api/versions/${encodeURIComponent(versionPath)}`);
    if (!response.ok) {
        throw new Error("Version konnte nicht geladen werden.");
    }
    return response.json();
}

async function startVersion(versionPath) {
    const response = await fetch(`/api/versions/${encodeURIComponent(versionPath)}/start`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || "Version konnte nicht gestartet werden.");
    }
    return payload;
}

async function restartVersion(versionPath) {
    const response = await fetch(`/api/versions/${encodeURIComponent(versionPath)}/restart`, { method: "POST" });
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
            updatePreview(await fetchVersionDetail(currentDetail.path), false);
        } catch (error) {
            console.error(error);
        }
    }, 5000);
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

if (startButton) {
    startButton.addEventListener("click", async () => {
        if (!startButton.dataset.versionName) return;
        startButton.disabled = true;
        try {
            updatePreview(await startVersion(startButton.dataset.versionName));
        } catch (error) {
            alert(error.message);
        } finally {
            startButton.disabled = false;
        }
    });
}

if (interactionToggle) {
    interactionToggle.addEventListener("click", () => {
        if (!currentDetail?.running) return;
        setPreviewInteraction(!previewInteractive);
    });
}

if (previewWidth) {
    previewWidth.addEventListener("change", syncPreviewControls);
}

if (previewHeight) {
    previewHeight.addEventListener("input", syncPreviewControls);
}

syncPreviewControls();
updatePreview(currentDetail);
setPreviewInteraction(false);

window.addEventListener("beforeunload", () => {
    if (autoRefreshHandle) {
        clearInterval(autoRefreshHandle);
    }
});
