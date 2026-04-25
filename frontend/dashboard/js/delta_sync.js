/**
 * Plotra Dashboard - Delta Sync Service
 * Offline-first sync with deduplication and conflict detection
 */

class DeltaSyncService {
    constructor() {
        this.deviceId = this._getOrCreateDeviceId();
        this.lastSyncTimestamp = localStorage.getItem('plotra_last_sync') || null;
        this.pendingRecords = [];
        this.syncedRecords = [];
        this.conflicts = [];
        this.syncInProgress = false;
        
        this.STORAGE_KEY = 'plotra_pending_sync';
        this.CONFLICT_KEY = 'plotra_sync_conflicts';
        
        this.loadPendingRecords();
        this.setupOnlineListener();
    }
    
    _getOrCreateDeviceId() {
        let deviceId = localStorage.getItem('plotra_device_id');
        if (!deviceId) {
            deviceId = 'DEV-' + Date.now().toString(36) + '-' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('plotra_device_id', deviceId);
        }
        return deviceId;
    }
    
    loadPendingRecords() {
        const stored = localStorage.getItem(this.STORAGE_KEY);
        this.pendingRecords = stored ? JSON.parse(stored) : [];
    }
    
    savePendingRecords() {
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.pendingRecords));
    }
    
    setupOnlineListener() {
        window.addEventListener('online', () => {
            console.log('Online - triggering delta sync');
            this.syncPendingRecords();
        });
        
        // Also sync periodically when online
        if (navigator.onLine) {
            setInterval(() => {
                if (this.pendingRecords.length > 0 && !this.syncInProgress) {
                    this.syncPendingRecords();
                }
            }, 60000); // Check every minute
        }
    }
    
    /**
     * Add a record for delta sync
     */
    addRecord(entityType, entityId, data) {
        const record = {
            id: entityId,
            entity_type: entityType,
            version: (data.version || 1) + 1,
            updated_at: new Date().toISOString(),
            checksum: this._generateChecksum(entityType, entityId, data),
            data: data,
            boundary_geojson: data.boundary_geojson || null,
            gps_accuracy_meters: data.gps_accuracy || null
        };
        
        // Check for existing pending record
        const existingIndex = this.pendingRecords.findIndex(
            r => r.entity_type === entityType && r.id === entityId
        );
        
        if (existingIndex >= 0) {
            this.pendingRecords[existingIndex] = record;
        } else {
            this.pendingRecords.push(record);
        }
        
        this.savePendingRecords();
        return record;
    }
    
    _generateChecksum(entityType, entityId, data) {
        const content = `${entityType}:${entityId}:${JSON.stringify(data)}`;
        return this._sha256(content);
    }
    
    _sha256(str) {
        // Simple hash implementation
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash).toString(16);
    }
    
    /**
     * Sync all pending records
     */
    async syncPendingRecords() {
        if (!navigator.onLine) {
            console.log('Offline - sync skipped');
            return { success: false, reason: 'offline' };
        }
        
        if (this.syncInProgress || this.pendingRecords.length === 0) {
            return { success: true, synced: 0 };
        }
        
        this.syncInProgress = true;
        
        try {
            const payload = {
                device_id: this.deviceId,
                last_sync_timestamp: this.lastSyncTimestamp,
                records: this.pendingRecords
            };
            
            const response = await fetch('/api/v2/sync/delta', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('plotra_token')}`
                },
                body: JSON.stringify(payload)
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Remove synced records
                this.pendingRecords = [];
                this.savePendingRecords();
                
                this.lastSyncTimestamp = result.server_timestamp;
                localStorage.setItem('plotra_last_sync', this.lastSyncTimestamp);
                
                // Handle conflicts
                if (result.conflicts && result.conflicts.length > 0) {
                    this.conflicts = result.conflicts;
                    localStorage.setItem(this.CONFLICT_KEY, JSON.stringify(this.conflicts));
                    this.showConflictNotification(result.conflicts.length);
                }
                
                return {
                    success: true,
                    synced: result.synced_count,
                    conflicts: result.conflict_count,
                    failed: result.failed_count
                };
            } else {
                return { success: false, reason: 'server_error' };
            }
        } catch (error) {
            console.error('Delta sync failed:', error);
            return { success: false, reason: error.message };
        } finally {
            this.syncInProgress = false;
        }
    }
    
    /**
     * Get sync statistics
     */
    getStats() {
        return {
            pending: this.pendingRecords.length,
            conflicts: this.conflicts.length,
            lastSync: this.lastSyncTimestamp,
            online: navigator.onLine
        };
    }
    
    /**
     * Get pending conflicts
     */
    getConflicts() {
        return this.conflicts;
    }
    
    /**
     * Resolve a conflict
     */
    async resolveConflict(conflictId, resolution) {
        try {
            const response = await fetch(`/api/v2/sync/conflicts/${conflictId}/resolve`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('plotra_token')}`
                },
                body: JSON.stringify(resolution)
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Remove from conflicts list
                this.conflicts = this.conflicts.filter(c => c.id !== conflictId);
                localStorage.setItem(this.CONFLICT_KEY, JSON.stringify(this.conflicts));
            }
            
            return result;
        } catch (error) {
            console.error('Conflict resolution failed:', error);
            return { success: false, reason: error.message };
        }
    }
    
    showConflictNotification(count) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('Plotra - Sync Conflicts', {
                body: `${count} parcel conflicts detected. Resolution required.`,
                icon: '/favicon.ico'
            });
        }
    }
}

/**
 * GPS Polygon Validator (Turf.js-style)
 * Client-side validation before server sync
 */
class PolygonValidator {
    static GPS_TOLERANCE_METERS = 3.0;
    static MIN_AREA_HA = 0.1;
    static MAX_AREA_HA = 100;
    
    /**
     * Validate polygon coordinates
     */
    static validate(coordinates) {
        const errors = [];
        const warnings = [];
        
        // Check minimum vertices
        if (coordinates.length < 3) {
            errors.push('Polygon must have at least 3 vertices');
        }
        
        // Check WGS84 bounds
        for (let i = 0; i < coordinates.length; i++) {
            const [lon, lat] = coordinates[i];
            if (lon < -180 || lon > 180) {
                errors.push(`Longitude ${lon} out of WGS84 range at vertex ${i}`);
            }
            if (lat < -90 || lat > 90) {
                errors.push(`Latitude ${lat} out of WGS84 range at vertex ${i}`);
            }
        }
        
        // Calculate area
        const areaHa = this.calculateArea(coordinates);
        
        if (areaHa < this.MIN_AREA_HA) {
            errors.push(`Polygon area ${areaHa.toFixed(2)}ha below minimum ${this.MIN_AREA_HA}ha`);
        }
        if (areaHa > this.MAX_AREA_HA) {
            errors.push(`Polygon area ${areaHa.toFixed(2)}ha above maximum ${this.MAX_AREA_HA}ha`);
        }
        
        return {
            valid: errors.length === 0,
            errors,
            warnings,
            area_hectares: areaHa,
            perimeter_meters: this.calculatePerimeter(coordinates)
        };
    }
    
    /**
     * Calculate area in hectares using Shoelace formula
     */
    static calculateArea(coordinates) {
        if (coordinates.length < 3) return 0;
        
        // Ensure closed ring
        const coords = [...coordinates];
        if (coords[0] !== coords[coords.length - 1]) {
            coords.push(coords[0]);
        }
        
        // Spherical correction factor for lat/lon
        const latMid = coords.reduce((sum, c) => sum + c[1], 0) / coords.length;
        const mPerDegLat = 111320;
        const mPerDegLon = 111320 * Math.cos(latMid * Math.PI / 180);
        
        let area = 0;
        for (let i = 0; i < coords.length - 1; i++) {
            area += coords[i][0] * coords[i + 1][1] * mPerDegLon;
            area -= coords[i + 1][0] * coords[i][1] * mPerDegLon;
        }
        
        area = Math.abs(area) / 2;
        return area / 10000; // Convert to hectares
    }
    
    /**
     * Calculate perimeter in meters
     */
    static calculatePerimeter(coordinates) {
        let perimeter = 0;
        
        for (let i = 0; i < coordinates.length - 1; i++) {
            perimeter += this.haversineDistance(
                coordinates[i][1], coordinates[i][0],
                coordinates[i + 1][1], coordinates[i + 1][0]
            );
        }
        
        return perimeter;
    }
    
    /**
     * Haversine distance between two points
     */
    static haversineDistance(lat1, lon1, lat2, lon2) {
        const R = 6371000; // Earth radius in meters
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        
        const a = Math.sin(dLat / 2) ** 2 +
                 Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                 Math.sin(dLon / 2) ** 2;
        
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }
    
    /**
     * Check parent-child containment
     */
    static checkContainment(childCoords, parentCoords, bufferMeters = GPS_TOLERANCE_METERS) {
        // Get child centroid
        const childCentroid = this.getCentroid(childCoords);
        
        // Check if centroid is within parent (with buffer)
        const inside = this.pointInPolygon(childCentroid, parentCoords);
        
        if (!inside) {
            return {
                valid: false,
                contained: false,
                errors: ['Child centroid not within parent boundary']
            };
        }
        
        // Check all vertices
        const outsideVertices = [];
        for (let i = 0; i < childCoords.length; i++) {
            if (!this.pointInPolygon(childCoords[i], parentCoords)) {
                outsideVertices.push(i);
            }
        }
        
        if (outsideVertices.length > 0) {
            return {
                valid: false,
                contained: false,
                errors: [`Vertices ${outsideVertices.join(', ')} outside parent`]
            };
        }
        
        return {
            valid: true,
            contained: true,
            buffer_used_meters: bufferMeters
        };
    }
    
    static getCentroid(coords) {
        const n = coords.length;
        const sumLon = coords.reduce((sum, c) => sum + c[0], 0);
        const sumLat = coords.reduce((sum, c) => sum + c[1], 0);
        return [sumLon / n, sumLat / n];
    }
    
    static pointInPolygon(point, polygon) {
        // Ray casting algorithm
        const [x, y] = point;
        let inside = false;
        
        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const [xi, yi] = polygon[i];
            const [xj, yj] = polygon[j];
            
            if (((yi > y) !== (yj > y)) &&
                (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) {
                inside = !inside;
            }
        }
        
        return inside;
    }
}

// Global instances
let deltaSyncService = null;
let polygonValidator = null;

function initDeltaSync() {
    if (!deltaSyncService) {
        deltaSyncService = new DeltaSyncService();
        polygonValidator = PolygonValidator;
    }
    return deltaSyncService;
}

function getDeltaSyncService() {
    return deltaSyncService;
}

function getPolygonValidator() {
    return polygonValidator;
}