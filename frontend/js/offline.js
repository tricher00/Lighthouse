/**
 * Lighthouse Offline Manager
 * Handles IndexedDB storage and action queueing for offline support.
 */

const DB_NAME = 'lighthouse-offline';
const DB_VERSION = 1;
const STORE_DASHBOARD = 'dashboard';
const STORE_ACTIONS = 'actions';

const OfflineManager = {
    db: null,

    /**
     * Initialize IndexedDB
     */
    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);

            request.onerror = (event) => {
                console.error('OfflineManager: Database error', event.target.error);
                reject(event.target.error);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                // Store for latest dashboard data
                if (!db.objectStoreNames.contains(STORE_DASHBOARD)) {
                    db.createObjectStore(STORE_DASHBOARD, { keyPath: 'id' });
                }
                // Store for offline actions queue
                if (!db.objectStoreNames.contains(STORE_ACTIONS)) {
                    db.createObjectStore(STORE_ACTIONS, { keyPath: 'id', autoIncrement: true });
                }
            };

            request.onsuccess = (event) => {
                this.db = event.target.result;
                console.log('OfflineManager: Database initialized');
                resolve(this.db);
            };
        });
    },

    /**
     * Cache the full dashboard data
     */
    async cacheDashboard(data) {
        if (!this.db) await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_DASHBOARD], 'readwrite');
            const store = transaction.objectStore(STORE_DASHBOARD);
            // We use a fixed ID 'latest' to store the single dashboard state
            const request = store.put({ id: 'latest', data: data, timestamp: Date.now() });

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    },

    /**
     * Retrieve cached dashboard data
     */
    async getCachedDashboard() {
        if (!this.db) await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_DASHBOARD], 'readonly');
            const store = transaction.objectStore(STORE_DASHBOARD);
            const request = store.get('latest');

            request.onsuccess = () => {
                if (request.result) {
                    resolve(request.result.data);
                } else {
                    resolve(null);
                }
            };
            request.onerror = () => reject(request.error);
        });
    },

    /**
     * Queue an action to be synced later
     * @param {Object} action - { type: 'read'|'rating'|'settings', payload: ... }
     */
    async queueAction(action) {
        if (!this.db) await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_ACTIONS], 'readwrite');
            const store = transaction.objectStore(STORE_ACTIONS);
            action.timestamp = Date.now();
            const request = store.add(action);

            request.onsuccess = () => {
                console.log('OfflineManager: Action queued', action);
                resolve();
            };
            request.onerror = () => reject(request.error);
        });
    },

    /**
     * access Pending Actions
    */
    async getPendingActions() {
        if (!this.db) await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_ACTIONS], 'readonly');
            const store = transaction.objectStore(STORE_ACTIONS);
            const request = store.getAll();

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    /**
     * Clear processed actions
     */
    async clearActions(actionIds) {
        if (!this.db) await this.init();
        const transaction = this.db.transaction([STORE_ACTIONS], 'readwrite');
        const store = transaction.objectStore(STORE_ACTIONS);

        actionIds.forEach(id => {
            store.delete(id);
        });

        return new Promise((resolve) => {
            transaction.oncomplete = () => resolve();
        });
    },

    /**
     * Sync queued actions with the server
     */
    async syncActions() {
        const actions = await this.getPendingActions();
        if (actions.length === 0) return;

        console.log(`OfflineManager: Syncing ${actions.length} actions...`);
        const deviceId = this.getDeviceId();

        // Group actions by type
        const readActions = actions.filter(a => a.type === 'read');
        const ratingActions = actions.filter(a => a.type === 'rating');
        // const settingActions = actions.filter(a => a.type === 'settings'); 

        // 1. Sync Reads
        if (readActions.length > 0) {
            const articleUrls = readActions.map(a => a.payload.url).filter(u => u);
            // Ideally we'd use IDs, but the sync endpoint takes URLs or IDs? 
            // The dashboard uses openArticle(url, id). 
            // The backend sync_read_status uses article_urls: list[str].

            if (articleUrls.length > 0) {
                try {
                    await fetch('/api/articles/sync-read-status', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ article_urls: articleUrls, device_id: deviceId })
                    });
                    await this.clearActions(readActions.map(a => a.id));
                } catch (e) {
                    console.error("Sync reads failed", e);
                }
            }
        }

        // 2. Sync Ratings
        if (ratingActions.length > 0) {
            const ratingsPayload = ratingActions.map(a => ({
                article_id: a.payload.articleId,
                rating: a.payload.rating
            }));

            try {
                const response = await fetch('/api/articles/sync-ratings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ratings: ratingsPayload, device_id: deviceId })
                });

                if (response.ok) {
                    await this.clearActions(ratingActions.map(a => a.id));
                }
            } catch (e) {
                console.error("Sync ratings failed", e);
            }
        }

        // 3. Sync Settings (replay latest settings update)
        const settingsActions = actions.filter(a => a.type === 'settings');
        if (settingsActions.length > 0) {
            // Only sync the latest settings action to avoid redundant updates
            const latestAction = settingsActions[settingsActions.length - 1];
            try {
                const response = await fetch('/api/settings', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(latestAction.payload)
                });

                if (response.ok) {
                    // Clear ALL settings actions as we've synced the latest state
                    await this.clearActions(settingsActions.map(a => a.id));
                    // Trigger refresh
                    await fetch('/api/settings/refresh', { method: 'POST' });
                }
            } catch (e) {
                console.error("Sync settings failed", e);
            }
        }

        console.log('OfflineManager: Sync complete');
    },

    getDeviceId() {
        let deviceId = localStorage.getItem('lighthouse_device_id');
        if (!deviceId) {
            deviceId = 'device_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('lighthouse_device_id', deviceId);
        }
        return deviceId;
    }
};
