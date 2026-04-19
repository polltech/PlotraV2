/**
 * Plotra Platform - Service Worker
 * Provides offline functionality for PWA
 */

const CACHE_NAME = 'plotra-v1';
const STATIC_CACHE = 'plotra-static-v1';
const DYNAMIC_CACHE = 'plotra-dynamic-v1';

// Static assets to cache
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/css/styles.css',
    '/js/config.js',
    '/js/api.js',
    '/js/auth.js',
    '/js/gps.js',
    '/js/app.js',
    '/manifest.json',
    '/icons/plotra-logo.png'
];

// API endpoints to cache (network-first strategy)
const API_CACHE_ROUTES = [
    '/api/v2/auth/token',
    '/api/v2/farmer/profile',
    '/api/v2/farmer/farm',
    '/api/v2/coop/deliveries',
    '/api/v2/coop/batches'
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Installing...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then((cache) => {
                console.log('[ServiceWorker] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('[ServiceWorker] Static assets cached');
                return self.skipWaiting();
            })
            .catch((error) => {
                console.error('[ServiceWorker] Install failed:', error);
            })
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activating...');
    
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => {
                            return name !== STATIC_CACHE && 
                                   name !== DYNAMIC_CACHE &&
                                   name !== CACHE_NAME;
                        })
                        .map((name) => {
                            console.log('[ServiceWorker] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                console.log('[ServiceWorker] Activated');
                return self.clients.claim();
            })
    );
});

// Fetch event - handle requests with appropriate strategy
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Skip non-GET requests for caching
    if (request.method !== 'GET') {
        // Store POST requests for offline queue if needed
        if (request.method === 'POST' && request.url.includes('/api/v2/')) {
            event.respondWith(handleOfflineQueue(request));
        }
        return;
    }
    
    // Handle API requests - Network first, fallback to cache
    if (url.pathname.startsWith('/api/v2/')) {
        event.respondWith(networkFirst(request));
        return;
    }
    
    // Handle static assets - Cache first, fallback to network
    if (isStaticAsset(url.pathname)) {
        event.respondWith(cacheFirst(request));
        return;
    }
    
    // Default - Network first
    event.respondWith(networkFirst(request));
});

// Cache first strategy
async function cacheFirst(request) {
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
        console.log('[ServiceWorker] Serving from cache:', request.url);
        return cachedResponse;
    }
    
    try {
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            const cache = await caches.open(STATIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.error('[ServiceWorker] Cache first failed:', error);
        return new Response('Offline', { status: 503 });
    }
}

// Network first strategy
async function networkFirst(request) {
    try {
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[ServiceWorker] Network failed, trying cache:', request.url);
        const cachedResponse = await caches.match(request);
        
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // Return offline page for HTML requests
        if (request.headers.get('Accept').includes('text/html')) {
            return caches.match('/index.html');
        }
        
        return new Response(JSON.stringify({ 
            error: 'offline', 
            message: 'You are currently offline. Data will sync when connection is restored.' 
        }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

// Handle offline queue for POST requests
async function handleOfflineQueue(request) {
    try {
        const networkResponse = await fetch(request);
        return networkResponse;
    } catch (error) {
        console.log('[ServiceWorker] Request queued for offline:', request.url);
        
        // Store request in IndexedDB for later sync
        const requestData = await request.clone().text();
        
        try {
            await storeOfflineRequest({
                url: request.url,
                method: request.method,
                headers: Object.fromEntries(request.headers.entries()),
                body: requestData,
                timestamp: Date.now()
            });
        } catch (dbError) {
            console.error('[ServiceWorker] Failed to store offline request:', dbError);
        }
        
        return new Response(JSON.stringify({
            success: true,
            offline: true,
            message: 'Request queued for sync when online'
        }), {
            status: 202,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

// Store offline request in IndexedDB
function storeOfflineRequest(requestData) {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('plotra-offline-queue', 1);
        
        request.onerror = () => reject(request.error);
        
        request.onsuccess = () => {
            const db = request.result;
            const tx = db.transaction('requests', 'readwrite');
            const store = tx.objectStore('requests');
            
            const addRequest = store.add(requestData);
            
            addRequest.onsuccess = () => resolve();
            addRequest.onerror = () => reject(addRequest.error);
        };
        
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains('requests')) {
                db.createObjectStore('requests', { keyPath: 'timestamp' });
            }
        };
    });
}

// Background sync for offline requests
self.addEventListener('sync', (event) => {
    console.log('[ServiceWorker] Sync event:', event.tag);
    
    if (event.tag === 'sync-deliveries') {
        event.waitUntil(syncOfflineRequests());
    }
});

// Sync offline requests when back online
async function syncOfflineRequests() {
    console.log('[ServiceWorker] Syncing offline requests...');
    
    try {
        const db = await openOfflineDB();
        const tx = db.transaction('requests', 'readwrite');
        const store = tx.objectStore('requests');
        const requests = await getAllFromStore(store);
        
        for (const requestData of requests) {
            try {
                const response = await fetch(requestData.url, {
                    method: requestData.method,
                    headers: requestData.headers,
                    body: requestData.body
                });
                
                if (response.ok) {
                    // Remove synced request
                    const deleteTx = db.transaction('requests', 'readwrite');
                    const deleteStore = deleteTx.objectStore('requests');
                    deleteStore.delete(requestData.timestamp);
                    
                    console.log('[ServiceWorker] Synced:', requestData.url);
                    
                    // Notify clients
                    const clients = await self.clients.matchAll();
                    clients.forEach(client => {
                        client.postMessage({
                            type: 'SYNC_COMPLETE',
                            url: requestData.url
                        });
                    });
                }
            } catch (error) {
                console.error('[ServiceWorker] Sync failed for:', requestData.url, error);
            }
        }
    } catch (error) {
        console.error('[ServiceWorker] Sync failed:', error);
    }
}

// Helper: Check if URL is a static asset
function isStaticAsset(pathname) {
    return pathname.match(/\.(js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot)$/);
}

// Helper: Open IndexedDB
function openOfflineDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('plotra-offline-queue', 1);
        
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
        
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains('requests')) {
                db.createObjectStore('requests', { keyPath: 'timestamp' });
            }
        };
    });
}

// Helper: Get all items from store
function getAllFromStore(store) {
    return new Promise((resolve, reject) => {
        const request = store.getAll();
        
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

// Push notifications (for future use)
self.addEventListener('push', (event) => {
    console.log('[ServiceWorker] Push received:', event);
    
    const data = event.data?.json() || {};
    
    const options = {
        body: data.body || 'New notification from Plotra Platform',
        icon: '/icons/plotra-logo.png',
        badge: '/icons/badge.png',
        vibrate: [100, 50, 100],
        data: {
            url: data.url || '/'
        },
        actions: [
            { action: 'open', title: 'Open' },
            { action: 'dismiss', title: 'Dismiss' }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title || 'Plotra Platform', options)
    );
});

// Notification click handler
self.addEventListener('notificationclick', (event) => {
    console.log('[ServiceWorker] Notification clicked:', event);
    
    event.notification.close();
    
    if (event.action === 'open' || !event.action) {
        event.waitUntil(
            clients.openWindow(event.notification.data.url)
        );
    }
});
