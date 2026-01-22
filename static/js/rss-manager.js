// rss-manager.js
// Gestion des API keys et URLs RSS

class RSSManager {
    constructor() {
        this.apiKeys = [];
        this.rssUrls = [];
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
                return { error: data.error, message: data.message };
            }

            this.rssUrls = data.urls || [];
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
                    <button class="btn btn-primary" onclick="rssManager.handleGenerateKey()">
                        Générer une clé
                    </button>
                </div>`;

        if (this.apiKeys.length === 0) {
            html += `
                <div class="info-box">
                    <p>Aucune clé API générée.</p>
                    <p>Générez une clé pour accéder aux flux RSS.</p>
                </div>`;
        } else {
            html += `<div class="api-keys-list">`;
            this.apiKeys.forEach(key => {
                const statusClass = key.enabled ? 'active' : 'inactive';
                const statusText = key.enabled ? 'Active' : 'Inactive';

                html += `
                    <div class="api-key-item ${statusClass}">
                        <div class="key-info">
                            <strong>${key.name || 'Sans nom'}</strong>
                            <code class="api-key-value">${key.key}</code>
                            <span class="key-status ${statusClass}">${statusText}</span>
                            <small>Créée le ${new Date(key.created_at).toLocaleDateString()}</small>
                        </div>
                        <div class="key-actions">
                            <button class="btn btn-sm btn-secondary" onclick="rssManager.copyKey('${key.key}', this)">
                                📋 Copier
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="rssManager.handleDeleteKey('${key.key}')">
                                🗑️ Supprimer
                            </button>
                        </div>
                    </div>`;
            });
            html += `</div>`;
        }

        html += `</div>`;
        container.innerHTML = html;
    }

    // Render l'interface URLs RSS
    renderRSSUrlsSection(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        let html = `<div class="rss-urls-section">`;

        if (this.rssUrls.length === 0) {
            html += `
                <div class="info-box warning">
                    <p>⚠️ Aucune URL RSS disponible.</p>
                    <p>Générez une clé API d'abord.</p>
                </div>`;
        } else {
            // Grouper par catégorie
            const principal = this.rssUrls.filter(u => u.category === 'principal');
            const trackers = this.rssUrls.filter(u => u.category === 'tracker');

            if (principal.length > 0) {
                html += `
                    <div class="url-category">
                        <h4>📡 Flux principaux</h4>
                        <div class="urls-list">`;

                principal.forEach(url => {
                    html += this.renderUrlCard(url);
                });

                html += `</div></div>`;
            }

            if (trackers.length > 0) {
                html += `
                    <div class="url-category">
                        <h4>🎯 Flux par tracker</h4>
                        <div class="urls-list">`;

                trackers.forEach(url => {
                    html += this.renderUrlCard(url);
                });

                html += `</div></div>`;
            }
        }

        html += `</div>`;
        container.innerHTML = html;
    }

    // Render une carte URL
    renderUrlCard(url) {
        return `
            <div class="url-card">
                <div class="url-info">
                    <strong>${url.name}</strong>
                    <p class="url-description">${url.description}</p>
                    <input type="text" class="url-value" value="${url.url}" readonly onclick="this.select()">
                </div>
                <button class="btn btn-primary btn-copy" onclick="rssManager.copyUrl('${url.url.replace(/'/g, "\\'")}', this)">
                    📋 Copier l'URL
                </button>
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

    // Initialiser l'interface
    async init() {
        await this.loadApiKeys();
        await this.loadRSSUrls();
        this.renderApiKeysSection('api-keys-container');
        this.renderRSSUrlsSection('rss-urls-container');
    }
}

// Fonction helper pour les notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
        color: white;
        border-radius: 4px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
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
