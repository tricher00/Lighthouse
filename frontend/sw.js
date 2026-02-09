const CACHE_NAME = 'lighthouse-v5';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/static/css/styles.css',
    '/static/js/dashboard.js',
    '/static/js/offline.js',
    '/manifest.json',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png'
];

// Install Event: Cache static assets
self.addEventListener('install', event => {
    console.log('[Service Worker] Installing Service Worker ...', event);
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[Service Worker] Caching App Shell');
                return cache.addAll(STATIC_ASSETS);
            })
    );
});

// Activate Event: specific cleanup if needed
self.addEventListener('activate', event => {
    console.log('[Service Worker] Activating Service Worker ....', event);
    event.waitUntil(
        caches.keys().then(keyList => {
            return Promise.all(keyList.map(key => {
                if (key !== CACHE_NAME) {
                    console.log('[Service Worker] Removing old cache.', key);
                    return caches.delete(key);
                }
            }));
        })
    );
    return self.clients.claim();
});

// Fetch Event: Network-first for API, Cache-first for static
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // API calls: Network first, fall back to cache?
    // Actually for dashboards we want fresh data, but if offline we need to handle it in JS or here.
    // Our plan says:
    // "Network-first for API calls with fallback to cache" 
    // BUT we are also implementing manual caching in dashboard.js via offline.js.
    // Having the SW cache API responses automatically is good as a backup, 
    // but the complex logic of "queueing actions" needs JS.
    // Let's stick to the plan: SW caches API responses too.

    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request)
                .then(response => {
                    // Check if we received a valid response
                    if (!response || response.status !== 200 || response.type !== 'basic') {
                        return response;
                    }

                    // Clone the response
                    const responseToCache = response.clone();

                    caches.open(CACHE_NAME)
                        .then(cache => {
                            // Don't cache specific non-idempotent methods if any?
                            // GET requests are fine.
                            if (event.request.method === 'GET') {
                                cache.put(event.request, responseToCache);
                            }
                        });

                    return response;
                })
                .catch(() => {
                    // Fallback to cache
                    return caches.match(event.request);
                })
        );
    } else {
        // Static assets: Cache first
        event.respondWith(
            caches.match(event.request)
                .then(response => {
                    if (response) {
                        return response;
                    }
                    return fetch(event.request).then(
                        response => {
                            // Validate response
                            if (!response || response.status !== 200 || response.type !== 'basic') {
                                return response;
                            }

                            // Cache new static assets dynamically ?? 
                            // Maybe not everything, but let's be safe.
                            return response;
                        }
                    );
                })
        );
    }
});
