// ==================== GLOBAL VARIABLES ====================

const API_BASE = "/api";
let configData = {};
let statsData = {};
let allTrackers = [];
let trackerChartInstance = null;
let grabsByDayChartInstance = null;
let topTorrentsChartInstance = null;

// ==================== UTILITY FUNCTIONS ====================

function getRssBaseUrl() {
    return window.location.origin;
}

// ==================== TAB MANAGEMENT ====================

function switchTab(tab) {
    // Remove active class from all tabs and buttons
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-button').forEach(el => el.classList.remove('active'));

    // Add active class to selected tab
    const tabElement = document.getElementById(tab);
    if (tabElement) {
        tabElement.classList.add('active');
    }

    // Find and activate the corresponding button by searching for onclick with the tab name
    const buttons = document.querySelectorAll('.tab-button');
    buttons.forEach(btn => {
        const onclick = btn.getAttribute('onclick');
        if (onclick && onclick.includes(`'${tab}'`)) {
            btn.classList.add('active');
        }
    });

    // Load tab content
    if (tab === 'config') loadConfig();
    if (tab === 'logs') loadLogs();
    if (tab === 'grabs') loadGrabs();
    if (tab === 'torrents') loadTorrents();
    if (tab === 'stats') loadStats();
    if (tab === 'rss') loadRssUrls();
    if (tab === 'admin') loadAdminTab();
    if (tab === 'security') loadApiKeys();
}

// ==================== RSS FEEDS ====================

function loadRssUrls() {
    const baseUrl = getRssBaseUrl();
    document.getElementById('rss-global-xml').textContent = baseUrl + '/rss';
    document.getElementById('rss-global-json').textContent = baseUrl + '/rss/torrent.json';
    updateTrackerRssUrls();
}

function updateTrackerRssUrls() {
    const tracker = document.getElementById('tracker-filter-rss').value;
    const baseUrl = getRssBaseUrl();

    if (tracker === 'all') {
        document.getElementById('rss-tracker-xml').textContent = baseUrl + '/rss';
        document.getElementById('rss-tracker-json').textContent = baseUrl + '/rss/torrent.json';
    } else {
        document.getElementById('rss-tracker-xml').textContent = baseUrl + '/rss/tracker/' + encodeURIComponent(tracker);
        document.getElementById('rss-tracker-json').textContent = baseUrl + '/rss/tracker/' + encodeURIComponent(tracker) + '/json';
    }
}

function copyToClipboard(elementId) {
    const text = document.getElementById(elementId).textContent;
    navigator.clipboard.writeText(text).then(() => {
        alert('✅ Copié dans le presse-papiers!');
    }).catch(() => {
        alert('❌ Erreur lors de la copie');
    });
}

// ==================== TRACKERS ====================

async function loadTrackers() {
    try {
        const res = await fetch(API_BASE + '/trackers');
        if (!res.ok) throw new Error('Trackers API error: ' + res.status);

        const data = await res.json();
        allTrackers = data.trackers;

        [document.getElementById('tracker-filter-grabs'), document.getElementById('tracker-filter-rss')].forEach(select => {
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

// ==================== GRABS ====================

async function filterGrabs() {
    const tracker = document.getElementById('tracker-filter-grabs').value;
    const url = API_BASE + '/grabs?limit=100&tracker=' + encodeURIComponent(tracker);

    try {
        const grabs = await fetch(url).then(r => r.json());
        const tbody = document.getElementById("grabs-table");
        tbody.innerHTML = grabs.length ? grabs.map(g =>
            '<tr>' +
            '<td class="date">' + new Date(g.grabbed_at).toLocaleString('fr-FR') + '</td>' +
            '<td>' + g.title + '</td>' +
            '<td><strong style="color: #1e90ff;">' + (g.tracker || 'N/A') + '</strong></td>' +
            '<td><a href="/torrents/' + encodeURIComponent(g.torrent_file) + '" target="_blank" style="color: #1e90ff; text-decoration: none;">📥 Download</a></td>' +
            '</tr>'
        ).join("") : '<tr><td colspan="4" style="text-align: center; color: #888;">Aucun grab</td></tr>';
    } catch (e) {
        console.error("Erreur filterGrabs:", e);
    }
}

async function loadGrabs() {
    await filterGrabs();
}

async function purgeAllGrabs() {
    if (confirm("⚠️  Êtes-vous CERTAIN ? Cela supprimera TOUS les grabs !")) {
        try {
            const res = await fetch(API_BASE + '/purge/all', { method: "POST" });
            const data = await res.json();
            alert("✅ " + data.message);
            refreshData();
            loadGrabs();
        } catch (e) {
            alert("❌ Erreur: " + e);
        }
    }
}

// ==================== STATISTICS & CHARTS ====================

async function loadStats() {
    try {
        const res = await fetch(API_BASE + '/stats');
        statsData = await res.json();

        const trackerLabels = statsData.tracker_stats.map(t => t.tracker);
        const trackerData = statsData.tracker_stats.map(t => t.count);

        const trackerCtx = document.getElementById('trackerChart').getContext('2d');
        if (trackerChartInstance) trackerChartInstance.destroy();
        trackerChartInstance = new Chart(trackerCtx, {
            type: 'doughnut',
            data: {
                labels: trackerLabels,
                datasets: [{
                    data: trackerData,
                    backgroundColor: [
                        '#1e90ff', '#ff6b6b', '#4ecdc4', '#45b7d1', '#f7b731',
                        '#5f27cd', '#00d2d3', '#ff9ff3', '#54a0ff', '#48dbfb'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#e0e0e0' } },
                    title: { display: true, text: 'Grabs par Tracker', color: '#1e90ff' }
                }
            }
        });

        const dayLabels = statsData.grabs_by_day.map(d => d.day).reverse();
        const dayData = statsData.grabs_by_day.map(d => d.count).reverse();

        const dayCtx = document.getElementById('grabsByDayChart').getContext('2d');
        if (grabsByDayChartInstance) grabsByDayChartInstance.destroy();
        grabsByDayChartInstance = new Chart(dayCtx, {
            type: 'line',
            data: {
                labels: dayLabels,
                datasets: [{
                    label: 'Grabs',
                    data: dayData,
                    borderColor: '#1e90ff',
                    backgroundColor: 'rgba(30, 144, 255, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#e0e0e0' } },
                    title: { display: true, text: 'Grabs par Jour (30 derniers jours)', color: '#1e90ff' }
                },
                scales: {
                    y: { ticks: { color: '#e0e0e0' }, grid: { color: '#333' } },
                    x: { ticks: { color: '#e0e0e0' }, grid: { color: '#333' } }
                }
            }
        });

        const topLabels = statsData.top_torrents.map(t => t.title.substring(0, 30) + '...');
        const topData = Array(statsData.top_torrents.length).fill(1);

        const topCtx = document.getElementById('topTorrentsChart').getContext('2d');
        if (topTorrentsChartInstance) topTorrentsChartInstance.destroy();
        topTorrentsChartInstance = new Chart(topCtx, {
            type: 'bar',
            data: {
                labels: topLabels,
                datasets: [{
                    label: 'Top Torrents',
                    data: topData,
                    backgroundColor: '#1e90ff'
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#e0e0e0' } },
                    title: { display: true, text: 'Top 10 des Torrents Récents', color: '#1e90ff' }
                },
                scales: {
                    y: { ticks: { color: '#e0e0e0' }, grid: { color: '#333' } },
                    x: { ticks: { color: '#e0e0e0' }, grid: { color: '#333' } }
                }
            }
        });

        const total = statsData.tracker_stats.reduce((a, b) => a + b.count, 0);
        let tbody = document.getElementById('tracker-stats-body');
        tbody.innerHTML = statsData.tracker_stats.map(t =>
            '<tr>' +
            '<td><strong>' + t.tracker + '</strong></td>' +
            '<td>' + t.count + '</td>' +
            '<td>' + ((t.count / total) * 100).toFixed(1) + '%</td>' +
            '</tr>'
        ).join("");

    } catch (e) {
        console.error("Erreur loadStats:", e);
    }
}

// ==================== DASHBOARD ====================

async function refreshData() {
    try {
        const [stats, sync, detailedStats, torrentsData] = await Promise.all([
            fetch(API_BASE + '/stats').then(r => r.json()),
            fetch(API_BASE + '/sync/status').then(r => r.json()),
            fetch(API_BASE + '/stats/detailed').then(r => r.json()),
            fetch(API_BASE + '/torrents').then(r => r.json())
        ]);

        // Statistiques principales
        document.getElementById("total-grabs").textContent = stats.total_grabs;
        document.getElementById("storage-size").textContent = stats.storage_size_mb;
        document.getElementById("latest-grab").textContent = stats.latest_grab ? new Date(stats.latest_grab).toLocaleString('fr-FR') : "-";

        // Nouvelles statistiques dashboard
        document.getElementById("dashboard-torrent-count").textContent = torrentsData.total;
        const totalSize = torrentsData.torrents.reduce((acc, t) => acc + t.size_mb, 0);
        document.getElementById("dashboard-torrent-size").textContent = totalSize.toFixed(2);

        // Nombre de trackers différents
        const uniqueTrackers = new Set(stats.tracker_stats.map(t => t.tracker)).size;
        document.getElementById("dashboard-trackers-count").textContent = uniqueTrackers;

        // Grabs aujourd'hui (dernières 24h)
        const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
        const grabsToday = stats.grabs_by_day[0]?.count || 0;
        document.getElementById("dashboard-grabs-today").textContent = grabsToday;

        // Uptime
        const uptime = detailedStats.system.uptime_seconds;
        const hours = Math.floor(uptime / 3600);
        const minutes = Math.floor((uptime % 3600) / 60);
        document.getElementById("dashboard-uptime").textContent = hours + 'h ' + minutes + 'm';

        // Statut sync
        const statusEl = document.getElementById("sync-status");

        let statusClass = "status offline";
        let statusText = "Inactif";

        if (sync.is_running) {
            statusClass = "status online";
            statusText = "Sync en cours...";
        } else if (sync.next_sync) {
            statusClass = "status online";
            statusText = "Actif";
        } else if (sync.last_sync) {
            statusClass = "status offline";
            statusText = "Arrêté";
        } else {
            statusClass = "status offline";
            statusText = "En attente";
        }

        statusEl.className = statusClass;
        statusEl.textContent = statusText;

        document.getElementById("next-sync").textContent = sync.next_sync ? 'Prochain: ' + new Date(sync.next_sync).toLocaleString('fr-FR') : "-";
    } catch (e) {
        console.error("❌ Erreur refreshData:", e);
    }
}

// ==================== LOGS ====================

async function loadLogs() {
    try {
        const logs = await fetch(API_BASE + '/sync/logs?limit=50').then(r => r.json());
        const tbody = document.getElementById("logs-table");
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

async function purgeAllLogs() {
    if (!confirm('Supprimer tous les logs de synchronisation ?')) return;

    try {
        const res = await fetch(API_BASE + '/logs/purge-all', { method: 'POST' });
        const data = await res.json();
        alert('✅ ' + data.message);
        await loadSystemLogs();
    } catch (e) {
        alert('❌ Erreur: ' + e);
    }
}

// ==================== CONFIGURATION ====================

async function loadConfig() {
    try {
        const response = await fetch(API_BASE + '/config');
        configData = await response.json();

        // Grouper les configurations par catégorie
        const categories = {
            prowlarr: { title: '🔍 Prowlarr', icon: '🔍', fields: {} },
            radarr: { title: '🎬 Radarr', icon: '🎬', fields: {} },
            sonarr: { title: '📺 Sonarr', icon: '📺', fields: {} },
            rss: { title: '📡 RSS & Domaine', icon: '📡', fields: {} },
            sync: { title: '🔄 Synchronisation', icon: '🔄', fields: {} },
            other: { title: '⚙️ Autres Paramètres', icon: '⚙️', fields: {} }
        };

        // Classer les champs par catégorie
        Object.entries(configData).forEach(([key, data]) => {
            if (key.startsWith('PROWLARR_')) {
                categories.prowlarr.fields[key] = data;
            } else if (key.startsWith('RADARR_')) {
                categories.radarr.fields[key] = data;
            } else if (key.startsWith('SONARR_')) {
                categories.sonarr.fields[key] = data;
            } else if (key.startsWith('RSS_')) {
                categories.rss.fields[key] = data;
            } else if (key.includes('SYNC') || key.includes('RETENTION') || key.includes('PURGE') || key.includes('DEDUP')) {
                categories.sync.fields[key] = data;
            } else {
                categories.other.fields[key] = data;
            }
        });

        // Générer le HTML avec layout en grille
        const form = document.getElementById("config-form");
        let html = '<div class="apps-grid">';

        Object.entries(categories).forEach(([catKey, category]) => {
            // Ignorer les catégories vides
            if (Object.keys(category.fields).length === 0) return;

            html += `
                <div class="section">
                    <div class="section-title">${category.title}</div>`;

            Object.entries(category.fields).forEach(([key, data]) => {
                const displayName = key.replace(/_/g, ' ').toLowerCase()
                    .split(' ')
                    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                    .join(' ');

                html += `
                    <div class="form-group">
                        <label for="${key}">${displayName}</label>
                        <input type="text"
                               id="${key}"
                               name="${key}"
                               value="${data.value || ''}"
                               placeholder="${data.description}">
                        <div class="help-text">${data.description}</div>
                    </div>`;
            });

            html += `</div>`;
        });

        html += '</div>';
        form.innerHTML = html;
    } catch (e) {
        alert("Erreur lors du chargement de la config: " + e);
    }
}

async function saveConfig() {
    try {
        const updates = {};
        Object.keys(configData).forEach(key => {
            const input = document.getElementById(key);
            if (input) {
                updates[key] = {
                    value: input.value,
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
            alert("✅ Configuration sauvegardée!");
            loadConfig();
        } else {
            alert("❌ Erreur lors de la sauvegarde");
        }
    } catch (e) {
        alert("❌ Erreur: " + e);
    }
}

// ==================== SYNC ====================

async function syncNow() {
    const btn = document.getElementById("sync-btn");
    btn.disabled = true;
    btn.textContent = "⏳ Sync en cours...";

    try {
        const triggerRes = await fetch(API_BASE + '/sync/trigger', { method: "POST" });
        const triggerData = await triggerRes.json();

        if (triggerData.status === "already_running") {
            alert("⏳ Une synchronisation est déjà en cours");
            btn.disabled = false;
            btn.textContent = "📡 Sync Maintenant";
            return;
        }

        let syncCompleted = false;
        const maxAttempts = 30;

        for (let i = 0; i < maxAttempts; i++) {
            await new Promise(resolve => setTimeout(resolve, 1000));

            const statusRes = await fetch(API_BASE + '/sync/status');
            const status = await statusRes.json();

            if (!status.is_running) {
                syncCompleted = true;

                if (status.last_error) {
                    alert("❌ Erreur sync: " + status.last_error);
                } else {
                    alert("✅ Synchronisation terminée !");
                }
                break;
            }
        }

        if (!syncCompleted) {
            alert("⏳ La synchronisation prend plus de temps que prévu. Vérifiez les logs.");
        }

        await refreshData();

    } catch (e) {
        alert("❌ Erreur: " + e);
    } finally {
        btn.disabled = false;
        btn.textContent = "📡 Sync Maintenant";
    }
}

// ==================== ADMIN ====================

async function loadAdminTab() {
    await loadAdminStats();
    await loadSystemLogs();
}

async function loadAdminStats() {
    try {
        const [detailedStats, torrentsData] = await Promise.all([
            fetch(API_BASE + '/stats/detailed').then(r => r.json()),
            fetch(API_BASE + '/torrents').then(r => r.json())
        ]);

        document.getElementById('admin-db-size').textContent = detailedStats.database.size_mb;
        document.getElementById('admin-db-grabs').textContent = detailedStats.database.grabs;
        document.getElementById('admin-db-logs').textContent = detailedStats.database.sync_logs;

        document.getElementById('admin-torrent-count').textContent = torrentsData.total;
        const totalSize = torrentsData.torrents.reduce((acc, t) => acc + t.size_mb, 0);
        document.getElementById('admin-torrent-size').textContent = totalSize.toFixed(2);

        // Compter les orphelins
        const orphans = torrentsData.torrents.filter(t => !t.has_grab).length;
        document.getElementById('admin-torrent-orphans').textContent = orphans;

        document.getElementById('admin-memory').textContent = detailedStats.system.memory_mb;
        document.getElementById('admin-cpu').textContent = detailedStats.system.cpu_percent;

        const uptime = detailedStats.system.uptime_seconds;
        const hours = Math.floor(uptime / 3600);
        const minutes = Math.floor((uptime % 3600) / 60);
        document.getElementById('admin-uptime').textContent = hours + 'h ' + minutes + 'm';

    } catch (e) {
        console.error("Erreur loadAdminStats:", e);
        alert("❌ Erreur lors du chargement des stats: " + e);
    }
}

async function loadSystemLogs() {
    const level = document.getElementById('log-level-filter').value;

    try {
        // Récupérer tous les logs de sync
        const res = await fetch(API_BASE + '/sync/logs?limit=100');
        const logs = await res.json();

        const container = document.getElementById('system-logs-container');

        if (logs.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: #888; padding: 20px;">Aucun log trouvé</p>';
            return;
        }

        // Filtrer par niveau
        let filteredLogs = logs;
        if (level === 'success') {
            filteredLogs = logs.filter(l => l.status === 'success');
        } else if (level === 'error') {
            filteredLogs = logs.filter(l => l.status !== 'success');
        }

        if (filteredLogs.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: #888; padding: 20px;">Aucun log trouvé pour ce niveau</p>';
            return;
        }

        const logIcons = {
            'success': '✅',
            'error': '❌'
        };

        container.innerHTML = filteredLogs.map(log => {
            const logLevel = log.status === 'success' ? 'success' : 'error';
            const icon = logIcons[logLevel] || '•';
            const timestamp = new Date(log.sync_at).toLocaleString('fr-FR');
            const message = `Sync: ${log.grabs_count} grabs récupérés, ${log.deduplicated_count || 0} doublons ignorés`;
            const details = log.error ? `Erreur: ${log.error}` : '';

            return `
                <div class="log-item ${logLevel}" style="position: relative;">
                    <div class="log-header">
                        <span class="log-level ${logLevel}">
                            ${icon} ${logLevel.toUpperCase()}
                        </span>
                        <span class="log-time">${timestamp}</span>
                    </div>
                    <div class="log-message">${message}</div>
                    ${details ? '<div class="log-details">' + details + '</div>' : ''}
                </div>
            `;
        }).join('');

    } catch (e) {
        console.error("Erreur loadSystemLogs:", e);
        alert("❌ Erreur lors du chargement des logs: " + e);
    }
}

async function clearCache() {
    if (confirm("Vider tous les caches (trackers + imports Radarr/Sonarr) ?")) {
        try {
            const res = await fetch(API_BASE + '/cache/clear', { method: "POST" });
            const data = await res.json();
            alert("✅ " + data.message);
            await loadAdminStats();
        } catch (e) {
            alert("❌ Erreur: " + e);
        }
    }
}

async function vacuumDatabase() {
    if (confirm("Optimiser la base de données (VACUUM) ? Cela peut prendre quelques secondes.")) {
        try {
            const res = await fetch(API_BASE + '/db/vacuum', { method: "POST" });
            const data = await res.json();
            alert("✅ " + data.message + "\nEspace libéré: " + data.saved_mb + " MB");
            await loadAdminStats();
        } catch (e) {
            alert("❌ Erreur: " + e);
        }
    }
}

async function purgeOldGrabs() {
    const hours = prompt("Supprimer les grabs plus anciens que combien d'heures ?\n(168 = 7 jours, 336 = 14 jours, 720 = 30 jours)", "168");

    if (hours === null) return;

    const hoursInt = parseInt(hours);
    if (isNaN(hoursInt) || hoursInt < 1) {
        alert("❌ Valeur invalide");
        return;
    }

    if (confirm("Supprimer tous les grabs > " + hoursInt + "h ?")) {
        try {
            const res = await fetch(API_BASE + '/purge/retention?hours=' + hoursInt, { method: "POST" });
            const data = await res.json();
            alert("✅ " + data.message);
            await refreshData();
            await loadAdminStats();
        } catch (e) {
            alert("❌ Erreur: " + e);
        }
    }
}

// ==================== TORRENTS MANAGEMENT ====================

async function loadTorrents() {
    try {
        const res = await fetch(API_BASE + '/torrents');
        const data = await res.json();

        // Mettre à jour les statistiques
        document.getElementById('torrents-total').textContent = data.total;

        const totalSize = data.torrents.reduce((acc, t) => acc + t.size_mb, 0);
        document.getElementById('torrents-size').textContent = totalSize.toFixed(2);

        const withGrab = data.torrents.filter(t => t.has_grab).length;
        document.getElementById('torrents-with-grab').textContent = withGrab;

        const orphans = data.torrents.filter(t => !t.has_grab).length;
        document.getElementById('torrents-orphans').textContent = orphans;

        // Remplir le tableau
        const tbody = document.getElementById('torrents-table');
        if (data.torrents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #888;">Aucun fichier torrent</td></tr>';
            return;
        }

        tbody.innerHTML = data.torrents.map(t => {
            const statusColor = t.has_grab ? '#00aa00' : '#ff6b6b';
            const statusText = t.has_grab ? '✓ Avec Grab' : '⚠ Orphelin';
            const grabDate = t.grabbed_at ? new Date(t.grabbed_at).toLocaleString('fr-FR') : '-';

            return `
                <tr>
                    <td><input type="checkbox" class="torrent-checkbox" value="${t.filename}"></td>
                    <td style="font-family: monospace; font-size: 11px; word-break: break-all;">${t.filename}</td>
                    <td>${t.title}</td>
                    <td><strong style="color: #1e90ff;">${t.tracker}</strong></td>
                    <td class="date">${grabDate}</td>
                    <td>${t.size_mb} MB</td>
                    <td><span style="color: ${statusColor}; font-weight: bold;">${statusText}</span></td>
                    <td>
                        <a href="/torrents/${encodeURIComponent(t.filename)}" target="_blank" class="button" style="text-decoration: none; padding: 5px 10px; font-size: 12px; display: inline-block;">📥 DL</a>
                        <button class="button danger" onclick="deleteSingleTorrent('${t.filename}')" style="padding: 5px 10px; font-size: 12px; margin-left: 5px;">🗑️</button>
                    </td>
                </tr>
            `;
        }).join('');

        // Gérer l'affichage du bouton d'actions groupées
        updateBulkActionsVisibility();

    } catch (e) {
        console.error("Erreur loadTorrents:", e);
        alert("❌ Erreur lors du chargement des torrents: " + e);
    }
}

function toggleAllTorrents() {
    const selectAll = document.getElementById('select-all-torrents');
    const checkboxes = document.querySelectorAll('.torrent-checkbox');
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
    updateBulkActionsVisibility();
}

function updateBulkActionsVisibility() {
    const checkboxes = document.querySelectorAll('.torrent-checkbox:checked');
    const bulkActions = document.getElementById('bulk-actions');
    if (checkboxes.length > 0) {
        bulkActions.style.display = 'flex';
    } else {
        bulkActions.style.display = 'none';
    }
}

async function deleteSingleTorrent(filename) {
    if (!confirm(`Supprimer le torrent "${filename}" ?`)) return;

    try {
        const res = await fetch(API_BASE + '/torrents/' + encodeURIComponent(filename), {
            method: 'DELETE'
        });

        if (res.ok) {
            alert('✅ Torrent supprimé');
            await loadTorrents();
        } else {
            alert('❌ Erreur lors de la suppression');
        }
    } catch (e) {
        alert('❌ Erreur: ' + e);
    }
}

async function deleteBulkTorrents() {
    const checkboxes = document.querySelectorAll('.torrent-checkbox:checked');
    const filenames = Array.from(checkboxes).map(cb => cb.value);

    if (filenames.length === 0) {
        alert('⚠️ Aucun torrent sélectionné');
        return;
    }

    if (!confirm(`Supprimer ${filenames.length} torrent(s) sélectionné(s) ?`)) return;

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

        alert(`✅ ${successCount} torrent(s) supprimé(s)${errorCount > 0 ? ', ' + errorCount + ' erreur(s)' : ''}`);
        await loadTorrents();

    } catch (e) {
        alert('❌ Erreur: ' + e);
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
        await loadAdminStats(); // Rafraîchir les stats admin
    } catch (e) {
        alert('❌ Erreur: ' + e);
    }
}

// ==================== HISTORY LIMITS TEST ====================

async function testHistoryLimits() {
    const btn = event.target;
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "⏳ Test en cours...";

    try {
        const res = await fetch(API_BASE + '/test-history-limits', { method: "POST" });

        if (!res.ok) {
            throw new Error("Erreur HTTP " + res.status);
        }

        const data = await res.json();

        // Afficher les résultats
        const resultsDiv = document.getElementById('history-test-results');
        resultsDiv.style.display = 'block';

        // Timestamp
        const timestamp = new Date(data.results.timestamp).toLocaleString('fr-FR');
        document.getElementById('history-test-timestamp').textContent =
            "Test effectué le " + timestamp;

        // Formater les résultats de manière lisible
        const results = data.results;
        let output = "=".repeat(80) + "\n";
        output += "TEST DES LIMITES D'HISTORIQUE\n";
        output += "=".repeat(80) + "\n\n";

        // Configuration
        output += "📋 CONFIGURATION\n";
        output += "-".repeat(80) + "\n";
        output += "Prowlarr URL:      " + results.configuration.prowlarr_url + "\n";
        output += "Prowlarr pageSize: " + results.configuration.prowlarr_page_size + "\n";
        output += "Radarr activé:     " + results.configuration.radarr_enabled + "\n";
        output += "Sonarr activé:     " + results.configuration.sonarr_enabled + "\n";
        output += "Sync interval:     " + results.configuration.sync_interval_seconds + "s\n";
        output += "Rétention:         " + results.configuration.retention_hours + "h\n\n";

        // Prowlarr
        output += "📡 PROWLARR\n";
        output += "-".repeat(80) + "\n";
        results.prowlarr.tested_page_sizes.forEach(test => {
            const d = test.data;
            if (d.error) {
                output += "pageSize=" + test.page_size + " → ❌ " + d.error + "\n";
            } else {
                output += "pageSize=" + test.page_size + " → ";
                output += d.total + " enregistrements, ";
                output += d.successful_grabs + " grabs réussis\n";
                if (d.oldest_grab) {
                    output += "  Plus ancien: " + new Date(d.oldest_grab).toLocaleString('fr-FR') + "\n";
                }
            }
        });

        output += "\n🔍 ANALYSE\n";
        output += "-".repeat(80) + "\n";
        output += "Type de limitation: " + results.prowlarr.analysis.limitation_type + "\n";
        output += results.prowlarr.analysis.details + "\n";
        output += "\n💡 Recommandation:\n";
        output += results.prowlarr.analysis.recommendation + "\n\n";

        // Radarr
        output += "🎬 RADARR\n";
        output += "-".repeat(80) + "\n";
        if (results.radarr.error) {
            output += "⚠️  " + results.radarr.error + "\n\n";
        } else {
            output += "Total: " + results.radarr.total + " | Grabs: " + results.radarr.grabs + "\n";
            if (results.radarr.oldest_grab) {
                output += "Plus ancien: " + new Date(results.radarr.oldest_grab).toLocaleString('fr-FR') + "\n";
            }
            output += "\n";
        }

        // Sonarr
        output += "📺 SONARR\n";
        output += "-".repeat(80) + "\n";
        if (results.sonarr.error) {
            output += "⚠️  " + results.sonarr.error + "\n\n";
        } else {
            output += "Total: " + results.sonarr.total + " | Grabs: " + results.sonarr.grabs + "\n";
            if (results.sonarr.oldest_grab) {
                output += "Plus ancien: " + new Date(results.sonarr.oldest_grab).toLocaleString('fr-FR') + "\n";
            }
            output += "\n";
        }

        // Comparaison
        output += "🔄 COMPARAISON DES PÉRIODES\n";
        output += "-".repeat(80) + "\n";
        if (results.comparison.prowlarr_oldest) {
            output += "Prowlarr: " + new Date(results.comparison.prowlarr_oldest).toLocaleString('fr-FR') + "\n";
        }
        if (results.comparison.radarr_oldest) {
            output += "Radarr:   " + new Date(results.comparison.radarr_oldest).toLocaleString('fr-FR') + "\n";
        }
        if (results.comparison.sonarr_oldest) {
            output += "Sonarr:   " + new Date(results.comparison.sonarr_oldest).toLocaleString('fr-FR') + "\n";
        }

        document.getElementById('history-test-content').textContent = output;

        // Lien de téléchargement
        const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        document.getElementById('history-test-download').href = url;

        // Scroll vers les résultats
        resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });

        alert("✅ Test terminé !\n\nRésultats sauvegardés dans:\n" + data.output_file);

    } catch (e) {
        console.error("Erreur testHistoryLimits:", e);
        alert("❌ Erreur lors du test: " + e);
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// ==================== AUTHENTICATION & SECURITY ====================

async function checkSetupStatus() {
    try {
        // Lire l'état initial injecté par le serveur au lieu d'appeler l'API
        if (window.INITIAL_STATE && window.INITIAL_STATE.first_run) {
            console.log("🔧 Premier lancement détecté - redirection vers /setup");
            window.location.href = '/setup';
            return false; // Bloquer l'initialisation
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
            document.getElementById('security-tab').style.display = 'block';
            document.getElementById('auth-info').style.display = 'block';
            document.getElementById('username-display').textContent = initialState.username || 'Utilisateur';
            document.getElementById('security-username').textContent = initialState.username || 'Utilisateur';
        }

        return true; // Continuer
    } catch (error) {
        console.error("Erreur vérification auth:", error);
        return true; // En cas d'erreur, continuer (éviter de bloquer)
    }
}

async function logout() {
    if (!confirm('Êtes-vous sûr de vouloir vous déconnecter ?')) {
        return;
    }

    try {
        const res = await fetch('/api/auth/logout', { method: 'POST' });
        if (res.ok) {
            window.location.href = '/login';
        }
    } catch (error) {
        alert('Erreur lors de la déconnexion');
        console.error(error);
    }
}

function showChangePasswordForm() {
    document.getElementById('change-password-form').style.display = 'block';
}

function hideChangePasswordForm() {
    document.getElementById('change-password-form').style.display = 'none';
    document.getElementById('old-password').value = '';
    document.getElementById('new-password').value = '';
}

async function changePassword() {
    const oldPassword = document.getElementById('old-password').value;
    const newPassword = document.getElementById('new-password').value;

    if (!oldPassword || !newPassword) {
        alert('Veuillez remplir tous les champs');
        return;
    }

    if (newPassword.length < 8) {
        alert('Le nouveau mot de passe doit contenir au moins 8 caractères');
        return;
    }

    try {
        const res = await fetch('/api/auth/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
        });

        const data = await res.json();

        if (data.success) {
            alert('✅ Mot de passe changé avec succès');
            hideChangePasswordForm();
        } else {
            alert('❌ Erreur: ' + (data.detail || 'Ancien mot de passe incorrect'));
        }
    } catch (error) {
        alert('❌ Erreur lors du changement de mot de passe');
        console.error(error);
    }
}

// ==================== API KEYS MANAGEMENT ====================

async function loadApiKeys() {
    try {
        const res = await fetch('/api/auth/api-keys');
        const data = await res.json();

        const list = document.getElementById('api-keys-list');

        if (!data.api_keys || data.api_keys.length === 0) {
            list.innerHTML = '<p style="color: #888; text-align: center;">Aucune API Key configurée</p>';
            return;
        }

        let html = '<table style="margin-top: 10px;"><thead><tr><th>Nom</th><th>Clé</th><th>Statut</th><th>Créée le</th><th>Actions</th></tr></thead><tbody>';

        data.api_keys.forEach(key => {
            const statusColor = key.enabled ? '#00aa00' : '#888';
            const statusText = key.enabled ? '✅ Activée' : '❌ Désactivée';
            const createdAt = new Date(key.created_at).toLocaleString('fr-FR');

            html += `
                <tr>
                    <td><strong>${key.name}</strong></td>
                    <td>
                        <code style="background: #0f0f0f; padding: 4px 8px; border-radius: 4px; font-size: 11px;">${key.key_masked || key.key}</code>
                        <button class="copy-btn" onclick="copyApiKey('${key.key}')" style="margin-left: 10px;">📋 Copier</button>
                    </td>
                    <td style="color: ${statusColor};">${statusText}</td>
                    <td style="color: #888; font-size: 12px;">${createdAt}</td>
                    <td>
                        <button class="button" style="font-size: 12px; padding: 5px 10px;" onclick="toggleApiKey('${key.key}', ${!key.enabled})">
                            ${key.enabled ? '⏸️ Désactiver' : '▶️ Activer'}
                        </button>
                        <button class="button danger" style="font-size: 12px; padding: 5px 10px;" onclick="deleteApiKey('${key.key}')">🗑️</button>
                    </td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        list.innerHTML = html;
    } catch (error) {
        console.error("Erreur chargement API keys:", error);
        document.getElementById('api-keys-list').innerHTML = '<p style="color: #ff4444;">Erreur lors du chargement des API keys</p>';
    }
}

async function createApiKey() {
    const name = document.getElementById('api-key-name').value.trim();

    if (!name) {
        alert("Veuillez donner un nom à l'API Key");
        return;
    }

    try {
        const res = await fetch('/api/auth/api-keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, enabled: true })
        });

        const data = await res.json();

        if (data.key) {
            alert(`✅ API Key créée avec succès !\n\nClé: ${data.key}\n\nCopiez-la maintenant, elle ne sera plus affichée en entier.`);
            document.getElementById('api-key-name').value = '';
            await loadApiKeys();
        } else {
            alert("❌ Erreur lors de la création de l'API Key");
        }
    } catch (error) {
        alert("❌ Erreur lors de la création de l'API Key");
        console.error(error);
    }
}

function copyApiKey(key) {
    navigator.clipboard.writeText(key).then(() => {
        alert('✅ API Key copiée dans le presse-papiers!');
    }).catch(() => {
        alert('❌ Erreur lors de la copie');
    });
}

async function deleteApiKey(key) {
    if (!confirm('Êtes-vous sûr de vouloir supprimer cette API Key ?')) {
        return;
    }

    try {
        const res = await fetch(`/api/auth/api-keys/${encodeURIComponent(key)}`, {
            method: 'DELETE'
        });

        const data = await res.json();

        if (data.success) {
            alert('✅ API Key supprimée');
            await loadApiKeys();
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
        const res = await fetch(`/api/auth/api-keys/${encodeURIComponent(key)}?enabled=${enabled}`, {
            method: 'PATCH'
        });

        const data = await res.json();

        if (data.success) {
            alert(`✅ API Key ${enabled ? 'activée' : 'désactivée'}`);
            await loadApiKeys();
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
    const form = document.getElementById('login-form');
    const errorMessage = document.getElementById('error-message');
    const loginBtn = document.getElementById('login-btn');
    const loading = document.getElementById('loading');

    if (!form) return; // Not on login page

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Récupérer les valeurs
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

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
                document.getElementById('password').value = '';
                document.getElementById('password').focus();
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
    document.getElementById('username').focus();
}

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', async () => {
    console.log("🚀 Initialisation Grab2RSS...");

    // Check if we're on the login page
    if (document.getElementById('login-form')) {
        initLoginPage();
        return;
    }

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

        // 3. Initialiser le dashboard
        await loadTrackers();
        await refreshData();
        await loadGrabs();

        // Refresh data every 30 seconds
        setInterval(refreshData, 30000);

        console.log("✅ Application initialisée");
    } catch (error) {
        console.error("❌ Erreur initialisation:", error);
        alert("Erreur lors du chargement de l'application. Vérifiez la console (F12).");
    }
});

// Event listener for torrent checkboxes
document.addEventListener('change', (e) => {
    if (e.target.classList.contains('torrent-checkbox')) {
        updateBulkActionsVisibility();
    }
});
