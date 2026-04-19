/**
 * Plotra Platform - API Module
 * Handles all API communications with offline support
 */

class API {
    constructor() {
        this.baseUrl = CONFIG.api.baseUrl;
        this.token = localStorage.getItem(CONFIG.session.tokenKey);
    }
    
    /**
     * Set authentication token
     */
    setToken(token) {
        this.token = token;
        localStorage.setItem(CONFIG.session.tokenKey, token);
    }
    
    /**
     * Clear authentication token
     */
    clearToken() {
        this.token = null;
        localStorage.removeItem(CONFIG.session.tokenKey);
        localStorage.removeItem(CONFIG.session.userKey);
    }
    
    /**
     * Get headers for requests
     */
    getHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        return headers;
    }
    
    /**
     * Make API request with retry logic
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            ...options,
            headers: {
                ...this.getHeaders(),
                ...options.headers
            }
        };
        
        // Try request with retry
        let lastError;
        
        for (let attempt = 0; attempt < CONFIG.api.retryAttempts; attempt++) {
            try {
                const response = await fetch(url, config);
                
                if (!response.ok) {
                    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
                    
                    if (response.status === 401) {
                        // Token expired - try to refresh
                        const refreshed = await this.refreshToken();
                        if (refreshed) {
                            config.headers = this.getHeaders();
                            continue;
                        }
                    }
                    
                    throw new Error(error.detail || `HTTP ${response.status}`);
                }
                
                return await response.json();
                
            } catch (error) {
                lastError = error;
                
                // Don't retry on client errors (4xx)
                if (error.message && error.message.startsWith('4')) {
                    throw error;
                }
                
                // Wait before retry
                if (attempt < CONFIG.api.retryAttempts - 1) {
                    await this.delay(CONFIG.api.retryDelay * (attempt + 1));
                }
            }
        }
        
        throw lastError;
    }
    
    /**
     * Try to refresh the access token
     */
    async refreshToken() {
        try {
            const response = await fetch(`${this.baseUrl}/auth/refresh`, {
                method: 'POST',
                headers: this.getHeaders()
            });
            
            if (response.ok) {
                const data = await response.json();
                this.setToken(data.access_token);
                return true;
            }
        } catch (error) {
            console.error('Token refresh failed:', error);
        }
        
        return false;
    }
    
    /**
     * Helper to delay execution
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    // ============== Authentication Endpoints ==============
    
    async login(email, password) {
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);
        formData.append('grant_type', 'password');
        
        const response = await fetch(`${this.baseUrl}/auth/token-form`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Login failed' }));
            throw new Error(error.detail || 'Login failed');
        }
        
        const data = await response.json();
        this.setToken(data.access_token);
        
        // Get user profile
        const user = await this.getCurrentUser();
        
        return { token: data.access_token, user };
    }
    
    async logout() {
        try {
            await this.request('/auth/logout', { method: 'POST' });
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            this.clearToken();
        }
    }
    
    async getCurrentUser() {
        return this.request('/auth/me');
    }
    
    async register(userData) {
        return this.request('/auth/register', {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    }
    
    async changePassword(currentPassword, newPassword) {
        const formData = new FormData();
        formData.append('current_password', currentPassword);
        formData.append('new_password', newPassword);
        formData.append('confirm_password', newPassword);
        
        return this.request('/auth/change-password', {
            method: 'POST',
            body: formData
        });
    }
    
    // ============== Farmer Endpoints ==============
    
    async getFarmerProfile() {
        return this.request('/farmer/profile');
    }
    
    async updateFarmerProfile(data) {
        return this.request('/farmer/profile', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }
    
    async createFarm(farmData) {
        return this.request('/farmer/farm', {
            method: 'POST',
            body: JSON.stringify(farmData)
        });
    }
    
    async getFarm() {
        return this.request('/farmer/farm');
    }
    
    async addParcel(parcelData) {
        return this.request('/farmer/farm/parcel', {
            method: 'POST',
            body: JSON.stringify(parcelData)
        });
    }
    
    async uploadDocument(formData) {
        const response = await fetch(`${this.baseUrl}/farmer/documents`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`
            },
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
            throw new Error(error.detail || 'Upload failed');
        }
        
        return response.json();
    }
    
    async getDocuments(farmId = null) {
        const endpoint = farmId 
            ? `/farmer/documents?farm_id=${farmId}`
            : '/farmer/documents';
        return this.request(endpoint);
    }
    
    // ============== Cooperative Endpoints ==============
    
    async getCoopMembers(statusFilter = null) {
        const endpoint = statusFilter 
            ? `/coop/members?status_filter=${statusFilter}`
            : '/coop/members';
        return this.request(endpoint);
    }
    
    async verifyMember(userId) {
        return this.request(`/coop/members/${userId}/verify`, {
            method: 'PUT'
        });
    }
    
    async recordDelivery(deliveryData) {
        return this.request('/coop/deliveries', {
            method: 'POST',
            body: JSON.stringify(deliveryData)
        });
    }
    
    async getDeliveries(filters = {}) {
        const params = new URLSearchParams(filters);
        return this.request(`/coop/deliveries?${params}`);
    }
    
    async createBatch(batchData) {
        return this.request('/coop/batches', {
            method: 'POST',
            body: JSON.stringify(batchData)
        });
    }
    
    async getBatches(cropYear = null) {
        const endpoint = cropYear 
            ? `/coop/batches?crop_year=${cropYear}`
            : '/coop/batches';
        return this.request(endpoint);
    }
    
    async getBatchTraceability(batchId) {
        return this.request(`/coop/batches/${batchId}/traceability`);
    }
    
    // ============== Admin Endpoints ==============
    
    async getAllUsers(filters = {}) {
        const params = new URLSearchParams(filters);
        return this.request(`/admin/users?${params}`);
    }
    
    async triggerSatelliteAnalysis(parcelIds, acquisitionDate = null) {
        const data = {
            parcel_ids: parcelIds,
            acquisition_date: acquisitionDate
        };
        
        return this.request('/admin/satellite/analyze', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    async getRiskReport(filters = {}) {
        const params = new URLSearchParams(filters);
        return this.request(`/admin/farms/risk-report?${params}`);
    }
    
    async getComplianceOverview() {
        return this.request('/admin/compliance/overview');
    }
    
    // ============== EUDR Endpoints ==============
    
    async generateDDS(ddsData) {
        return this.request('/admin/eudr/dds', {
            method: 'POST',
            body: JSON.stringify(ddsData)
        });
    }
    
    async getDDS(ddsId) {
        return this.request(`/admin/eudr/dds/${ddsId}`);
    }
    
    async generateCertificate(certData) {
        return this.request('/admin/eudr/certificate', {
            method: 'POST',
            body: JSON.stringify(certData)
        });
    }
    
    async verifyCertificate(certId) {
        return this.request(`/admin/eudr/certificate/${certId}/verify`);
    }
    
    async runComplianceCheck(farmId) {
        return this.request(`/admin/farms/${farmId}/compliance-check`, {
            method: 'POST'
        });
    }
}

// Create global API instance
window.api = new API();
