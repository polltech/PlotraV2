/**
 * Plotra Platform - GPS Module
 * Handles GPS coordinate recording for farm boundary mapping
 */

class GPSRecorder {
    constructor() {
        this.watchId = null;
        this.points = [];
        this.isRecording = false;
        this.onPositionUpdate = null;
        this.onError = null;
    }
    
    /**
     * Check if GPS is available
     */
    isAvailable() {
        return 'geolocation' in navigator;
    }
    
    /**
     * Get current position (single reading)
     */
    async getCurrentPosition(options = {}) {
        const config = {
            enableHighAccuracy: CONFIG.gps.enableHighAccuracy,
            timeout: CONFIG.gps.timeout,
            maximumAge: CONFIG.gps.maximumAge,
            ...options
        };
        
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    resolve({
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        accuracy: position.coords.accuracy,
                        altitude: position.coords.altitude,
                        timestamp: position.timestamp
                    });
                },
                (error) => {
                    const errorMessage = this.getErrorMessage(error);
                    if (this.onError) {
                        this.onError(errorMessage);
                    }
                    reject(new Error(errorMessage));
                },
                config
            );
        });
    }
    
    /**
     * Start recording GPS coordinates
     */
    startRecording(onUpdate, onError) {
        if (!this.isAvailable()) {
            const error = new Error('GPS is not available on this device');
            if (onError) onError(error);
            throw error;
        }
        
        if (this.isRecording) {
            console.warn('GPS recording already in progress');
            return;
        }
        
        this.points = [];
        this.isRecording = true;
        this.onPositionUpdate = onUpdate;
        this.onError = onError;
        
        this.watchId = navigator.geolocation.watchPosition(
            (position) => {
                const point = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    altitude: position.coords.altitude,
                    timestamp: position.timestamp
                };
                
                // Only add point if accuracy is acceptable
                if (point.accuracy <= CONFIG.gps.minAccuracy * 2) {
                    this.points.push(point);
                    
                    if (this.onPositionUpdate) {
                        this.onPositionUpdate(point, this.points);
                    }
                }
            },
            (error) => {
                const errorMessage = this.getErrorMessage(error);
                console.error('GPS Error:', errorMessage);
                if (this.onError) {
                    this.onError(new Error(errorMessage));
                }
            },
            {
                enableHighAccuracy: CONFIG.gps.enableHighAccuracy,
                timeout: CONFIG.gps.timeout,
                maximumAge: CONFIG.gps.maximumAge
            }
        );
        
        console.log('GPS recording started');
    }
    
    /**
     * Stop recording GPS coordinates
     */
    stopRecording() {
        if (this.watchId !== null) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
        
        this.isRecording = false;
        console.log('GPS recording stopped', `${this.points.length} points recorded`);
    }
    
    /**
     * Get recorded points
     */
    getPoints() {
        return [...this.points];
    }
    
    /**
     * Clear recorded points
     */
    clearPoints() {
        this.points = [];
    }
    
    /**
     * Check if minimum points collected
     */
    hasMinimumPoints() {
        return this.points.length >= CONFIG.gps.minPoints;
    }
    
    /**
     * Calculate average accuracy of recorded points
     */
    getAverageAccuracy() {
        if (this.points.length === 0) return 0;
        
        const sum = this.points.reduce((acc, p) => acc + p.accuracy, 0);
        return sum / this.points.length;
    }
    
    /**
     * Generate GeoJSON Polygon from recorded points
     */
    toGeoJSONPolygon(closeRing = true) {
        if (this.points.length < 3) {
            throw new Error('Need at least 3 points to create a polygon');
        }
        
        const coordinates = this.points.map(p => [p.longitude, p.latitude]);
        
        // Close the ring by adding the first point at the end
        if (closeRing) {
            coordinates.push([...coordinates[0]]);
        }
        
        return {
            type: 'Polygon',
            coordinates: [coordinates]
        };
    }
    
    /**
     * Calculate area of polygon (in hectares)
     */
    calculateAreaHectares() {
        if (this.points.length < 3) {
            return 0;
        }
        
        // Use the coordinates to calculate area
        const coords = this.points.map(p => [p.longitude, p.latitude]);
        
        // Calculate area using the Shoelace formula
        let area = 0;
        const n = coords.length;
        
        for (let i = 0; i < n; i++) {
            const j = (i + 1) % n;
            area += coords[i][0] * coords[j][1];
            area -= coords[j][0] * coords[i][1];
        }
        
        area = Math.abs(area) / 2;
        
        // Convert to hectares (approximate for East Africa)
        // At the equator, 1 degree ≈ 111km
        const areaSqDegrees = area;
        const areaSqKm = areaSqDegrees * 111 * 111;
        const areaHectares = areaSqKm * 100;
        
        return Math.round(areaHectares * 100) / 100;
    }
    
    /**
     * Get GPS status summary
     */
    getStatus() {
        return {
            isRecording: this.isRecording,
            pointsCount: this.points.length,
            averageAccuracy: this.getAverageAccuracy(),
            hasMinimum: this.hasMinimumPoints()
        };
    }
    
    /**
     * Get human-readable error message
     */
    getErrorMessage(error) {
        const errors = {
            1: 'GPS permission denied. Please enable location access.',
            2: 'GPS position unavailable. Please check your GPS signal.',
            3: 'GPS request timed out. Please try again.',
            default: 'An unknown GPS error occurred.'
        };
        
        return errors[error.code] || errors.default;
    }
}

/**
 * Distance calculator between GPS points
 */
class GPSCalculator {
    /**
     * Calculate distance between two points (Haversine formula)
     */
    static distance(point1, point2) {
        const R = 6371; // Earth's radius in km
        const dLat = this.toRad(point2.latitude - point1.latitude);
        const dLon = this.toRad(point2.longitude - point1.longitude);
        
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(this.toRad(point1.latitude)) * 
                  Math.cos(this.toRad(point2.latitude)) *
                  Math.sin(dLon / 2) * Math.sin(dLon / 2);
        
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        
        return R * c; // Distance in km
    }
    
    /**
     * Convert degrees to radians
     */
    static toRad(deg) {
        return deg * (Math.PI / 180);
    }
    
    /**
     * Calculate perimeter of GPS points (in meters)
     */
    static perimeter(points) {
        if (points.length < 2) return 0;
        
        let perimeter = 0;
        
        for (let i = 0; i < points.length - 1; i++) {
            perimeter += this.distance(points[i], points[i + 1]) * 1000; // Convert to meters
        }
        
        // Close the polygon
        perimeter += this.distance(points[points.length - 1], points[0]) * 1000;
        
        return Math.round(perimeter);
    }
}

// Create global GPS instances
window.gpsRecorder = new GPSRecorder();
window.gpsCalculator = GPSCalculator;
