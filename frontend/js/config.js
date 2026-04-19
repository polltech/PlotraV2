/**
 * Plotra Platform - Configuration
 * Frontend configuration and constants
 */

const CONFIG = {
    // API Configuration
    api: {
        baseUrl: window.API_BASE_URL || 'http://localhost:8000/api/v2',
        timeout: 30000,
        retryAttempts: 3,
        retryDelay: 1000
    },
    
    // GPS Configuration
    gps: {
        enableHighAccuracy: true,
        timeout: 30000,
        maximumAge: 60000,
        minAccuracy: 20, // meters
        minPoints: 4,
        recordingInterval: 2000 // ms between GPS points
    },
    
    // Offline Storage
    offline: {
        enabled: true,
        maxQueuedRequests: 100,
        syncOnReconnect: true
    },
    
    // Map Configuration
    map: {
        defaultCenter: [0.0236, 37.9062], // Kenya center
        defaultZoom: 6,
        parcelZoom: 15,
        tileUrl: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
    },
    
    // Session Configuration
    session: {
        tokenKey: 'plotra_token',
        userKey: 'plotra_user',
        refreshBeforeExpiry: 5 * 60 * 1000 // 5 minutes
    },
    
    // UI Configuration
    ui: {
        animations: true,
        toastDuration: 3000,
        pageTransition: 200
    }
};

// Environment detection
const ENV = {
    isProduction: window.location.hostname !== 'localhost',
    isMobile: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent),
    hasGPS: 'geolocation' in navigator,
    hasNetwork: 'onLine' in navigator,
    serviceWorkerSupported: 'serviceWorker' in navigator
};

// Export for use in other scripts
window.PLOTRA_CONFIG = CONFIG;
window.PLOTRA_ENV = ENV;
