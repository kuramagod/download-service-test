// ===== Общие настройки =====
const STATUS_LABELS = {
    idle: "Ожидание",
    running: "Выполняется",
    stopped: "Остановлено",
    blocked: "Заблокировано",
    done: "Завершено",
    error: "Ошибка",
};

const STATUS_COLORS = {
    idle: "bg-gray-50 border-gray-300 text-gray-700",
    running: "bg-blue-50 border-blue-300 text-blue-700",
    stopped: "bg-orange-50 border-orange-300 text-orange-700",
    blocked: "bg-yellow-50 border-yellow-300 text-yellow-700",
    done: "bg-green-50 border-green-300 text-green-700",
    error: "bg-red-50 border-red-300 text-red-700",
};

let statusPollTimer = null;

function formatDate(value) {
    if (!value) return "—";
    return value.replace("T", " ").split(".")[0];
}

// ===== Статус скачивания (общий для всех страниц) =====
async function fetchDownloadStatus() {
    try {
        const res = await fetch("/api/download/status");
        if (!res.ok) return;
        const data = await res.json();
        renderGlobalBanner(data);
        renderDownloadPage(data);

        if (data.status === "running") {
            if (!statusPollTimer) {
                statusPollTimer = setInterval(fetchDownloadStatus, 1300);
            }
        } else if (statusPollTimer) {
            clearInterval(statusPollTimer);
            statusPollTimer = null;
        }
    } catch (e) {
        console.error("Ошибка получения статуса:", e);
    }
}

function renderGlobalBanner(data) {
    const banner = document.getElementById("global-status-banner");
    if (!banner) return;

    if (data.status === "idle") {
        banner.classList.add("hidden");
        return;
    }

    banner.classList.remove("hidden");
    banner.className = "mb-4 p-3 rounded-lg text-sm border " + (STATUS_COLORS[data.status] || "");

    const total = data.batch_total ?? data.total_names_seen ?? 0;
    const downloaded = data.batch_downloaded ?? data.downloaded_count ?? 0;

    let text = `Статус скачивания: ${STATUS_LABELS[data.status] || data.status}. ` +
        `Получено ${total} имён файлов, скачано ${downloaded} из ${total}.`;

    if (data.status === "blocked" && data.blocked_until) {
        text += ` Заблокировано до ${formatDate(data.blocked_until)} (НСК).`;
    }
    if (data.message) {
        text += ` ${data.message}`;
    }
    banner.textContent = text;

    const globalBtn = document.getElementById("global-download-btn");
    if (globalBtn) {
        globalBtn.disabled = data.status === "running";
    }
}

function renderDownloadPage(data) {
    const statusValue = document.getElementById("status-value");
    if (!statusValue) return; // не на странице загрузки

    statusValue.textContent = STATUS_LABELS[data.status] || data.status;
    document.getElementById("started-at-value").textContent = formatDate(data.started_at);
    document.getElementById("blocked-until-value").textContent = formatDate(data.blocked_until);
    document.getElementById("message-value").textContent = data.message || "—";

    const total = data.batch_total ?? data.total_names_seen ?? 0;
    const downloaded = data.batch_downloaded ?? data.downloaded_count ?? 0;
    const percent = total > 0 ? Math.round((downloaded / total) * 100) : 0;

    const label = data.status === "running"
        ? `Получено ${total} имён файлов, скачивается ${downloaded} из ${total}`
        : `Получено ${total} имён файлов, скачано ${downloaded} из ${total}`;

    document.getElementById("progress-label").textContent = label;
    document.getElementById("progress-percent").textContent = percent + "%";
    document.getElementById("progress-bar").style.width = percent + "%";

    const startBtn = document.getElementById("start-download-btn");
    if (startBtn) {
        startBtn.disabled = data.status === "running";
    }

    const stopBtn = document.getElementById("stop-download-btn");
    if (stopBtn) {
        stopBtn.disabled = data.status !== "running";
    }
}

async function startDownload() {
    try {
        const res = await fetch("/api/download/start", { method: "POST" });
        if (!res.ok) {
            alert("Не удалось начать скачивание.");
            return;
        }
        fetchDownloadStatus();
    } catch (e) {
        console.error("Ошибка запуска скачивания:", e);
        alert("Ошибка запуска скачивания.");
    }
}

async function stopDownload() {
    try {
        const res = await fetch("/api/download/stop", { method: "POST" });
        if (!res.ok) {
            alert("Не удалось остановить скачивание.");
            return;
        }
        await fetchDownloadStatus();
    } catch (e) {
        console.error("Ошибка остановки скачивания:", e);
        alert("Ошибка остановки скачивания.");
    }
}

// ===== Страница файлов и расчётов =====
const filesState = {
    page: 1,
    size: 20,
    sort: "desc",
    total: 0,
    items: [],
    selected: new Set(),
};

async function loadFiles() {
    const params = new URLSearchParams({
        page: filesState.page,
        size: filesState.size,
        sort: filesState.sort,
    });
    const res = await fetch(`/api/files?${params.toString()}`);
    if (!res.ok) return;
    const data = await res.json();

    filesState.items = data.items;
    filesState.total = data.total;
    filesState.page = data.page;
    filesState.size = data.size;

    renderFilesTable();
    renderPagination();
    updateSelectedCount();
}

function renderFilesTable() {
    const tbody = document.getElementById("files-table-body");
    tbody.innerHTML = "";

    filesState.items.forEach((item) => {
        const tr = document.createElement("tr");
        tr.className = "border-b hover:bg-gray-50";

        const checked = filesState.selected.has(item.filename) ? "checked" : "";

        tr.innerHTML = `
            <td class="p-2">
                <input type="checkbox" class="file-checkbox" data-filename="${item.filename}" ${checked}>
            </td>
            <td class="p-2 break-all">${item.filename}</td>
            <td class="p-2 whitespace-nowrap">${formatDate(item.downloaded_at)}</td>
        `;
        tbody.appendChild(tr);
    });

    document.querySelectorAll(".file-checkbox").forEach((cb) => {
        cb.addEventListener("change", (e) => {
            const filename = e.target.dataset.filename;
            if (e.target.checked) {
                filesState.selected.add(filename);
            } else {
                filesState.selected.delete(filename);
            }
            syncSelectPageCheckbox();
            updateSelectedCount();
        });
    });

    syncSelectPageCheckbox();
}

function syncSelectPageCheckbox() {
    const pageCheckbox = document.getElementById("select-page-checkbox");
    const pageFilenames = filesState.items.map((i) => i.filename);
    const allSelected = pageFilenames.length > 0 &&
        pageFilenames.every((f) => filesState.selected.has(f));
    pageCheckbox.checked = allSelected;
}

function renderPagination() {
    const totalPages = Math.max(1, Math.ceil(filesState.total / filesState.size));
    document.getElementById("pagination-info").textContent =
        `Всего файлов: ${filesState.total}`;
    document.getElementById("page-indicator").textContent =
        `Страница ${filesState.page} из ${totalPages}`;

    document.getElementById("prev-page-btn").disabled = filesState.page <= 1;
    document.getElementById("next-page-btn").disabled = filesState.page >= totalPages;
}

function updateSelectedCount() {
    document.getElementById("selected-count").textContent =
        `Выбрано файлов: ${filesState.selected.size}`;
    document.getElementById("calc-btn").disabled = filesState.selected.size === 0;
}

async function selectAllFilesOverall() {
    try {
        const res = await fetch("/api/files/all");
        if (!res.ok) return;

        const payload = await res.json();
        const filenames = Array.isArray(payload?.filenames)
            ? payload.filenames
            : Array.isArray(payload)
                ? payload
                : [];

        filenames.forEach((f) => filesState.selected.add(f));
        renderFilesTable();
        updateSelectedCount();
    } catch (e) {
        console.error("Ошибка выбора всех файлов:", e);
    }
}

function clearSelection() {
    filesState.selected.clear();
    renderFilesTable();
    updateSelectedCount();
}

async function runCalculations() {
    const errorEl = document.getElementById("calc-error");
    errorEl.classList.add("hidden");

    const filenames = Array.from(filesState.selected);
    if (filenames.length === 0) return;

    try {
        const res = await fetch("/api/files/statistics", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filenames }),
        });

        if (res.status === 422) {
            errorEl.textContent = "Не выбрано ни одного файла для расчёта.";
            errorEl.classList.remove("hidden");
            return;
        }
        if (res.status === 404) {
            errorEl.textContent = "Некоторые из выбранных файлов не найдены на сервере.";
            errorEl.classList.remove("hidden");
            return;
        }
        if (!res.ok) {
            errorEl.textContent = "Не удалось выполнить расчёты.";
            errorEl.classList.remove("hidden");
            return;
        }

        const data = await res.json();
        renderCalcResults(data);
    } catch (e) {
        console.error("Ошибка расчётов:", e);
        errorEl.textContent = "Ошибка при обращении к серверу.";
        errorEl.classList.remove("hidden");
    }
}

function renderCalcResults(data) {
    const resultsBlock = document.getElementById("calc-results");
    resultsBlock.classList.remove("hidden");

    const totalGrid = document.getElementById("total-stat-grid");
    totalGrid.innerHTML = "";
    for (let digit = 0; digit <= 9; digit++) {
        const count = data.total_statistic[String(digit)] ?? 0;
        totalGrid.innerHTML += `
            <div class="border rounded p-2">
                <div class="text-xs text-gray-500">Цифра ${digit}</div>
                <div class="font-semibold">${count}</div>
            </div>
        `;
    }

    const fileBody = document.getElementById("file-stat-body");
    fileBody.innerHTML = "";
    data.file_statistic.forEach((fileStat) => {
        const digitsCells = Array.from({ length: 10 }, (_, digit) =>
            `<td class="p-2 text-center">${fileStat.digits[String(digit)] ?? 0}</td>`
        ).join("");

        fileBody.innerHTML += `
            <tr class="border-b">
                <td class="p-2 break-all">${fileStat.filename}</td>
                ${digitsCells}
            </tr>
        `;
    });
}

// ===== Инициализация =====
document.addEventListener("DOMContentLoaded", () => {
    // Кнопка "Скачать данные" (доступна на любой странице)
    const globalBtn = document.getElementById("global-download-btn");
    if (globalBtn) {
        globalBtn.addEventListener("click", startDownload);
    }
    const startBtn = document.getElementById("start-download-btn");
    if (startBtn) {
        startBtn.addEventListener("click", startDownload);
    }

    const stopBtn = document.getElementById("stop-download-btn");
    if (stopBtn) {
        stopBtn.addEventListener("click", stopDownload);
    }

    // Статус опрашивается всегда, каждую секунду, пока идёт скачивание,
    // и один раз при загрузке любой страницы
    fetchDownloadStatus();
    if (!statusPollTimer) {
        // на случай, если процесс запущен из другой вкладки/страницы
        setInterval(fetchDownloadStatus, 1300);
    }

    // Инициализация страницы файлов, если мы на ней
    if (document.getElementById("files-table-body")) {
        loadFiles();

        document.getElementById("sort-select").addEventListener("change", (e) => {
            filesState.sort = e.target.value;
            filesState.page = 1;
            loadFiles();
        });

        document.getElementById("size-select").addEventListener("change", (e) => {
            filesState.size = parseInt(e.target.value, 10);
            filesState.page = 1;
            loadFiles();
        });

        document.getElementById("prev-page-btn").addEventListener("click", () => {
            if (filesState.page > 1) {
                filesState.page -= 1;
                loadFiles();
            }
        });

        document.getElementById("next-page-btn").addEventListener("click", () => {
            filesState.page += 1;
            loadFiles();
        });

        document.getElementById("select-page-checkbox").addEventListener("change", (e) => {
            filesState.items.forEach((item) => {
                if (e.target.checked) {
                    filesState.selected.add(item.filename);
                } else {
                    filesState.selected.delete(item.filename);
                }
            });
            renderFilesTable();
            updateSelectedCount();
        });

        document.getElementById("select-all-btn").addEventListener("click", selectAllFilesOverall);
        document.getElementById("clear-selection-btn").addEventListener("click", clearSelection);
        document.getElementById("calc-btn").addEventListener("click", runCalculations);
    }
});