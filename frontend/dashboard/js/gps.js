/**
 * Plotra Dashboard - GPS Mapping Module
 * Leaflet map initialization, polygon capture, GPS tracking
 */

let gpsMapping = null;

function initGPSMapping() {
    if (gpsMapping) return gpsMapping;
    gpsMapping = new GPSMapping();
    return gpsMapping;
}

function setupGPSButtons() {
    const startBtn = document.getElementById('startCaptureBtn');
    const addBtn = document.getElementById('addPointBtn');
    const finishBtn = document.getElementById('finishCaptureBtn');
    const clearBtn = document.getElementById('clearPointsBtn');
    
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            gpsMapping = initGPSMapping();
            gpsMapping.initMap('farmMap');
            
            const started = gpsMapping.startGPSCapture();
            if (started) {
                startBtn.disabled = true;
                startBtn.classList.add('btn-secondary');
                startBtn.classList.remove('btn-primary');
                
                if (addBtn) addBtn.disabled = false;
                if (clearBtn) clearBtn.disabled = false;
                
                const instructions = document.getElementById('captureInstructions');
                if (instructions) {
                    instructions.textContent = 'GPS tracking started. Walk around the perimeter and click "Add Point" at each corner.';
                }
            }
        });
    }
    
    if (addBtn) {
        addBtn.addEventListener('click', () => {
            if (gpsMapping) {
                const pt = gpsMapping.capturePoint();
                if (pt) {
                    updateGPSUI();
                    
                    if (gpsMapping.capturedPoints.length >= 3 && finishBtn) {
                        finishBtn.disabled = false;
                    }
                } else {
                    alert('Click "Start Capture" first to get GPS position.');
                }
            }
        });
    }
    
    if (finishBtn) {
        finishBtn.addEventListener('click', () => {
            if (gpsMapping && gpsMapping.capturedPoints.length >= 3) {
                gpsMapping.stopGPSCapture();
                
                if (startBtn) {
                    startBtn.disabled = false;
                    startBtn.classList.remove('btn-secondary');
                    startBtn.classList.add('btn-primary');
                }
                if (addBtn) addBtn.disabled = true;
                if (finishBtn) finishBtn.disabled = true;
                
                const geojson = gpsMapping.getGeoJSON();
                console.log('Polygon captured:', geojson);
                
                const instructions = document.getElementById('captureInstructions');
                if (instructions) {
                    instructions.textContent = 'Polygon captured with ' + gpsMapping.capturedPoints.length + ' points.';
                }
                
                window.dispatchEvent(new CustomEvent('gpsPointsUpdated', {
                    detail: { count: gpsMapping.capturedPoints.length, geojson }
                }));
            }
        });
    }
    
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            if (gpsMapping) {
                gpsMapping.clear();
                gpsMapping.stopGPSCapture();
                
                document.getElementById('gpsAccuracy').textContent = '--';
                document.getElementById('pointCount').textContent = '0';
                document.getElementById('calculatedArea').textContent = '--';
                
                if (startBtn) {
                    startBtn.disabled = false;
                    startBtn.classList.remove('btn-secondary');
                    startBtn.classList.add('btn-primary');
                }
                if (addBtn) addBtn.disabled = true;
                if (finishBtn) finishBtn.disabled = true;
                if (clearBtn) clearBtn.disabled = true;
                
                const instructions = document.getElementById('captureInstructions');
                if (instructions) {
                    instructions.textContent = 'Click "Start Capture" to begin mapping your farm boundary.';
                }
                
                window.dispatchEvent(new CustomEvent('gpsPointsUpdated', {
                    detail: { count: 0, geojson: null }
                }));
            }
        });
    }
}

function updateGPSUI() {
    if (!gpsMapping) return;
    
    const accuracyEl = document.getElementById('gpsAccuracy');
    const countEl = document.getElementById('pointCount');
    const areaEl = document.getElementById('calculatedArea');
    
    if (gpsMapping.currentPosition && accuracyEl) {
        accuracyEl.textContent = gpsMapping.currentPosition.accuracy.toFixed(1);
    }
    
    if (countEl) {
        countEl.textContent = gpsMapping.capturedPoints.length;
    }
    
    if (gpsMapping.capturedPoints.length >= 3) {
        const coords = gpsMapping.capturedPoints.map(p => [p.lon, p.lat]);
        coords.push(coords[0]);
        const area = gpsMapping.calculateArea(coords);
        if (areaEl) areaEl.textContent = area.toFixed(2);
    }
}

class GPSMapping {
    constructor() {
        this.map = null;
        this.drawnItems = null;
        this.captureMode = false;
        this.capturedPoints = [];
        this.currentPolygon = null;
        this.gpsWatchId = null;
        this.currentPosition = null;
    }
    
    initMap(containerId = 'farmMap') {
        if (this.map) return this.map;
        
        const container = document.getElementById(containerId);
        if (!container) return null;
        
        this.map = L.map(containerId, {
            center: [-0.0236, 37.9062],
            zoom: 8,
            zoomControl: true
        });
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: 'OpenStreetMap contributors',
            maxZoom: 18
        }).addTo(this.map);
        
        this.drawnItems = new L.FeatureGroup();
        this.map.addLayer(this.drawnItems);
        
        const drawControl = new L.Control.Draw({
            edit: { featureGroup: this.drawnItems, edit: false, remove: false },
            draw: {
                polygon: {
                    allowIntersection: false,
                    showArea: true,
                    shapeOptions: {
                        color: '#6f4e37',
                        weight: 3,
                        fillColor: '#8b6914',
                        fillOpacity: 0.3
                    }
                },
                rectangle: false,
                circle: false,
                marker: false,
                polyline: false,
                circlemarker: false
            }
        });
        
        this.map.addControl(drawControl);
        
        this.map.on(L.Draw.Event.CREATED, (event) => {
            const layer = event.layer;
            this.drawnItems.addLayer(layer);
            this.currentPolygon = layer.toGeoJSON();
            this.updateStats();
        });
        
        return this.map;
    }
    
    startGPSCapture() {
        if ('geolocation' in navigator) {
            this.captureMode = true;
            this.capturedPoints = [];
            
            this.gpsWatchId = navigator.geolocation.watchPosition(
                (pos) => this.onGPSUpdate(pos),
                (err) => this.onGPSError(err),
                { enableHighAccuracy: true, timeout: 10000 }
            );
            
            return true;
        }
        return false;
    }
    
    onGPSUpdate(position) {
        this.currentPosition = {
            lat: position.coords.latitude,
            lon: position.coords.longitude,
            accuracy: position.coords.accuracy,
            timestamp: position.timestamp
        };
        
        if (this.captureMode && this.map) {
            L.circleMarker([this.currentPosition.lat, this.currentPosition.lon], {
                radius: 6,
                color: '#28a745',
                fillColor: '#28a745',
                fillOpacity: 1
            }).addTo(this.map);
        }
        
        const statusEl = document.getElementById('gpsStatus');
        if (statusEl) {
            statusEl.innerHTML = '<span class="text-success">GPS: ' + this.currentPosition.accuracy.toFixed(1) + 'm</span>';
        }
    }
    
    onGPSError(error) {
        const statusEl = document.getElementById('gpsStatus');
        if (statusEl) {
            statusEl.innerHTML = '<span class="text-danger">GPS: ' + error.message + '</span>';
        }
    }
    
    capturePoint() {
        if (!this.currentPosition) return null;
        
        const point = { ...this.currentPosition };
        this.capturedPoints.push(point);
        this.updatePolygon();
        
        return point;
    }
    
    updatePolygon() {
        if (this.capturedPoints.length < 3) return;
        
        this.drawnItems?.clearLayers();
        
        const latlngs = this.capturedPoints.map(p => [p.lat, p.lon]);
        latlngs.push(latlngs[0]);
        
        L.polygon(latlngs, {
            color: '#6f4e37',
            fillColor: '#8b6914',
            fillOpacity: 0.3
        }).addTo(this.drawnItems);
        
        this.capturedPoints.forEach((p, i) => {
            L.circleMarker([p.lat, p.lon], {
                radius: 8,
                color: '#28a745',
                fillColor: '#fff',
                fillOpacity: 1
            }).bindTooltip(String(i + 1)).addTo(this.drawnItems);
        });
        
        this.currentPolygon = {
            type: 'Feature',
            geometry: {
                type: 'Polygon',
                coordinates: [this.capturedPoints.map(p => [p.lon, p.lat]).concat([[this.capturedPoints[0].lon, this.capturedPoints[0].lat]])]
            }
        };
        
        this.map?.fitBounds(this.drawnItems.getBounds());
        
        const finishBtn = document.getElementById('finishCaptureBtn');
        if (finishBtn) finishBtn.disabled = false;
    }
    
    stopGPSCapture() {
        if (this.gpsWatchId) {
            navigator.geolocation.clearWatch(this.gpsWatchId);
            this.gpsWatchId = null;
        }
        this.captureMode = false;
    }
    
    updateStats() {
        if (!this.currentPolygon) return;
        
        const coords = this.currentPolygon.geometry.coordinates[0];
        const area = this.calculateArea(coords);
        
        const areaEl = document.getElementById('polygonArea');
        if (areaEl) areaEl.textContent = area.toFixed(2) + ' ha';
    }
    
    calculateArea(coords) {
        if (coords.length < 3) return 0;
        
        const latMid = coords.reduce((s, c) => s + c[1], 0) / coords.length;
        const mPerDegLon = 111320 * Math.cos(latMid * Math.PI / 180);
        const mPerDegLat = 111320;
        
        let area = 0;
        for (let i = 0; i < coords.length - 1; i++) {
            area += coords[i][0] * coords[i + 1][1] * mPerDegLon;
            area -= coords[i + 1][0] * coords[i][1] * mPerDegLon;
        }
        
        return Math.abs(area) / 2 * mPerDegLat / 10000;
    }
    
    getGeoJSON() {
        if (this.capturedPoints.length < 3) return null;
        
        const coordinates = this.capturedPoints.map(p => [p.lon, p.lat]);
        coordinates.push(coordinates[0]);
        
        return { type: 'Polygon', coordinates: [coordinates] };
    }
    
    clear() {
        this.drawnItems?.clearLayers();
        this.capturedPoints = [];
        this.currentPolygon = null;
        this.currentPosition = null;
    }
    
    destroy() {
        this.stopGPSCapture();
        if (this.map) { this.map.remove(); this.map = null; }
    }
}

window.GPSMapping = GPSMapping;

function getCapturedPolygon() {
    if (!gpsMapping || gpsMapping.capturedPoints.length < 3) return null;
    return gpsMapping.getGeoJSON();
}

window.getCapturedPolygon = getCapturedPolygon;