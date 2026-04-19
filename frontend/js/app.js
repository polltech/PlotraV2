/**
 * Plotra Platform - Main Application
 * SPA with offline support and PWA functionality
 */

// Helper function to decode JWT token
function decodeJWT(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(
            atob(base64).split('').map(c =>
                '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
            ).join('')
        );
        return JSON.parse(jsonPayload);
    } catch (e) {
        return null;
    }
}

// Helper function to get token expiry time
function getTokenExpiry(token) {
    const decoded = decodeJWT(token);
    if (decoded && decoded.exp) {
        return decoded.exp * 1000; // Convert to milliseconds
    }
    return null;
}

class App {
    constructor() {
        this.currentPage = null;
        this.user = null;
        this.farm = null;
        this.sessionCheckInterval = null;

        this.init();
    }
    
    /**
     * Initialize the application
     */
    async init() {
        // Check authentication
        this.checkAuth();

        // Setup session monitoring
        this.setupSessionMonitoring();

        // Setup offline detection
        this.setupOfflineDetection();

        // Setup navigation
        this.setupNavigation();

        // Setup forms
        this.setupForms();

        // Handle URL params
        this.handleURLParams();

        console.log('Plotra Platform initialized');
    }
    
    /**
     * Check if user is authenticated
     */
    checkAuth() {
        const token = localStorage.getItem(CONFIG.session.tokenKey);
        const userData = localStorage.getItem(CONFIG.session.userKey);
        
        if (token && userData) {
            try {
                this.user = JSON.parse(userData);
                this.showPage('dashboard');
            } catch (e) {
                this.logout();
            }
        } else {
            this.showPage('login');
        }
    }
    
    /**
     * Setup offline detection
     */
    setupOfflineDetection() {
        const offlineIndicator = document.getElementById('offline-indicator');

        const updateOnlineStatus = () => {
            if (navigator.onLine) {
                offlineIndicator.classList.add('hidden');
                this.syncOfflineData();
            } else {
                offlineIndicator.classList.remove('hidden');
            }
        };

        window.addEventListener('online', updateOnlineStatus);
        window.addEventListener('offline', updateOnlineStatus);
        updateOnlineStatus();

        // Listen for sync messages from service worker
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.addEventListener('message', (event) => {
                if (event.data.type === 'SYNC_COMPLETE') {
                    this.showToast('Data synced successfully');
                }
            });
        }
    }

    /**
     * Setup session monitoring for automatic logout
     */
    setupSessionMonitoring() {
        // Start monitoring session
        this.startSessionMonitoring();

        // Also monitor visibility change - pause monitoring when tab is hidden
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.stopSessionMonitoring();
            } else {
                this.startSessionMonitoring();
            }
        });
    }

    /**
     * Start session monitoring interval
     */
    startSessionMonitoring() {
        // Clear any existing interval
        this.stopSessionMonitoring();

        // Check session every 30 seconds
        this.sessionCheckInterval = setInterval(() => {
            this.checkSessionValidity();
        }, 30000);

        // Also check immediately
        this.checkSessionValidity();
    }

    /**
     * Stop session monitoring
     */
    stopSessionMonitoring() {
        if (this.sessionCheckInterval) {
            clearInterval(this.sessionCheckInterval);
            this.sessionCheckInterval = null;
        }
    }

    /**
     * Check if current session is still valid
     */
    async checkSessionValidity() {
        const token = localStorage.getItem(CONFIG.session.tokenKey);

        if (!token) {
            // No token, user is not logged in
            return;
        }

        const expiry = getTokenExpiry(token);

        if (!expiry) {
            // Could not decode token, logout
            await this.handleSessionExpiry('Invalid session token');
            return;
        }

        const now = Date.now();
        const timeUntilExpiry = expiry - now;

        // If token expires within the next minute, try to refresh
        const refreshThreshold = CONFIG.session.refreshBeforeExpiry;

        if (timeUntilExpiry <= refreshThreshold) {
            // Attempt to refresh token through API
            try {
                const refreshed = await api.refreshToken();
                if (!refreshed) {
                    // Refresh failed, logout
                    await this.handleSessionExpiry('Session expired');
                    return;
                }
                // Token refreshed successfully, continue monitoring
                console.log('Token refreshed successfully');
            } catch (error) {
                console.error('Token refresh failed:', error);
                await this.handleSessionExpiry('Session expired');
                return;
            }
        }

        // If token already expired, logout immediately
        if (timeUntilExpiry <= 0) {
            await this.handleSessionExpiry('Session expired');
        }
    }

    /**
     * Handle session expiry - logout and redirect
     */
    async handleSessionExpiry(reason) {
        console.log(`Session ending: ${reason}`);

        // Stop monitoring
        this.stopSessionMonitoring();

        // Clear token and user data
        localStorage.removeItem(CONFIG.session.tokenKey);
        localStorage.removeItem(CONFIG.session.userKey);

        // Show notification
        this.showToast(reason === 'Session expired' ?
            'Your session has expired. Please log in again.' :
            'You have been logged out', 'info');

        // Redirect to landing page after brief delay to show toast
        setTimeout(() => {
            window.location.href = '/index.html';
        }, 1500);
    }
    
    /**
     * Setup navigation
     */
    setupNavigation() {
        const navButtons = document.querySelectorAll('.nav-btn');
        
        navButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const page = btn.dataset.page;
                
                // Update active state
                navButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                this.showPage(page);
            });
        });
    }
    
    /**
     * Setup form handlers
     */
    setupForms() {
        // Login form step 1
        const loginFormStep1 = document.getElementById('login-form-step1');
        if (loginFormStep1) {
            loginFormStep1.addEventListener('submit', (e) => {
                e.preventDefault();
                this.goToLoginStep2();
            });
        }
        
        // Login form step 2
        const loginForm = document.getElementById('login-form');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        }
        
        // Login step navigation
        const btnNextLogin = document.getElementById('btnNextLogin');
        if (btnNextLogin) {
            btnNextLogin.addEventListener('click', () => this.goToLoginStep2());
        }
        
        const btnBackLogin = document.getElementById('btnBackLogin');
        if (btnBackLogin) {
            btnBackLogin.addEventListener('click', () => this.goToLoginStep1());
        }
        
        // Register form step 1
        const registerFormStep1 = document.getElementById('register-form-step1');
        if (registerFormStep1) {
            registerFormStep1.addEventListener('submit', (e) => {
                e.preventDefault();
                this.goToRegStep2();
            });
        }
        
        const btnNextReg1 = document.getElementById('btnNextReg1');
        if (btnNextReg1) {
            btnNextReg1.addEventListener('click', () => this.goToRegStep2());
        }
        
        // Register form step 2
        const btnNextReg2 = document.getElementById('btnNextReg2');
        if (btnNextReg2) {
            btnNextReg2.addEventListener('click', () => {
                if (this.validatePasswordStep()) {
                    this.goToRegStep3();
                }
            });
        }
        
        // Register form step 3
        const registerForm = document.getElementById('register-form');
        if (registerForm) {
            registerForm.addEventListener('submit', (e) => this.handleRegister(e));
        }
        
        // Logout button
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.logout());
        }
        
        // Parcel form
        const parcelForm = document.getElementById('parcel-form-element');
        if (parcelForm) {
            parcelForm.addEventListener('submit', (e) => this.handleParcelSubmit(e));
        }
        
        // Delivery form
        const deliveryForm = document.getElementById('delivery-form');
        if (deliveryForm) {
            deliveryForm.addEventListener('submit', (e) => this.handleDeliverySubmit(e));
        }
        
        // GPS buttons
        const startGpsBtn = document.getElementById('start-gps-btn');
        if (startGpsBtn) {
            startGpsBtn.addEventListener('click', () => this.startGpsRecording());
        }
    }
    
    /**
     * Go to login step 2
     */
    goToLoginStep2() {
        const email = document.getElementById('loginEmail');
        if (!email || !email.value || !email.validity.valid) {
            this.showToast('Please enter a valid email', 'error');
            return;
        }
        
        document.getElementById('loginStep1').classList.remove('active');
        document.getElementById('loginStep2').classList.add('active');
        document.getElementById('displayLoginEmail').textContent = email.value;
        document.getElementById('loginPassword').focus();
    }
    
    /**
     * Go to login step 1
     */
    goToLoginStep1() {
        document.getElementById('loginStep2').classList.remove('active');
        document.getElementById('loginStep1').classList.add('active');
    }
    
    /**
     * Go to register step 2
     */
    goToRegStep2() {
        const firstName = document.getElementById('regFirstName');
        const lastName = document.getElementById('regLastName');
        const email = document.getElementById('regEmail');
        
        if (!firstName?.value || !lastName?.value || !email?.value || !email.validity.valid) {
            this.showToast('Please fill in all required fields', 'error');
            return;
        }
        
        document.getElementById('regStep1').classList.remove('active');
        document.getElementById('regStep2').classList.add('active');
        document.getElementById('regPassword').focus();
    }
    
    /**
     * Go to register step 1
     */
    goToRegStep1() {
        document.getElementById('regStep2').classList.remove('active');
        document.getElementById('regStep1').classList.add('active');
    }
    
    /**
     * Validate password step
     */
    validatePasswordStep() {
        const password = document.getElementById('regPassword');
        const confirmPassword = document.getElementById('regConfirmPassword');
        
        if (!password?.value || password.value.length < 8) {
            this.showToast('Password must be at least 8 characters', 'error');
            return false;
        }
        
        if (password.value !== confirmPassword?.value) {
            this.showToast('Passwords do not match', 'error');
            return false;
        }
        
        return true;
    }
    
    /**
     * Go to register step 3
     */
    goToRegStep3() {
        document.getElementById('regStep2').classList.remove('active');
        document.getElementById('regStep3').classList.add('active');
        document.getElementById('regRole').focus();
    }
    
    /**
     * Go to register step 2 from step 3
     */
    goToRegStep2() {
        document.getElementById('regStep3').classList.remove('active');
        document.getElementById('regStep2').classList.add('active');
    }
    
    /**
     * Show register from login
     */
    showRegisterFromLogin() {
        this.showPage('register');
    }
    
    /**
     * Show login from register
     */
    showLoginFromRegister() {
        this.showPage('login');
    }
    
    /**
     * Toggle password visibility
     */
    togglePassword(inputId, iconId) {
        const input = document.getElementById(inputId);
        const icon = document.getElementById(iconId);
        if (input && icon) {
            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.remove('bi-eye');
                icon.classList.add('bi-eye-slash');
            } else {
                input.type = 'password';
                icon.classList.remove('bi-eye-slash');
                icon.classList.add('bi-eye');
            }
        }
    }
    
    /**
     * Handle URL parameters
     */
    handleURLParams() {
        const params = new URLSearchParams(window.location.search);
        
        if (params.get('action') === 'delivery') {
            this.showPage('deliveries');
            this.openDeliveryModal();
        } else if (params.get('action') === 'map') {
            this.showPage('map');
        }
    }
    
    /**
     * Show a page
     */
    async showPage(pageName) {
        const mainContent = document.getElementById('main-content');
        const bottomNav = document.getElementById('bottom-nav');
        const pageContent = document.getElementById('pageContent');
        
        // Show loading
        this.showLoading(true);
        
        try {
            // Update navigation
            if (pageName !== 'login' && pageName !== 'register') {
                bottomNav.classList.remove('hidden');
                this.updateActiveNav(pageName);
            } else {
                bottomNav.classList.add('hidden');
            }
            
            // Handle farmer-profile as special case (loaded from file)
            if (pageName === 'farmer-profile') {
                try {
                    const response = await fetch('farmer-profile.html');
                    if (!response.ok) {
                        throw new Error(`Failed to load farmer profile: ${response.status}`);
                    }
                    const html = await response.text();
                    pageContent.innerHTML = html;
                } catch (error) {
                    console.error('Error loading farmer profile:', error);
                    pageContent.innerHTML = '<div class="alert alert-danger">Error loading farmer profile page</div>';
                }
            } else {
                // Regular template-based page loading
                const templateId = `${pageName}-template`;
                const template = document.getElementById(templateId);
                
                if (!template) {
                    console.error(`Template not found: ${templateId}`);
                    pageContent.innerHTML = '<div class="alert alert-danger">Page template not found</div>';
                    return;
                }
                
                // Clone template content
                const content = template.content.cloneNode(true);
                pageContent.innerHTML = '';
                pageContent.appendChild(content);
            }
            
            // Load page data
            await this.loadPageData(pageName);
            
            // Re-setup forms after page load
            this.setupForms();
            
            this.currentPage = pageName;
            
        } catch (error) {
            console.error(`Error loading page ${pageName}:`, error);
            this.showToast('Error loading page', 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    /**
     * Update active navigation
     */
    updateActiveNav(pageName) {
        const navButtons = document.querySelectorAll('.nav-btn');
        navButtons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.page === pageName);
        });
    }
    
    /**
     * Load page-specific data
     */
    async loadPageData(pageName) {
        switch (pageName) {
            case 'login':
            case 'register':
                // No data to load for auth pages
                break;
            case 'dashboard':
                await this.loadDashboard();
                break;
            case 'deliveries':
                await this.loadDeliveries();
                break;
            case 'profile':
                await this.loadProfile();
                break;
            case 'map':
                await this.loadMap();
                break;
            case 'farmer-profile':
                // Farmer profile is loaded dynamically via AJAX
                // The FarmerProfileManager class handles initialization
                break;
        }
    }
    
    /**
     * Load dashboard data
     */
    async loadDashboard() {
        try {
            const [user, farm, deliveries, documents] = await Promise.all([
                api.getCurrentUser().catch(() => null),
                api.getFarm().catch(() => null),
                api.getDeliveries().catch(() => []),
                api.getDocuments().catch(() => [])
            ]);
            
            // Update UI
            document.getElementById('farm-status').textContent = 
                farm ? 'Farm Created' : 'No Farm';
            
            document.getElementById('compliance-status').textContent = 
                farm?.compliance_status || 'N/A';
            
            document.getElementById('delivery-count').textContent = 
                deliveries.length || 0;
            
            document.getElementById('document-count').textContent = 
                documents.length || 0;
            
            // Store for later use
            this.user = user;
            this.farm = farm;
            
        } catch (error) {
            console.error('Dashboard load error:', error);
        }
    }
    
    /**
     * Load deliveries page
     */
    async loadDeliveries() {
        try {
            const deliveries = await api.getDeliveries();
            this.renderDeliveries(deliveries);
        } catch (error) {
            console.error('Deliveries load error:', error);
            document.getElementById('deliveries-list').innerHTML = 
                '<p class="empty-state">No deliveries found</p>';
        }
    }
    
    /**
     * Render deliveries list
     */
    renderDeliveries(deliveries) {
        const container = document.getElementById('deliveries-list');
        
        if (!deliveries || deliveries.length === 0) {
            container.innerHTML = '<p class="empty-state">No deliveries recorded yet</p>';
            return;
        }
        
        container.innerHTML = deliveries.map(d => `
            <div class="delivery-item">
                <div class="delivery-info">
                    <h4>${d.delivery_number}</h4>
                    <p>${d.net_weight_kg} kg • ${d.quality_grade || 'Ungraded'}</p>
                </div>
                <div class="delivery-status status-${d.status}">
                    ${d.status}
                </div>
            </div>
        `).join('');
    }
    
    /**
     * Load profile page
     */
    async loadProfile() {
        try {
            const user = await api.getCurrentUser();
            const farm = await api.getFarm().catch(() => null);
            
            document.getElementById('user-name').textContent = 
                `${user.first_name} ${user.last_name}`;
            document.getElementById('user-role').textContent = 
                user.role.replace('_', ' ').toUpperCase();
            document.getElementById('user-email').textContent = user.email;
            document.getElementById('user-phone').textContent = 
                user.phone_number || 'Not set';
            document.getElementById('user-verification').textContent = 
                user.verification_status;
            
            document.getElementById('farm-area').textContent = 
                farm?.total_area_hectares ? `${farm.total_area_hectares} ha` : 'N/A';
            document.getElementById('farm-parcels').textContent = 
                farm?.parcels?.length || 0;
            
        } catch (error) {
            console.error('Profile load error:', error);
        }
    }
    
    /**
     * Load map page
     */
    async loadMap() {
        // Map initialization would go here
        console.log('Map page loaded');
    }
    
    /**
     * Handle login
     */
    async handleLogin(event) {
        event.preventDefault();
        
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;
        
        this.showLoading(true);
        
        try {
            const { user } = await api.login(email, password);
            this.user = user;
            
            localStorage.setItem(CONFIG.session.userKey, JSON.stringify(user));
            
            this.showToast('Login successful');
            this.showPage('dashboard');
            
        } catch (error) {
            this.showToast(error.message || 'Login failed', 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    /**
     * Handle registration
     */
    async handleRegister(event) {
        event.preventDefault();
        
        const userData = {
            email: document.getElementById('regEmail').value,
            password: document.getElementById('regPassword').value,
            first_name: document.getElementById('regFirstName').value,
            last_name: document.getElementById('regLastName').value,
            phone_number: document.getElementById('regPhone').value,
            role: document.getElementById('regRole').value,
            country: document.getElementById('regCountry').value,
            region: document.getElementById('regRegion').value
        };
        
        this.showLoading(true);
        
        try {
            const { user } = await api.register(userData);
            this.user = user;
            
            localStorage.setItem(CONFIG.session.userKey, JSON.stringify(user));
            
            this.showToast('Account created successfully');
            this.showPage('dashboard');
            
        } catch (error) {
            this.showToast(error.message || 'Registration failed', 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    /**
     * Handle logout
     */
    async logout() {
        // Stop session monitoring
        this.stopSessionMonitoring();

        await api.logout();
        this.user = null;
        this.farm = null;

        // Show logout message then redirect
        this.showToast('Logged out successfully');

        // Small delay to show the toast, then redirect to landing page
        setTimeout(() => {
            window.location.href = '/index.html';
        }, 500);
    }
    
    /**
     * Start GPS recording
     */
    async startGpsRecording() {
        const gpsBtn = document.getElementById('start-gps-btn');
        const gpsStatus = document.getElementById('gps-status');
        
        if (gpsRecorder.isRecording) {
            gpsRecorder.stopRecording();
            gpsBtn.textContent = '📍 Start GPS Recording';
            gpsBtn.classList.remove('btn-danger');
            gpsBtn.classList.add('btn-secondary');
            
            if (gpsRecorder.hasMinimumPoints()) {
                gpsStatus.innerHTML = `
                    <p class="success">Recorded ${gpsRecorder.getPoints().length} points</p>
                    <p>Average accuracy: ${Math.round(gpsRecorder.getAverageAccuracy())}m</p>
                `;
            }
        } else {
            try {
                gpsRecorder.clearPoints();
                
                gpsRecorder.onPositionUpdate = (point, points) => {
                    document.getElementById('point-count').textContent = points.length;
                    
                    const gpsStatus = document.getElementById('gps-status');
                    gpsStatus.innerHTML = `
                        <p class="recording">🔴 Recording...</p>
                        <p>Points: ${points.length} | Accuracy: ${Math.round(point.accuracy)}m</p>
                    `;
                };
                
                gpsRecorder.startRecording();
                gpsBtn.textContent = '⏹️ Stop Recording';
                gpsBtn.classList.remove('btn-secondary');
                gpsBtn.classList.add('btn-danger');
                
            } catch (error) {
                this.showToast(error.message, 'error');
            }
        }
    }
    
    /**
     * Handle parcel form submission
     */
    async handleParcelSubmit(event) {
        event.preventDefault();
        
        if (!gpsRecorder.hasMinimumPoints()) {
            this.showToast('Please record at least 4 GPS points', 'error');
            return;
        }
        
        const form = event.target;
        const parcelName = form.parcelName.value;
        
        try {
            const polygon = gpsRecorder.toGeoJSONPolygon();
            const area = gpsRecorder.calculateAreaHectares();
            
            const parcelData = {
                parcel_number: Date.now(), // Use timestamp as parcel number
                parcel_name: parcelName,
                boundary_geojson: polygon,
                area_hectares: area,
                gps_accuracy_meters: gpsRecorder.getAverageAccuracy()
            };
            
            await api.addParcel(parcelData);
            
            this.showToast('Parcel saved successfully');
            gpsRecorder.clearPoints();
            
            // Close modal
            document.getElementById('parcel-form').classList.add('hidden');
            
        } catch (error) {
            this.showToast(error.message || 'Failed to save parcel', 'error');
        }
    }
    
    /**
     * Handle delivery form submission
     */
    async handleDeliverySubmit(event) {
        event.preventDefault();
        
        const form = event.target;
        
        const deliveryData = {
            farm_id: parseInt(form.farmId.value),
            gross_weight_kg: parseFloat(form.grossWeight.value),
            tare_weight_kg: parseFloat(form.tareWeight.value) || 0,
            moisture_content: form.moistureContent.value ? 
                parseFloat(form.moistureContent.value) : null
        };
        
        try {
            await api.recordDelivery(deliveryData);
            
            this.showToast('Delivery recorded successfully');
            this.closeDeliveryModal();
            
            // Refresh deliveries
            this.loadDeliveries();
            
        } catch (error) {
            this.showToast(error.message || 'Failed to record delivery', 'error');
        }
    }
    
    /**
     * Open delivery modal
     */
    async openDeliveryModal() {
        const modal = document.getElementById('delivery-form-modal');
        const farmSelect = document.getElementById('delivery-farm');
        
        // Load farms
        try {
            const farm = await api.getFarm();
            farmSelect.innerHTML = `
                <option value="${farm.id}">${farm.farm_name || 'My Farm'}</option>
            `;
        } catch (error) {
            farmSelect.innerHTML = '<option value="">No farms found</option>';
        }
        
        modal.classList.remove('hidden');
    }
    
    /**
     * Close delivery modal
     */
    closeDeliveryModal() {
        document.getElementById('delivery-form-modal').classList.add('hidden');
    }
    
    /**
     * Sync offline data
     */
    async syncOfflineData() {
        console.log('Syncing offline data...');
        // Trigger service worker sync
        if ('serviceWorker' in navigator && 'SyncManager' in window) {
            try {
                const registration = await navigator.serviceWorker.ready;
                await registration.sync.register('sync-deliveries');
            } catch (error) {
                console.error('Sync registration failed:', error);
            }
        }
    }
    
    /**
     * Show/hide loading overlay
     */
    showLoading(show) {
        const overlay = document.getElementById('loading-overlay');
        overlay.classList.toggle('hidden', !show);
    }
    
    /**
     * Show toast notification
     */
    showToast(message, type = 'success') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        // Animate in
        setTimeout(() => toast.classList.add('show'), 10);
        
        // Remove after duration
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, CONFIG.ui.toastDuration);
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
