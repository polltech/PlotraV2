/**
 * Plotra Dashboard - Conflict Resolution UI
 * Polygon overlap resolution for cooperative managers
 */

class ConflictResolutionUI {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.conflicts = [];
        this.currentConflict = null;
        this.map = null;
    }
    
    async loadConflicts() {
        try {
            const response = await fetch('/api/v2/sync/conflicts', {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('plotra_token')}`
                }
            });
            
            this.conflicts = await response.json();
            this.render();
        } catch (error) {
            console.error('Failed to load conflicts:', error);
            this.showError('Failed to load conflicts');
        }
    }
    
    render() {
        if (!this.container) return;
        
        if (this.conflicts.length === 0) {
            this.container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-check-circle text-success fs-1"></i>
                    <p class="mt-2">No pending conflicts</p>
                </div>
            `;
            return;
        }
        
        this.container.innerHTML = `
            <div class="conflict-list">
                ${this.conflicts.map(c => this.renderConflictCard(c)).join('')}
            </div>
            <div id="conflictDetailModal" class="modal fade" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Resolve Conflict</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="conflictMap" style="height: 300px;"></div>
                            <div class="mt-3">
                                <h6>Resolution Options</h6>
                                <div class="list-group">
                                    <button class="list-group-item list-group-item-action" onclick="conflictUI.resolve('keep_local')">
                                        <i class="bi bi-phone"></i> Keep Local Version
                                    </button>
                                    <button class="list-group-item list-group-item-action" onclick="conflictUI.resolve('keep_server')">
                                        <i class="bi bi-server"></i> Keep Server Version
                                    </button>
                                    <button class="list-group-item list-group-item-action" onclick="conflictUI.resolve('resurvey')">
                                        <i class="bi bi-camera"></i> Re-Survey Required
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    renderConflictCard(conflict) {
        const age = this.getAgeText(conflict.created_at);
        const severityClass = this.getSeverityClass(conflict.severity);
        
        return `
            <div class="card mb-2 conflict-card" data-id="${conflict.id}">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <span class="badge ${severityClass}">${conflict.severity}</span>
                            <span class="ms-2 text-muted">${conflict.entity_type}</span>
                        </div>
                        <div class="text-muted small">${age}</div>
                    </div>
                    <div class="mt-2">
                        <p class="mb-1">Overlap: ${conflict.intersection_area?.toFixed(2) || 0} ha</p>
                    </div>
                    <button class="btn btn-sm btn-primary" onclick="conflictUI.showDetail('${conflict.id}')">
                        Resolve
                    </button>
                </div>
            </div>
        `;
    }
    
    getAgeText(createdAt) {
        const diff = Date.now() - new Date(createdAt).getTime();
        const hours = Math.floor(diff / (1000 * 60 * 60));
        
        if (hours >= 44) return `<span class="text-danger">Critical - ${hours}h</span>`;
        if (hours >= 36) return `<span class="text-warning">Warning - ${hours}h</span>`;
        if (hours >= 24) return `${Math.floor(hours / 24)}d ago`;
        return `${hours}h ago`;
    }
    
    getSeverityClass(severity) {
        return {
            'critical': 'bg-danger text-white',
            'high': 'bg-warning',
            'medium': 'bg-info',
            'low': 'bg-secondary'
        }[severity] || 'bg-secondary';
    }
    
    showDetail(conflictId) {
        this.currentConflict = this.conflicts.find(c => c.id === conflictId);
        if (!this.currentConflict) return;
        
        const modal = new bootstrap.Modal(document.getElementById('conflictDetailModal'));
        modal.show();
        
        this.initMap();
    }
    
    initMap() {
        if (this.map) {
            this.map.remove();
            this.map = null;
        }
        
        const mapElement = document.getElementById('conflictMap');
        if (!mapElement) return;
        
        this.map = L.map('conflictMap').setView([-0.0236, 37.9062], 15);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap'
        }).addTo(this.map);
        
        // Add parcel polygons if available
        if (this.currentConflict) {
            if (this.currentConflict.local_data?.boundary_geojson) {
                const local = L.geoJSON(this.currentConflict.local_data.boundary_geojson, {
                    style: { color: 'blue', fillOpacity: 0.3 }
                }).addTo(this.map);
                this.map.fitBounds(local.getBounds());
            }
            
            if (this.currentConflict.server_data?.boundary_geojson) {
                const server = L.geoJSON(this.currentConflict.server_data.boundary_geojson, {
                    style: { color: 'red', fillOpacity: 0.3 }
                }).addTo(this.map);
            }
        }
    }
    
    async resolve(resolutionType) {
        if (!this.currentConflict) return;
        
        const resolutionData = {
            resolution: resolutionType,
            resolution_data: null,
            boundary_photo_required: resolutionType === 'resurvey'
        };
        
        try {
            const response = await fetch(`/api/v2/sync/conflicts/${this.currentConflict.id}/resolve`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('plotra_token')}`
                },
                body: JSON.stringify(resolutionData)
            });
            
            const result = await response.json();
            
            if (result.success) {
                bootstrap.Modal.getInstance(document.getElementById('conflictDetailModal')).hide();
                this.showToast('Conflict resolved successfully', 'success');
                await this.loadConflicts();
            } else {
                this.showToast('Resolution failed: ' + result.error, 'danger');
            }
        } catch (error) {
            this.showToast('Resolution failed', 'danger');
        }
    }
    
    showError(message) {
        this.container.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> ${message}
            </div>
        `;
    }
    
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast show align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
}

/**
 * GPS Walk UI for polygon capture
 */
class GPSWalkUI {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.sessionId = null;
        this.points = [];
        this.watchId = null;
        this.map = null;
        this.polygonLayer = null;
    }
    
    async startWalk(farmId, parcelId = null) {
        try {
            const response = await fetch('/api/v2/gis/gps-walk', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('plotra_token')}`
                },
                body: JSON.stringify({ farm_id: farmId, parcel_id: parcelId })
            });
            
            const data = await response.json();
            this.sessionId = data.session_id;
            
            this.render();
            this.initMap();
            this.startGPS();
        } catch (error) {
            console.error('Failed to start GPS walk:', error);
        }
    }
    
    render() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="gps-walk-ui">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h5 class="mb-0">GPS Boundary Walk</h5>
                    <span class="badge bg-primary">${this.points.length} points</span>
                </div>
                
                <div id="gpsWalkMap" style="height: 300px;" class="mb-2 rounded"></div>
                
                <div class="mb-2">
                    <label class="form-label">GPS Status</label>
                    <div id="gpsStatus" class="text-muted">Waiting for GPS...</div>
                </div>
                
                <div class="btn-group">
                    <button class="btn btn-success" onclick="gpsWalkUI.addPoint()">
                        <i class="bi bi-plus-circle"></i> Add Point
                    </button>
                    <button class="btn btn-danger" onclick="gpsWalkUI.removeLast()">
                        <i class="bi bi-arrow-counterclockwise"></i> Undo
                    </button>
                    <button class="btn btn-primary" onclick="gpsWalkUI.complete()">
                        <i class="bi bi-check-circle"></i> Complete
                    </button>
                </div>
                
                <div id="walkResult" class="mt-3 d-none">
                    <div class="alert alert-success">
                        <i class="bi bi-check-circle"></i> Polygon captured
                    </div>
                    <div>Area: <span id="walkArea">0</span> ha</div>
                </div>
            </div>
        `;
    }
    
    initMap() {
        this.map = L.map('gpsWalkMap').setView([-0.0236, 37.9062], 17);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap'
        }).addTo(this.map);
        
        this.markerLayer = L.featureGroup().addTo(this.map);
        this.polygonLayer = L.featureGroup().addTo(this.map);
    }
    
    startGPS() {
        if ('geolocation' in navigator) {
            this.watchId = navigator.geolocation.watchPosition(
                (pos) => this.updateGPS(pos),
                (err) => this.showGPSError(err),
                { enableHighAccuracy: true, timeout: 10000 }
            );
        }
    }
    
    updateGPS(position) {
        const { latitude, longitude, accuracy } = position.coords;
        
        this.currentPosition = { lat: latitude, lon: longitude, accuracy };
        
        document.getElementById('gpsStatus').innerHTML = `
            <span class="text-success">GPS Active</span> - 
            Accuracy: ${accuracy.toFixed(1)}m
        `;
    }
    
    showGPSError(error) {
        document.getElementById('gpsStatus').innerHTML = `
            <span class="text-danger">GPS Error: ${error.message}</span>
        `;
    }
    
    addPoint() {
        if (!this.currentPosition) {
            alert('Waiting for GPS signal...');
            return;
        }
        
        const point = this.currentPosition;
        this.points.push(point);
        
        // Add marker
        L.circleMarker([point.lat, point.lon], {
            radius: 6,
            color: '#6f4e37',
            fillColor: '#c8956c',
            fillOpacity: 1
        }).addTo(this.markerLayer);
        
        // Update polygon
        this.updatePolygon();
        
        // Update badge
        document.querySelector('.gps-walk-ui .badge').textContent = `${this.points.length} points`;
    }
    
    removeLast() {
        if (this.points.length === 0) return;
        
        this.points.pop();
        this.updatePolygon();
        document.querySelector('.gps-walk-ui .badge').textContent = `${this.points.length} points`;
    }
    
    updatePolygon() {
        this.polygonLayer.clearLayers();
        
        if (this.points.length >= 3) {
            const latlngs = this.points.map(p => [p.lat, p.lon]);
            latlngs.push(latlngs[0]); // Close ring
            
            this.polygonLayer.addLayer(L.polygon(latlngs, {
                color: '#6f4e37',
                fillColor: '#8b6914',
                fillOpacity: 0.3
            }));
            
            this.map.fitBounds(this.polygonLayer.getBounds());
        }
    }
    
    complete() {
        if (this.points.length < 3) {
            alert('Need at least 3 points');
            return;
        }
        
        // Calculate area
        const areaHa = this.calculateArea(this.points);
        
        document.getElementById('walkArea').textContent = areaHa.toFixed(2);
        document.getElementById('walkResult').classList.remove('d-none');
        
        // Stop GPS
        if (this.watchId) {
            navigator.geolocation.clearWatch(this.watchId);
        }
    }
    
    calculateArea(points) {
        // Shoelace formula
        const coords = points.map(p => [p.lon, p.lat]);
        coords.push(coords[0]);
        
        let area = 0;
        for (let i = 0; i < coords.length - 1; i++) {
            area += coords[i][0] * coords[i + 1][1];
            area -= coords[i + 1][0] * coords[i][1];
        }
        
        area = Math.abs(area) / 2;
        return area * 111.32 * 111.32 / 10000; // Approximate conversion to hectares
    }
    
    getGeoJSON() {
        if (this.points.length < 3) return null;
        
        const coordinates = this.points.map(p => [p.lon, p.lat]);
        coordinates.push(coordinates[0]);
        
        return {
            type: 'Polygon',
            coordinates: [coordinates]
        };
    }
    
    destroy() {
        if (this.watchId) {
            navigator.geolocation.clearWatch(this.watchId);
        }
        if (this.map) {
            this.map.remove();
        }
    }
}

// Global instances
let conflictUI = null;
let gpsWalkUI = null;

function initConflictUI(containerId) {
    conflictUI = new ConflictResolutionUI(containerId);
    return conflictUI;
}

function initGPSWalkUI(containerId) {
    gpsWalkUI = new GPSWalkUI(containerId);
    return gpsWalkUI;
}