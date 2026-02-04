// ==================== GLOBAL VARIABLES ====================

const API_BASE = "/api";
let configData = {};
let statsData = {};
let allTrackers = [];
let trackerChartInstance = null;
let grabsByDayChartInstance = null;
let topTorrentsChartInstance = null;

// ==================== DOM HELPERS ====================

function byId(id) {
    return document.getElementById(id);
}

function setText(id, value) {
    const el = byId(id);
    if (el) el.textContent = value;
}

function setClass(id, value) {
    const el = byId(id);
    if (el) el.className = value;
}

function setHtml(id, value) {
    const el = byId(id);
    if (el) el.innerHTML = value;
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

// ==================== UTILITY FUNCTIONS ====================

// ==================== TRACKERS ====================

async function loadTrackers() {
    try {
        const res = await fetch(API_BASE + '/trackers');
        if (!res.ok) throw new Error('Trackers API error: ' + res.status);

        const data = await res.json();
        allTrackers = data.trackers;

        [byId('tracker-filter-grabs'), byId('tracker-filter-rss')].forEach(select => {
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
    const trackerSelect = byId('tracker-filter-grabs');
    const tbody = byId('grabs-table');
    if (!trackerSelect || !tbody) return;
    const tracker = trackerSelect.value;
    const url = API_BASE + '/grabs?limit=100&tracker=' + encodeURIComponent(tracker);

    try {
        const grabs = await fetch(url).then(r => r.json());
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
        setText("total-grabs", stats.total_grabs);
        setText("storage-size", stats.storage_size_mb);
        setText("latest-grab", stats.latest_grab ? new Date(stats.latest_grab).toLocaleString('fr-FR') : "-");

        // Nouvelles statistiques dashboard
        setText("dashboard-torrent-count", torrentsData.total);
        const totalSize = torrentsData.torrents.reduce((acc, t) => acc + t.size_mb, 0);
        setText("dashboard-torrent-size", totalSize.toFixed(2));

        // Nombre de trackers différents
        const uniqueTrackers = new Set(stats.tracker_stats.map(t => t.tracker)).size;
        setText("dashboard-trackers-count", uniqueTrackers);

        // Grabs aujourd'hui (dernières 24h)
        const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
        const grabsToday = stats.grabs_by_day[0]?.count || 0;
        setText("dashboard-grabs-today", grabsToday);

        // Uptime
        const uptime = detailedStats.system.uptime_seconds;
        const hours = Math.floor(uptime / 3600);
        const minutes = Math.floor((uptime % 3600) / 60);
        setText("dashboard-uptime", hours + 'h ' + minutes + 'm');

        // Statut sync
        const statusEl = byId("sync-status");

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

        if (statusEl) {
            statusEl.className = statusClass;
            statusEl.textContent = statusText;
        }

        setText("next-sync", sync.next_sync ? 'Prochain: ' + new Date(sync.next_sync).toLocaleString('fr-FR') : "-");
    } catch (e) {
        console.error("❌ Erreur refreshData:", e);
    }
}

// ==================== LOGS ====================

async function loadLogs() {
    try {
        const logs = await fetch(API_BASE + '/sync/logs?limit=50').then(r => r.json());
        const tbody = byId("logs-table");
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
        const form = byId("config-form");
        if (!form) return;
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
    const btn = byId("sync-btn");
    if (!btn) return;
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

async function loadAdminStats() {
    try {
        const [detailedStats, torrentsData] = await Promise.all([
            fetch(API_BASE + '/stats/detailed').then(r => r.json()),
            fetch(API_BASE + '/torrents').then(r => r.json())
        ]);

        setText('admin-db-size', detailedStats.database.size_mb);
        setText('admin-db-grabs', detailedStats.database.grabs);
        setText('admin-db-logs', detailedStats.database.sync_logs);

        setText('admin-torrent-count', torrentsData.total);
        const totalSize = torrentsData.torrents.reduce((acc, t) => acc + t.size_mb, 0);
        setText('admin-torrent-size', totalSize.toFixed(2));

        // Compter les orphelins
        const orphans = torrentsData.torrents.filter(t => !t.has_grab).length;
        setText('admin-torrent-orphans', orphans);

        setText('admin-memory', detailedStats.system.memory_mb);
        setText('admin-cpu', detailedStats.system.cpu_percent);

        const uptime = detailedStats.system.uptime_seconds;
        const hours = Math.floor(uptime / 3600);
        const minutes = Math.floor((uptime % 3600) / 60);
        setText('admin-uptime', hours + 'h ' + minutes + 'm');

    } catch (e) {
        console.error("Erreur loadAdminStats:", e);
        alert("❌ Erreur lors du chargement des stats: " + e);
    }
}

async function loadSystemLogs() {
    const levelSelect = byId('log-level-filter');
    if (!levelSelect) return;
    const level = levelSelect.value;

    try {
        // Récupérer tous les logs de sync
        const res = await fetch(API_BASE + '/sync/logs?limit=100');
        const logs = await res.json();

        const container = byId('system-logs-container');
        if (!container) return;

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

// ==================== TORRENTS MANAGEMENT ====================

async function loadTorrents() {
    try {
        const res = await fetch(API_BASE + '/torrents');
        const data = await res.json();

        // Mettre à jour les statistiques
        setText('torrents-total', data.total);

        const totalSize = data.torrents.reduce((acc, t) => acc + t.size_mb, 0);
        setText('torrents-size', totalSize.toFixed(2));

        const withGrab = data.torrents.filter(t => t.has_grab).length;
        setText('torrents-with-grab', withGrab);

        const orphans = data.torrents.filter(t => !t.has_grab).length;
        setText('torrents-orphans', orphans);

        // Remplir le tableau
        const tbody = byId('torrents-table');
        if (!tbody) return;
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
    const selectAll = byId('select-all-torrents');
    if (!selectAll) return;
    const checkboxes = document.querySelectorAll('.torrent-checkbox');
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
    updateBulkActionsVisibility();
}

function updateBulkActionsVisibility() {
    const checkboxes = document.querySelectorAll('.torrent-checkbox:checked');
    const bulkActions = byId('bulk-actions');
    if (!bulkActions) return;
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
    const form = byId('change-password-form');
    if (form) form.style.display = 'block';
}

function hideChangePasswordForm() {
    const form = byId('change-password-form');
    if (form) form.style.display = 'none';
    const oldPassword = byId('old-password');
    const newPassword = byId('new-password');
    if (oldPassword) oldPassword.value = '';
    if (newPassword) newPassword.value = '';
}

async function changePassword() {
    const oldPasswordInput = byId('old-password');
    const newPasswordInput = byId('new-password');
    if (!oldPasswordInput || !newPasswordInput) return;
    const oldPassword = oldPasswordInput.value;
    const newPassword = newPasswordInput.value;

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

        const list = byId('api-keys-list');
        if (!list) return;

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
    const nameInput = byId('api-key-name');
    if (!nameInput) return;
    const name = nameInput.value.trim();

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
            nameInput.value = '';
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
    setActiveNav(page);
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
                '#storage-size',
                '#sync-status'
            ]);
            await loadTrackers();
            await refreshData();
            if (typeof Chart !== 'undefined') {
                await loadStats();
            }
            setInterval(refreshData, 30000);
        } else if (page === 'grabs') {
            ensureElements('grabs', ['#tracker-filter-grabs', '#grabs-table']);
            await loadTrackers();
            await loadGrabs();
        } else if (page === 'torrents') {
            ensureElements('torrents', ['#torrents-table', '#torrents-total']);
            await loadTorrents();
        } else if (page === 'logs') {
            ensureElements('logs', ['#logs-table', '#log-level-filter', '#system-logs-container']);
            await loadLogs();
            await loadSystemLogs();
        } else if (page === 'configuration') {
            ensureElements('configuration', ['#config-form']);
            await loadConfig();
        } else if (page === 'security') {
            ensureElements('security', ['#api-keys-list']);
            await loadApiKeys();
        } else if (page === 'setup') {
            initSetupPage();
        }

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
    const container = document.querySelector('.page-shell[data-first-run][data-config-exists]');
    if (!container) return;

    const firstRun = container.dataset.firstRun === 'true';
    const configExists = container.dataset.configExists === 'true';
    if (!firstRun && configExists) {
        window.location.href = '/';
        return;
    }

    const form = byId('setupForm');
    const alertEl = byId('alert');
    const loadingEl = byId('loading');
    const authToggle = byId('auth_enabled');
    const authFields = byId('auth_fields');

    if (!form || !alertEl || !loadingEl || !authToggle || !authFields) {
        warnMissing('setup', '#setupForm, #alert, #loading, #auth_enabled, #auth_fields');
        return;
    }

    const showAlert = (message, type) => {
        alertEl.textContent = message;
        alertEl.className = `alert ${type}`;
        alertEl.style.display = 'block';

        if (type === 'success' && !message.includes('Test')) {
            setTimeout(() => {
                alertEl.style.display = 'none';
            }, 3000);
        }
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
    };

    let testInFlight = false;
    let submitInFlight = false;

    const setButtonState = (button, loading, loadingText) => {
        if (!button) return;
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.textContent;
        }
        button.disabled = loading;
        button.textContent = loading ? loadingText : button.dataset.originalText;
    };

    const testConnection = async () => {
        if (testInFlight) return;
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
        const testButton = document.querySelector('[data-action="test-connection"]');
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

    const submitSetup = async (event) => {
        event.preventDefault();
        if (submitInFlight) return;

        const formData = new FormData(form);
        const config = {
            prowlarr_url: formData.get('prowlarr_url'),
            prowlarr_api_key: formData.get('prowlarr_api_key'),
            prowlarr_history_page_size: parseInt(formData.get('prowlarr_history_page_size')),

            radarr_enabled: true,
            radarr_url: formData.get('radarr_url'),
            radarr_api_key: formData.get('radarr_api_key'),

            sonarr_enabled: true,
            sonarr_url: formData.get('sonarr_url'),
            sonarr_api_key: formData.get('sonarr_api_key'),

            sync_interval: parseInt(formData.get('sync_interval')),
            retention_hours: parseInt(formData.get('retention_hours')),
            auto_purge: byId('auto_purge')?.checked || false,
            dedup_hours: 168,

            rss_domain: window.location.hostname,
            rss_scheme: window.location.protocol.replace(':', ''),
            rss_title: 'grabb2RSS',
            rss_description: 'Prowlarr to RSS Feed',

            auth_enabled: authToggle.checked,
            auth_username: formData.get('auth_username') || '',
            auth_password: formData.get('auth_password') || ''
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
        const submitButton = document.querySelector('[data-action="submit-setup"]');
        setButtonState(submitButton, true, 'Sauvegarde...');
        form.style.display = 'none';
        loadingEl.style.display = 'block';

        try {
            const response = await fetch('/api/setup/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            const data = await response.json();

            if (data.success) {
                showNotification('Configuration enregistrée', 'success');
                showAlert('Configuration enregistrée ! Redirection...', 'success');
                setTimeout(() => {
                    window.location.href = '/';
                }, 2000);
            } else {
                form.style.display = 'block';
                loadingEl.style.display = 'none';
                showAlert('Erreur: ' + (data.error || data.message || 'Impossible de sauvegarder'), 'error');
            }
        } catch (error) {
            form.style.display = 'block';
            loadingEl.style.display = 'none';
            showAlert('Erreur: ' + error.message, 'error');
        } finally {
            submitInFlight = false;
            setButtonState(submitButton, false);
        }
    };

    toggleAuthFields();

    authToggle.addEventListener('change', toggleAuthFields);
    const testButton = document.querySelector('[data-action="test-connection"]');
    if (testButton) testButton.addEventListener('click', testConnection);
    form.addEventListener('submit', submitSetup);
}

// Event listener for torrent checkboxes
document.addEventListener('change', (e) => {
    if (e.target.classList.contains('torrent-checkbox')) {
        updateBulkActionsVisibility();
    }
});
