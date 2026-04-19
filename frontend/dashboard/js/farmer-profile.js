/**
 * Farmer Profile Page - PLOTRA EUDR Compliance Platform
 * Handles two-section farmer profile with auto-fill and EUDR risk detection
 * Fully functional with API integration and comprehensive error handling
 */

class FarmerProfileManager {
    constructor() {
        this.form = document.getElementById('farmerProfileForm');
        this.currentUser = null;
        this.farmData = null;
        this.map = null;
        this.editableLayers = null;
        this.isSubmitting = false;
        this.riskFlags = {
            treesCleared: false,
            establishedAfter2020: false,
            communalNoRegistration: false,
            highRiskFlags: []
        };
        
        this.init();
    }

    /**
     * Initialize the farmer profile manager
     */
    async init() {
        try {
            // Load current user data
            await this.loadUserData();
            
            // Initialize form
            this.initializeForm();
            
            // Setup event listeners
            this.setupEventListeners();
            
            // Initialize GPS map
            this.initializeGPSMap();
            
            // Load existing profile data if available
            await this.loadProfileData();
            
            console.log('Farmer Profile Manager initialized');
        } catch (error) {
            console.error('Error initializing farmer profile:', error);
            this.showAlert('Error initializing profile. Please refresh the page.', 'danger');
        }
    }

    /**
     * Load current user data from session
     */
    async loadUserData() {
        try {
            const token = localStorage.getItem(CONFIG.session.tokenKey);
            const userData = localStorage.getItem(CONFIG.session.userKey);
            
            if (!userData) {
                throw new Error('User not authenticated');
            }
            
            this.currentUser = JSON.parse(userData);
            
            // Pre-fill Section 1 with user data
            this.prefillUserData();
        } catch (error) {
            console.error('Error loading user data:', error);
            throw error;
        }
    }

    /**
     * Pre-fill Section 1 with user data
     */
    prefillUserData() {
        if (this.currentUser) {
            document.getElementById('firstName').value = this.currentUser.first_name || '';
            document.getElementById('lastName').value = this.currentUser.last_name || '';
            document.getElementById('email').value = this.currentUser.email || '';
            document.getElementById('phone').value = this.currentUser.phone || '';
            document.getElementById('county').value = this.currentUser.county || '';
            document.getElementById('district').value = this.currentUser.district || '';
            document.getElementById('ward').value = this.currentUser.ward || '';
            document.getElementById('address').value = this.currentUser.address || '';
            document.getElementById('nationalId').value = this.currentUser.national_id || '';
        }
    }

    /**
     * Initialize form sections and collapsible functionality
     */
    initializeForm() {
        const sectionHeaders = document.querySelectorAll('.section-header');
        
        sectionHeaders.forEach(header => {
            header.addEventListener('click', (e) => {
                const card = header.closest('.section-card');
                card.classList.toggle('collapsed');
            });
        });
    }

    /**
     * Setup all event listeners for form interactions
     */
    setupEventListeners() {
        // Back buttons
        const backBtns = document.querySelectorAll('#backToDashboardBtn, #backBtn');
        backBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                if (this.formHasChanges()) {
                    const confirmed = confirm('You have unsaved changes. Are you sure you want to leave?\n\nClick "Cancel" to save your draft first.');
                    if (!confirmed) return;
                }
                window.location.hash = '#dashboard';
            });
        });

        // Save draft buttons
        const saveDraftBtns = document.querySelectorAll('#saveDraftBtn, #saveDraftBtn2');
        saveDraftBtns.forEach(btn => {
            btn.addEventListener('click', () => this.saveDraft());
        });

        // Section 1: Cooperative membership toggle
        const coopRadios = document.querySelectorAll('input[name="memberOfCoop"]');
        coopRadios.forEach(radio => {
            radio.addEventListener('change', () => this.toggleCooperativeFields());
        });

        // Section 2: Mixed farming toggle
        const mixedFarmingRadios = document.querySelectorAll('input[name="mixedFarming"]');
        mixedFarmingRadios.forEach(radio => {
            radio.addEventListener('change', () => this.toggleMixedFarmingFields());
        });

        // Trees planted toggle
        const treesPlantedRadios = document.querySelectorAll('input[name="treesPlanedLast5"]');
        treesPlantedRadios.forEach(radio => {
            radio.addEventListener('change', () => this.toggleTreesPlantedFields());
        });

        // Trees cleared toggle (HIGH RISK)
        const treesClearedRadios = document.querySelectorAll('input[name="treesCleared"]');
        treesClearedRadios.forEach(radio => {
            radio.addEventListener('change', () => this.toggleTreesClearedFields());
        });

        // Irrigation toggle
        const irrigationRadios = document.querySelectorAll('input[name="irrigationUsed"]');
        irrigationRadios.forEach(radio => {
            radio.addEventListener('change', () => this.toggleIrrigationFields());
        });

        // Livestock toggle
        const livestockRadios = document.querySelectorAll('input[name="livestock"]');
        livestockRadios.forEach(radio => {
            radio.addEventListener('change', () => this.toggleLivestockFields());
        });

        // Previous violations toggle
        const violationRadios = document.querySelectorAll('input[name="previousViolations"]');
        violationRadios.forEach(radio => {
            radio.addEventListener('change', () => this.toggleViolationFields());
        });

        // Coffee percentage slider
        const coffeePercentRange = document.getElementById('coffeePercent');
        if (coffeePercentRange) {
            coffeePercentRange.addEventListener('input', (e) => {
                document.getElementById('coffeePercentValue').textContent = e.target.value;
            });
        }

        // Form submission
        this.form.addEventListener('submit', (e) => this.handleFormSubmit(e));

        // Monitor form changes for progress
        const formInputs = this.form.querySelectorAll('input, select, textarea');
        formInputs.forEach(input => {
            input.addEventListener('change', () => this.updateProgress());
        });
    }

    /**
     * Check if form has unsaved changes
     */
    formHasChanges() {
        const currentData = JSON.stringify(this.collectFormData());
        const savedData = localStorage.getItem('farmerProfileDraft');
        return currentData !== savedData;
    }

    /**
     * Trigger state updates for conditional fields
     */
    triggerStateUpdates() {
        this.toggleCooperativeFields();
        this.toggleMixedFarmingFields();
        this.toggleTreesPlantedFields();
        this.toggleTreesClearedFields();
        this.toggleIrrigationFields();
        this.toggleLivestockFields();
        this.toggleViolationFields();
        this.updateProgress();
    }

    /**
     * Initialize GPS mapping with Leaflet and Draw
     */
    initializeGPSMap() {
        const mapContainer = document.getElementById('gpsMapContainer');
        if (!mapContainer) return;

        try {
            // Check if Leaflet is loaded
            if (typeof L === 'undefined') {
                console.warn('Leaflet library not loaded. GPS mapping disabled.');
                mapContainer.innerHTML = '<div class="alert alert-warning m-3">GPS mapping feature unavailable. Please ensure Leaflet library is loaded.</div>';
                return;
            }

            // Initialize map centered on Kenya
            this.map = L.map('gpsMapContainer').setView([0.5, 36.5], 6);

            // Add tile layer
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                maxZoom: 19
            }).addTo(this.map);

            // Initialize editable layers group
            this.editableLayers = new L.FeatureGroup();
            this.map.addLayer(this.editableLayers);

            // Check if Leaflet.Draw is loaded
            if (typeof L.Control.Draw === 'undefined') {
                console.warn('Leaflet.Draw not available. Drawing controls disabled.');
                return;
            }

            // Add drawing controls
            const drawControl = new L.Control.Draw({
                position: 'topleft',
                draw: {
                    polygon: true,
                    polyline: false,
                    rectangle: false,
                    circle: false,
                    marker: false,
                    circlemarker: false
                },
                edit: {
                    featureGroup: this.editableLayers,
                    edit: true,
                    remove: true
                }
            });
            this.map.addControl(drawControl);

            // Handle drawing events
            this.map.on('draw:created', (e) => this.handleShapeCreated(e));
            this.map.on('draw:edited', (e) => this.handleShapeEdited(e));
            this.map.on('draw:deleted', () => this.clearBoundaryData());

            // Custom buttons
            const captureBtn = document.getElementById('captureGPS');
            const clearBtn = document.getElementById('clearGPS');

            if (captureBtn) {
                captureBtn.addEventListener('click', () => {
                    this.map.flyTo([0.5, 36.5], 10);
                    this.showAlert('📍 You can now draw your farm boundary on the map. Click on the map to start drawing.', 'info');
                });
            }

            if (clearBtn) {
                clearBtn.addEventListener('click', () => {
                    this.editableLayers.clearLayers();
                    this.clearBoundaryData();
                    this.showAlert('✓ Boundary cleared. You can draw a new one.', 'success');
                });
            }

        } catch (error) {
            console.error('Error initializing GPS map:', error);
            this.showAlert('🗺️ Could not initialize mapping feature. GPS drawing disabled. You can still fill other fields.', 'warning');
        }
    }

    /**
     * Handle shape created on map
     */
    handleShapeCreated(e) {
        const layer = e.layer;
        const geoJSON = layer.toGeoJSON();
        
        // Store GeoJSON
        document.getElementById('boundaryGeojson').value = JSON.stringify(geoJSON);
        
        // Calculate area if polygon
        if (geoJSON.geometry.type === 'Polygon') {
            const area = this.calculatePolygonArea(geoJSON.geometry.coordinates[0]);
            document.getElementById('areaCalculated').value = area.toFixed(4);
            
            // Auto-fill total area if empty
            const totalAreaInput = document.getElementById('totalArea');
            if (!totalAreaInput.value) {
                totalAreaInput.value = area.toFixed(2);
            }
        }
        
        console.log('Parcel boundary captured:', geoJSON);
    }

    /**
     * Handle shape edited on map
     */
    handleShapeEdited(e) {
        const layers = e.layers;
        layers.eachLayer((layer) => {
            const geoJSON = layer.toGeoJSON();
            document.getElementById('boundaryGeojson').value = JSON.stringify(geoJSON);
            
            if (geoJSON.geometry.type === 'Polygon') {
                const area = this.calculatePolygonArea(geoJSON.geometry.coordinates[0]);
                document.getElementById('areaCalculated').value = area.toFixed(4);
            }
        });
    }

    /**
     * Clear boundary data
     */
    clearBoundaryData() {
        document.getElementById('boundaryGeojson').value = '';
        document.getElementById('areaCalculated').value = '';
    }

    /**
     * Calculate polygon area using Haversine formula (in hectares)
     */
    calculatePolygonArea(coords) {
        const R = 6371000; // Earth's radius in meters
        let area = 0;
        
        for (let i = 0; i < coords.length - 1; i++) {
            const lat1 = (coords[i][1] * Math.PI) / 180;
            const lon1 = (coords[i][0] * Math.PI) / 180;
            const lat2 = (coords[i + 1][1] * Math.PI) / 180;
            const lon2 = (coords[i + 1][0] * Math.PI) / 180;
            
            const dLat = lat2 - lat1;
            const dLon = lon2 - lon1;
            
            const a = Math.sin(dLat / 2) ** 2 + 
                     Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
            const distance = R * c;
            
            area += (distance * distance) / 2;
        }
        
        // Convert square meters to hectares
        return Math.abs(area) / 10000;
    }

    /**
     * Toggle cooperative membership fields
     */
    toggleCooperativeFields() {
        const value = document.querySelector('input[name="memberOfCoop"]:checked')?.value;
        document.getElementById('cooperativeNameField').style.display = value === 'yes' ? 'block' : 'none';
        document.getElementById('coopRegNumberField').style.display = value === 'yes' ? 'block' : 'none';
    }

    /**
     * Toggle mixed farming fields
     */
    toggleMixedFarmingFields() {
        const value = document.querySelector('input[name="mixedFarming"]:checked')?.value;
        const show = value === 'yes';
        
        document.getElementById('coffeePercentField').style.display = show ? 'block' : 'none';
        document.getElementById('otherCropsField').style.display = show ? 'block' : 'none';
        document.getElementById('livestockField').style.display = show ? 'block' : 'none';
        document.getElementById('cropRotationField').style.display = show ? 'block' : 'none';
    }

    /**
     * Toggle trees planted fields
     */
    toggleTreesPlantedFields() {
        const value = document.querySelector('input[name="treesPlanedLast5"]:checked')?.value;
        const show = value === 'yes';
        
        document.getElementById('treeSpeciesField').style.display = show ? 'block' : 'none';
        document.getElementById('treeCountField').style.display = show ? 'block' : 'none';
        document.getElementById('treePlanningReasonField').style.display = show ? 'block' : 'none';
    }

    /**
     * Toggle trees cleared fields (HIGH EUDR RISK)
     */
    toggleTreesClearedFields() {
        const value = document.querySelector('input[name="treesCleared"]:checked')?.value;
        const show = value === 'yes';
        
        document.getElementById('reasonForClearingField').style.display = show ? 'block' : 'none';
        document.getElementById('treeClearingAlert').style.display = show ? 'block' : 'none';
        
        // Flag for EUDR risk
        this.riskFlags.treesCleared = show;
        this.checkEUDRRisks();
    }

    /**
     * Toggle irrigation fields
     */
    toggleIrrigationFields() {
        const value = document.querySelector('input[name="irrigationUsed"]:checked')?.value;
        document.getElementById('irrigationTypeField').style.display = value === 'yes' ? 'block' : 'none';
    }

    /**
     * Toggle livestock fields
     */
    toggleLivestockFields() {
        const value = document.querySelector('input[name="livestock"]:checked')?.value;
        document.getElementById('livestockTypeField').style.display = value === 'yes' ? 'block' : 'none';
    }

    /**
     * Toggle violation fields
     */
    toggleViolationFields() {
        const value = document.querySelector('input[name="previousViolations"]:checked')?.value;
        document.getElementById('violationDetailsField').style.display = value === 'yes' ? 'block' : 'none';
    }

    /**
     * Check EUDR risk triggers
     */
    checkEUDRRisks() {
        this.riskFlags.highRiskFlags = [];

        // Risk 1: Trees cleared in last 5 years
        if (this.riskFlags.treesCleared) {
            this.riskFlags.highRiskFlags.push('Trees cleared in last 5 years = HIGH RISK → mandatory satellite review');
        }

        // Risk 2: Farm established after Dec 31, 2020
        const yearPlanted = parseInt(document.getElementById('yearCoffeePlanted').value) || 0;
        if (yearPlanted > 2020) {
            this.riskFlags.establishedAfter2020 = true;
            this.riskFlags.highRiskFlags.push('Farm established after Dec 31, 2020 → Mandatory deforestation check required');
        }

        // Risk 3: Communal land with no registration
        const landType = document.getElementById('farmType').value;
        const regNumber = document.getElementById('landRegNumber').value;
        if (landType === 'communal' && !regNumber) {
            this.riskFlags.communalNoRegistration = true;
            this.riskFlags.highRiskFlags.push('Communal land with no registration → Flag for additional documentation');
        }

        // Update status badge
        this.updateStatusBadge();

        if (this.riskFlags.highRiskFlags.length > 0) {
            console.warn('EUDR Risk Flags:', this.riskFlags.highRiskFlags);
        }
    }

    /**
     * Update profile status badge
     */
    updateStatusBadge() {
        const badge = document.getElementById('profileStatusBadge');
        
        if (this.riskFlags.highRiskFlags.length > 0) {
            badge.className = 'badge badge-danger';
            badge.textContent = `⚠️ ${this.riskFlags.highRiskFlags.length} Risk Flag(s)`;
        }
    }

    /**
     * Update form progress
     */
    updateProgress() {
        const totalFields = this.form.querySelectorAll('input[required], select[required], textarea[required]').length;
        const filledFields = Array.from(this.form.querySelectorAll('input[required], select[required], textarea[required]'))
            .filter(field => {
                if (field.type === 'checkbox' || field.type === 'radio') {
                    return document.querySelector(`input[name="${field.name}"]:checked`);
                }
                return field.value.trim() !== '';
            }).length;

        const progress = Math.round((filledFields / totalFields) * 100);
        const progressBar = document.getElementById('profileProgressBar');
        const progressText = document.getElementById('profileProgressText');

        progressBar.style.width = progress + '%';
        progressText.textContent = `${progress}% Complete`;

        if (progress === 100) {
            progressBar.classList.add('complete');
        }
    }

    /**
     * Load existing profile data
     */
    async loadProfileData() {
        try {
            // First, try to load saved draft
            const draftData = localStorage.getItem('farmerProfileDraft');
            if (draftData) {
                try {
                    const draft = JSON.parse(draftData);
                    this.populateFormWithDraftData(draft);
                    this.showAlert('📋 Draft loaded. You can continue editing your profile.', 'info');
                } catch (e) {
                    console.warn('Invalid draft data:', e);
                    localStorage.removeItem('farmerProfileDraft');
                }
            }

            // Then, try to fetch existing farm data from API
            const token = localStorage.getItem(CONFIG.session.tokenKey);
            if (!token) return;

            const response = await fetch(`${CONFIG.api.baseUrl}/farmer/farm`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const farms = await response.json();
                if (farms && farms.length > 0) {
                    this.farmData = Array.isArray(farms) ? farms[0] : farms;
                    if (!draftData) {
                        this.populateFormWithFarmData();
                    }
                }
            }
        } catch (error) {
            console.log('No existing farm data found. Starting with blank form.');
        }
    }

    /**
     * Populate form with draft data
     */
    populateFormWithDraftData(draft) {
        if (!draft) return;

        // Section 1: Personal Details
        if (draft.personal) {
            Object.keys(draft.personal).forEach(key => {
                const element = document.getElementById(key);
                if (element) {
                    element.value = draft.personal[key] || '';
                }
            });
        }

        // Section 2: Farm Details
        if (draft.farm) {
            Object.keys(draft.farm).forEach(key => {
                const element = document.getElementById(key);
                if (element) {
                    if (element.type === 'checkbox') {
                        element.checked = draft.farm[key] === true;
                    } else if (element.type === 'radio') {
                        const radio = document.querySelector(`input[name="${key}"][value="${draft.farm[key]}"]`);
                        if (radio) radio.checked = true;
                    } else if (element.multiple) {
                        // Multi-select
                        Array.from(element.options).forEach(opt => {
                            opt.selected = (draft.farm[key] || []).includes(opt.value);
                        });
                    } else {
                        element.value = draft.farm[key] || '';
                    }
                }
            });
        }

        // Trigger change events to show conditional fields
        this.triggerStateUpdates();
    }

    /**
     * Populate form with existing farm data
     */
    populateFormWithFarmData() {
        if (!this.farmData) return;

        // Section 2: Farm Details
        document.getElementById('farmName').value = this.farmData.farm_name || '';
        document.getElementById('totalArea').value = this.farmData.total_area_hectares || '';
        document.getElementById('altitude').value = this.farmData.altitude || '';
        
        if (this.farmData.coffee_varieties) {
            const varietySelect = document.getElementById('coffeeVariety');
            Array.from(varietySelect.options).forEach(option => {
                option.selected = this.farmData.coffee_varieties.includes(option.value);
            });
        }

        document.getElementById('estimatedYield').value = this.farmData.average_annual_production_kg || '';
    }

    /**
     * Validate form
     */
    validateForm() {
        const errors = [];

        // Section 1 validation
        if (!document.getElementById('firstName').value.trim()) {
            errors.push('First name is required');
        }
        if (!document.getElementById('lastName').value.trim()) {
            errors.push('Last name is required');
        }
        if (!document.getElementById('email').value.trim()) {
            errors.push('Email is required');
        }
        if (!document.getElementById('phone').value.trim()) {
            errors.push('Phone number is required');
        }
        if (!document.getElementById('county').value) {
            errors.push('County is required');
        }
        if (!document.getElementById('district').value.trim()) {
            errors.push('District is required');
        }

        // Section 2 validation
        if (!document.getElementById('farmName').value.trim()) {
            errors.push('Farm/Parcel name is required');
        }
        if (!document.getElementById('farmType').value) {
            errors.push('Farm type is required');
        }
        if (!document.getElementById('totalArea').value) {
            errors.push('Total parcel area is required');
        }
        if (!document.getElementById('soilType').value) {
            errors.push('Soil type is required');
        }
        if (!document.getElementById('terrain').value) {
            errors.push('Terrain is required');
        }
        if (!document.getElementById('coffeeVariety').value) {
            errors.push('At least one coffee variety is required');
        }
        if (!document.getElementById('yearCoffeePlanted').value) {
            errors.push('Year coffee first planted is required');
        }
        if (!document.getElementById('farmStatus').value) {
            errors.push('Farm status is required');
        }
        if (!document.getElementById('plantingMethod').value) {
            errors.push('Planting method is required');
        }
        if (!document.querySelector('input[name="irrigationUsed"]:checked')) {
            errors.push('Please indicate if irrigation is used');
        }
        if (!document.querySelector('input[name="mixedFarming"]:checked')) {
            errors.push('Please indicate if mixed farming is practiced');
        }
        if (!document.querySelector('input[name="treesPlanedLast5"]:checked')) {
            errors.push('Please indicate if trees were planted in last 5 years');
        }
        if (!document.querySelector('input[name="treesCleared"]:checked')) {
            errors.push('Please indicate if trees were cleared in last 5 years');
        }
        if (!document.getElementById('currentCanopyCover').value) {
            errors.push('Current canopy cover is required');
        }
        if (!document.getElementById('satelliteConsent').checked) {
            errors.push('Satellite monitoring consent is required');
        }
        if (!document.getElementById('historicalImageryConsent').checked) {
            errors.push('Historical imagery consent is required');
        }

        return errors;
    }

    /**
     * Collect form data
     */
    collectFormData() {
        const formData = new FormData(this.form);
        const data = {
            // Section 1: Personal Details
            personal: {
                firstName: document.getElementById('firstName').value,
                lastName: document.getElementById('lastName').value,
                email: document.getElementById('email').value,
                phone: document.getElementById('phone').value,
                dob: document.getElementById('dob').value,
                nationalId: document.getElementById('nationalId').value,
                county: document.getElementById('county').value,
                district: document.getElementById('district').value,
                ward: document.getElementById('ward').value,
                address: document.getElementById('address').value,
                memberOfCoop: document.querySelector('input[name="memberOfCoop"]:checked')?.value,
                cooperativeName: document.getElementById('cooperativeName').value,
                coopRegNumber: document.getElementById('coopRegNumber').value
            },
            // Section 2: Farm Details
            farm: {
                // Land & Parcel Information
                farmName: document.getElementById('farmName').value,
                farmType: document.getElementById('farmType').value,
                landRegNumber: document.getElementById('landRegNumber').value,
                totalArea: parseFloat(document.getElementById('totalArea').value),
                altitude: document.getElementById('altitude').value ? parseInt(document.getElementById('altitude').value) : null,
                soilType: document.getElementById('soilType').value,
                terrain: document.getElementById('terrain').value,
                boundaryGeojson: document.getElementById('boundaryGeojson').value,
                areaCalculated: document.getElementById('areaCalculated').value,

                // Coffee Farming Details
                coffeeVariety: Array.from(document.getElementById('coffeeVariety').selectedOptions).map(o => o.value),
                yearCoffeePlanted: parseInt(document.getElementById('yearCoffeePlanted').value),
                coffeeTreeCount: document.getElementById('coffeeTreeCount').value ? parseInt(document.getElementById('coffeeTreeCount').value) : null,
                farmStatus: document.getElementById('farmStatus').value,
                plantingMethod: document.getElementById('plantingMethod').value,
                irrigationUsed: document.querySelector('input[name="irrigationUsed"]:checked')?.value,
                irrigationType: document.getElementById('irrigationType').value,
                estimatedYield: document.getElementById('estimatedYield').value ? parseFloat(document.getElementById('estimatedYield').value) : null,

                // Mixed Farming
                mixedFarming: document.querySelector('input[name="mixedFarming"]:checked')?.value,
                coffeePercent: document.getElementById('coffeePercent').value,
                otherCrops: Array.from(document.querySelectorAll('input[name="otherCrops"]:checked')).map(c => c.value),
                livestock: document.querySelector('input[name="livestock"]:checked')?.value,
                livestockType: Array.from(document.querySelectorAll('input[name="livestockType"]:checked')).map(l => l.value),
                cropRotation: document.querySelector('input[name="cropRotation"]:checked')?.value,

                // Trees & Deforestation
                treesPlanedLast5: document.querySelector('input[name="treesPlanedLast5"]:checked')?.value,
                treeSpecies: Array.from(document.querySelectorAll('input[name="treeSpecies"]:checked')).map(t => t.value),
                treeCount: document.getElementById('treeCount').value ? parseInt(document.getElementById('treeCount').value) : null,
                treePlanningReason: Array.from(document.querySelectorAll('input[name="treePlanningReason"]:checked')).map(r => r.value),
                treesCleared: document.querySelector('input[name="treesCleared"]:checked')?.value,
                reasonForClearing: document.getElementById('reasonForClearing').value,
                currentCanopyCover: document.getElementById('currentCanopyCover').value,

                // Satellite Consent
                satelliteConsent: document.getElementById('satelliteConsent').checked,
                historicalImageryConsent: document.getElementById('historicalImageryConsent').checked,
                monitoringFrequency: document.getElementById('monitoringFrequency').value,

                // Certifications
                certifications: Array.from(document.querySelectorAll('input[name="certifications"]:checked')).map(c => c.value),
                certExpiryDate: document.getElementById('certExpiryDate').value,
                previousViolations: document.querySelector('input[name="previousViolations"]:checked')?.value,
                violationDetails: document.getElementById('violationDetails').value
            },
            eudrRisks: this.riskFlags
        };

        return data;
    }

    /**
     * Handle form submission
     */
    async handleFormSubmit(e) {
        e.preventDefault();

        // Prevent duplicate submissions
        if (this.isSubmitting) {
            this.showAlert('Profile is being submitted. Please wait...', 'info');
            return;
        }

        // Validate form
        const errors = this.validateForm();
        if (errors.length > 0) {
            this.showAlert(`Please fix the following errors:\n• ${errors.join('\n• ')}`, 'danger');
            return;
        }

        // Check EUDR risks
        this.checkEUDRRisks();
        if (this.riskFlags.highRiskFlags.length > 0) {
            const confirmed = confirm(
                `⚠️ WARNING: Your profile has HIGH EUDR RISK flags:\n\n• ${this.riskFlags.highRiskFlags.join('\n• ')}\n\n` +
                'Your profile will be flagged for mandatory satellite review and compliance team verification.\n\n' +
                'Do you want to proceed with submission?'
            );
            if (!confirmed) return;
        }

        this.isSubmitting = true;
        const submitBtn = document.getElementById('submitBtn');
        const originalText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="loading-spinner"></span> Submitting...';

        try {
            // Collect form data
            const formData = this.collectFormData();

            // Validate API configuration
            if (!CONFIG?.api?.baseUrl) {
                throw new Error('API configuration not found. Please refresh the page.');
            }

            // Submit to API
            const token = localStorage.getItem(CONFIG.session.tokenKey);
            if (!token) {
                throw new Error('Authentication required. Please log in again.');
            }

            const response = await fetch(`${CONFIG.api.baseUrl}/farmer/profile/submit`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `Server error: ${response.status}`);
            }

            const result = await response.json();

            // Clear draft
            localStorage.removeItem('farmerProfileDraft');

            // Show success alert
            this.showAlert(
                '✅ Profile submitted successfully!\n\nYour farming information has been received. ' +
                'Our compliance team will review your data and contact you within 3-5 business days.',
                'success'
            );

            // Wait before redirecting
            setTimeout(() => {
                window.location.hash = '#dashboard';
            }, 3000);

        } catch (error) {
            console.error('Error submitting profile:', error);
            this.showAlert(
                `❌ Error submitting profile:\n\n${error.message}\n\nPlease try again or contact support if the problem persists.`,
                'danger'
            );
        } finally {
            this.isSubmitting = false;
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
    }

    /**
     * Save draft locally
     */
    saveDraft() {
        try {
            const formData = this.collectFormData();
            localStorage.setItem('farmerProfileDraft', JSON.stringify(formData));
            this.showAlert('💾 Profile draft saved successfully! You can continue editing anytime.', 'success');
        } catch (error) {
            console.error('Error saving draft:', error);
            this.showAlert('❌ Error saving draft to browser storage', 'danger');
        }
    }

    /**
     * Show alert message with better styling
     */
    showAlert(message, type = 'info') {
        const alertContainer = document.querySelector('.profile-header');
        if (!alertContainer) return;

        // Create alert element
        const alertId = `alert-${Date.now()}`;
        const alertClasses = {
            'danger': 'alert-danger',
            'success': 'alert-success',
            'warning': 'alert-warning',
            'info': 'alert-info'
        };

        const alert = document.createElement('div');
        alert.id = alertId;
        alert.className = `alert ${alertClasses[type] || alertClasses['info']} alert-dismissible fade show mt-3`;
        alert.role = 'alert';
        alert.style.whiteSpace = 'pre-wrap';
        alert.innerHTML = `
            <div style="display: flex; align-items: flex-start;">
                <div style="flex: 1;">
                    ${message}
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;

        // Insert after page header
        alertContainer.insertAdjacentElement('afterend', alert);

        // Auto-dismiss after delay (longer for errors)
        const duration = type === 'danger' ? 8000 : type === 'success' ? 5000 : 4000;
        setTimeout(() => {
            const element = document.getElementById(alertId);
            if (element) {
                element.remove();
            }
        }, duration);

        // Scroll to alert
        setTimeout(() => {
            alert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 100);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('farmer-profile-page')) {
        window.farmerProfileManager = new FarmerProfileManager();
    }
});
