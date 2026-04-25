/**
 * Plotra Dashboard - Configuration
 * Frontend environment settings
 * 
 * For Digital Ocean deployment, the API URL is automatically proxied through nginx
 * as /api/ -> http://backend:8000
 * 
 * Override baseUrl if needed: window.PLOTRA_CONFIG.api.baseUrl = 'https://your-domain.com/api/v2';
 */

window.PLOTRA_CONFIG = {
    // API Configuration
    // Uses relative URL for Docker/nginx proxy (/api/ -> backend:8000)
    // Override this if not using Docker
    api: {
        baseUrl: '/api/v2',
        timeout: 10000,
        retryAttempts: 3
    },
    
    // GPS Settings
    gps: {
        toleranceMeters: 3.0,           // GPS tolerance (3-5m per spec)
        minAccuracy: 10,               // Max acceptable GPS accuracy in meters
        minPolygonPoints: 3,            // Minimum vertices for polygon
        minAreaHectares: 0.1,          // Minimum polygon area
        maxAreaHectares: 100            // Maximum polygon area
    },
    
    // Satellite Settings
    satellite: {
        simulationMode: true,
        ndviThreshold: 0.65,
        confidenceThreshold: 0.90,     // >90% per spec
        cloudCoverMax: 0.20            // 20% max cloud cover
    },
    
    // Heritage Settings (2015-2020 per spec)
    heritage: {
        startYear: 2015,
        endYear: 2020
    },
    
    // EUDR Settings
    eudr: {
        baselineDate: '2020-12-31',      // Forest cover as of 31 Dec 2020
        falsePositiveThreshold: 5,       // <5% per spec
        conflictSlaHours: 48,          // 48h SLA per spec
        polygonValidationMaxSeconds: 2  // <2s per spec
    },
    
    // Sync Settings
    sync: {
        successThreshold: 99.5,        // >99.5% per spec
        batchSize: 100,
        retryDelays: [5000, 30000, 120000, 300000]  // Exponential backoff in ms
    },
    
    // Map Settings
    map: {
        defaultCenter: [-0.0236, 37.9062],  // Kenya center
        defaultZoom: 8,
        maxZoom: 18,
        polygonColor: '#6f4e37',
        polygonFillColor: '#8b6914',
        polygonFillOpacity: 0.3
    },
    
    // Session Settings
    session: {
        warningMinutes: 5,             // Show warning 5 min before expiry
        checkInterval: 10000,          // Check every 10 seconds
        defaultTimeout: 3600           // 1 hour default
    },
    
    // Role Configuration
    roles: {
        farmer: { id: 'farmer', label: 'Farmer' },
        cooperative_officer: { id: 'cooperative_officer', label: 'Cooperative Officer' },
        plotra_admin: { id: 'plotra_admin', label: 'Platform Admin' },
        eudr_reviewer: { id: 'eudr_reviewer', label: 'EUDR Reviewer' }
    },
    
    // Ownership Types
    ownershipTypes: {
        TITLE: 'Title Deed',
        LEASE: 'Lease',
        FAMILY: 'Family Land',
        CUSTOMARY: 'Customary Rights'
    },
    
    // Land Use Types
    landUseTypes: {
        COFFEE: 'Coffee Production',
        AGROFORESTRY: 'Agroforestry',
        FOOD_CROPS: 'Food Crops',
        PASTURE: 'Pasture',
        FOREST: 'Forest',
        OTHER: 'Other'
    },
    
    // Practice Types
    practiceTypes: {
        INTERCROPPING: 'Intercropping',
        PRUNING: 'Pruning',
        PLANTING: 'Planting',
        HARVEST: 'Harvest',
        FERTILIZATION: 'Fertilization',
        PEST_CONTROL: 'Pest Control',
        IRRIGATION: 'Irrigation',
        WEEDING: 'Weeding'
    },
    
    // Verification Status Flow
    verificationFlow: {
        DRAFT: 'draft',
        COOP_APPROVED: 'cooperative_approved',
        KIPAWA_VERIFIED: 'kipawa_verified',
        EUDR_SUBMITTED: 'eudr_submitted'
    },
    
    // NDVI Thresholds
    ndvi: {
        dense: { min: 0.7, label: 'Dense Vegetation' },
        moderate: { min: 0.5, label: 'Moderate Vegetation' },
        sparse: { min: 0.3, label: 'Sparse Vegetation' },
        bare: { min: 0, label: 'Bare Soil' }
    },
    
    // Error Messages
    errors: {
        networkError: 'Network error. Please check your connection.',
        authError: 'Authentication failed. Please login again.',
        serverError: 'Server error. Please try again later.',
        validationError: 'Please check your input and try again.',
        gpsError: 'GPS error. Please ensure location services are enabled.',
        polygonError: 'Invalid polygon. Please check coordinates.',
        conflictError: 'Parcel conflict detected. Please resolve before submitting.'
    },
    
    // Success Messages
    success: {
        login: 'Login successful!',
        save: 'Saved successfully!',
        submit: 'Submitted successfully!',
        sync: 'Sync completed!',
        verify: 'Verified successfully!'
    }
};

// Freeze config to prevent accidental modification
Object.freeze(window.PLOTRA_CONFIG);

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.PLOTRA_CONFIG;
}