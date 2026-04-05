const folderTreeElement = document.getElementById("folder-tree");
const versionList = document.getElementById("version-list");
const subfolderList = document.getElementById("subfolder-list");
const restartButton = document.getElementById("restart-button");
const startButton = document.getElementById("start-button");
const interactionToggle = document.getElementById("interaction-toggle");
const previewToolbar = document.getElementById("preview-toolbar");
const previewWidth = document.getElementById("preview-width");
const previewHeight = document.getElementById("preview-height");
const previewHeightValue = document.getElementById("preview-height-value");
const emptyState = document.getElementById("empty-state");
const detailHead = document.getElementById("detail-head");
const detailStats = document.getElementById("detail-stats");
const previewShell = document.getElementById("preview-shell");
const logSection = document.getElementById("log-section");

let folderTree = window.__INITIAL_TREE__ || null;
let currentFolderPath = "";
let currentDetail = window.__INITIAL_VERSION__ || null;
let autoRefreshHandle = null;
let previewInteractive = false;
const expandedFolders = new Set([""]);

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

function collectFolderCount(node) {
    if (!node) return 0;
    return 1 + (node.folders || []).reduce((total, child) => total + collectFolderCount(child), 0);
}

function getFolderNodeByPath(path, node = folderTree) {
    if (!node) return null;
    if ((node.path || "") === path) return node;
    for (const child of node.folders || []) {
        const match = getFolderNodeByPath(path, child);
        if (match) return match;
    }
    return null;
}

function findVersionCard(versionPath, node = folderTree) {
    if (!node) return null;
    for (const version of node.versions || []) {
        if (version.path === versionPath) return version;
    }
    for (const child of node.folders || []) {
        const match = findVersionCard(versionPath, child);
        if (match) return match;
    }
    return null;
}

function folderLabel(path) {
    return path || "Versions";
}

function setActiveFolder(path) {
    currentFolderPath = path;
    document.querySelectorAll(".folder-node").forEach((element) => {
        element.classList.toggle("active", element.dataset.folderPath === path);
    });
}

function setActiveCard(versionPath) {
    document.querySelectorAll(".version-tile").forEach((card) => {
        card.classList.toggle("active", !!versionPath && card.dataset.versionPath === versionPath);
    });
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
            <p id="error-message">${escapeHtml(detail.last_error || "Starte die Version manuell oder aktiviere den Autostart für ihren Ordner.")}</p>
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
    previewToolbar?.classList.toggle("hidden", !selected);
    previewShell?.classList.toggle("hidden", !selected);
    logSection?.classList.toggle("hidden", !selected);
}

function updateStaticInfo(detail) {
    setSelectedState(true);
    document.getElementById("detail-title").textContent = detail.name;
    document.getElementById("detail-path").textContent = detail.path;
    document.getElementById("detail-stats").innerHTML = `
        <div class="metric-card"><span>Dateien</span><strong>${detail.file_count}</strong></div>
        <div class="metric-card"><span>Ordner</span><strong>${detail.dir_count}</strong></div>
        <div class="metric-card"><span>Port</span><strong>${detail.port || "-"}</strong></div>
    `;

    if (restartButton) {
        restartButton.dataset.versionName = detail.path;
        restartButton.disabled = !detail.is_runnable;
    }
    if (startButton) {
        startButton.dataset.versionName = detail.path;
        startButton.classList.toggle("hidden", !!detail.running);
        startButton.disabled = !detail.is_runnable;
    }
    if (interactionToggle) {
        interactionToggle.classList.toggle("hidden", !detail.running);
    }

    updateLogView(detail);
}

function updatePreview(detail, restartTimer = true) {
    const previousUrl = currentDetail?.iframe_url || null;
    previewInteractive = false;
    currentDetail = detail;
    setActiveFolder(detail.folder_path || "");
    setActiveCard(detail.path);
    updateStaticInfo(detail);

    if (detail.iframe_url !== previousUrl || !detail.running) {
        renderMainPreview(detail);
    }

    if (restartTimer) {
        scheduleAutoRefresh();
    }
}

function versionTileMarkup(version) {
    return `
        <a class="version-tile ${currentDetail?.path === version.path ? "active" : ""}" data-version-path="${escapeHtml(version.path)}" href="/version/${encodeURIComponent(version.path)}">
            <div class="tile-shot">
                ${version.running && version.iframe_url ? `
                    <div class="shot-scale">
                        <iframe src="${version.iframe_url}" loading="lazy" title="${escapeHtml(version.name)}" allow="microphone *"></iframe>
                    </div>
                ` : `
                    <div class="shot-fallback">
                        <span class="material-symbols-outlined">web_asset</span>
                        <strong>${escapeHtml(version.name)}</strong>
                        <small>${escapeHtml(version.last_error || "Manuell starten oder Autostart für den Ordner aktivieren.")}</small>
                    </div>
                `}
                <span class="live-dot ${version.running ? "is-live" : "is-offline"}"></span>
            </div>
            <div class="tile-copy">
                <div class="tile-title-row">
                    <h3>${escapeHtml(version.name)}</h3>
                    <span class="tile-state">${version.running ? "Live" : version.last_error ? "Fehler" : "Offline"}</span>
                </div>
                <p>${escapeHtml(version.description || "Keine Beschreibung vorhanden.")}</p>
                <p class="tile-path">${escapeHtml(version.path)}</p>
            </div>
        </a>
    `;
}

function subfolderCardMarkup(folder) {
    return `
        <button type="button" class="subfolder-card" data-open-folder="${escapeHtml(folder.path)}">
            <div>
                <strong>${escapeHtml(folder.name)}</strong>
                <p>${folder.version_count_total} Versionen gesamt, ${folder.folder_count} Unterordner</p>
            </div>
            <span class="material-symbols-outlined">chevron_right</span>
        </button>
    `;
}

function renderFolderBranch(node, depth = 0) {
    const path = node.path || "";
    const isExpanded = expandedFolders.has(path);
    const hasChildren = (node.folders || []).length > 0;

    return `
        <div class="folder-branch depth-${Math.min(depth, 5)}">
            <div class="folder-node ${currentFolderPath === path ? "active" : ""}" data-folder-path="${escapeHtml(path)}">
                <button type="button" class="folder-select" data-folder-open="${escapeHtml(path)}">
                    <span class="material-symbols-outlined folder-chevron ${hasChildren ? "" : "is-hidden"}" data-folder-toggle="${escapeHtml(path)}">${isExpanded ? "expand_more" : "chevron_right"}</span>
                    <span class="material-symbols-outlined folder-icon">folder</span>
                    <span class="folder-copy">
                        <strong>${escapeHtml(node.name)}</strong>
                        <small>${node.version_count_total} Versionen</small>
                    </span>
                </button>
                <label class="folder-switch">
                    <input type="checkbox" data-folder-autostart="${escapeHtml(path)}" ${node.auto_start ? "checked" : ""}>
                    <span>Autostart</span>
                </label>
            </div>
            ${hasChildren && isExpanded ? `
                <div class="folder-children">
                    ${(node.folders || []).map((child) => renderFolderBranch(child, depth + 1)).join("")}
                </div>
            ` : ""}
        </div>
    `;
}

function renderFolderTree() {
    if (!folderTreeElement || !folderTree) return;
    folderTreeElement.innerHTML = renderFolderBranch(folderTree);
    const folderCount = document.getElementById("folder-count");
    if (folderCount) {
        folderCount.textContent = String(collectFolderCount(folderTree));
    }
    setActiveFolder(currentFolderPath);
}

function renderFolderContent() {
    const folder = getFolderNodeByPath(currentFolderPath) || folderTree;
    if (!folder) return;

    document.getElementById("folder-title").textContent = folderLabel(folder.path);
    document.getElementById("folder-subtitle").textContent = folder.path
        ? `${folder.version_count_total} Versionen in diesem Ordnerzweig.`
        : "Alle Ordner und Versionen unterhalb von Versions.";
    document.getElementById("subfolder-count").textContent = String((folder.folders || []).length);
    document.getElementById("version-count").textContent = String((folder.versions || []).length);

    subfolderList.innerHTML = (folder.folders || []).length
        ? folder.folders.map(subfolderCardMarkup).join("")
        : '<div class="empty-inline">Keine Unterordner in diesem Bereich.</div>';

    versionList.innerHTML = (folder.versions || []).length
        ? folder.versions.map(versionTileMarkup).join("")
        : '<div class="empty-inline">Keine direkten Versionen in diesem Ordner.</div>';

    setActiveFolder(folder.path || "");
    setActiveCard(currentDetail?.path || null);
}

async function fetchTree() {
    const response = await fetch("/api/tree");
    if (!response.ok) {
        throw new Error("Ordnerstruktur konnte nicht geladen werden.");
    }
    folderTree = await response.json();
    return folderTree;
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

async function updateFolderAutostart(folderPath, enabled) {
    const response = await fetch("/api/folders/autostart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder_path: folderPath, enabled }),
    });
    if (!response.ok) {
        throw new Error("Autostart konnte nicht gespeichert werden.");
    }
    folderTree = await response.json();
    renderFolderTree();
    renderFolderContent();
}

function scheduleAutoRefresh() {
    if (autoRefreshHandle) {
        clearInterval(autoRefreshHandle);
    }

    autoRefreshHandle = setInterval(async () => {
        if (!currentDetail) return;
        try {
            const refreshed = await fetchVersionDetail(currentDetail.path);
            const card = findVersionCard(currentDetail.path);
            if (card) {
                Object.assign(card, {
                    running: refreshed.running,
                    iframe_url: refreshed.iframe_url,
                    launch_url: refreshed.launch_url,
                    last_error: refreshed.last_error,
                });
            }
            updatePreview(refreshed, false);
            renderFolderContent();
        } catch (error) {
            console.error(error);
        }
    }, 5000);
}

if (folderTreeElement) {
    folderTreeElement.addEventListener("click", async (event) => {
        const openButton = event.target.closest("[data-folder-open]");
        const toggleButton = event.target.closest("[data-folder-toggle]");

        if (toggleButton) {
            const path = toggleButton.dataset.folderToggle;
            if (expandedFolders.has(path)) {
                expandedFolders.delete(path);
            } else {
                expandedFolders.add(path);
            }
            renderFolderTree();
            return;
        }

        if (openButton) {
            currentFolderPath = openButton.dataset.folderOpen || "";
            expandedFolders.add(currentFolderPath);
            renderFolderTree();
            renderFolderContent();
        }
    });

    folderTreeElement.addEventListener("change", async (event) => {
        const input = event.target.closest("[data-folder-autostart]");
        if (!input) return;
        try {
            await updateFolderAutostart(input.dataset.folderAutostart || "", input.checked);
        } catch (error) {
            input.checked = !input.checked;
            alert(error.message);
        }
    });
}

if (subfolderList) {
    subfolderList.addEventListener("click", (event) => {
        const card = event.target.closest("[data-open-folder]");
        if (!card) return;
        currentFolderPath = card.dataset.openFolder || "";
        expandedFolders.add(currentFolderPath);
        renderFolderTree();
        renderFolderContent();
    });
}

if (restartButton) {
    restartButton.addEventListener("click", async () => {
        if (!restartButton.dataset.versionName) return;

        restartButton.disabled = true;
        try {
            const detail = await restartVersion(restartButton.dataset.versionName);
            const card = findVersionCard(detail.path);
            if (card) Object.assign(card, detail);
            updatePreview(detail);
            renderFolderContent();
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
            const detail = await startVersion(startButton.dataset.versionName);
            const card = findVersionCard(detail.path);
            if (card) Object.assign(card, detail);
            updatePreview(detail);
            renderFolderContent();
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
renderFolderTree();
renderFolderContent();
setSelectedState(false);
setActiveCard(null);
setPreviewInteraction(false);

window.addEventListener("beforeunload", () => {
    if (autoRefreshHandle) {
        clearInterval(autoRefreshHandle);
    }
});
