// rss-manager.js
// Gestion des API keys et URLs RSS

class RSSManager {
    constructor() {
        this.apiKeys = [];
        this.rssUrls = [];
        this.availableTokens = [];
        this.selectedToken = '';
        this.selectedTokenId = '';
        this.apiKeyVault = new Map();
        this.tokenVault = new Map();
        this.copyVault = new Map();
        this._copySeq = 0;
        this._filterTimer = null;
    }

    escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    maskSecret(value, visibleStart = 8, visibleEnd = 4) {
        const raw = String(value ?? '');
        if (!raw) return '';
        if (raw.length <= visibleStart + visibleEnd + 3) return `${raw.slice(0, 3)}***`;
        return `${raw.slice(0, visibleStart)}…${raw.slice(-visibleEnd)}`;
    }

    maskUrlApiKey(rawUrl) {
        const value = String(rawUrl ?? '');
        if (!value) return '';
        return value.replace(/([?&]apikey=)([^&]+)/i, (match, prefix, token) => {
            return `${prefix}${this.maskSecret(token, 6, 3)}`;
        });
    }

    keyId(prefix, value, index) {
        const raw = String(value ?? '');
        const safe = raw.replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 16) || 'k';
        return `${prefix}-${index}-${safe}`;
    }

    setCopyRef(ref, value) {
        if (!ref) return;
        this.copyVault.set(ref, String(value ?? ''));
    }

    getCopyRef(ref) {
        if (!ref) return '';
        return this.copyVault.get(ref) || '';
    }

    findTokenIdByValue(tokenValue) {
        if (!tokenValue) return '';
        for (const [id, value] of this.tokenVault.entries()) {
            if (value === tokenValue) return id;
        }
        return '';
    }

    // Charger les API keys
    async loadApiKeys() {
        try {
            const response = await fetch('/api/auth/keys');
            const data = await response.json();
            this.apiKeys = data.keys || [];
            this.apiKeyVault.clear();
            this.apiKeys.forEach((key, index) => {
                this.apiKeyVault.set(this.keyId('api', key.key, index), key.key || '');
            });
            return this.apiKeys;
        } catch (error) {
            console.error('Erreur chargement API keys:', error);
            return [];
        }
    }

    // Générer une nouvelle API key
    async generateApiKey(requestedName = '') {
        try {
            const payload = requestedName && requestedName.trim()
                ? { name: requestedName.trim() }
                : {};
            const response = await fetch('/api/auth/keys/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error('Erreur génération API key');
            }

            const data = await response.json();
            await this.loadApiKeys();
            await this.loadRSSUrls();

            return data;
        } catch (error) {
            console.error('Erreur génération API key:', error);
            throw error;
        }
    }

    // Supprimer une API key
    async deleteApiKey(key) {
        try {
            const response = await fetch(`/api/auth/keys/${key}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error('Erreur suppression API key');
            }

            await this.loadApiKeys();
            await this.loadRSSUrls();

            return true;
        } catch (error) {
            console.error('Erreur suppression API key:', error);
            throw error;
        }
    }

    // Charger les URLs RSS
    async loadRSSUrls() {
        try {
            const token = this.selectedToken ? encodeURIComponent(this.selectedToken) : '';
            const url = token ? `/api/rss/urls?token=${token}` : '/api/rss/urls';
            const response = await fetch(url);
            const data = await response.json();

            if (data.error) {
                this.rssUrls = [];
                this.availableTokens = [];
                this.tokenVault.clear();
                return { error: data.error, message: data.message };
            }

            this.rssUrls = data.urls || [];
            this.availableTokens = data.api_keys || [];
            this.tokenVault.clear();
            this.availableTokens.forEach((tokenData, index) => {
                this.tokenVault.set(this.keyId('token', tokenData.key, index), tokenData.key || '');
            });
            if (data.selected_api_key && data.selected_api_key.key) {
                this.selectedToken = data.selected_api_key.key;
                this.selectedTokenId = this.findTokenIdByValue(this.selectedToken);
            }
            return data;
        } catch (error) {
            console.error('Erreur chargement URLs RSS:', error);
            return { error: true, message: error.message };
        }
    }

    // Copier une URL dans le presse-papiers
    async copyToClipboard(text, buttonElement) {
        try {
            await navigator.clipboard.writeText(text);

            // Feedback visuel
            if (buttonElement) {
                const originalText = buttonElement.innerHTML;
                buttonElement.innerHTML = '✓ Copié !';
                buttonElement.classList.add('copied');

                setTimeout(() => {
                    buttonElement.innerHTML = originalText;
                    buttonElement.classList.remove('copied');
                }, 2000);
            }

            return true;
        } catch (error) {
            console.error('Erreur copie:', error);
            // Fallback pour anciens navigateurs
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                document.body.removeChild(textArea);
                return true;
            } catch (err) {
                document.body.removeChild(textArea);
                return false;
            }
        }
    }

    // Render l'interface API Keys
    renderApiKeysSection(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        let html = `
            <div class="api-keys-section">
                <div class="section-header">
                    <h3>🔑 Clés API</h3>
                    <div class="api-keys-generate">
                        <input id="rss-token-name-input" class="config-input" type="text" placeholder="Nom du token (optionnel)">
                        <button class="btn btn-primary" type="button" data-action="generate-key">
                            Générer une clé
                        </button>
                    </div>
                </div>`;

        if (this.apiKeys.length === 0) {
            html += `
                <div class="info-box">
                    <p><strong>Aucune clé API générée.</strong></p>
                    <p>Générez une clé pour accéder aux flux RSS.</p>
                </div>`;
        } else {
            html += `
                <div class="api-keys-panel">
                    <table>
                        <thead>
                            <tr>
                                <th>Nom</th>
                                <th>Clé</th>
                                <th>Statut</th>
                                <th>Créée le</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>`;

            this.apiKeys.forEach((key, index) => {
                const statusClass = key.enabled ? 'active' : 'inactive';
                const statusText = key.enabled ? 'Active' : 'Inactive';
                const createdAt = new Date(key.created_at).toLocaleDateString();
                const isSelected = this.selectedToken && this.selectedToken === key.key;
                const selectLabel = isSelected ? 'Sélectionné' : 'Sélectionner';
                const selectClass = isSelected ? 'btn-success' : 'btn-secondary';
                const id = this.keyId('api', key.key, index);
                this.apiKeyVault.set(id, key.key || '');

                html += `
                            <tr>
                                <td><strong>${this.escapeHtml(key.name || 'API Key')}</strong></td>
                                <td><code class="api-key-chip" title="Clé masquée">${this.escapeHtml(this.maskSecret(key.key))}</code></td>
                                <td><span class="key-status ${statusClass}">${statusText}</span></td>
                                <td>${createdAt}</td>
                                <td>
                                    <div class="api-key-actions">
                                        <button class="btn btn-sm ${selectClass}" type="button" data-action="select-key" data-key-id="${id}" ${key.enabled ? '' : 'disabled'}>
                                            ${selectLabel}
                                        </button>
                                        <button class="btn btn-sm btn-secondary" type="button" data-action="copy-key" data-key-id="${id}">Copier</button>
                                        <button class="btn btn-sm btn-danger" type="button" data-action="delete-key" data-key-id="${id}">Supprimer</button>
                                    </div>
                                </td>
                            </tr>`;
            });

            html += `
                        </tbody>
                    </table>
                </div>`;
        }

        html += `</div>`;
        container.innerHTML = html;
        this.bindContainerHandlers(container);
    }

    // Render l'interface URLs RSS
    renderRSSUrlsSection(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const filteredUrls = this.getFilteredUrls();
        this.copyVault.clear();
        this._copySeq = 0;
        let html = `<div class="rss-urls-section rss-urls-section--flat">`;

        if (this.rssUrls.length === 0) {
            html += `
                <div class="info-box warning">
                    <p>⚠️ Aucune URL RSS disponible.</p>
                    <p>Générez une clé API d'abord.</p>
                </div>`;
        } else if (filteredUrls.length === 0) {
            html += `
                <div class="info-box warning">
                    <p>Aucun résultat avec les filtres courants.</p>
                    <p>Modifiez la catégorie ou la recherche.</p>
                </div>`;
        } else {
            // Grouper par catégorie
            const principal = filteredUrls.filter(u => u.category === 'principal');
            const trackers = filteredUrls.filter(u => u.category === 'tracker');

            if (principal.length > 0) {
                html += `
                    <div class="rss-group-panel">
                        <div class="rss-group-panel__title">Flux principaux</div>
                        <div class="rss-group-panel__subtitle">Tous les torrents récents</div>`;

                principal.forEach(url => {
                    html += this.renderUrlRow(url);
                });

                html += `</div>`;
            }

            if (trackers.length > 0) {
                html += `
                    <div class="rss-group-panel">
                        <div class="rss-group-panel__title">Flux par tracker</div>
                        <div class="rss-group-panel__subtitle">Sources filtrées par tracker</div>`;

                trackers.forEach(url => {
                    html += this.renderUrlRow(url);
                });

                html += `</div>`;
            }
        }

        html += `</div>`;
        container.innerHTML = html;
        this.bindContainerHandlers(container);
    }

    updateSummary() {
        const totalKeys = this.apiKeys.length;
        const activeKeys = this.apiKeys.filter(key => !!key.enabled).length;
        const totalUrls = this.rssUrls.length;
        const trackerUrls = this.rssUrls.filter(url => url.category === 'tracker').length;

        const setText = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.textContent = String(value);
        };

        setText('rss-summary-keys-total', totalKeys);
        setText('rss-summary-keys-active', activeKeys);
        setText('rss-summary-urls-total', totalUrls);
        setText('rss-summary-urls-trackers', trackerUrls);
    }

    getFilters() {
        const categoryEl = document.getElementById('rss-url-category-filter');
        const searchEl = document.getElementById('rss-url-search');
        return {
            category: categoryEl ? categoryEl.value : '',
            search: searchEl ? searchEl.value.trim().toLowerCase() : ''
        };
    }

    getFilteredUrls() {
        const { category, search } = this.getFilters();
        let rows = this.rssUrls.slice();

        if (category) {
            rows = rows.filter(url => url.category === category);
        }
        if (search) {
            rows = rows.filter(url => {
                const name = String(url.name || '').toLowerCase();
                const desc = String(url.description || '').toLowerCase();
                const link = String(url.url || '').toLowerCase();
                return name.includes(search) || desc.includes(search) || link.includes(search);
            });
        }

        return rows;
    }

    bindPageFilters() {
        const tokenEl = document.getElementById('rss-token-filter');
        const categoryEl = document.getElementById('rss-url-category-filter');
        const searchEl = document.getElementById('rss-url-search');
        if (tokenEl && tokenEl.dataset.bound !== 'true') {
            tokenEl.addEventListener('change', async () => {
                const tokenId = tokenEl.value || '';
                this.selectedTokenId = tokenId;
                this.selectedToken = tokenId ? (this.tokenVault.get(tokenId) || '') : '';
                await this.loadRSSUrls();
                this.updateSummary();
                this.renderRSSUrlsSection('rss-urls-container');
                this.renderTokenFilter();
            });
            tokenEl.dataset.bound = 'true';
        }
        if (categoryEl && categoryEl.dataset.bound !== 'true') {
            categoryEl.addEventListener('change', () => this.renderRSSUrlsSection('rss-urls-container'));
            categoryEl.dataset.bound = 'true';
        }
        if (searchEl && searchEl.dataset.bound !== 'true') {
            searchEl.addEventListener('input', () => {
                if (this._filterTimer) clearTimeout(this._filterTimer);
                this._filterTimer = setTimeout(() => this.renderRSSUrlsSection('rss-urls-container'), 220);
            });
            searchEl.dataset.bound = 'true';
        }
    }

    renderTokenFilter() {
        const tokenEl = document.getElementById('rss-token-filter');
        if (!tokenEl) return;
        const prev = tokenEl.value || '';
        this.tokenVault.clear();
        const options = ['<option value="">Auto</option>'].concat(
            this.availableTokens.map((t, index) => {
                const name = this.escapeHtml(t.name || 'API Key');
                const id = this.keyId('token', t.key, index);
                this.tokenVault.set(id, t.key || '');
                return `<option value="${id}">${name}</option>`;
            })
        );
        tokenEl.innerHTML = options.join('');
        const selectedByValue = this.findTokenIdByValue(this.selectedToken);
        const nextValue = this.selectedTokenId || selectedByValue || prev || '';
        tokenEl.value = nextValue;
    }

    // Render une carte URL
    renderUrlRow(url) {
        const safeName = this.escapeHtml(url.name || '');
        const safeDesc = this.escapeHtml(url.description || '');
        const safeUrl = this.escapeHtml(this.maskUrlApiKey(url.url || ''));
        const rowId = `row-${++this._copySeq}`;

        this.setCopyRef(`${rowId}:url`, url.url || '');

        return `
            <div class="rss-url-row">
                <div class="rss-url-row__meta">
                    <div class="rss-url-row__name">${safeName}</div>
                    <div class="rss-url-row__desc">${safeDesc}</div>
                </div>
                <div class="rss-url-row__control">
                    <div class="copy-field">
                        <input type="text" class="config-input" value="${safeUrl}" readonly data-select="all" title="URL masquée (copie complète via bouton)">
                        <button class="btn btn-sm btn-secondary" type="button" data-action="copy-ref" data-copy-ref="${rowId}:url">Copier config</button>
                    </div>
                </div>
            </div>`;
    }

    // Handlers
    async handleGenerateKey() {
        try {
            const input = document.getElementById('rss-token-name-input');
            const requestedName = input ? input.value.trim() : '';
            await this.generateApiKey(requestedName);
            this.updateSummary();
            this.renderApiKeysSection('api-keys-container');
            this.renderRSSUrlsSection('rss-urls-container');
            this.renderTokenFilter();

            // Afficher message succès
            showNotification('✅ API key générée avec succès !', 'success');
        } catch (error) {
            showNotification('❌ Erreur génération API key', 'error');
        }
    }

    async handleDeleteKey(key, buttonElement = null) {
        try {
            await this.deleteApiKey(key);
            this.updateSummary();
            this.renderApiKeysSection('api-keys-container');
            this.renderRSSUrlsSection('rss-urls-container');
            this.renderTokenFilter();

            showNotification('API key supprimée', 'success');
        } catch (error) {
            showNotification('Erreur suppression API key', 'error');
            if (buttonElement) {
                buttonElement.disabled = false;
                buttonElement.dataset.confirming = 'false';
                buttonElement.classList.remove('btn-warning');
                buttonElement.classList.add('btn-danger');
                buttonElement.textContent = 'Supprimer';
            }
        }
    }

    async copyKey(key, button) {
        await this.copyToClipboard(key, button);
    }

    bindContainerHandlers(container) {
        if (!container || container.dataset.boundActions === 'true') return;
        container.addEventListener('click', event => {
            const target = event.target;
            if (!target) return;

            if (target.matches('[data-select="all"]')) {
                target.select();
                return;
            }

            const actionEl = target.closest('[data-action]');
            if (!actionEl) return;

            const action = actionEl.dataset.action;
            if (action === 'generate-key') {
                this.handleGenerateKey();
            } else if (action === 'select-key') {
                const keyId = actionEl.dataset.keyId;
                const key = keyId ? (this.apiKeyVault.get(keyId) || '') : '';
                if (!key) return;
                this.selectedToken = key;
                this.selectedTokenId = this.findTokenIdByValue(key);
                this.loadRSSUrls().then(() => {
                    this.updateSummary();
                    this.renderTokenFilter();
                    this.renderApiKeysSection('api-keys-container');
                    this.renderRSSUrlsSection('rss-urls-container');
                    showNotification('Token RSS sélectionné', 'success');
                }).catch(() => {
                    showNotification('Erreur sélection token', 'error');
                });
            } else if (action === 'copy-key') {
                const keyId = actionEl.dataset.keyId;
                const key = keyId ? (this.apiKeyVault.get(keyId) || '') : '';
                if (key) this.copyKey(key, actionEl);
            } else if (action === 'delete-key') {
                const keyId = actionEl.dataset.keyId;
                const key = keyId ? (this.apiKeyVault.get(keyId) || '') : '';
                if (!key) return;
                if (actionEl.dataset.confirming !== 'true') {
                    actionEl.dataset.confirming = 'true';
                    actionEl.classList.remove('btn-danger');
                    actionEl.classList.add('btn-warning');
                    actionEl.textContent = 'Confirmer';
                    if (actionEl._confirmTimer) clearTimeout(actionEl._confirmTimer);
                    actionEl._confirmTimer = setTimeout(() => {
                        actionEl.dataset.confirming = 'false';
                        actionEl.classList.remove('btn-warning');
                        actionEl.classList.add('btn-danger');
                        actionEl.textContent = 'Supprimer';
                    }, 3200);
                    return;
                }
                if (actionEl._confirmTimer) clearTimeout(actionEl._confirmTimer);
                actionEl.disabled = true;
                actionEl.dataset.confirming = 'false';
                actionEl.classList.remove('btn-warning');
                actionEl.classList.add('btn-danger');
                actionEl.textContent = 'Suppression...';
                this.handleDeleteKey(key, actionEl);
            } else if (action === 'copy-ref') {
                const ref = actionEl.dataset.copyRef;
                const value = this.getCopyRef(ref);
                if (value) this.copyToClipboard(value, actionEl);
            }
        });
        container.dataset.boundActions = 'true';
    }

    // Initialiser l'interface
    async init() {
        await this.loadApiKeys();
        await this.loadRSSUrls();
        this.bindPageFilters();
        this.renderTokenFilter();
        this.updateSummary();
        this.renderApiKeysSection('api-keys-container');
        this.renderRSSUrlsSection('rss-urls-container');
    }
}

// Fonction helper pour les notifications (centralisée)
function showNotification(message, type = 'info') {
    if (window.showNotification) {
        window.showNotification(message, type);
        return;
    }

    const notification = document.createElement('div');
    notification.className = `ui-toast ui-toast--${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Créer l'instance globale
const rssManager = new RSSManager();

// Charger au démarrage si sur la page appropriée
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('api-keys-container')) {
            rssManager.init();
        }
    });
} else {
    if (document.getElementById('api-keys-container')) {
        rssManager.init();
    }
}
