// ==================== GLOBAL VARIABLES ====================

const API_BASE = "/api";
let configData = {};
let statsData = {};
let allTrackers = [];
let trackerChartInstance = null;
let grabsByDayChartInstance = null;
let topTorrentsChartInstance = null;
let overviewTrackerChartPayload = null;
let overviewGrabsTrendPayload = null;
let overviewChartResizeBound = false;
let historyReconcileCache = [];
let torrentsTableCache = [];
let historySyncConfirmTimer = null;
let syncNowConfirmTimer = null;
let purgeLogsConfirmTimer = null;
let purgeDbConfirmTimer = null;
let loadConfigConfirmTimer = null;
let saveConfigConfirmTimer = null;
let apiKeysTargetId = 'api-keys-list';
let apiKeysVault = new Map();
let toggleAuthConfirmTimer = null;
let securityAuthState = {
    auth_enabled: false,
    username: '',
    password_configured: false,
    cookie_secure: false
};

// ==================== DOM HELPERS ====================

function byId(id) {
    return document.getElementById(id);
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function maskSecret(value, visibleStart = 6, visibleEnd = 3) {
    const raw = String(value ?? '');
    if (!raw) return '';
    if (raw.length <= visibleStart + visibleEnd + 3) return `${raw.slice(0, 3)}***`;
    return `${raw.slice(0, visibleStart)}…${raw.slice(-visibleEnd)}`;
}

function maskUrlSecret(rawUrl) {
    const value = String(rawUrl ?? '');
    if (!value) return '';
    return value.replace(/([?&](?:apikey|token)=)([^&]+)/ig, (match, prefix, token) => {
        return `${prefix}${maskSecret(token)}`;
    });
}

function setText(id, value) {
    const el = byId(id);
    if (el) el.textContent = value;
}

function debounce(fn, delay) {
    let timer = null;
    return (...args) => {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

async function fetchJsonSafe(url, fallbackValue) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.warn(`API indisponible (${url}):`, error);
        return fallbackValue;
    }
}

function truncateChartLabel(value, max = 22) {
    const text = String(value || '');
    if (text.length <= max) return text;
    return text.slice(0, max - 1) + '…';
}

function formatShortDateLabel(value) {
    if (!value) return '';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
}

function getOverviewChartCommonOptions(compact) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        layout: {
            padding: {
                top: 6,
                right: 8,
                bottom: 4,
                left: 4
            }
        },
        plugins: {
            legend: {
                display: true,
                position: compact ? 'bottom' : 'right',
                align: 'center',
                labels: {
                    color: '#e0e0e0',
                    boxWidth: compact ? 12 : 14,
                    boxHeight: compact ? 12 : 14,
                    padding: compact ? 10 : 12,
                    usePointStyle: true,
                    pointStyle: 'circle',
                    font: {
                        size: compact ? 11 : 12,
                        weight: '600'
                    }
                }
            },
            title: {
                display: true,
                color: '#1e90ff',
                font: {
                    size: compact ? 14 : 15,
                    weight: '700'
                },
                padding: {
                    top: 4,
                    bottom: compact ? 6 : 8
                }
            },
            tooltip: {}
        }
    };
}

function renderOverviewTrackerChart(payload, forceRebuild = false) {
    const canvas = byId('trackerChart');
    if (!canvas) return;
    if (typeof Chart === 'undefined') {
        showNotificationDetail('Chart indisponible (librairie non chargée).', 'warning');
        return;
    }

    const labels = (payload?.labels || []).slice();
    const data = (payload?.data || []).slice();
    if (!labels.length || !data.length) {
        if (trackerChartInstance) {
            trackerChartInstance.destroy();
            trackerChartInstance = null;
        }
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        return;
    }
    const compact = window.innerWidth < 768;
    const chartData = {
        labels: labels,
        datasets: [{
            data: data,
            backgroundColor: [
                '#1e90ff', '#ff6b6b', '#4ecdc4', '#45b7d1', '#f7b731',
                '#5f27cd', '#00d2d3', '#ff9ff3', '#54a0ff', '#48dbfb'
            ]
        }]
    };

    const options = getOverviewChartCommonOptions(compact);
    options.plugins.title.text = 'Grabs par Tracker';
    options.plugins.legend.labels.generateLabels = (chart) => {
        const source = chart.data.labels || [];
        return source.map((name, i) => ({
            text: truncateChartLabel(name, compact ? 14 : 22),
            fillStyle: chart.data.datasets[0].backgroundColor[i % chart.data.datasets[0].backgroundColor.length],
            strokeStyle: chart.data.datasets[0].backgroundColor[i % chart.data.datasets[0].backgroundColor.length],
            hidden: !chart.getDataVisibility(i),
            index: i
        }));
    };
    options.plugins.tooltip.callbacks = {
        title: (items) => {
            if (!items || !items.length) return '';
            const idx = items[0].dataIndex;
            return labels[idx] || '';
        }
    };
    options.cutout = compact ? '44%' : '48%';

    const ctx = canvas.getContext('2d');
    if (trackerChartInstance && !forceRebuild) {
        trackerChartInstance.data = chartData;
        trackerChartInstance.options = options;
        trackerChartInstance.update('none');
        return;
    }
    if (trackerChartInstance) {
        trackerChartInstance.destroy();
    }
    trackerChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: chartData,
        options
    });
}

function renderOverviewGrabsTrendChart(payload, forceRebuild = false) {
    const canvas = byId('grabsTrendChart');
    if (!canvas || typeof Chart === 'undefined') return;

    const labels = (payload?.labels || []).slice();
    const data = (payload?.data || []).slice();
    if (!labels.length || !data.length) {
        if (grabsByDayChartInstance) {
            grabsByDayChartInstance.destroy();
            grabsByDayChartInstance = null;
        }
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        return;
    }

    const compact = window.innerWidth < 768;
    const chartData = {
        labels: labels.map(formatShortDateLabel),
        datasets: [{
            label: 'Grabs',
            data,
            borderColor: '#60a5fa',
            backgroundColor: 'rgba(96, 165, 250, 0.18)',
            pointRadius: compact ? 1.5 : 2.5,
            pointHoverRadius: compact ? 3 : 4,
            tension: 0.3,
            fill: true
        }]
    };

    const options = getOverviewChartCommonOptions(compact);
    options.plugins.title.text = 'Grabs (30 jours)';
    options.plugins.tooltip.callbacks = {
        title: (items) => {
            if (!items || !items.length) return '';
            const idx = items[0].dataIndex;
            const raw = labels[idx];
            const d = new Date(raw);
            if (Number.isNaN(d.getTime())) return String(raw || '');
            return d.toLocaleDateString('fr-FR', {
                weekday: 'short',
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            });
        }
    };
    options.scales = {
        x: {
            ticks: {
                color: '#cbd5e1',
                maxTicksLimit: compact ? 6 : 10
            },
            grid: {
                color: 'rgba(51, 65, 85, 0.35)'
            }
        },
        y: {
            beginAtZero: true,
            ticks: {
                color: '#cbd5e1',
                precision: 0
            },
            grid: {
                color: 'rgba(51, 65, 85, 0.35)'
            }
        }
    };

    const ctx = canvas.getContext('2d');
    if (grabsByDayChartInstance && !forceRebuild) {
        grabsByDayChartInstance.data = chartData;
        grabsByDayChartInstance.options = options;
        grabsByDayChartInstance.update('none');
        return;
    }
    if (grabsByDayChartInstance) {
        grabsByDayChartInstance.destroy();
    }
    grabsByDayChartInstance = new Chart(ctx, {
        type: 'line',
        data: chartData,
        options
    });
}

function setOverviewKpiCardsState(state) {
    const cards = document.querySelectorAll('.ui-card--kpi');
    if (!cards.length) return;
    cards.forEach(card => {
        card.classList.remove('is-loading', 'is-empty', 'is-error');
        if (state === 'loading') card.classList.add('is-loading');
        if (state === 'error') card.classList.add('is-error');
    });
}

function updateOverviewKpiEmptyState() {
    const cards = document.querySelectorAll('.ui-card--kpi[data-kpi-target]');
    cards.forEach(card => {
        card.classList.remove('is-empty');
        const targetId = card.dataset.kpiTarget;
        const target = targetId ? byId(targetId) : null;
        if (!target) {
            card.classList.add('is-empty');
            return;
        }
        const value = (target.textContent || '').trim();
        if (!value || value === '-' || value.toLowerCase() === 'n/a') {
            card.classList.add('is-empty');
        }
    });
}

// ==================== NOTIFICATIONS ====================

function showNotification(message, type = 'info') {
    const existing = document.querySelector('.ui-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `ui-toast ui-toast--${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function showNotificationDetail(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `ui-toast ui-toast--${type}`;
    toast.textContent = message;
    toast.style.marginTop = '8px';
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, 3500);
}

function copyText(value) {
    if (!value) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value).then(() => {
            showNotificationDetail('Copié', 'success');
        }).catch(() => {
            fallbackCopyText(value);
        });
    } else {
        fallbackCopyText(value);
    }
}

function copyTextWithButtonFeedback(value, buttonElement) {
    if (!value) return;
    const setCopiedState = () => {
        if (!buttonElement) return;
        const originalText = buttonElement.textContent;
        buttonElement.textContent = 'Copie OK';
        buttonElement.classList.add('copied');
        setTimeout(() => {
            buttonElement.textContent = originalText;
            buttonElement.classList.remove('copied');
        }, 2000);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value).then(() => {
            setCopiedState();
        }).catch(() => {
            fallbackCopyText(value);
            setCopiedState();
        });
    } else {
        fallbackCopyText(value);
        setCopiedState();
    }
}

function fallbackCopyText(value) {
    const temp = document.createElement('textarea');
    temp.value = value;
    temp.setAttribute('readonly', '');
    temp.style.position = 'absolute';
    temp.style.left = '-9999px';
    document.body.appendChild(temp);
    temp.select();
    try {
        document.execCommand('copy');
        showNotificationDetail('Copié', 'success');
    } catch (e) {
        showNotificationDetail('Copie impossible', 'warning');
    } finally {
        document.body.removeChild(temp);
    }
}

function openGrabHistoryDetailModal(row) {
    const modal = byId('grab-history-detail-modal');
    const body = byId('grab-history-detail-body');
    if (!modal || !body || !row) return;

    const items = [
        { label: 'Instance', value: row.instance || '-' },
        { label: 'Tracker', value: row.indexer || '-' },
        { label: 'Source', value: row.source || '-' },
        { label: 'Source (last)', value: row.source_last_seen || '-' },
        { label: 'Titre', value: row.source_title || '-' },
        { label: 'Info URL', value: row.info_url || '-' },
        { label: 'Taille', value: row.size ? `${(row.size / (1024 ** 3)).toFixed(2)} GiB` : '-' },
        { label: 'Date', value: row.grabbed_at ? new Date(row.grabbed_at).toLocaleString('fr-FR') : '-' }
    ];

    const downloadId = row.download_id || '-';
    body.innerHTML = `
        <div class="detail-row detail-row--highlight">
            <div class="detail-label">Download ID</div>
            <div class="detail-value"><strong>${downloadId}</strong></div>
            <button class="btn btn-primary btn-xs" type="button" data-copy-value="${String(downloadId).replace(/"/g, '&quot;')}">Copier</button>
        </div>
    ` + items.map(item => `
        <div class="detail-row">
            <div class="detail-label">${item.label}</div>
            <div class="detail-value">${item.value}</div>
            <button class="btn btn-secondary btn-xs" type="button" data-copy-value="${String(item.value).replace(/"/g, '&quot;')}">Copier</button>
        </div>
    `).join('');

    body.querySelectorAll('[data-copy-value]').forEach(btn => {
        btn.addEventListener('click', () => copyText(btn.dataset.copyValue || ''));
    });

    modal.hidden = false;
}

function closeGrabHistoryDetailModal() {
    const modal = byId('grab-history-detail-modal');
    if (modal) modal.hidden = true;
}

function updateGrabHistorySummary(rows) {
    const safeRows = Array.isArray(rows) ? rows : [];
    const total = safeRows.length;
    const webhookCount = safeRows.filter(row => String(row?.source || '').toLowerCase() === 'webhook').length;
    const missingCount = safeRows.filter(row => !row?.torrent_file).length;
    const latestGrab = safeRows
        .map(row => row?.grabbed_at)
        .filter(Boolean)
        .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0];

    setText('grabs-summary-total', total);
    setText('grabs-summary-webhook', webhookCount);
    setText('grabs-summary-missing', missingCount);
    setText('grabs-summary-last-sync', latestGrab ? new Date(latestGrab).toLocaleString('fr-FR') : '-');
}

function showPageError(message) {
    const errorBox = document.querySelector('[data-role="page-error"]');
    if (!errorBox) return;
    errorBox.textContent = message;
    errorBox.classList.add('is-visible');
    errorBox.hidden = false;
}

function clearPageError() {
    const errorBox = document.querySelector('[data-role="page-error"]');
    if (!errorBox) return;
    errorBox.textContent = '';
    errorBox.classList.remove('is-visible');
    errorBox.hidden = true;
}

function warnMissing(feature, selector) {
    console.warn(`UI: élément manquant pour ${feature}: ${selector}`);
    showPageError(`UI incomplète: ${feature}. Élément(s) manquant(s): ${selector}`);
    showNotification(`UI incomplète: ${feature}`, 'warning');
}

function ensureElements(feature, selectors) {
    const missing = selectors.filter(selector => !document.querySelector(selector));
    if (missing.length) {
        warnMissing(feature, missing.join(', '));
        return false;
    }
    return true;
}

function setActiveNav(page) {
    if (!page) return;
    document.querySelectorAll('.app-sidebar__link').forEach(link => {
        link.classList.toggle('is-active', link.dataset.page === page);
    });
}

function bindActionHandlers() {
    const actionHandlers = {
        'sync-now': syncNow,
        'refresh-data': refreshData,
        'purge-grabs': purgeAllGrabs,
        'save-config': saveConfig,
        'load-config': loadConfig,
        'logout': logout,
        'security-edit-auth': showSecurityAuthEditor,
        'security-cancel-auth-edit': hideSecurityAuthEditor,
        'security-save-auth-credentials': saveSecurityAuthCredentials,
        'security-toggle-auth': toggleSecurityAuthEnabled,
        'load-torrents': loadTorrents,
        'cleanup-orphans': cleanupOrphanTorrents,
        'purge-torrents': purgeAllTorrents,
        'delete-bulk-torrents': deleteBulkTorrents,
        'purge-logs': purgeAllLogs,
        'purge-db': purgeDatabase,
        'sync-grab-history': syncGrabHistory,
        'toggle-all-torrents': toggleAllTorrents,
        'copy-api-key': handleCopyApiKey,
        'delete-api-key': handleDeleteApiKey,
        'toggle-api-key': handleToggleApiKey,
        'toggle-auth-inline': toggleSecurityAuthEnabled
    };

    document.querySelectorAll('[data-action]').forEach(element => {
        const action = element.dataset.action;
        const handler = actionHandlers[action];
        if (!handler) return;
        if (element.dataset.boundAction === 'true') return;
        const eventName = ['toggle-all-torrents'].includes(action) ? 'change' : 'click';
        element.addEventListener(eventName, event => {
            event.preventDefault();
            handler(event, element);
        });
        element.dataset.boundAction = 'true';
    });
}

// ==================== UTILITY FUNCTIONS ====================

function applySyncStatus(sync) {
    const statusEl = byId("sync-status");

    let statusClass = "status offline";
    let statusText = "Inactif";
    if (sync?.is_running) {
        statusClass = "status online";
        statusText = "Sync en cours...";
    } else if (sync?.next_sync) {
        statusClass = "status online";
        statusText = "Actif";
    } else if (sync?.last_sync) {
        statusClass = "status offline";
        statusText = "Arrete";
    } else {
        statusClass = "status offline";
        statusText = "En attente";
    }

    if (statusEl) {
        statusEl.className = statusClass;
        statusEl.textContent = statusText;
    }

    const syncButtons = document.querySelectorAll('[data-action="sync-now"]');
    syncButtons.forEach(btn => {
        if (sync?.is_running) {
            btn.disabled = true;
            btn.textContent = 'Sync en cours...';
            return;
        }
        if (btn.dataset.manualSyncLoading === 'true') {
            return;
        }
        if (btn.dataset.confirming === 'true') {
            return;
        }
        btn.disabled = false;
        btn.textContent = 'Synchroniser';
    });
}

async function refreshSyncIndicators() {
    try {
        const res = await fetch(API_BASE + '/sync/status');
        if (!res.ok) return;
        const sync = await res.json();
        applySyncStatus(sync);
        setText("next-sync", sync.next_sync ? new Date(sync.next_sync).toLocaleString('fr-FR') : "-");
    } catch (e) {
        console.error("Erreur refreshSyncIndicators:", e);
    }
}

function buildWebhookUrl(token) {
    const protocol = window.location.protocol || 'http:';
    let host = window.location.hostname || 'localhost';
    const port = window.location.port ? `:${window.location.port}` : '';

    if (host === 'localhost' || host === '127.0.0.1') {
        host = '172.17.0.1';
    }

    const base = `${protocol}//${host}${port}/api/webhook/grab`;
    if (token) {
        return `${base}?token=${encodeURIComponent(token)}`;
    }
    return base;
}

// ==================== TRACKERS ====================

async function loadTrackers() {
    try {
        const res = await fetch(API_BASE + '/trackers');
        if (!res.ok) throw new Error('Trackers API error: ' + res.status);

        const data = await res.json();
        allTrackers = data.trackers;

        [byId('tracker-filter-rss')].forEach(select => {
            if (!select) return;
            select.innerHTML = '<option value="all">Tous les trackers</option>';
            allTrackers.forEach(tracker => {
                const option = document.createElement('option');
                option.value = tracker;
                option.textContent = tracker;
                select.appendChild(option);
            });
        });
    } catch (e) {
        console.error("❌ Erreur loadTrackers:", e);
    }
}

async function purgeAllGrabs() {
    if (confirm("⚠️  Êtes-vous CERTAIN ? Cela supprimera TOUS les grabs !")) {
        try {
            const res = await fetch(API_BASE + '/purge/all', { method: "POST" });
            const data = await res.json();
            alert("✅ " + data.message);
            refreshData();
            loadGrabHistory();
        } catch (e) {
            alert("❌ Erreur: " + e);
        }
    }
}

// ==================== STATISTICS & CHARTS ====================

async function loadStats() {
    try {
        const res = await fetch(API_BASE + '/stats');
        if (!res.ok) throw new Error('Stats API error: ' + res.status);
        statsData = await res.json();

        const trackerStats = Array.isArray(statsData.tracker_stats) ? statsData.tracker_stats : [];
        const filtered = trackerStats
            .filter(item => item && item.tracker && Number(item.count || 0) > 0)
            .sort((a, b) => Number(b.count || 0) - Number(a.count || 0))
            .slice(0, 10);

        overviewTrackerChartPayload = {
            labels: filtered.map(t => t.tracker),
            data: filtered.map(t => Number(t.count || 0))
        };
        const grabsByDay = (Array.isArray(statsData.grabs_by_day) ? statsData.grabs_by_day : [])
            .filter(item => item && item.day)
            .slice()
            .sort((a, b) => new Date(a.day) - new Date(b.day))
            .slice(-30);
        overviewGrabsTrendPayload = {
            labels: grabsByDay.map(d => d.day),
            data: grabsByDay.map(d => Number(d.count || 0))
        };
        renderOverviewTrackerChart(overviewTrackerChartPayload);
        renderOverviewGrabsTrendChart(overviewGrabsTrendPayload);

        if (!overviewChartResizeBound) {
            const onResize = debounce(() => {
                if (!overviewTrackerChartPayload) return;
                renderOverviewTrackerChart(overviewTrackerChartPayload, true);
                renderOverviewGrabsTrendChart(overviewGrabsTrendPayload, true);
            }, 180);
            window.addEventListener('resize', onResize);
            overviewChartResizeBound = true;
        }

    } catch (e) {
        console.error("Erreur loadStats:", e);
        showNotificationDetail('Erreur lors du chargement du chart.', 'warning');
    }
}

// ==================== DASHBOARD ====================

async function refreshData() {
    setOverviewKpiCardsState('loading');
    try {
        const [stats, sync, detailedStats, torrentsData] = await Promise.all([
            fetchJsonSafe(API_BASE + '/stats', { total_grabs: 0, storage_size_mb: 0, tracker_stats: [], grabs_by_day: [] }),
            fetchJsonSafe(API_BASE + '/sync/status', { is_running: false, next_sync: null, last_sync: null }),
            fetchJsonSafe(API_BASE + '/stats/detailed', { system: { uptime_seconds: 0 } }),
            fetchJsonSafe(API_BASE + '/torrents', { total: 0, torrents: [] })
        ]);

        // Statistiques principales
        const totalGrabs = Number(stats?.total_grabs || 0);
        setText("total-grabs", totalGrabs);
        const storageSizeMb = Number(stats.storage_size_mb || 0);
        setText("dashboard-storage-size", storageSizeMb.toFixed(2) + ' MB');
        setText("latest-grab", stats.latest_grab ? new Date(stats.latest_grab).toLocaleString('fr-FR') : "-");

        // Nouvelles statistiques dashboard
        setText("dashboard-torrent-count", Number(torrentsData?.total || 0));

        // Nombre de trackers différents
        const trackerStats = Array.isArray(stats?.tracker_stats) ? stats.tracker_stats : [];
        const uniqueTrackers = new Set(trackerStats.map(t => t?.tracker).filter(Boolean)).size;
        setText("dashboard-trackers-count", uniqueTrackers);

        // Grabs aujourd'hui (dernières 24h)
        const grabsByDay = Array.isArray(stats?.grabs_by_day) ? stats.grabs_by_day : [];
        const grabsToday = Number(grabsByDay[0]?.count || 0);
        setText("dashboard-grabs-today", grabsToday);

        // Uptime
        const uptime = Number(detailedStats?.system?.uptime_seconds || 0);
        const hours = Math.floor(uptime / 3600);
        const minutes = Math.floor((uptime % 3600) / 60);
        setText("dashboard-uptime", hours + 'h ' + minutes + 'm');

        applySyncStatus(sync);
        setText("next-sync", sync.next_sync ? new Date(sync.next_sync).toLocaleString('fr-FR') : "-");
        setOverviewKpiCardsState('idle');
        updateOverviewKpiEmptyState();
    } catch (e) {
        console.error("❌ Erreur refreshData:", e);
        setOverviewKpiCardsState('error');
        updateOverviewKpiEmptyState();
    }
}

// ==================== LOGS ====================

async function loadLogs(targetId = 'logs-table') {
    try {
        const logs = await fetch(API_BASE + '/sync/logs?limit=50').then(r => r.json());
        const tbody = byId(targetId);
        if (!tbody) return;
        tbody.innerHTML = logs.length ? logs.map(l =>
            '<tr>' +
            '<td class="date">' + new Date(l.sync_at).toLocaleString('fr-FR') + '</td>' +
            '<td><span class="status ' + (l.status === 'success' ? 'online' : 'offline') + '">' + l.status + '</span></td>' +
            '<td>' + l.grabs_count + '</td>' +
            '<td>' + (l.deduplicated_count || 0) + '</td>' +
            '<td style="color: #ff4444; font-size: 12px;">' + (l.error ? l.error.substring(0, 50) : '-') + '</td>' +
            '</tr>'
        ).join("") : '<tr><td colspan="5" style="text-align: center; color: #888;">Aucun log</td></tr>';
    } catch (e) {
        console.error("Erreur loadLogs:", e);
    }
}

async function loadGrabHistory() {
    try {
        const instanceFilter = byId('grab-history-instance-filter');
        const trackerFilter = byId('grab-history-tracker-filter');
        const sourceFilter = byId('grab-history-source-filter');
        const idSearch = byId('grab-history-id-search');
        const sortSelect = byId('grab-history-sort');
        const instance = instanceFilter ? instanceFilter.value : '';
        const tracker = trackerFilter ? trackerFilter.value : '';
        const source = sourceFilter ? sourceFilter.value : '';
        const downloadId = idSearch ? idSearch.value.trim() : '';
        const sortValue = sortSelect ? sortSelect.value : 'date_desc';
        const params = new URLSearchParams();
        params.set('limit', '200');
        params.set('dedup', 'true');
        if (instance) params.set('instance', instance);
        if (tracker) params.set('tracker', tracker);
        if (source) params.set('source', source);
        if (downloadId) params.set('download_id', downloadId);
        const url = `${API_BASE}/history/reconcile?${params.toString()}`;
        const res = await fetch(url);
        let rows = await res.json();
        updateGrabHistorySummary(rows);
        const tbody = byId("grab-history-table");
        if (!tbody) return;
        historyReconcileCache = rows;
        if (instanceFilter && rows.length) {
            const instances = Array.from(new Set(rows.map(r => r.instance).filter(Boolean)));
            const existing = Array.from(instanceFilter.options).map(o => o.value);
            instances.forEach(name => {
                if (!existing.includes(name)) {
                    const opt = document.createElement('option');
                    opt.value = name;
                    opt.textContent = name;
                    instanceFilter.appendChild(opt);
                }
            });
        }
        if (trackerFilter && rows.length) {
            const trackers = Array.from(new Set(rows.map(r => r.indexer).filter(Boolean)));
            const existing = Array.from(trackerFilter.options).map(o => o.value);
            trackers.forEach(name => {
                if (!existing.includes(name)) {
                    const opt = document.createElement('option');
                    opt.value = name;
                    opt.textContent = name;
                    trackerFilter.appendChild(opt);
                }
            });
        }
        rows = rows.slice().sort((a, b) => {
            if (sortValue === 'instance') {
                return (a.instance || '').localeCompare(b.instance || '');
            }
            if (sortValue === 'tracker') {
                return (a.indexer || '').localeCompare(b.indexer || '');
            }
            const aDate = a.grabbed_at ? new Date(a.grabbed_at).getTime() : 0;
            const bDate = b.grabbed_at ? new Date(b.grabbed_at).getTime() : 0;
            return sortValue === 'date_asc' ? aDate - bDate : bDate - aDate;
        });
        const isYggapi = (value) => (value || '').toLowerCase().includes('yggapi');
        tbody.innerHTML = rows.length ? rows.map(row => {
            const yggBlocked = isYggapi(row.indexer);
            let fileButton = '';
            if (row.torrent_file) {
                fileButton = `<a class="btn btn-success btn-xs" href="/api/torrents/download/${encodeURIComponent(row.torrent_file)}" target="_blank" rel="noopener noreferrer">Télécharger</a>`;
            } else if (yggBlocked) {
                fileButton = '<button class="btn btn-warning btn-xs" type="button" disabled>Absent</button>';
            } else {
                fileButton = `<button class="btn btn-primary btn-xs" type="button" data-action="history-recover" data-download-id="${row.download_id || ''}" data-instance="${row.instance || ''}">Récupérer</button>`;
            }
            return (
            '<tr>' +
            '<td class="date">' + (row.grabbed_at ? new Date(row.grabbed_at).toLocaleString('fr-FR') : '-') + '</td>' +
            '<td>' + (row.instance || '-') + '</td>' +
            '<td>' + (row.indexer || '-') + '</td>' +
            `<td><button class="link-button" type="button" data-action="grab-history-detail" data-download-id="${row.download_id || ''}" data-instance="${row.instance || ''}">${row.source_title || '-'}</button></td>` +
            '<td>' + (row.source || '-') + '</td>' +
            '<td>' + fileButton + '</td>' +
            '</tr>'
            );
        }).join("") : '<tr><td colspan="6" style="text-align: center; color: #888;">Aucun élément</td></tr>';
        document.querySelectorAll('[data-action="history-recover"]').forEach(btn => {
            if (btn.dataset.boundAction === 'true') return;
            btn.addEventListener('click', async () => {
                const downloadId = btn.dataset.downloadId || '';
                const instance = btn.dataset.instance || '';
                if (!downloadId) {
                    showNotification('Download ID manquant', 'warning');
                    return;
                }

                if (btn.dataset.confirming !== 'true') {
                    btn.dataset.confirming = 'true';
                    btn.textContent = 'Confirmer';
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-warning');
                    if (btn._confirmTimer) clearTimeout(btn._confirmTimer);
                    btn._confirmTimer = setTimeout(() => {
                        btn.dataset.confirming = 'false';
                        btn.textContent = 'Récupérer';
                        btn.classList.remove('btn-warning');
                        btn.classList.add('btn-primary');
                    }, 3500);
                    return;
                }

                if (btn._confirmTimer) clearTimeout(btn._confirmTimer);
                btn.disabled = true;
                btn.textContent = 'Récupération...';
                try {
                    const res = await fetch(API_BASE + '/history/reconcile/recover', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ download_id: downloadId, instance })
                    });
                    const data = await res.json();
                    if (!res.ok) {
                        throw new Error(data.detail || data.reason || 'Erreur récupération');
                    }
                    if (data.status === 'ok') {
                        const mode = data.fallback_used ? 'fallback utilisé' : 'recherche directe';
                        showNotification(`Récupération OK (${mode})`, 'success');
                        const score = data.score !== undefined && data.score !== null ? data.score : 'n/a';
                        const indexer = data.indexer || 'n/a';
                        const hash = data.hash_check ? (data.hash_check.match ? 'OK' : 'KO') : 'n/a';
                        showNotificationDetail(`Détail: score=${score} indexer=${indexer} hash=${hash}`, 'info');
                    } else if (data.status === 'exists') {
                        showNotification('Déjà présent (rien à faire)', 'info');
                    } else {
                        const mode = data.fallback_used ? 'fallback utilisé' : 'recherche directe';
                        showNotification(`Récupération échouée (${mode})`, 'error');
                        const score = data.score !== undefined && data.score !== null ? data.score : 'n/a';
                        const indexer = data.indexer || 'n/a';
                        const hash = data.hash_check ? (data.hash_check.match ? 'OK' : 'KO') : 'n/a';
                        showNotificationDetail(`Détail: score=${score} indexer=${indexer} hash=${hash}`, 'warning');
                    }
                    await loadGrabHistory();
                } catch (e) {
                    console.error("Erreur recover history:", e);
                    showNotification(`Erreur récupération: ${e.message || e}`, 'error');
                } finally {
                    btn.disabled = false;
                    btn.dataset.confirming = 'false';
                    btn.textContent = 'Récupérer';
                    btn.classList.remove('btn-warning');
                    btn.classList.add('btn-primary');
                }
            });
            btn.dataset.boundAction = 'true';
        });
        document.querySelectorAll('[data-action="grab-history-detail"]').forEach(btn => {
            if (btn.dataset.boundAction === 'true') return;
            btn.addEventListener('click', () => {
                const downloadId = btn.dataset.downloadId || '';
                const instance = btn.dataset.instance || '';
                const row = historyReconcileCache.find(r => r.download_id === downloadId && (instance ? r.instance === instance : true));
                openGrabHistoryDetailModal(row);
            });
            btn.dataset.boundAction = 'true';
        });
    } catch (e) {
        console.error("Erreur loadGrabHistory:", e);
        updateGrabHistorySummary([]);
    }
}

function resetHistorySyncButton(button) {
    if (!button) return;
    button.textContent = 'Rafraîchir';
    button.classList.remove('btn-warning');
    button.classList.add('btn-secondary');
    button.dataset.confirming = 'false';
}

function resetInlineButton(button, label) {
    if (!button) return;
    button.textContent = label;
    button.classList.remove('btn-warning');
    button.classList.add('btn-secondary');
    button.dataset.confirming = 'false';
}

async function purgeAllLogs(event, button) {
    const targetButton = button || event?.currentTarget || document.querySelector('[data-action="purge-logs"]');
    if (!targetButton) return;

    if (targetButton.dataset.confirming !== 'true') {
        targetButton.dataset.confirming = 'true';
        targetButton.textContent = 'Confirmer';
        targetButton.classList.remove('btn-secondary');
        targetButton.classList.add('btn-warning');
        if (purgeLogsConfirmTimer) clearTimeout(purgeLogsConfirmTimer);
        purgeLogsConfirmTimer = setTimeout(() => resetInlineButton(targetButton, 'Vider tous les logs'), 3500);
        return;
    }

    if (purgeLogsConfirmTimer) clearTimeout(purgeLogsConfirmTimer);
    targetButton.disabled = true;
    targetButton.textContent = 'Suppression...';
    try {
        const res = await fetch(API_BASE + '/logs/purge-all', { method: 'POST' });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data?.detail || 'Erreur purge logs');
        }
        showNotification(data.message || 'Logs supprimés', 'success');
        await loadLogs();
    } catch (e) {
        showNotification(`Erreur: ${e.message || e}`, 'error');
    } finally {
        targetButton.disabled = false;
        resetInlineButton(targetButton, 'Vider tous les logs');
    }
}

async function purgeDatabase(event, button) {
    const targetButton = button || event?.currentTarget || document.querySelector('[data-action="purge-db"]');
    if (!targetButton) return;

    if (targetButton.dataset.confirming !== 'true') {
        targetButton.dataset.confirming = 'true';
        targetButton.textContent = 'Confirmer';
        targetButton.classList.remove('btn-secondary');
        targetButton.classList.add('btn-warning');
        if (purgeDbConfirmTimer) clearTimeout(purgeDbConfirmTimer);
        purgeDbConfirmTimer = setTimeout(() => resetInlineButton(targetButton, 'Nettoyer la base'), 3500);
        return;
    }

    if (purgeDbConfirmTimer) clearTimeout(purgeDbConfirmTimer);
    targetButton.disabled = true;
    targetButton.textContent = 'Nettoyage...';
    try {
        const res = await fetch(API_BASE + '/db/purge-all', { method: 'POST' });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data?.detail || 'Erreur nettoyage base');
        }
        showNotification(data.message || 'Base nettoyée', 'success');
        await loadLogs();
        refreshData();
        loadGrabHistory();
    } catch (e) {
        showNotification(`Erreur: ${e.message || e}`, 'error');
    } finally {
        targetButton.disabled = false;
        resetInlineButton(targetButton, 'Nettoyer la base');
    }
}

async function syncGrabHistory(event, button) {
    return syncNow(event, button);
}

async function fetchSecurityAuthState() {
    const res = await fetch('/api/auth/security-status');
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        throw new Error(data?.detail || `HTTP ${res.status}`);
    }
    securityAuthState = {
        auth_enabled: !!data.auth_enabled,
        username: data.username || '',
        password_configured: !!data.password_configured,
        cookie_secure: !!data.cookie_secure
    };
    return securityAuthState;
}

function renderSecurityAuthState() {
    const usernameEl = byId('security-auth-username-value');
    if (usernameEl) {
        usernameEl.textContent = securityAuthState.username || 'Non défini';
    }
    const passwordEl = byId('security-auth-password-value');
    if (passwordEl) {
        passwordEl.textContent = securityAuthState.password_configured ? 'Configuré' : 'Non configuré';
    }
    const statusEl = byId('auth-enabled-state');
    if (statusEl) {
        statusEl.textContent = securityAuthState.auth_enabled ? 'Activée' : 'Désactivée';
    }
    const toggleBtn = document.querySelector('[data-action="security-toggle-auth"]');
    if (toggleBtn) {
        toggleBtn.textContent = securityAuthState.auth_enabled ? 'Désactiver l’authentification' : 'Activer l’authentification';
        toggleBtn.classList.remove('btn-primary', 'btn-secondary', 'btn-warning');
        toggleBtn.classList.add(securityAuthState.auth_enabled ? 'btn-secondary' : 'btn-primary');
    }
}

function showSecurityAuthEditor() {
    const editor = byId('security-auth-editor');
    if (!editor) return;
    const usernameInput = byId('security-auth-username-input');
    const passwordInput = byId('security-auth-password-input');
    const confirmInput = byId('security-auth-password-confirm-input');
    if (usernameInput) usernameInput.value = securityAuthState.username || '';
    if (passwordInput) passwordInput.value = '';
    if (confirmInput) confirmInput.value = '';
    editor.hidden = false;
}

function hideSecurityAuthEditor() {
    const editor = byId('security-auth-editor');
    if (editor) editor.hidden = true;
}

function formatAuthErrorMessage(error) {
    const raw = String(error?.message || error || '').trim();
    return raw.replace(/^Erreur auth:\s*/i, '').trim() || 'Erreur authentification';
}

async function saveSecurityAuthCredentials(event, button) {
    const targetButton = button || event?.currentTarget;
    const usernameInput = byId('security-auth-username-input');
    const passwordInput = byId('security-auth-password-input');
    const confirmInput = byId('security-auth-password-confirm-input');
    if (!usernameInput || !passwordInput || !confirmInput) return;

    const username = (usernameInput.value || '').trim();
    const password = (passwordInput.value || '').trim();
    const passwordConfirm = (confirmInput.value || '').trim();

    if (!username) {
        showNotification('Nom utilisateur requis', 'warning');
        return;
    }
    if (!password) {
        showNotification('Mot de passe requis', 'warning');
        return;
    }
    if (password.length < 8) {
        showNotification('Mot de passe: minimum 8 caractères', 'warning');
        return;
    }
    if (password !== passwordConfirm) {
        showNotification('Confirmation mot de passe invalide', 'warning');
        return;
    }

    if (targetButton) {
        targetButton.disabled = true;
        targetButton.textContent = 'Enregistrement...';
    }
    try {
        const res = await fetch('/api/auth/configure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(data?.detail || `HTTP ${res.status}`);
        }
        securityAuthState.username = data.username || username;
        securityAuthState.password_configured = !!data.password_configured;
        renderSecurityAuthState();
        hideSecurityAuthEditor();
        showNotification('Identifiants enregistrés', 'success');
    } catch (e) {
        showNotification(`Erreur auth: ${formatAuthErrorMessage(e)}`, 'error');
    } finally {
        if (targetButton) {
            targetButton.disabled = false;
            targetButton.textContent = 'Enregistrer';
        }
    }
}

async function toggleSecurityAuthEnabled(event, button) {
    const targetButton = button || event?.currentTarget || document.querySelector('[data-action="security-toggle-auth"]');
    if (!targetButton) return;

    const nextEnabled = !securityAuthState.auth_enabled;
    if (nextEnabled && (!securityAuthState.username || !securityAuthState.password_configured)) {
        showNotification('Configurer utilisateur + mot de passe avant activation', 'warning');
        showSecurityAuthEditor();
        return;
    }

    if (targetButton.dataset.confirming !== 'true') {
        targetButton.dataset.confirming = 'true';
        targetButton.textContent = 'Confirmer';
        targetButton.classList.remove('btn-primary', 'btn-secondary');
        targetButton.classList.add('btn-warning');
        if (toggleAuthConfirmTimer) clearTimeout(toggleAuthConfirmTimer);
        toggleAuthConfirmTimer = setTimeout(() => {
            targetButton.dataset.confirming = 'false';
            renderSecurityAuthState();
        }, 3500);
        return;
    }

    if (toggleAuthConfirmTimer) clearTimeout(toggleAuthConfirmTimer);
    targetButton.disabled = true;
    targetButton.textContent = 'Application...';
    try {
        const res = await fetch('/api/auth/configure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: nextEnabled })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(data?.detail || `HTTP ${res.status}`);
        }
        securityAuthState.auth_enabled = !!data.auth_enabled;
        if (window.INITIAL_STATE) {
            window.INITIAL_STATE.auth_enabled = securityAuthState.auth_enabled;
        }
        renderSecurityAuthState();
        showNotification('Authentification mise à jour', 'success');
    } catch (e) {
        showNotification(`Erreur auth: ${formatAuthErrorMessage(e)}`, 'error');
        renderSecurityAuthState();
    } finally {
        targetButton.disabled = false;
        targetButton.dataset.confirming = 'false';
    }
}

// ==================== CONFIGURATION ====================

async function loadConfig(event, button) {
    const targetButton = button || event?.currentTarget || null;
    if (targetButton) {
        if (targetButton.dataset.confirming !== 'true') {
            targetButton.dataset.confirming = 'true';
            targetButton.textContent = 'Confirmer';
            targetButton.classList.remove('btn-secondary');
            targetButton.classList.add('btn-warning');
            if (loadConfigConfirmTimer) clearTimeout(loadConfigConfirmTimer);
            loadConfigConfirmTimer = setTimeout(() => resetInlineButton(targetButton, 'Recharger'), 3500);
            return;
        }
        if (loadConfigConfirmTimer) clearTimeout(loadConfigConfirmTimer);
        targetButton.disabled = true;
        targetButton.textContent = 'Rechargement...';
    }

    try {
        const response = await fetch(API_BASE + '/config');
        configData = await response.json();

        // Grouper les configurations par catégorie
        const categories = {
            essential: { title: 'Essentiel', fields: {} },
            cycle: { title: 'Cycle & Rétention', fields: {} },
            history: { title: 'Historique consolidé', fields: {} },
            webhook: { title: 'Webhook', fields: {} },
            rss: { title: 'RSS', fields: {} },
            security: { title: 'Sécurité', fields: {} },
            maintenance: { title: 'Maintenance', fields: {} },
            advanced: { title: 'Avancé', fields: {} }
        };

        // Classer les champs par catégorie
        Object.entries(configData).forEach(([key, data]) => {
            const upperKey = key.toUpperCase();
            if (key === 'history_apps'
                || upperKey.startsWith('PROWLARR_') || key.startsWith('prowlarr_')
                || upperKey.startsWith('RADARR_') || key.startsWith('radarr_')
                || upperKey.startsWith('SONARR_') || key.startsWith('sonarr_')) {
                categories.essential.fields[key] = data;
            } else if (upperKey.startsWith('RSS_') || key.startsWith('rss_')) {
                categories.rss.fields[key] = data;
            } else if (upperKey.startsWith('WEBHOOK_') || key.startsWith('webhook_')) {
                categories.webhook.fields[key] = data;
            } else if (upperKey.startsWith('AUTH_') || key.startsWith('auth_')) {
                categories.security.fields[key] = data;
            } else if (upperKey === 'HISTORY_DOWNLOAD_FROM_HISTORY'
                       || upperKey === 'HISTORY_MIN_SCORE'
                       || upperKey === 'HISTORY_STRICT_HASH'
                       || key === 'history_download_from_history'
                       || key === 'history_min_score'
                       || key === 'history_strict_hash') {
                categories.history.fields[key] = data;
            } else if (upperKey === 'HISTORY_SYNC_INTERVAL_SECONDS'
                       || upperKey === 'HISTORY_LOOKBACK_DAYS'
                       || upperKey === 'HISTORY_INGESTION_MODE'
                       || upperKey === 'RETENTION_HOURS'
                       || upperKey === 'AUTO_PURGE'
                       || key === 'history_sync_interval_seconds'
                       || key === 'history_lookback_days'
                       || key === 'history_ingestion_mode'
                       || key === 'sync_retention_hours'
                       || key === 'sync_auto_purge') {
                categories.cycle.fields[key] = data;
            } else if (upperKey.includes('NETWORK')
                       || upperKey.startsWith('TORRENTS_')
                       || upperKey.startsWith('CORS_')
                       || upperKey === 'LOG_LEVEL'
                       || upperKey.startsWith('APP_')) {
                categories.advanced.fields[key] = data;
            } else if (upperKey.includes('RETENTION') || upperKey.includes('PURGE')
                       || key.startsWith('retention_') || key.startsWith('auto_purge')) {
                categories.maintenance.fields[key] = data;
            } else {
                categories.advanced.fields[key] = data;
            }
        });

        // Générer le HTML avec onglets + panneaux de champs
        const form = byId("config-form");
        if (!form) return;
        let tabsHtml = '';
        let panelsHtml = '';

        const subtitleOverrides = {
            essential: 'Instances et accès API principaux',
            cycle: 'Fréquence, mode d’ingestion et rétention',
            history: 'Comportement de réconciliation history',
            webhook: 'Réception temps réel des grabs',
            rss: 'Génération des flux et domaines',
            security: 'Authentification et gestion des clés',
            maintenance: 'Purge et diagnostics',
            advanced: 'Paramètres globaux complémentaires'
        };
        const fieldLabelOverrides = {
            prowlarr_url: 'URL Prowlarr',
            prowlarr_api_key: 'Clé API Prowlarr',
            radarr_url: 'URL Radarr',
            radarr_api_key: 'Clé API Radarr',
            radarr_enabled: 'Activer Radarr',
            sonarr_url: 'URL Sonarr',
            sonarr_api_key: 'Clé API Sonarr',
            sonarr_enabled: 'Activer Sonarr',
            history_apps: 'Instances surveillées',
            history_sync_interval_seconds: 'Intervalle sync historique (secondes)',
            history_lookback_days: 'Fenêtre de rattrapage (jours)',
            history_ingestion_mode: "Mode d'ingestion",
            sync_retention_hours: 'Rétention locale (heures)',
            sync_auto_purge: 'Purge automatique',
            history_download_from_history: 'Télécharger depuis historique',
            history_min_score: 'Score minimum (historique)',
            history_strict_hash: 'Validation stricte du hash',
            webhook_enabled: 'Webhook activé',
            webhook_token: 'Token webhook',
            webhook_min_score: 'Score minimum (webhook)',
            webhook_strict: 'Mode strict webhook',
            webhook_download: 'Télécharger via webhook',
            rss_domain: 'Domaine RSS',
            rss_scheme: 'Protocole RSS',
            rss_title: 'Titre RSS',
            rss_description: 'Description RSS',
            rss_allowed_hosts: 'Hôtes autorisés RSS',
            auth_enabled: 'Authentification activée',
            auth_cookie_secure: 'Cookie sécurisé (HTTPS)',
            network_retries: 'Tentatives réseau',
            network_backoff_seconds: 'Backoff réseau (secondes)',
            network_timeout_seconds: 'Timeout réseau (secondes)',
            torrents_expose_static: 'Exposer /torrents en statique',
            torrents_max_size_mb: 'Taille max .torrent (MB)',
            log_level: 'Niveau de logs'
        };
        const historyIngestionModeOptions = [
            {
                value: 'webhook_plus_history',
                label: 'Webhook + History (recommandé)',
                detail: 'Temps réel via webhook, avec rattrapage history pour limiter les manques.'
            },
            {
                value: 'webhook_only',
                label: 'Webhook uniquement',
                detail: 'Ingestion immédiate, sans rattrapage périodique history.'
            },
            {
                value: 'history_only',
                label: 'History uniquement',
                detail: 'Ignore les webhooks Grab et s’appuie uniquement sur les cycles history.'
            }
        ];
        const historyMinScoreOptions = [
            {
                value: '1',
                label: '1 - Très permissif',
                detail: 'Accepte presque tous les matchs, y compris les correspondances faibles.'
            },
            {
                value: '2',
                label: '2 - Permissif',
                detail: 'Tolère des correspondances partielles, utile si vos noms de release sont variables.'
            },
            {
                value: '3',
                label: '3 - Équilibré (recommandé)',
                detail: 'Bon compromis précision/rappel pour la majorité des bibliothèques.'
            },
            {
                value: '4',
                label: '4 - Précis',
                detail: 'Réduit les faux positifs, mais peut ignorer quelques grabs valides.'
            },
            {
                value: '5',
                label: '5 - Strict',
                detail: 'Privilégie la fiabilité maximale des correspondances.'
            }
        ];
        const subgroupDefinitions = {
            essential: [
                {
                    id: 'prowlarr',
                    title: 'Prowlarr',
                    subtitle: 'Indexation et source des grabs',
                    match: (fieldKey) => fieldKey.startsWith('prowlarr_')
                },
                {
                    id: 'radarr',
                    title: 'Radarr',
                    subtitle: 'Films et imports associés',
                    match: (fieldKey) => fieldKey.startsWith('radarr_')
                },
                {
                    id: 'sonarr',
                    title: 'Sonarr',
                    subtitle: 'Séries et imports associés',
                    match: (fieldKey) => fieldKey.startsWith('sonarr_')
                },
                {
                    id: 'history_apps',
                    title: 'Instances surveillées',
                    subtitle: 'Instances additionnelles (ex: radarr4k)',
                    match: (fieldKey) => fieldKey === 'history_apps'
                }
            ],
            cycle: [
                {
                    id: 'history_cycle',
                    title: 'Cycle de consolidation',
                    subtitle: "Planification et fenêtre de rattrapage",
                    match: (fieldKey) => fieldKey.startsWith('history_')
                },
                {
                    id: 'retention',
                    title: 'Rétention locale',
                    subtitle: 'Purge automatique et conservation',
                    match: (fieldKey) => fieldKey.startsWith('sync_')
                }
            ],
            history: [
                {
                    id: 'history_matching',
                    title: 'Règles de matching',
                    subtitle: "Téléchargement et validation des grabs consolidés",
                    match: (fieldKey) => fieldKey.startsWith('history_')
                }
            ],
            webhook: [
                {
                    id: 'webhook_ingestion',
                    title: 'Réception webhook',
                    subtitle: 'Traitement temps réel des événements Grab',
                    match: (fieldKey) => fieldKey.startsWith('webhook_')
                }
            ],
            rss: [
                {
                    id: 'rss_publication',
                    title: 'Publication RSS',
                    subtitle: 'Domaine, schéma et métadonnées de flux',
                    match: (fieldKey) => fieldKey.startsWith('rss_')
                }
            ],
            security: [
                {
                    id: 'security_auth',
                    title: 'Authentification',
                    subtitle: 'Session, cookies et accès API',
                    match: (fieldKey) => fieldKey.startsWith('auth_')
                }
            ],
            maintenance: [
                {
                    id: 'maintenance_policy',
                    title: 'Maintenance automatique',
                    subtitle: 'Nettoyage cyclique des données locales',
                    match: (fieldKey) => fieldKey.startsWith('sync_') || fieldKey.includes('retention') || fieldKey.includes('purge')
                }
            ],
            advanced: [
                {
                    id: 'advanced_network',
                    title: 'Réseau',
                    subtitle: 'Timeouts, retries et backoff',
                    match: (fieldKey) => fieldKey.startsWith('network_')
                },
                {
                    id: 'advanced_torrents',
                    title: 'Fichiers torrents',
                    subtitle: 'Exposition et limites de taille',
                    match: (fieldKey) => fieldKey.startsWith('torrents_')
                },
                {
                    id: 'advanced_cross_origin',
                    title: 'Accès applicatif',
                    subtitle: 'CORS et paramètres applicatifs globaux',
                    match: (fieldKey) => fieldKey.startsWith('cors_') || fieldKey.startsWith('app_') || fieldKey === 'log_level'
                }
            ]
        };
        const buildSubgroups = (categoryKey, fieldsObj) => {
            const defs = subgroupDefinitions[categoryKey] || [];
            const fieldEntries = Object.entries(fieldsObj || {});
            const assignedKeys = new Set();
            const groups = [];

            defs.forEach((def) => {
                const entries = fieldEntries.filter(([fieldKey]) => {
                    if (assignedKeys.has(fieldKey)) return false;
                    if (!def.match(fieldKey)) return false;
                    assignedKeys.add(fieldKey);
                    return true;
                });
                if (entries.length) {
                    groups.push({
                        id: def.id,
                        title: def.title,
                        subtitle: def.subtitle,
                        entries
                    });
                }
            });

            const remaining = fieldEntries.filter(([fieldKey]) => !assignedKeys.has(fieldKey));
            if (remaining.length) {
                groups.push({
                    id: 'other',
                    title: 'Autres paramètres',
                    subtitle: 'Réglages complémentaires',
                    entries: remaining
                });
            }
            return groups;
        };
        const order = ['essential', 'cycle', 'history', 'webhook', 'rss', 'security', 'maintenance', 'advanced'];
        const visibleCategories = order.filter(key => {
            const category = categories[key];
            if (!category) return false;
            if (key === 'maintenance' || key === 'security') return true;
            return Object.keys(category.fields).length > 0;
        });
        const urlTab = (new URLSearchParams(window.location.search).get('tab') || '').toLowerCase();
        const tabAliases = {
            logs: 'maintenance',
            prowlarr: 'essential',
            radarr: 'essential',
            sonarr: 'essential',
            other: 'advanced',
            sync: 'cycle'
        };
        const requestedTab = tabAliases[urlTab] || urlTab;
        const initialTab = visibleCategories.includes(requestedTab) ? requestedTab : (visibleCategories[0] || '');

        visibleCategories.forEach((key) => {
            const category = categories[key];
            const title = category.title;
            const subtitle = subtitleOverrides[key] || '';
            const isActive = key === initialTab;

            tabsHtml += `
                <button class="config-tab${isActive ? ' is-active' : ''}" type="button"
                        role="tab" aria-selected="${isActive ? 'true' : 'false'}"
                        data-config-tab="${key}">
                    ${title}
                </button>`;

            panelsHtml += `
                <section class="config-panel${isActive ? ' is-active' : ''}" data-config-panel="${key}">
                    <div class="config-panel__header">
                        <div class="config-panel__title">${title}</div>
                        ${subtitle ? `<div class="config-panel__subtitle">${subtitle}</div>` : ''}
                    </div>
                    <div class="config-panel__body">`;

                const subgroups = buildSubgroups(key, category.fields);
                subgroups.forEach((subgroup) => {
                    panelsHtml += `
                        <section class="config-subsection" data-config-subsection="${subgroup.id}">
                            <header class="config-subsection__header">
                                <h3 class="config-subsection__title">${subgroup.title}</h3>
                                ${subgroup.subtitle ? `<p class="config-subsection__subtitle">${subgroup.subtitle}</p>` : ''}
                            </header>
                            <div class="config-subsection__body">`;

                    subgroup.entries.forEach(([fieldKey, data]) => {
                    const displayName = fieldLabelOverrides[fieldKey] || fieldKey.replace(/_/g, ' ').toLowerCase()
                        .split(' ')
                        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                        .join(' ');

                    const isWebhookToken = fieldKey === 'webhook_token';
                    const isEssentialApiKey = key === 'essential' && /api_key$/i.test(fieldKey);
                    const isHistoryApps = fieldKey === 'history_apps';
                    const isHistoryIngestionMode = fieldKey === 'history_ingestion_mode';
                    const isHistoryMinScore = fieldKey === 'history_min_score';
                    const isHistoryStrictHash = fieldKey === 'history_strict_hash';
                    const skipField = key === 'security' && fieldKey === 'auth_enabled';
                    if (skipField) {
                        return;
                    }
                    const isBoolean = String(data.value).toLowerCase() === 'true' || String(data.value).toLowerCase() === 'false';
                    const inputType = isBoolean ? 'checkbox' : 'text';
                    const inputValue = isBoolean ? '' : (data.value || '');
                    const isEditableText = !isBoolean && !isHistoryApps && !isWebhookToken && !isEssentialApiKey && !isHistoryIngestionMode && !isHistoryMinScore;
                    const isChecked = isBoolean && String(data.value).toLowerCase() === 'true';
                    const normalizedIngestionValue = String(inputValue || '').trim().toLowerCase();
                    const selectedIngestionValue = historyIngestionModeOptions.some(option => option.value === normalizedIngestionValue)
                        ? normalizedIngestionValue
                        : 'webhook_plus_history';
                    const normalizedHistoryMinScore = String(inputValue || '').trim();
                    const selectedHistoryMinScore = historyMinScoreOptions.some(option => option.value === normalizedHistoryMinScore)
                        ? normalizedHistoryMinScore
                        : '3';
                    const fieldHelp = isHistoryIngestionMode
                        ? "Détermine la source prioritaire d'ingestion des grabs."
                        : isHistoryStrictHash
                            ? "Si activé, un grab history sans hash valide est rejeté pour éviter les faux rattachements."
                        : data.description;

                    panelsHtml += `
                        <div class="config-field">
                            <div class="config-field__meta">
                                <label class="config-field__label" for="${fieldKey}">${displayName}</label>
                                <div class="config-field__help">${fieldHelp}</div>
                            </div>
                            <div class="config-field__control">
                                ${isHistoryApps ? `
                                <div class="history-apps" data-role="history-apps">
                                    <div class="history-apps__list" data-role="history-apps-list"></div>
                                    <div class="history-apps__form">
                                        <input class="config-input" type="text" id="history_app_name" placeholder="Nom (ex: radarr4k)">
                                        <input class="config-input" type="text" id="history_app_url" placeholder="URL (ex: http://radarr4k:7878)">
                                        <input class="config-input" type="text" id="history_app_key" placeholder="API Key">
                                        <input class="config-input" type="text" id="history_app_type" placeholder="Type (radarr/sonarr)">
                                        <div class="history-apps__controls">
                                            <label class="config-switch history-apps__toggle" for="history_app_enabled">
                                                <input class="config-toggle" type="checkbox" id="history_app_enabled" checked>
                                                <span class="config-switch__slider" aria-hidden="true"></span>
                                                <span class="history-apps__toggle-label">Activé</span>
                                            </label>
                                            <button class="btn btn-primary" type="button" data-action="history-app-add">Ajouter</button>
                                        </div>
                                    </div>
                                    <input type="hidden" id="${fieldKey}" name="${fieldKey}" value="${inputValue}">
                                </div>
                                ` : isWebhookToken ? `
                                <div class="copy-field">
                                    <input class="config-input" type="password"
                                           id="${fieldKey}"
                                           name="${fieldKey}"
                                           value="${inputValue}"
                                           placeholder="${data.description}"
                                           autocomplete="new-password">
                                    <button class="btn btn-secondary" type="button" data-action="generate-webhook-token" data-target="${fieldKey}">Générer</button>
                                    <button class="btn btn-secondary" type="button" data-action="copy-config-field" data-copy-target="${fieldKey}">Copier config</button>
                                </div>
                                ` : isEssentialApiKey ? `
                                <div class="copy-field">
                                    <input class="config-input" type="password"
                                           id="${fieldKey}"
                                           name="${fieldKey}"
                                           value="${inputValue}"
                                           placeholder="${data.description}"
                                           autocomplete="new-password">
                                    <button class="btn btn-secondary" type="button" data-action="copy-config-field" data-copy-target="${fieldKey}">Copier config</button>
                                </div>
                                ` : isHistoryIngestionMode ? `
                                <div class="edit-field">
                                    <select class="config-input config-input--edit"
                                            id="${fieldKey}"
                                            name="${fieldKey}">
                                        ${historyIngestionModeOptions.map(option => `
                                            <option value="${option.value}" ${option.value === selectedIngestionValue ? 'selected' : ''}>${option.label}</option>
                                        `).join('')}
                                    </select>
                                </div>
                                <div class="config-ingestion-mode-details">
                                    ${historyIngestionModeOptions.map(option => `
                                        <div class="config-ingestion-mode-item${option.value === selectedIngestionValue ? ' is-selected' : ''}" data-mode="${option.value}">
                                            <div class="config-ingestion-mode-title">${option.label}</div>
                                            <div class="config-ingestion-mode-note">${option.detail}</div>
                                        </div>
                                    `).join('')}
                                </div>
                                ` : isHistoryMinScore ? `
                                <div class="edit-field">
                                    <select class="config-input config-input--edit"
                                            id="${fieldKey}"
                                            name="${fieldKey}">
                                        ${historyMinScoreOptions.map(option => `
                                            <option value="${option.value}" ${option.value === selectedHistoryMinScore ? 'selected' : ''}>${option.label}</option>
                                        `).join('')}
                                    </select>
                                </div>
                                <div class="config-history-score-details">
                                    ${historyMinScoreOptions.map(option => `
                                        <div class="config-history-score-item${option.value === selectedHistoryMinScore ? ' is-selected' : ''}" data-score="${option.value}">
                                            <div class="config-history-score-title">${option.label}</div>
                                            <div class="config-history-score-note">${option.detail}</div>
                                        </div>
                                    `).join('')}
                                </div>
                                ` : `
                                ${isBoolean ? `
                                <label class="config-switch" for="${fieldKey}">
                                    <input class="config-toggle" type="checkbox"
                                           id="${fieldKey}"
                                           name="${fieldKey}"
                                           ${isChecked ? 'checked' : ''}>
                                    <span class="config-switch__slider" aria-hidden="true"></span>
                                </label>
                                ` : isEditableText ? `
                                <div class="edit-field">
                                    <input class="config-input config-input--edit" type="${inputType}"
                                           id="${fieldKey}"
                                           name="${fieldKey}"
                                           value="${inputValue}"
                                           placeholder="${data.description}">
                                </div>
                                ` : `
                                <input class="config-input" type="${inputType}"
                                       id="${fieldKey}"
                                       name="${fieldKey}"
                                       ${isChecked ? 'checked' : ''}
                                       value="${inputValue}"
                                       placeholder="${data.description}">
                                `}
                                `}
                            </div>
                        </div>`;

                    if (isWebhookToken) {
                        panelsHtml += `
                        <div class="config-field">
                            <div class="config-field__meta">
                                <label class="config-field__label" for="webhook_url">Webhook URL (POST)</label>
                                <div class="config-field__help">URL à copier/coller dans Radarr/Sonarr</div>
                            </div>
                            <div class="config-field__control">
                                <div class="copy-field">
                                    <input class="config-input" type="text" id="webhook_url" name="webhook_url" readonly>
                                    <button class="btn btn-sm btn-secondary" type="button" data-action="copy-config-field" data-copy-target="webhook_url">Copier config</button>
                                </div>
                            </div>
                        </div>`;
                    }
                });
                    panelsHtml += `</div></section>`;
                });

                panelsHtml += `</div></section>`;
        });

        let html = '';
        if (visibleCategories.length === 0) {
            html = '<div class="config-grid"></div>';
        } else {
            html = `
                <div class="config-tabs" role="tablist" aria-label="Catégories de configuration">
                    ${tabsHtml}
                </div>
                <div class="config-panels">
                    ${panelsHtml}
                </div>`;
        }
        form.innerHTML = html;

        const securityPanelBody = form.querySelector('[data-config-panel="security"] .config-panel__body');
        if (securityPanelBody) {
            const initialState = window.INITIAL_STATE || {};
            securityAuthState.auth_enabled = !!initialState.auth_enabled;
            securityAuthState.username = initialState.username || '';
            securityAuthState.password_configured = false;
            securityPanelBody.insertAdjacentHTML('beforeend', `
                <section class="config-subsection" data-config-subsection="security-account">
                    <header class="config-subsection__header">
                        <h3 class="config-subsection__title">Compte et clés API</h3>
                    </header>
                    <div class="config-subsection__body">
                        <div class="config-field">
                            <div class="config-field__meta">
                                <span class="config-field__label">Utilisateur</span>
                            </div>
                            <div class="config-field__control">
                                <div class="security-inline-actions">
                                    <span class="security-inline-value" id="security-auth-username-value">-</span>
                                    <button class="btn btn-secondary btn-sm" type="button" data-action="security-edit-auth">Modifier</button>
                                </div>
                            </div>
                        </div>
                        <div class="config-field">
                            <div class="config-field__meta">
                                <span class="config-field__label">Mot de passe</span>
                            </div>
                            <div class="config-field__control">
                                <div class="security-inline-actions">
                                    <span class="security-inline-value" id="security-auth-password-value">Non configuré</span>
                                    <button class="btn btn-secondary btn-sm" type="button" data-action="security-edit-auth">Modifier</button>
                                </div>
                            </div>
                        </div>
                        <div class="config-field" id="security-auth-editor" hidden>
                            <div class="config-field__meta">
                                <span class="config-field__label">Édition identifiants</span>
                                <div class="config-field__help">Définissez utilisateur + mot de passe avant activation.</div>
                            </div>
                            <div class="config-field__control">
                                <div class="security-auth-editor-grid">
                                    <input class="config-input" type="text" id="security-auth-username-input" placeholder="Nom utilisateur">
                                    <input class="config-input" type="password" id="security-auth-password-input" placeholder="Nouveau mot de passe">
                                    <input class="config-input" type="password" id="security-auth-password-confirm-input" placeholder="Confirmer le mot de passe">
                                    <div class="security-auth-editor-actions">
                                        <button class="btn btn-primary" type="button" data-action="security-save-auth-credentials">Enregistrer</button>
                                        <button class="btn btn-secondary" type="button" data-action="security-cancel-auth-edit">Annuler</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="config-field">
                            <div class="config-field__meta">
                                <span class="config-field__label">Bascule d’authentification</span>
                                <div class="config-field__help">Action immédiate avec confirmation inline</div>
                            </div>
                            <div class="config-field__control">
                                <div class="security-inline-actions">
                                    <span class="security-inline-value" id="auth-enabled-state">-</span>
                                    <button class="btn btn-primary" type="button" data-action="security-toggle-auth">Activer l’authentification</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>
                <section class="config-subsection" data-config-subsection="security-api-keys">
                    <header class="config-subsection__header">
                        <h3 class="config-subsection__title">API Keys</h3>
                    </header>
                </section>
                <div class="api-keys-panel"><div id="config-api-keys-list"><p>Chargement...</p></div></div>
            `);
        }

        const maintenancePanelBody = form.querySelector('[data-config-panel="maintenance"] .config-panel__body');
        if (maintenancePanelBody) {
            maintenancePanelBody.insertAdjacentHTML('beforeend', `
                <div class="section-note">Actions de maintenance</div>
                <div class="actions-bar">
                    <button class="btn btn-secondary" type="button" data-action="purge-logs">Vider tous les logs</button>
                    <button class="btn btn-danger" type="button" data-action="purge-db">Nettoyer la base</button>
                </div>
                <div class="config-divider"></div>
                <div class="section-note">Logs de synchronisation</div>
                <table class="ui-table logs-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Statut</th>
                            <th>Grabs</th>
                            <th>Doublons</th>
                            <th>Erreur</th>
                        </tr>
                    </thead>
                    <tbody id="config-logs-table" aria-live="polite" aria-busy="true">
                        <tr>
                            <td colspan="5" class="ui-table__state ui-table__state--loading">Chargement...</td>
                        </tr>
                    </tbody>
                </table>
            `);
        }

        const tabButtons = form.querySelectorAll('[data-config-tab]');
        tabButtons.forEach((tabBtn) => {
            tabBtn.addEventListener('click', () => {
                const tab = tabBtn.getAttribute('data-config-tab');
                tabButtons.forEach((btn) => {
                    const active = btn.getAttribute('data-config-tab') === tab;
                    btn.classList.toggle('is-active', active);
                    btn.setAttribute('aria-selected', active ? 'true' : 'false');
                });
                form.querySelectorAll('[data-config-panel]').forEach((panel) => {
                    const active = panel.getAttribute('data-config-panel') === tab;
                    panel.classList.toggle('is-active', active);
                });
                const url = new URL(window.location.href);
                url.searchParams.set('tab', tab);
                window.history.replaceState({}, '', url.toString());
            });
        });

        const updateWebhookUrl = () => {
            const tokenInput = byId('webhook_token');
            const webhookUrlInput = byId('webhook_url');
            if (!webhookUrlInput) return;
            const tokenValue = tokenInput ? tokenInput.value.trim() : '';
            const rawUrl = buildWebhookUrl(tokenValue);
            webhookUrlInput.value = maskUrlSecret(rawUrl);
            webhookUrlInput.dataset.rawValue = rawUrl;
        };

        document.querySelectorAll('[data-action="generate-webhook-token"]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const targetId = btn.getAttribute('data-target');
                const input = targetId ? byId(targetId) : null;
                try {
                    const res = await fetch('/api/webhook/token/generate', { method: 'POST' });
                    const data = await res.json();
                    if (data && data.token && input) {
                        input.value = data.token;
                        updateWebhookUrl();
                    } else {
                        alert("❌ Impossible de générer un token webhook");
                    }
                } catch (e) {
                    alert("❌ Erreur génération token webhook: " + e);
                }
            });
        });

        updateWebhookUrl();

        document.querySelectorAll('[data-action="copy-config-field"]').forEach(btn => {
            if (btn.dataset.boundCopyConfig === 'true') return;
            btn.dataset.boundCopyConfig = 'true';
            btn.addEventListener('click', (event) => {
                const targetId = btn.getAttribute('data-copy-target');
                const input = targetId ? byId(targetId) : null;
                if (!input) return;
                const rawValue = input.dataset.rawValue || input.value || '';
                copyTextWithButtonFeedback(rawValue, event.currentTarget);
            });
        });

        const webhookTokenInput = byId('webhook_token');
        if (webhookTokenInput) {
            webhookTokenInput.addEventListener('input', updateWebhookUrl);
        }

        const historyAppsContainer = document.querySelector('[data-role="history-apps"]');
        if (historyAppsContainer) {
            const listEl = historyAppsContainer.querySelector('[data-role="history-apps-list"]');
            const hiddenInput = byId('history_apps');
            const addBtn = historyAppsContainer.querySelector('[data-action="history-app-add"]');

            const getList = () => {
                try {
                    const raw = hiddenInput ? hiddenInput.value : '[]';
                    const parsed = JSON.parse(raw);
                    return Array.isArray(parsed) ? parsed : [];
                } catch {
                    return [];
                }
            };
            const seedFromLegacy = () => {
                const items = [];
                const radarrUrl = configData?.radarr_url?.value || '';
                const radarrKey = configData?.radarr_api_key?.value || '';
                const radarrEnabled = String(configData?.radarr_enabled?.value || 'true') === 'true';
                if (radarrUrl && radarrKey) {
                    items.push({ name: 'radarr', url: radarrUrl, api_key: radarrKey, type: 'radarr', enabled: radarrEnabled });
                }
                const sonarrUrl = configData?.sonarr_url?.value || '';
                const sonarrKey = configData?.sonarr_api_key?.value || '';
                const sonarrEnabled = String(configData?.sonarr_enabled?.value || 'true') === 'true';
                if (sonarrUrl && sonarrKey) {
                    items.push({ name: 'sonarr', url: sonarrUrl, api_key: sonarrKey, type: 'sonarr', enabled: sonarrEnabled });
                }
                if (items.length && hiddenInput) {
                    hiddenInput.value = JSON.stringify(items);
                }
            };
            const setList = (items) => {
                if (hiddenInput) {
                    hiddenInput.value = JSON.stringify(items);
                }
            };
            const renderList = () => {
                if (!listEl) return;
                let items = getList();
                if (!items.length) {
                    seedFromLegacy();
                    items = getList();
                }
                listEl.innerHTML = items.length ? items.map((item, index) => `
                    <div class="history-apps__item">
                        <div class="history-apps__meta">
                            <strong>${item.name || 'app'}</strong>
                            <span>${item.type || 'radarr'} — ${item.url || ''}</span>
                        </div>
                        <div class="history-apps__actions">
                            <span class="badge ${item.enabled ? 'badge-success' : 'badge-warning'}">${item.enabled ? 'Activé' : 'Désactivé'}</span>
                            ${['radarr','sonarr'].includes((item.name || '').toLowerCase()) ? '' : `<button class="btn btn-secondary" type="button" data-action="history-app-remove" data-index="${index}">Supprimer</button>`}
                        </div>
                    </div>
                `).join('') : '<div class="history-apps__empty">Aucune instance configurée</div>';
            };

            renderList();
            if (addBtn) {
                addBtn.addEventListener('click', () => {
                    const name = (byId('history_app_name')?.value || '').trim();
                    const url = (byId('history_app_url')?.value || '').trim();
                    const apiKey = (byId('history_app_key')?.value || '').trim();
                    const type = (byId('history_app_type')?.value || '').trim() || 'radarr';
                    const enabled = !!byId('history_app_enabled')?.checked;
                    if (!name || !url || !apiKey) {
                        alert('Nom, URL et API Key sont obligatoires.');
                        return;
                    }
                    const items = getList();
                    items.push({ name, url, api_key: apiKey, type, enabled });
                    setList(items);
                    renderList();
                    byId('history_app_name').value = '';
                    byId('history_app_url').value = '';
                    byId('history_app_key').value = '';
                    byId('history_app_type').value = '';
                    byId('history_app_enabled').checked = true;
                });
            }

            historyAppsContainer.addEventListener('click', (event) => {
                const target = event.target;
                if (!(target instanceof HTMLElement)) return;
                if (target.dataset.action === 'history-app-remove') {
                    const index = Number(target.dataset.index);
                    const items = getList();
                    items.splice(index, 1);
                    setList(items);
                    renderList();
                }
            });
        }

        const ingestionModeSelect = byId('history_ingestion_mode');
        if (ingestionModeSelect) {
            const refreshIngestionModeDetails = () => {
                const selected = String(ingestionModeSelect.value || '').trim().toLowerCase();
                document.querySelectorAll('.config-ingestion-mode-item').forEach((item) => {
                    if (!(item instanceof HTMLElement)) return;
                    item.classList.toggle('is-selected', item.dataset.mode === selected);
                });
            };
            ingestionModeSelect.addEventListener('change', refreshIngestionModeDetails);
            refreshIngestionModeDetails();
        }

        const historyMinScoreSelect = byId('history_min_score');
        if (historyMinScoreSelect) {
            const refreshHistoryScoreDetails = () => {
                const selected = String(historyMinScoreSelect.value || '').trim();
                document.querySelectorAll('.config-history-score-item').forEach((item) => {
                    if (!(item instanceof HTMLElement)) return;
                    item.classList.toggle('is-selected', item.dataset.score === selected);
                });
            };
            historyMinScoreSelect.addEventListener('change', refreshHistoryScoreDetails);
            refreshHistoryScoreDetails();
        }

        bindActionHandlers();
        if (securityPanelBody) {
            try {
                await fetchSecurityAuthState();
            } catch (e) {
                showNotification(`Erreur auth: ${e.message || e}`, 'error');
            }
            renderSecurityAuthState();
        }
        await loadApiKeys('config-api-keys-list');
        await loadLogs('config-logs-table');
    } catch (e) {
        showNotification("Erreur chargement config: " + e, 'error');
    } finally {
        if (targetButton) {
            targetButton.disabled = false;
            resetInlineButton(targetButton, 'Recharger');
        }
    }
}

async function saveConfig(event, button) {
    const targetButton = button || event?.currentTarget || null;
    if (targetButton) {
        if (targetButton.dataset.confirming !== 'true') {
            targetButton.dataset.confirming = 'true';
            targetButton.textContent = 'Confirmer';
            targetButton.classList.remove('btn-primary');
            targetButton.classList.add('btn-warning');
            if (saveConfigConfirmTimer) clearTimeout(saveConfigConfirmTimer);
            saveConfigConfirmTimer = setTimeout(() => {
                targetButton.textContent = 'Sauvegarder';
                targetButton.classList.remove('btn-warning');
                targetButton.classList.remove('btn-secondary');
                targetButton.classList.add('btn-primary');
                targetButton.dataset.confirming = 'false';
            }, 3500);
            return;
        }
        if (saveConfigConfirmTimer) clearTimeout(saveConfigConfirmTimer);
        targetButton.disabled = true;
        targetButton.textContent = 'Sauvegarde...';
    }

    try {
        const updates = {};
        Object.keys(configData).forEach(key => {
            const input = document.getElementById(key);
            if (input) {
                const value = input.type === 'checkbox' ? String(!!input.checked) : input.value;
                updates[key] = {
                    value,
                    description: configData[key]?.description || ""
                };
            }
        });

        const res = await fetch(API_BASE + '/config', {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(updates)
        });

        if (res.ok) {
            showNotification("Configuration sauvegardée", 'success');
            await loadConfig();
        } else {
            let details = "Erreur lors de la sauvegarde";
            try {
                const data = await res.json();
                details = data?.detail || data?.message || data?.error || details;
            } catch (_) {
                // noop
            }
            showNotification(details, 'error');
        }
    } catch (e) {
        showNotification("Erreur: " + e, 'error');
    } finally {
        if (targetButton) {
            targetButton.disabled = false;
            targetButton.textContent = 'Sauvegarder';
            targetButton.classList.remove('btn-warning');
            targetButton.classList.remove('btn-secondary');
            targetButton.classList.add('btn-primary');
            targetButton.dataset.confirming = 'false';
        }
    }
}

// ==================== SYNC ====================

async function syncNow(event, button) {
    const targetButton = button || event?.currentTarget || document.querySelector('[data-action="sync-now"]');
    if (!targetButton) return;

    try {
        const statusRes = await fetch(API_BASE + '/sync/status');
        if (statusRes.ok) {
            const sync = await statusRes.json();
            if (sync?.is_running) {
                applySyncStatus(sync);
                showNotification('Synchronisation deja en cours', 'info');
                return;
            }
        }
    } catch (_) {
        // ignore status pre-check failures
    }

    if (targetButton.dataset.confirming !== 'true') {
        targetButton.dataset.confirming = 'true';
        targetButton.textContent = 'Confirmer';
        if (!targetButton.classList.contains('app-topbar__button')) {
            targetButton.classList.remove('btn-primary', 'btn-secondary');
            targetButton.classList.add('btn-warning');
        }
        if (syncNowConfirmTimer) clearTimeout(syncNowConfirmTimer);
        syncNowConfirmTimer = setTimeout(() => {
            targetButton.dataset.confirming = 'false';
            if (targetButton.classList.contains('app-topbar__button')) {
                targetButton.textContent = 'Synchroniser';
            } else {
                targetButton.classList.remove('btn-warning');
                targetButton.classList.add('btn-primary');
                targetButton.textContent = 'Synchroniser';
            }
        }, 3500);
        return;
    }

    if (syncNowConfirmTimer) clearTimeout(syncNowConfirmTimer);
    targetButton.dataset.manualSyncLoading = 'true';
    targetButton.dataset.confirming = 'false';
    targetButton.disabled = true;
    if (!targetButton.classList.contains('app-topbar__button')) {
        targetButton.classList.remove('btn-warning');
    }
    targetButton.textContent = 'Synchronisation...';

    try {
        const res = await fetch(API_BASE + '/history/reconcile/sync', { method: 'POST' });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data?.detail || data?.reason || 'Erreur sync');
        }
        showNotification(`Historique consolide rafraichi (${data?.status || 'ok'})`, 'success');

        const page = document.querySelector('.app-content')?.dataset.page || '';
        if (page === 'grabs') {
            await loadGrabHistory();
        } else if (page === 'overview') {
            await refreshData();
        }
    } catch (e) {
        showNotification(`Erreur synchronisation: ${e.message || e}`, 'error');
    } finally {
        targetButton.dataset.manualSyncLoading = 'false';
        targetButton.disabled = false;
        if (targetButton.classList.contains('app-topbar__button')) {
            targetButton.textContent = 'Synchroniser';
        } else {
            targetButton.textContent = 'Synchroniser';
            targetButton.classList.remove('btn-warning');
            targetButton.classList.add('btn-primary');
        }
        await refreshSyncIndicators();
    }
}


// ==================== TORRENTS MANAGEMENT ====================

async function loadTorrents() {
    try {
        const res = await fetch(API_BASE + '/torrents');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const torrents = Array.isArray(data.torrents) ? data.torrents : [];
        torrentsTableCache = torrents;
        const summary = data.summary || {};

        // Mettre à jour les statistiques
        setText('torrents-total', Number(data.total || torrents.length));
        const totalSize = Number(summary.total_size_mb ?? torrents.reduce((acc, t) => acc + Number(t.size_mb || 0), 0));
        setText('torrents-size', totalSize.toFixed(2));
        const withGrab = Number(summary.with_grab_count ?? torrents.filter(t => t.has_grab).length);
        setText('torrents-with-grab', withGrab);
        const orphans = Number(summary.orphan_count ?? torrents.filter(t => !t.has_grab).length);
        setText('torrents-orphans', orphans);

        const trackerFilter = byId('torrents-tracker-filter');
        if (trackerFilter) {
            const trackers = Array.from(new Set(torrents.map(t => t.tracker).filter(Boolean))).sort((a, b) => a.localeCompare(b));
            const current = trackerFilter.value;
            trackerFilter.innerHTML = '<option value="">Tous</option>' + trackers.map(tr => `<option value="${tr}">${tr}</option>`).join('');
            trackerFilter.value = trackers.includes(current) ? current : '';
        }

        renderTorrentsTable();
    } catch (e) {
        console.error("Erreur loadTorrents:", e);
        showNotification("Erreur lors du chargement des torrents: " + (e.message || e), 'error');
    }
}

function getFilteredAndSortedTorrents() {
    const trackerFilter = byId('torrents-tracker-filter');
    const statusFilter = byId('torrents-status-filter');
    const searchInput = byId('torrents-search');
    const sortSelect = byId('torrents-sort');

    const tracker = trackerFilter ? trackerFilter.value : '';
    const status = statusFilter ? statusFilter.value : '';
    const search = searchInput ? searchInput.value.trim().toLowerCase() : '';
    const sort = sortSelect ? sortSelect.value : 'date_desc';

    let rows = torrentsTableCache.slice();
    if (tracker) {
        rows = rows.filter(t => (t.tracker || '') === tracker);
    }
    if (status === 'with_grab') {
        rows = rows.filter(t => !!t.has_grab);
    } else if (status === 'orphan') {
        rows = rows.filter(t => !t.has_grab);
    }
    if (search) {
        rows = rows.filter(t => {
            const filename = String(t.filename || '').toLowerCase();
            const title = String(t.title || '').toLowerCase();
            const tr = String(t.tracker || '').toLowerCase();
            return filename.includes(search) || title.includes(search) || tr.includes(search);
        });
    }

    rows.sort((a, b) => {
        if (sort === 'name_asc') return String(a.filename || '').localeCompare(String(b.filename || ''));
        if (sort === 'size_desc') return Number(b.size_mb || 0) - Number(a.size_mb || 0);
        if (sort === 'tracker_asc') return String(a.tracker || '').localeCompare(String(b.tracker || ''));
        const aDate = a.grabbed_at ? new Date(a.grabbed_at).getTime() : 0;
        const bDate = b.grabbed_at ? new Date(b.grabbed_at).getTime() : 0;
        return sort === 'date_asc' ? aDate - bDate : bDate - aDate;
    });

    return rows;
}

function renderTorrentsTable() {
    const tbody = byId('torrents-table');
    const selectAll = byId('select-all-torrents');
    if (!tbody) return;

    if (selectAll) selectAll.checked = false;

    const torrents = getFilteredAndSortedTorrents();
    if (torrents.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="ui-table__state ui-table__state--empty">Aucun fichier torrent</td></tr>';
        updateBulkActionsVisibility();
        return;
    }

    tbody.innerHTML = torrents.map(t => {
            const statusText = t.has_grab ? '✓ Avec Grab' : '⚠ Orphelin';
            const statusClass = t.has_grab ? 'status-pill status-pill--ok' : 'status-pill status-pill--warn';
            const grabDate = t.grabbed_at ? new Date(t.grabbed_at).toLocaleString('fr-FR') : '-';

            return `
                <tr>
                    <td><input type="checkbox" class="torrent-checkbox" value="${t.filename}"></td>
                    <td class="torrent-filename">${t.filename}</td>
                    <td>${t.title}</td>
                    <td><strong class="inline-link">${t.tracker}</strong></td>
                    <td class="date">${grabDate}</td>
                    <td>${t.size_mb} MB</td>
                    <td><span class="${statusClass}">${statusText}</span></td>
                    <td class="table-actions-cell">
                        <div class="table-actions">
                            <a href="/api/torrents/download/${encodeURIComponent(t.filename)}" target="_blank" rel="noopener noreferrer" class="btn btn-success btn-xs">Télécharger</a>
                            <button class="btn btn-danger btn-xs" type="button" data-action="delete-torrent" data-filename="${t.filename}">Supprimer</button>
                        </div>
                    </td>
                </tr>
            `;
    }).join('');

    document.querySelectorAll('[data-action="delete-torrent"]').forEach(button => {
        button.addEventListener('click', () => {
            const filename = button.getAttribute('data-filename');
            if (filename) {
                deleteSingleTorrent(filename, button);
            }
        });
    });

    updateBulkActionsVisibility();
}

function toggleAllTorrents() {
    const selectAll = byId('select-all-torrents');
    if (!selectAll) return;
    const checkboxes = document.querySelectorAll('.torrent-checkbox');
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
    updateBulkActionsVisibility();
}

function updateBulkActionsVisibility() {
    const checkboxes = document.querySelectorAll('.torrent-checkbox:checked');
    const bulkActions = byId('bulk-actions');
    const bulkDeleteBtn = byId('delete-bulk-torrents-btn');
    if (!bulkActions) return;
    bulkActions.classList.toggle('is-visible', checkboxes.length > 0);
    if (bulkDeleteBtn) {
        const count = checkboxes.length;
        bulkDeleteBtn.textContent = count > 0 ? `Supprimer la selection (${count})` : 'Supprimer la selection';
    }
}

async function deleteSingleTorrent(filename, button = null) {
    const targetButton = button || null;
    if (targetButton) {
        if (targetButton.dataset.confirming !== 'true') {
            targetButton.dataset.confirming = 'true';
            targetButton.textContent = 'Confirmer';
            targetButton.classList.remove('btn-danger');
            targetButton.classList.add('btn-warning');
            if (targetButton._confirmTimer) clearTimeout(targetButton._confirmTimer);
            targetButton._confirmTimer = setTimeout(() => {
                targetButton.dataset.confirming = 'false';
                targetButton.textContent = 'Supprimer';
                targetButton.classList.remove('btn-warning');
                targetButton.classList.add('btn-danger');
            }, 3000);
            return;
        }
        if (targetButton._confirmTimer) clearTimeout(targetButton._confirmTimer);
        targetButton.dataset.confirming = 'false';
        targetButton.disabled = true;
        targetButton.textContent = 'Suppression...';
        targetButton.classList.remove('btn-warning');
        targetButton.classList.add('btn-danger');
    }

    try {
        const res = await fetch(API_BASE + '/torrents/' + encodeURIComponent(filename), {
            method: 'DELETE'
        });

        if (res.ok) {
            showNotification('Torrent supprimé', 'success');
            await loadTorrents();
        } else {
            showNotification('Erreur lors de la suppression', 'error');
        }
    } catch (e) {
        showNotification('Erreur: ' + (e.message || e), 'error');
    } finally {
        if (targetButton) {
            targetButton.disabled = false;
            targetButton.textContent = 'Supprimer';
            targetButton.classList.remove('btn-warning');
            targetButton.classList.add('btn-danger');
            targetButton.dataset.confirming = 'false';
        }
    }
}

async function deleteBulkTorrents() {
    const checkboxes = document.querySelectorAll('.torrent-checkbox:checked');
    const filenames = Array.from(checkboxes).map(cb => cb.value);
    const bulkDeleteBtn = byId('delete-bulk-torrents-btn');

    if (filenames.length === 0) {
        showNotification('Aucun torrent selectionne', 'warning');
        return;
    }

    if (bulkDeleteBtn) {
        if (bulkDeleteBtn.dataset.confirming !== 'true') {
            bulkDeleteBtn.dataset.confirming = 'true';
            bulkDeleteBtn.textContent = `Confirmer suppression (${filenames.length})`;
            bulkDeleteBtn.classList.remove('btn-danger');
            bulkDeleteBtn.classList.add('btn-warning');
            if (bulkDeleteBtn._confirmTimer) clearTimeout(bulkDeleteBtn._confirmTimer);
            bulkDeleteBtn._confirmTimer = setTimeout(() => {
                bulkDeleteBtn.dataset.confirming = 'false';
                bulkDeleteBtn.textContent = `Supprimer la selection (${filenames.length})`;
                bulkDeleteBtn.classList.remove('btn-warning');
                bulkDeleteBtn.classList.add('btn-danger');
            }, 3000);
            return;
        }
        if (bulkDeleteBtn._confirmTimer) clearTimeout(bulkDeleteBtn._confirmTimer);
        bulkDeleteBtn.dataset.confirming = 'false';
        bulkDeleteBtn.disabled = true;
        bulkDeleteBtn.textContent = 'Suppression...';
        bulkDeleteBtn.classList.remove('btn-warning');
        bulkDeleteBtn.classList.add('btn-danger');
    }

    try {
        let successCount = 0;
        let errorCount = 0;

        for (const filename of filenames) {
            try {
                const res = await fetch(API_BASE + '/torrents/' + encodeURIComponent(filename), {
                    method: 'DELETE'
                });
                if (res.ok) successCount++;
                else errorCount++;
            } catch (e) {
                errorCount++;
            }
        }

        if (errorCount > 0) {
            showNotification(`${successCount} torrent(s) supprimes, ${errorCount} erreur(s)`, 'warning');
        } else {
            showNotification(`${successCount} torrent(s) supprimes`, 'success');
        }
        await loadTorrents();

    } catch (e) {
        showNotification('Erreur suppression: ' + (e.message || e), 'error');
    } finally {
        if (bulkDeleteBtn) {
            bulkDeleteBtn.disabled = false;
            bulkDeleteBtn.dataset.confirming = 'false';
            bulkDeleteBtn.classList.remove('btn-warning');
            bulkDeleteBtn.classList.add('btn-danger');
            updateBulkActionsVisibility();
        }
    }
}

async function cleanupOrphanTorrents() {
    if (!confirm('Supprimer tous les torrents orphelins (sans grab associé) ?')) return;

    try {
        const res = await fetch(API_BASE + '/torrents/cleanup-orphans', { method: 'POST' });
        const data = await res.json();
        alert('✅ ' + data.message);
        await loadTorrents();
    } catch (e) {
        alert('❌ Erreur: ' + e);
    }
}

async function purgeAllTorrents() {
    if (!confirm('⚠️ ATTENTION : Supprimer TOUS les fichiers torrents ? Cette action est irréversible !')) return;

    try {
        const res = await fetch(API_BASE + '/torrents/purge-all', { method: 'POST' });
        const data = await res.json();
        alert('✅ ' + data.message);
        await loadTorrents();
    } catch (e) {
        alert('❌ Erreur: ' + e);
    }
}

// ==================== AUTHENTICATION & SECURITY ====================

async function checkSetupStatus() {
    try {
        // Lire l'état initial injecté par le serveur au lieu d'appeler l'API
        if (window.INITIAL_STATE && window.INITIAL_STATE.first_run) {
            if (window.location.pathname !== '/setup') {
                console.log("🔧 Premier lancement détecté - redirection vers /setup");
                window.location.href = '/setup';
                return false; // Bloquer l'initialisation sur les autres pages
            }
            return true; // Déjà sur /setup: continuer l'initialisation normale
        }

        return true; // Setup terminé, continuer
    } catch (error) {
        console.error("Erreur vérification setup:", error);
        return true; // En cas d'erreur, continuer (éviter de bloquer)
    }
}

async function checkAuthStatus() {
    try {
        // Lire l'état initial injecté par le serveur au lieu d'appeler l'API
        const initialState = window.INITIAL_STATE || {};

        if (initialState.auth_enabled) {
            // Vérifier si l'utilisateur est authentifié
            if (!initialState.authenticated) {
                // Auth activée mais utilisateur non connecté - rediriger vers /login
                console.log("🔐 Authentification requise - redirection vers /login");
                window.location.href = '/login';
                return false; // Bloquer l'initialisation
            }

            // Auth activée et utilisateur connecté - afficher les éléments d'auth
            const securityTab = byId('security-tab');
            const authInfo = byId('auth-info');
            if (securityTab) securityTab.style.display = 'block';
            if (authInfo) authInfo.style.display = 'block';
            setText('username-display', initialState.username || 'Utilisateur');
            setText('security-username', initialState.username || 'Utilisateur');
        }

        return true; // Continuer
    } catch (error) {
        console.error("Erreur vérification auth:", error);
        return true; // En cas d'erreur, continuer (éviter de bloquer)
    }
}

async function logout() {
    const button = document.querySelector('[data-action="logout"]');
    if (!button) return;

    if (button.dataset.confirming !== 'true') {
        button.dataset.confirming = 'true';
        button.textContent = 'Confirmer';
        button.classList.remove('app-topbar__button--secondary');
        button.classList.add('btn-warning');
        if (button._confirmTimer) clearTimeout(button._confirmTimer);
        button._confirmTimer = setTimeout(() => {
            button.dataset.confirming = 'false';
            button.textContent = 'Déconnexion';
            button.classList.remove('btn-warning');
            button.classList.add('app-topbar__button--secondary');
        }, 3500);
        return;
    }

    if (button._confirmTimer) clearTimeout(button._confirmTimer);
    button.disabled = true;
    button.textContent = 'Déconnexion...';
    button.classList.remove('btn-warning');
    button.classList.add('app-topbar__button--secondary');

    try {
        const res = await fetch('/api/auth/logout', { method: 'POST' });
        if (res.ok) {
            window.location.href = '/login';
            return;
        }
        showNotification('Erreur lors de la déconnexion', 'error');
    } catch (error) {
        showNotification('Erreur lors de la déconnexion', 'error');
        console.error(error);
    } finally {
        button.disabled = false;
        button.dataset.confirming = 'false';
        button.textContent = 'Déconnexion';
        button.classList.remove('btn-warning');
        button.classList.add('app-topbar__button--secondary');
    }
}

// ==================== API KEYS MANAGEMENT ====================

async function loadApiKeys(targetId = 'api-keys-list') {
    try {
        apiKeysTargetId = targetId;
        const res = await fetch('/api/auth/keys');
        const data = await res.json();

        const list = byId(targetId);
        if (!list) return;

        const apiKeys = data.api_keys || data.keys || [];
        if (!apiKeys || apiKeys.length === 0) {
            apiKeysVault = new Map();
            list.innerHTML = '<p style="color: #888; text-align: center;">Aucune API Key configurée</p>';
            return;
        }

        const vault = new Map();
        let html = '<table style="margin-top: 10px;"><thead><tr><th>Nom</th><th>Clé</th><th>Statut</th><th>Créée le</th><th>Actions</th></tr></thead><tbody>';

        apiKeys.forEach((key, index) => {
            const statusColor = key.enabled ? '#00aa00' : '#888';
            const statusText = key.enabled ? '✅ Activée' : '❌ Désactivée';
            const createdAt = new Date(key.created_at).toLocaleString('fr-FR');
            const safeName = escapeHtml(key.name || 'API Key');
            const rawKey = String(key.key || '');
            const masked = String(key.key_masked || '');
            const displayKey = masked || (rawKey ? `${rawKey.slice(0, 15)}...${rawKey.slice(-5)}` : '');
            const safeDisplayKey = escapeHtml(displayKey);
            const safeCreatedAt = escapeHtml(createdAt);
            const keyId = `k_${index}_${Date.now()}`;
            vault.set(keyId, rawKey);

            html += `
                <tr>
                    <td><strong>${safeName}</strong></td>
                    <td>
                        <code class="api-key-chip">${safeDisplayKey}</code>
                        <button class="btn btn-secondary btn-sm" type="button" data-action="copy-api-key" data-key-id="${keyId}">Copier</button>
                    </td>
                    <td style="color: ${statusColor};">${statusText}</td>
                    <td style="color: #888; font-size: 12px;">${safeCreatedAt}</td>
                    <td>
                        <div class="api-key-actions">
                            <button class="btn btn-secondary btn-sm" type="button" data-action="toggle-api-key" data-key-id="${keyId}" data-enabled="${!key.enabled}">
                                ${key.enabled ? 'Désactiver' : 'Activer'}
                            </button>
                            <button class="btn btn-danger btn-sm" type="button" data-action="delete-api-key" data-key-id="${keyId}">Supprimer</button>
                        </div>
                    </td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        apiKeysVault = vault;
        list.innerHTML = html;
        bindActionHandlers();
    } catch (error) {
        console.error("Erreur chargement API keys:", error);
        const list = byId(targetId);
        if (list) {
            list.innerHTML = '<p style="color: #ff4444;">Erreur lors du chargement des API keys</p>';
        }
    }
}

function copyApiKey(key) {
    navigator.clipboard.writeText(key).then(() => {
        alert('✅ API Key copiée dans le presse-papiers!');
    }).catch(() => {
        alert('❌ Erreur lors de la copie');
    });
}

function handleCopyApiKey(event, element) {
    const key = apiKeysVault.get(element?.dataset?.keyId || '') || '';
    if (!key) return;
    copyApiKey(key);
}

async function handleDeleteApiKey(event, element) {
    if (!element) return;
    if (element.dataset.confirming !== 'true') {
        element.dataset.confirming = 'true';
        if (!element.dataset.confirmOriginalText) {
            element.dataset.confirmOriginalText = element.textContent || 'Supprimer';
        }
        element.classList.remove('btn-danger', 'btn-secondary');
        element.classList.add('btn-warning');
        element.textContent = 'Confirmer';
        if (element._confirmTimer) clearTimeout(element._confirmTimer);
        element._confirmTimer = setTimeout(() => {
            element.dataset.confirming = 'false';
            element.classList.remove('btn-warning');
            element.classList.add('btn-danger');
            element.textContent = element.dataset.confirmOriginalText || 'Supprimer';
        }, 3500);
        return;
    }
    if (element._confirmTimer) clearTimeout(element._confirmTimer);
    element.dataset.confirming = 'false';
    element.classList.remove('btn-warning');
    element.classList.add('btn-danger');
    element.textContent = 'Suppression...';
    element.disabled = true;
    const key = apiKeysVault.get(element?.dataset?.keyId || '') || '';
    if (!key) return;
    try {
        await deleteApiKey(key);
    } finally {
        element.disabled = false;
        element.textContent = element.dataset.confirmOriginalText || 'Supprimer';
    }
}

async function handleToggleApiKey(event, element) {
    if (!element) return;
    if (element.dataset.confirming !== 'true') {
        element.dataset.confirming = 'true';
        if (!element.dataset.confirmOriginalText) {
            element.dataset.confirmOriginalText = element.textContent || 'Désactiver';
        }
        element.classList.remove('btn-secondary', 'btn-danger');
        element.classList.add('btn-warning');
        element.textContent = 'Confirmer';
        if (element._confirmTimer) clearTimeout(element._confirmTimer);
        element._confirmTimer = setTimeout(() => {
            element.dataset.confirming = 'false';
            element.classList.remove('btn-warning');
            element.classList.add('btn-secondary');
            element.textContent = element.dataset.confirmOriginalText || 'Désactiver';
        }, 3500);
        return;
    }
    if (element._confirmTimer) clearTimeout(element._confirmTimer);
    element.dataset.confirming = 'false';
    element.classList.remove('btn-warning');
    element.classList.add('btn-secondary');
    element.textContent = 'Application...';
    element.disabled = true;
    const key = apiKeysVault.get(element?.dataset?.keyId || '') || '';
    const enabled = String(element?.dataset?.enabled || '').toLowerCase() === 'true';
    if (!key) return;
    try {
        await toggleApiKey(key, enabled);
    } finally {
        element.disabled = false;
        element.textContent = element.dataset.confirmOriginalText || (enabled ? 'Activer' : 'Désactiver');
    }
}

async function deleteApiKey(key) {
    try {
        const res = await fetch(`/api/auth/keys/${encodeURIComponent(key)}`, {
            method: 'DELETE'
        });

        const data = await res.json();

        if (data.success) {
            alert('✅ API Key supprimée');
            await loadApiKeys(apiKeysTargetId || 'api-keys-list');
        } else {
            alert('❌ Erreur lors de la suppression');
        }
    } catch (error) {
        alert('❌ Erreur lors de la suppression');
        console.error(error);
    }
}

async function toggleApiKey(key, enabled) {
    try {
        const res = await fetch(`/api/auth/keys/${encodeURIComponent(key)}?enabled=${enabled}`, {
            method: 'PATCH'
        });

        const data = await res.json();

        if (data.success) {
            alert(`✅ API Key ${enabled ? 'activée' : 'désactivée'}`);
            await loadApiKeys(apiKeysTargetId || 'api-keys-list');
        } else {
            alert('❌ Erreur lors de la modification');
        }
    } catch (error) {
        alert('❌ Erreur lors de la modification');
        console.error(error);
    }
}

// ==================== LOGIN PAGE FUNCTIONALITY ====================
// This section is only used on the /login page

function initLoginPage() {
    const form = byId('login-form');
    const errorMessage = byId('error-message');
    const loginBtn = byId('login-btn');
    const loading = byId('loading');

    if (!form) return; // Not on login page

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Récupérer les valeurs
        const usernameInput = byId('username');
        const passwordInput = byId('password');
        if (!usernameInput || !passwordInput) return;
        const username = usernameInput.value;
        const password = passwordInput.value;

        // Désactiver le formulaire
        loginBtn.disabled = true;
        loginBtn.textContent = 'Connexion...';
        loading.style.display = 'block';
        errorMessage.style.display = 'none';

        try {
            // Envoyer la requête de connexion
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password }),
                credentials: 'include'
            });

            const data = await response.json();

            if (data.success) {
                // Connexion réussie - rediriger vers la page d'accueil
                window.location.href = '/';
            } else {
                // Afficher l'erreur
                errorMessage.textContent = data.message || 'Identifiants incorrects';
                errorMessage.style.display = 'block';
                loginBtn.disabled = false;
                loginBtn.textContent = 'Se connecter';
                loading.style.display = 'none';

                // Réinitialiser le mot de passe
                passwordInput.value = '';
                passwordInput.focus();
            }
        } catch (error) {
            errorMessage.textContent = 'Erreur de connexion au serveur';
            errorMessage.style.display = 'block';
            loginBtn.disabled = false;
            loginBtn.textContent = 'Se connecter';
            loading.style.display = 'none';
            console.error('Erreur:', error);
        }
    });

    // Focus sur le champ username au chargement
    const userInput = byId('username');
    if (userInput) userInput.focus();
}

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', async () => {
    console.log("🚀 Initialisation Grab2RSS...");

    // Check if we're on the login page
    if (byId('login-form')) {
        initLoginPage();
        return;
    }

    initDrawer();

    const page = document.querySelector('.app-content')?.dataset.page;
    if (page) {
        setActiveNav(page);
    }
    bindActionHandlers();
    clearPageError();

    // Dashboard initialization
    try {
        // 1. Vérifier si c'est le premier lancement (setup requis)
        const setupCompleted = await checkSetupStatus();
        if (!setupCompleted) {
            return; // Redirection vers /setup en cours
        }

        // 2. Vérifier l'authentification (si activée)
        const authOk = await checkAuthStatus();
        if (!authOk) {
            return; // Redirection vers /login en cours
        }

        // 3. Initialiser par page
        if (page === 'overview') {
            ensureElements('overview', [
                '#total-grabs',
                '#dashboard-torrent-count',
                '#dashboard-storage-size',
                '#sync-status'
            ]);
            await loadTrackers();
            await refreshData();
            if (typeof Chart !== 'undefined') {
                await loadStats();
            }
            await refreshSyncIndicators();
            setInterval(refreshData, 30000);
        } else if (page === 'grabs') {
            ensureElements('grabs', [
                '#grab-history-table',
                '#grabs-summary-total',
                '#grabs-summary-webhook',
                '#grabs-summary-missing',
                '#grabs-summary-last-sync'
            ]);
            await loadGrabHistory();
            await refreshSyncIndicators();
            const instanceFilter = byId('grab-history-instance-filter');
            if (instanceFilter) {
                instanceFilter.addEventListener('change', loadGrabHistory);
            }
            const trackerFilter = byId('grab-history-tracker-filter');
            if (trackerFilter) {
                trackerFilter.addEventListener('change', loadGrabHistory);
            }
            const sourceFilter = byId('grab-history-source-filter');
            if (sourceFilter) {
                sourceFilter.addEventListener('change', loadGrabHistory);
            }
            const idSearch = byId('grab-history-id-search');
            if (idSearch) {
                idSearch.addEventListener('input', debounce(loadGrabHistory, 300));
            }
            const sortSelect = byId('grab-history-sort');
            if (sortSelect) {
                sortSelect.addEventListener('change', loadGrabHistory);
            }
            document.querySelectorAll('[data-action="grab-history-detail-close"]').forEach(btn => {
                btn.addEventListener('click', closeGrabHistoryDetailModal);
            });
            document.addEventListener('keydown', (event) => {
                if (event.key === 'Escape') {
                    closeGrabHistoryDetailModal();
                }
            });
        } else if (page === 'torrents') {
            ensureElements('torrents', ['#torrents-table', '#torrents-total']);
            await loadTorrents();
            const trackerFilter = byId('torrents-tracker-filter');
            if (trackerFilter) trackerFilter.addEventListener('change', renderTorrentsTable);
            const statusFilter = byId('torrents-status-filter');
            if (statusFilter) statusFilter.addEventListener('change', renderTorrentsTable);
            const searchInput = byId('torrents-search');
            if (searchInput) searchInput.addEventListener('input', debounce(renderTorrentsTable, 250));
            const sortSelect = byId('torrents-sort');
            if (sortSelect) sortSelect.addEventListener('change', renderTorrentsTable);
        } else if (page === 'logs') {
            ensureElements('logs', ['#logs-table']);
            await loadLogs();
        } else if (page === 'history-grabb') {
            window.location.href = '/grabs';
        } else if (page === 'configuration') {
            ensureElements('configuration', ['#config-form']);
            await loadConfig();
        } else if (page === 'security') {
            ensureElements('security', ['#api-keys-list']);
            await loadApiKeys();
        } else if (page === 'setup') {
            initSetupPage();
        } else {
            // Fallback for pages that don't render the shell (e.g. setup)
            if (document.querySelector('.page-shell[data-first-run][data-config-exists]')) {
                initSetupPage();
            }
        }

        await refreshSyncIndicators();
        setInterval(refreshSyncIndicators, 10000);

        console.log("✅ Application initialisée");
    } catch (error) {
        console.error("❌ Erreur initialisation:", error);
        showPageError("Erreur lors du chargement. Certaines sections peuvent être indisponibles.");
    }
});

// ==================== DRAWER NAVIGATION ====================

function initDrawer() {
    const toggleBtn = document.getElementById('drawer-toggle');
    const drawer = document.getElementById('app-drawer');
    const overlay = document.getElementById('drawer-overlay');

    if (!toggleBtn || !drawer || !overlay) return;

    let lastFocused = null;

    const openDrawer = () => {
        lastFocused = document.activeElement;
        document.body.classList.add('drawer-open');
        overlay.hidden = false;
        drawer.setAttribute('aria-hidden', 'false');
        toggleBtn.setAttribute('aria-expanded', 'true');

        const focusTarget = drawer.querySelector('a, button, input, [tabindex]:not([tabindex="-1"])') || drawer;
        focusTarget.focus();
    };

    const closeDrawer = () => {
        document.body.classList.remove('drawer-open');
        overlay.hidden = true;
        drawer.setAttribute('aria-hidden', 'true');
        toggleBtn.setAttribute('aria-expanded', 'false');
        if (lastFocused) {
            lastFocused.focus();
        } else {
            toggleBtn.focus();
        }
    };

    toggleBtn.addEventListener('click', () => {
        if (document.body.classList.contains('drawer-open')) {
            closeDrawer();
        } else {
            openDrawer();
        }
    });

    overlay.addEventListener('click', () => closeDrawer());

    drawer.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            event.preventDefault();
            closeDrawer();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && document.body.classList.contains('drawer-open')) {
            event.preventDefault();
            closeDrawer();
        }
    });

    drawer.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            setTimeout(() => closeDrawer(), 0);
        });
    });
}

// ==================== SETUP PAGE ====================

function initSetupPage() {
    const container = document.querySelector('.page-shell[data-first-run][data-config-exists]') || document.querySelector('.page-shell');
    if (!container) return;

    if ('firstRun' in container.dataset && 'configExists' in container.dataset) {
        const firstRun = container.dataset.firstRun === 'true';
        const configExists = container.dataset.configExists === 'true';
        if (!firstRun && configExists) {
            window.location.href = '/';
            return;
        }
    }

    const form = byId('setupForm');
    const alertEl = byId('alert');
    const loadingEl = byId('loading');
    const authToggle = byId('auth_enabled');
    const authFields = byId('auth_fields');
    const webhookToggle = byId('webhook_enabled');
    const webhookTokenInput = byId('webhook_token');
    const webhookUrlPrimaryInput = byId('webhook_url_primary');
    const webhookUrlFallbackInput = byId('webhook_url_fallback');
    const webhookGenerateBtn = document.querySelector('[data-action="generate-webhook-token"]');
    const webhookCopyPrimaryBtn = document.querySelector('[data-action="copy-webhook-url-primary"]');
    const webhookCopyFallbackBtn = document.querySelector('[data-action="copy-webhook-url-fallback"]');
    const webhookApplyBtn = document.querySelector('[data-action="apply-webhook-setup"]');
    const webhookActivationStatus = byId('webhook_activation_status');
    const webhookPrimaryRow = byId('webhook_url_primary_row');
    const webhookFallbackRow = byId('webhook_url_fallback_row');
    const webhookPrimaryBadge = byId('webhook_primary_badge');
    const webhookFallbackBadge = byId('webhook_fallback_badge');
    const webhookStrict = byId('webhook_strict');
    const webhookDownload = byId('webhook_download');
    const webhookMinScore = byId('webhook_min_score');
    const webhookTokenRow = webhookTokenInput?.closest('.form-field') || null;
    const webhookGuide = document.querySelector('.setup-webhook-guide');
    const webhookAdvancedBlock = webhookMinScore?.closest('.advanced-block') || null;
    const steps = Array.from(document.querySelectorAll('[data-setup-step]'));
    const stepPills = Array.from(document.querySelectorAll('.setup-wizard__step'));
    const nextStepButton = document.querySelector('[data-action="next-step"]');
    const prevStepButton = document.querySelector('[data-action="prev-step"]');
    const wizardActions = document.querySelector('[data-role="setup-wizard-actions"]');
    const goFixButton = document.querySelector('[data-action="go-fix"]');
    const progressBar = document.querySelector('[data-role="setup-progress"]');

    if (!form || !authToggle || !authFields) {
        warnMissing('setup', '#setupForm, #auth_enabled, #auth_fields');
        return;
    }
    if (form.dataset.setupInitialized === 'true') return;
    form.dataset.setupInitialized = 'true';

    let currentStep = 0;

    const getStepRequiredFields = () => {
        const current = steps[currentStep];
        if (!current) return [];
        const fields = Array.from(current.querySelectorAll('input[required], select[required]'));
        if (!authToggle.checked) {
            return fields.filter(field => !['auth_username', 'auth_password'].includes(field.id));
        }
        return fields;
    };

    const validateStep = () => {
        const fields = getStepRequiredFields();
        let valid = true;
        fields.forEach(field => {
            const value = field.value?.trim();
            if (!value) {
                valid = false;
            }
        });
        if (nextStepButton) {
            nextStepButton.disabled = !valid;
        }
        return valid;
    };

    const updateWizard = () => {
        if (!steps.length) return;
        steps.forEach((step, index) => {
            step.hidden = index !== currentStep;
        });
        stepPills.forEach((pill, index) => {
            pill.classList.toggle('is-active', index === currentStep);
            pill.setAttribute('aria-current', index === currentStep ? 'step' : 'false');
        });
        if (prevStepButton) {
            prevStepButton.disabled = currentStep === 0;
        }
        if (nextStepButton) {
            nextStepButton.hidden = currentStep >= steps.length - 1;
        }
        if (wizardActions) {
            wizardActions.hidden = currentStep >= steps.length - 1;
            wizardActions.classList.toggle('is-hidden', currentStep >= steps.length - 1);
        }
        if (progressBar) {
            const progress = ((currentStep + 1) / steps.length) * 100;
            progressBar.style.width = `${progress}%`;
        }
        validateStep();
    };

    updateWizard();

    if (nextStepButton) {
        nextStepButton.addEventListener('click', () => {
            if (!validateStep()) {
                showAlert('Veuillez compléter les champs obligatoires avant de continuer.', 'error');
                return;
            }
            if (currentStep < steps.length - 1) {
                currentStep += 1;
                updateWizard();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
    }

    if (prevStepButton) {
        prevStepButton.addEventListener('click', () => {
            if (currentStep > 0) {
                currentStep -= 1;
                updateWizard();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
    }

    if (goFixButton) {
        goFixButton.addEventListener('click', () => {
            if (!requireSetupInlineConfirmation(goFixButton)) return;
            currentStep = 0;
            updateWizard();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    stepPills.forEach((pill, index) => {
        pill.addEventListener('click', () => {
            currentStep = index;
            updateWizard();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });

    const showAlert = (message, type) => {
        if (!alertEl) {
            const level = type === 'error' ? 'error' : (type === 'success' ? 'success' : 'info');
            showNotification(message, level);
            return;
        }
        alertEl.textContent = message;
        alertEl.className = `alert ${type}`;
        alertEl.style.display = 'block';

        if (type === 'success' && !message.includes('Test')) {
            setTimeout(() => {
                alertEl.style.display = 'none';
            }, 3000);
        }
    };

    const resetSetupInlineConfirmation = (button) => {
        if (!button) return;
        if (button._confirmTimer) {
            clearTimeout(button._confirmTimer);
            button._confirmTimer = null;
        }
        if (button.dataset.confirmOriginalText) {
            button.textContent = button.dataset.confirmOriginalText;
        }
        button.dataset.confirming = 'false';
    };

    const requireSetupInlineConfirmation = (button) => {
        if (!button) return true;
        if (button.dataset.confirming === 'true') {
            resetSetupInlineConfirmation(button);
            return true;
        }
        if (!button.dataset.confirmOriginalText) {
            button.dataset.confirmOriginalText = button.textContent;
        }
        button.dataset.confirming = 'true';
        button.textContent = 'Confirmer';
        if (button._confirmTimer) clearTimeout(button._confirmTimer);
        button._confirmTimer = setTimeout(() => {
            resetSetupInlineConfirmation(button);
        }, 3500);
        return false;
    };

    const toggleAuthFields = () => {
        const enabled = authToggle.checked;
        authFields.style.display = enabled ? 'block' : 'none';

        const usernameField = byId('auth_username');
        const passwordField = byId('auth_password');
        if (usernameField && passwordField) {
            if (enabled) {
                usernameField.setAttribute('required', 'required');
                passwordField.setAttribute('required', 'required');
            } else {
                usernameField.removeAttribute('required');
                passwordField.removeAttribute('required');
            }
        }
        validateStep();
    };

    const toggleWebhookFields = () => {
        if (!webhookToggle || !webhookTokenInput) return;
        const enabled = webhookToggle.checked;
        if (webhookTokenRow) webhookTokenRow.hidden = !enabled;
        if (webhookGuide) webhookGuide.hidden = !enabled;
        if (webhookPrimaryRow) webhookPrimaryRow.hidden = !enabled;
        if (webhookFallbackRow) webhookFallbackRow.hidden = !enabled;
        if (webhookAdvancedBlock) webhookAdvancedBlock.hidden = !enabled;
        if (webhookGenerateBtn) webhookGenerateBtn.disabled = !enabled;
        if (webhookCopyPrimaryBtn) webhookCopyPrimaryBtn.disabled = !enabled;
        if (webhookCopyFallbackBtn) webhookCopyFallbackBtn.disabled = !enabled;
        if (enabled) {
            webhookTokenInput.setAttribute('required', 'required');
            updateSetupWebhookUrls();
            setWebhookActivationStatus('Webhook activé. Vous pouvez copier les URLs.', 'success');
            ensureWebhookToken();
        } else {
            webhookTokenInput.removeAttribute('required');
            setRecommendedWebhook(null);
            setWebhookActivationStatus('Webhook désactivé (optionnel, mais recommandé).', 'info');
        }
        validateStep();
    };

    let testInFlight = false;
    let submitInFlight = false;

    const buildWebhookUrlByHost = (token, hostValue) => {
        // Les endpoints Docker internes (grabb2rss / 172.17.0.1) exposent typiquement HTTP.
        const internalHosts = new Set(['grabb2rss', '172.17.0.1']);
        const protocol = internalHosts.has(hostValue) ? 'http:' : (window.location.protocol || 'http:');
        const tokenPart = token ? `?token=${encodeURIComponent(token)}` : '';
        return `${protocol}//${hostValue}:8000/api/webhook/grab${tokenPart}`;
    };

    const updateSetupWebhookUrls = () => {
        const token = (webhookTokenInput?.value || '').trim();
        if (webhookUrlPrimaryInput) {
            webhookUrlPrimaryInput.value = buildWebhookUrlByHost(token, 'grabb2rss');
        }
        if (webhookUrlFallbackInput) {
            webhookUrlFallbackInput.value = buildWebhookUrlByHost(token, '172.17.0.1');
        }
        setRecommendedWebhook('primary');
    };

    const ensureWebhookToken = async () => {
        if (!webhookTokenInput) return;
        if (!webhookToggle?.checked) {
            updateSetupWebhookUrls();
            validateStep();
            return;
        }
        if ((webhookTokenInput.value || '').trim()) {
            updateSetupWebhookUrls();
            validateStep();
            return;
        }
        try {
            const res = await fetch('/api/webhook/token/generate?enable=true', { method: 'POST' });
            const data = await res.json();
            if (data && data.token) {
                webhookTokenInput.value = data.token;
                updateSetupWebhookUrls();
                setWebhookActivationStatus('Webhook activé avec token généré: utilisable immédiatement.', 'success');
            }
        } catch (e) {
            console.warn('Impossible de pré-générer le token webhook:', e);
        } finally {
            validateStep();
        }
    };

    const setButtonState = (button, loading, loadingText) => {
        if (!button) return;
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.textContent;
        }
        button.disabled = loading;
        button.textContent = loading ? loadingText : button.dataset.originalText;
    };

    const setWebhookActivationStatus = (message, type = 'info') => {
        if (!webhookActivationStatus) return;
        webhookActivationStatus.textContent = message;
        webhookActivationStatus.classList.remove('text-success', 'text-danger', 'text-muted');
        if (type === 'success') webhookActivationStatus.classList.add('text-success');
        else if (type === 'error') webhookActivationStatus.classList.add('text-danger');
        else webhookActivationStatus.classList.add('text-muted');
    };

    const setRecommendedWebhook = (choice) => {
        const primary = choice === 'primary';
        const fallback = choice === 'fallback';
        if (webhookPrimaryRow) webhookPrimaryRow.classList.toggle('is-recommended', primary);
        if (webhookFallbackRow) webhookFallbackRow.classList.toggle('is-recommended', fallback);
        if (webhookPrimaryBadge) webhookPrimaryBadge.hidden = !primary;
        if (webhookFallbackBadge) webhookFallbackBadge.hidden = !fallback;
    };

    const testConnection = async () => {
        if (testInFlight) return;
        const testButton = document.querySelector('[data-action="test-connection"]');
        if (!requireSetupInlineConfirmation(testButton)) return;
        const urlInput = byId('prowlarr_url');
        const apiKeyInput = byId('prowlarr_api_key');
        if (!urlInput || !apiKeyInput) {
            warnMissing('setup', '#prowlarr_url, #prowlarr_api_key');
            return;
        }

        const url = urlInput.value;
        const apiKey = apiKeyInput.value;
        if (!url || !apiKey) {
            showAlert("Veuillez remplir l'URL et la clé API Prowlarr", 'error');
            return;
        }

        testInFlight = true;
        setButtonState(testButton, true, 'Test en cours...');
        showAlert('Test de connexion en cours...', 'info');

        try {
            const response = await fetch('/api/setup/test-prowlarr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url, api_key: apiKey })
            });

            const data = await response.json();

            if (data.success) {
                showNotification('Connexion réussie à Prowlarr', 'success');
                showAlert('Connexion réussie à Prowlarr !', 'success');
            } else {
                showAlert('Erreur: ' + (data.error || 'Connexion échouée'), 'error');
            }
        } catch (error) {
            showAlert('Erreur de connexion: ' + error.message, 'error');
        } finally {
            testInFlight = false;
            setButtonState(testButton, false);
        }
    };

    const applyWebhookSetup = async () => {
        if (!requireSetupInlineConfirmation(webhookApplyBtn)) return;
        if (!webhookToggle) return;
        if (!webhookToggle.checked) {
            webhookToggle.checked = true;
            toggleWebhookFields();
        }
        await ensureWebhookToken();
        showAlert("Webhook prêt. Cliquez sur « Enregistrer et démarrer » pour sauvegarder définitivement.", 'success');
    };

    const submitSetup = async (event) => {
        event.preventDefault();
        if (submitInFlight) return;
        const submitButton = document.querySelector('[data-action="submit-setup"]');
        if (!requireSetupInlineConfirmation(submitButton)) return;

        const formData = new FormData(form);
        const config = {
            prowlarr_url: formData.get('prowlarr_url'),
            prowlarr_api_key: formData.get('prowlarr_api_key'),

            radarr_enabled: true,
            radarr_url: formData.get('radarr_url'),
            radarr_api_key: formData.get('radarr_api_key'),

            sonarr_enabled: true,
            sonarr_url: formData.get('sonarr_url'),
            sonarr_api_key: formData.get('sonarr_api_key'),

            retention_hours: parseInt(formData.get('retention_hours')),
            auto_purge: byId('auto_purge')?.checked || false,

            rss_domain: window.location.hostname,
            rss_scheme: window.location.protocol.replace(':', ''),
            rss_title: 'grabb2RSS',
            rss_description: 'Prowlarr to RSS Feed',

            auth_enabled: authToggle.checked,
            auth_username: formData.get('auth_username') || '',
            auth_password: formData.get('auth_password') || '',

            webhook_enabled: webhookToggle?.checked || false,
            webhook_token: formData.get('webhook_token') || '',
            webhook_min_score: parseInt(formData.get('webhook_min_score') || '3'),
            webhook_strict: webhookStrict?.checked || false,
            webhook_download: webhookDownload?.checked || false,

            history_lookback_days: Math.max(1, Math.min(30, parseInt(formData.get('history_lookback_days') || '7', 10) || 7))
        };

        if (config.auth_enabled) {
            if (!config.auth_username || !config.auth_password) {
                showAlert("Veuillez remplir le nom d'utilisateur et le mot de passe pour l'authentification", 'error');
                return;
            }
            if (config.auth_password.length < 8) {
                showAlert('Le mot de passe doit contenir au moins 8 caractères', 'error');
                return;
            }
        }

        submitInFlight = true;
        setButtonState(submitButton, true, 'Sauvegarde...');
        form.style.display = 'none';
        if (loadingEl) loadingEl.style.display = 'block';

        try {
            const response = await fetch('/api/setup/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            let data = {};
            try {
                data = await response.json();
            } catch (parseError) {
                data = {};
            }
            if (response.ok && data.success) {
                showNotification('Configuration enregistrée', 'success');
                showAlert('Configuration enregistrée ! Redirection...', 'success');
                setTimeout(() => {
                    window.location.href = '/';
                }, 2000);
            } else {
                form.style.display = 'block';
                if (loadingEl) loadingEl.style.display = 'none';
                showAlert('Erreur: ' + (data.detail || data.error || data.message || `HTTP ${response.status}`), 'error');
            }
        } catch (error) {
            form.style.display = 'block';
            if (loadingEl) loadingEl.style.display = 'none';
            showAlert('Erreur: ' + error.message, 'error');
        } finally {
            submitInFlight = false;
            setButtonState(submitButton, false);
        }
    };

    toggleAuthFields();
    toggleWebhookFields();

    authToggle.addEventListener('change', toggleAuthFields);
    if (webhookToggle) {
        webhookToggle.addEventListener('change', toggleWebhookFields);
    }
    ensureWebhookToken();

    if (webhookCopyPrimaryBtn && webhookUrlPrimaryInput) {
        webhookCopyPrimaryBtn.addEventListener('click', () => {
            if (!requireSetupInlineConfirmation(webhookCopyPrimaryBtn)) return;
            copyText(webhookUrlPrimaryInput.value);
            showAlert("URL webhook Docker copiée", 'success');
        });
    }
    if (webhookCopyFallbackBtn && webhookUrlFallbackInput) {
        webhookCopyFallbackBtn.addEventListener('click', () => {
            if (!requireSetupInlineConfirmation(webhookCopyFallbackBtn)) return;
            copyText(webhookUrlFallbackInput.value);
            showAlert("URL webhook fallback copiée", 'success');
        });
    }

    if (webhookGenerateBtn && webhookTokenInput) {
        webhookGenerateBtn.addEventListener('click', async () => {
            if (!requireSetupInlineConfirmation(webhookGenerateBtn)) return;
            try {
                const res = await fetch('/api/webhook/token/generate', { method: 'POST' });
                const data = await res.json();
                if (data && data.token) {
                    webhookTokenInput.value = data.token;
                    if (webhookToggle) webhookToggle.checked = true;
                    updateSetupWebhookUrls();
                    toggleWebhookFields();
                } else {
                    showAlert("Impossible de générer un token webhook", 'error');
                }
            } catch (e) {
                showAlert("Erreur génération token webhook: " + e, 'error');
            }
        });
    }

    if (webhookTokenInput) {
        webhookTokenInput.addEventListener('input', () => {
            updateSetupWebhookUrls();
        });
    }
    if (webhookApplyBtn) {
        webhookApplyBtn.addEventListener('click', applyWebhookSetup);
    }
    const testButton = document.querySelector('[data-action="test-connection"]');
    if (testButton) testButton.addEventListener('click', testConnection);
    form.addEventListener('submit', submitSetup);
    form.addEventListener('input', () => {
        if (steps[currentStep]?.contains(document.activeElement)) {
            validateStep();
        }
    });

    updateWizard();
}

// Fallback dédié setup: évite un setup partiellement inactif si l'init globale échoue.
if (window.location.pathname === '/setup') {
    window.addEventListener('load', () => {
        const form = byId('setupForm');
        if (!form || form.dataset.setupInitialized === 'true') return;
        try {
            initSetupPage();
        } catch (error) {
            console.error("Erreur fallback init setup:", error);
        }
    });
}

// Event listener for torrent checkboxes
document.addEventListener('change', (e) => {
    if (e.target.classList.contains('torrent-checkbox')) {
        updateBulkActionsVisibility();
    }
});
