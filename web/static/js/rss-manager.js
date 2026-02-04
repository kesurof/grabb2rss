// rss-manager.js
// Gestion des API keys et URLs RSS

class RSSManager {
    constructor() {
        this.apiKeys = [];
        this.rssUrls = [];
        this.authInfo = null;
    }

    // Charger les API keys
    async loadApiKeys() {
        try {
            const response = await fetch('/api/auth/keys');
            const data = await response.json();
            this.apiKeys = data.keys || [];
            return this.apiKeys;
        } catch (error) {
            console.error('Erreur chargement API keys:', error);
            return [];
        }
    }

    // Générer une nouvelle API key
    async generateApiKey() {
        try {
            const response = await fetch('/api/auth/keys/generate', {
                method: 'POST'
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
            const response = await fetch('/api/rss/urls');
            const data = await response.json();

            if (data.error) {
                this.rssUrls = [];
                this.authInfo = null;
                return { error: data.error, message: data.message };
            }

            this.rssUrls = data.urls || [];
            this.authInfo = data.auth || null;
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
                    <button class="btn btn-primary" type="button" data-action="generate-key">
                        Générer une clé
                    </button>
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

            this.apiKeys.forEach(key => {
                const statusClass = key.enabled ? 'active' : 'inactive';
                const statusText = key.enabled ? 'Active' : 'Inactive';
                const createdAt = new Date(key.created_at).toLocaleDateString();

                html += `
                            <tr>
                                <td><strong>${key.name || 'API Key'}</strong></td>
                                <td><code class="api-key-chip">${key.key}</code></td>
                                <td><span class="key-status ${statusClass}">${statusText}</span></td>
                                <td>${createdAt}</td>
                                <td>
                                    <div class="api-key-actions">
                                        <button class="btn btn-sm btn-secondary" type="button" data-action="copy-key" data-key="${key.key}">Copier</button>
                                        <button class="btn btn-sm btn-danger" type="button" data-action="delete-key" data-key="${key.key}">Supprimer</button>
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

        let html = `<div class="rss-urls-section config-grid">`;

        if (this.rssUrls.length === 0) {
            html += `
                <div class="info-box warning">
                    <p>⚠️ Aucune URL RSS disponible.</p>
                    <p>Générez une clé API d'abord.</p>
                </div>`;
        } else {
            if (this.authInfo && (this.authInfo.x_api_key || this.authInfo.authorization)) {
                const xApiKey = this.authInfo.x_api_key || '';
                const bearer = this.authInfo.authorization || '';
                html += `
                    <div class="config-card">
                        <div class="config-card__header">
                            <div class="config-card__title">Authentification via headers</div>
                            <div class="config-card__subtitle">Recommandé pour sécuriser l'accès</div>
                        </div>
                        <div class="config-card__body">
                            <div class="config-field">
                                <div class="config-field__meta">
                                    <label class="config-field__label">Header principal</label>
                                    <div class="config-field__help">À ajouter dans votre client torrent</div>
                                </div>
                                <div class="config-field__control">
                                    <div class="config-inline">
                                        <input type="text" class="config-input" value="X-API-Key: ${xApiKey}" readonly data-select="all" title="Cliquez pour sélectionner">
                                        <button class="btn btn-sm btn-secondary" type="button" data-action="copy-text" data-text="X-API-Key: ${xApiKey}">Copier</button>
                                    </div>
                                </div>
                            </div>
                            <div class="config-field">
                                <div class="config-field__meta">
                                    <label class="config-field__label">Alternative</label>
                                    <div class="config-field__help">Utilisez si votre client n'accepte pas X-API-Key</div>
                                </div>
                                <div class="config-field__control">
                                    <div class="config-inline">
                                        <input type="text" class="config-input" value="Authorization: ${bearer}" readonly data-select="all" title="Cliquez pour sélectionner">
                                        <button class="btn btn-sm btn-secondary" type="button" data-action="copy-text" data-text="Authorization: ${bearer}">Copier</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>`;
            }

            // Grouper par catégorie
            const principal = this.rssUrls.filter(u => u.category === 'principal');
            const trackers = this.rssUrls.filter(u => u.category === 'tracker');

            if (principal.length > 0) {
                html += `
                    <div class="config-card">
                        <div class="config-card__header">
                            <div class="config-card__title">Flux principaux</div>
                            <div class="config-card__subtitle">Tous les torrents récents</div>
                        </div>
                        <div class="config-card__body">`;

                principal.forEach(url => {
                    html += this.renderUrlRow(url);
                });

                html += `</div></div>`;
            }

            if (trackers.length > 0) {
                html += `
                    <div class="config-card">
                        <div class="config-card__header">
                            <div class="config-card__title">Flux par tracker</div>
                            <div class="config-card__subtitle">Sources filtrées par tracker</div>
                        </div>
                        <div class="config-card__body">`;

                trackers.forEach(url => {
                    html += this.renderUrlRow(url);
                });

                html += `</div></div>`;
            }
        }

        html += `</div>`;
        container.innerHTML = html;
        this.bindContainerHandlers(container);
    }

    // Render une carte URL
    renderUrlRow(url) {
        return `
            <div class="config-field">
                <div class="config-field__meta">
                    <label class="config-field__label">${url.name}</label>
                    <div class="config-field__help">${url.description}</div>
                </div>
                <div class="config-field__control">
                    <div class="config-inline">
                        <input type="text" class="config-input" value="${url.url}" readonly data-select="all" title="Cliquez pour sélectionner">
                        <button class="btn btn-sm btn-secondary" type="button" data-action="copy-url" data-url="${url.url.replace(/'/g, "\\'")}">
                            Copier
                        </button>
                    </div>
                </div>
            </div>`;
    }

    // Handlers
    async handleGenerateKey() {
        try {
            const data = await this.generateApiKey();
            this.renderApiKeysSection('api-keys-container');
            this.renderRSSUrlsSection('rss-urls-container');

            // Afficher message succès
            showNotification('✅ API key générée avec succès !', 'success');
        } catch (error) {
            showNotification('❌ Erreur génération API key', 'error');
        }
    }

    async handleDeleteKey(key) {
        if (!confirm('Supprimer cette clé API ? Les URLs utilisant cette clé cesseront de fonctionner.')) {
            return;
        }

        try {
            await this.deleteApiKey(key);
            this.renderApiKeysSection('api-keys-container');
            this.renderRSSUrlsSection('rss-urls-container');

            showNotification('✅ API key supprimée', 'success');
        } catch (error) {
            showNotification('❌ Erreur suppression API key', 'error');
        }
    }

    async copyKey(key, button) {
        await this.copyToClipboard(key, button);
    }

    async copyUrl(url, button) {
        await this.copyToClipboard(url, button);
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
            } else if (action === 'copy-key') {
                const key = actionEl.dataset.key;
                if (key) this.copyKey(key, actionEl);
            } else if (action === 'delete-key') {
                const key = actionEl.dataset.key;
                if (key) this.handleDeleteKey(key);
            } else if (action === 'copy-text') {
                const text = actionEl.dataset.text;
                if (text) this.copyToClipboard(text, actionEl);
            } else if (action === 'copy-url') {
                const url = actionEl.dataset.url;
                if (url) this.copyUrl(url, actionEl);
            }
        });
        container.dataset.boundActions = 'true';
    }

    // Initialiser l'interface
    async init() {
        await this.loadApiKeys();
        await this.loadRSSUrls();
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
