/**
 * Plotra Dashboard - API Module
 * Handles all API communications
 */

class PlotraAPI {
    constructor() {
        this.baseUrl = this.getApiUrl();
        this.token = localStorage.getItem('plotra_token');
    }
    
    getApiUrl() {
        // Explicit override injected by nginx (window.API_URL set in config.js)
        if (window.API_URL) return window.API_URL;

        const protocol = window.location.protocol;

        // Opened as a local file (file://) — backend must be on localhost:8000
        if (protocol === 'file:') {
            return 'http://localhost:8000/api/v2';
        }

        // Served from any HTTP/HTTPS host — nginx proxies /api/ to the backend
        // Works for localhost:8080 (Docker), dev.plotra.eu, or any custom domain
        return '/api/v2';
    }
    
    setToken(token) {
        this.token = token;
        localStorage.setItem('plotra_token', token);
    }
    
    clearToken() {
        this.token = null;
        localStorage.removeItem('plotra_token');
        localStorage.removeItem('plotra_user');
    }
    
    getHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        return headers;
    }
    
    async request(endpoint, options = {}, retryCount = 0) {
        const url = `${this.baseUrl}${endpoint}`;
        console.log(`[API Request] ${options.method || 'GET'} ${url}`);
        
        // Build config with timeout support
        const config = {
            ...options,
            headers: { ...this.getHeaders(), ...options.headers }
        };

        if (config.headers['Content-Type'] === null) {
            delete config.headers['Content-Type'];
        }

        // Add timeout if AbortSignal.timeout is supported
        if (typeof AbortSignal !== 'undefined' && AbortSignal.timeout) {
            config.signal = AbortSignal.timeout(10000); // 10 second timeout
        } else {
            // Fallback for older browsers
            const controller = new AbortController();
            setTimeout(() => controller.abort(), 10000);
            config.signal = controller.signal;
        }
        
        try {
            const response = await fetch(url, config);
            console.log(`[API Response] Status: ${response.status} ${response.statusText}`);
            
            if (!response.ok) {
                // Handle 401 Unauthorized - try to refresh token
                if (response.status === 401 && retryCount === 0) {
                    console.log('[API] Token expired, attempting refresh...');
                    try {
                        const refreshed = await this.refreshToken();
                        if (refreshed) {
                            console.log('[API] Token refreshed successfully, retrying request...');
                            return this.request(endpoint, options, retryCount + 1);
                        }
                    } catch (refreshError) {
                        console.error('[API] Token refresh failed:', refreshError);
                    }
                }
                
                // Return default for optional requests on any error
                if (options.optional) {
                    console.log(`[API] Optional request got ${response.status}, returning default`);
                    return options.default !== undefined ? options.default : null;
                }

                let errorData;
                try {
                    errorData = await response.json();
                } catch (e) {
                    errorData = { detail: `HTTP ${response.status}: ${response.statusText}` };
                }
                
                // Handle validation errors which come as an array
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                if (Array.isArray(errorData.detail)) {
                    errorMessage = errorData.detail.map(err => err.msg || err.message || JSON.stringify(err)).join(', ');
                } else if (errorData.detail) {
                    errorMessage = errorData.detail;
                } else if (errorData.message) {
                    errorMessage = errorData.message;
                } else if (errorData.error) {
                    errorMessage = errorData.error;
                }
                
                console.error(`[API Error] ${errorMessage}`);
                throw new Error(errorMessage);
            }
            
            const data = await response.json();
            console.log(`[API] Received data:`, data);
            return data;
        } catch (error) {
            if (error.name === 'TimeoutError' || error.name === 'AbortError') {
                if (options.optional) return options.default !== undefined ? options.default : null;
                throw new Error('Request timed out. Please check if the backend is running.');
            }
            if (error.message === 'Failed to fetch') {
                if (options.optional) return options.default !== undefined ? options.default : null;
                const diagMsg = `Network error (Failed to fetch). Possible causes:
1. Backend server is not running
2. Browser extension is blocking the request
3. CORS issue
Attempted URL: ${url}`;
                console.error(diagMsg);
                throw new Error(diagMsg);
            }
            console.error('API Error:', error);
            if (options.optional) return options.default !== undefined ? options.default : null;
            throw error;
        }
    }
    
    /**
     * Refresh authentication token
     */
    async refreshToken() {
        try {
            const response = await fetch(`${this.baseUrl}/auth/refresh`, {
                method: 'POST',
                headers: this.getHeaders()
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.access_token) {
                    this.setToken(data.access_token);
                    console.log('[API] Token refreshed successfully');
                    return true;
                }
            }
            console.warn('[API] Token refresh returned status:', response.status);
            return false;
        } catch (error) {
            console.error('[API] Token refresh failed:', error);
            return false;
        }
    }
    
    // Authentication
    async login(email, password) {
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);
        
        const data = await this.request('/auth/token-form', {
            method: 'POST',
            body: formData,
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        });
        
        // Validate response has access_token before setting
        if (!data || !data.access_token) {
            throw new Error('Invalid server response: missing access token');
        }
        
        // Set token after successful login
        this.setToken(data.access_token);
        return data;
    }
    
    async register(userData) {
        return this.request('/auth/register', {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    }
    
    async forgotPassword(email) {
        const formData = new URLSearchParams();
        formData.append('email', email);
        return this.request('/auth/forgot-password', {
            method: 'POST',
            body: formData,
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });
    }
    
    async resetPassword(token, newPassword, confirmPassword) {
        // Backend expects Form data, not JSON
        const formData = new URLSearchParams();
        formData.append('token', token);
        formData.append('new_password', newPassword);
        formData.append('confirm_password', confirmPassword);
        
        return this.request('/auth/reset-password', {
            method: 'POST',
            body: formData,
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        });
    }
    
    logout() {
        this.clearToken();
    }
    
    async getCurrentUser() {
        return this.request('/auth/me');
    }

    async getMyMembership() {
        return this.request('/auth/me/membership');
    }

    async sendOTP(phone) {
        const fd = new FormData(); fd.append('phone', phone);
        return this.request('/auth/send-otp', { method: 'POST', body: fd, headers: { 'Content-Type': null } });
    }

    async verifyOTP(phone, code) {
        const fd = new FormData(); fd.append('phone', phone); fd.append('code', code);
        return this.request('/auth/verify-otp', { method: 'POST', body: fd, headers: { 'Content-Type': null } });
    }

    async checkField(params) {
        const qs = new URLSearchParams(params).toString();
        return this.request(`/auth/check-field?${qs}`);
    }
    
    async updateProfile(userData) {
        return this.request('/auth/profile', {
            method: 'PUT',
            body: JSON.stringify(userData)
        });
    }
    async resubmitForReview() {
        return this.request('/farmer/resubmit', { method: 'PATCH' });
    }
    
    // Farms
    async getFarms(filters = {}) {
        const user = JSON.parse(localStorage.getItem('plotra_user') || '{}');
        const role = (user.role || '').toUpperCase();
        console.log('getFarms - User role:', role);
        console.log('getFarms - User object:', user);
        
        const isAdmin = role.includes('ADMIN') || role === 'PLOTRA_ADMIN';
        const isFarmer = role === 'FARMER';
        const isCoopOfficer = role === 'COOPERATIVE_OFFICER' || role === 'COOP_ADMIN';
        
        let endpoint;
        if (isAdmin || isCoopOfficer) {
            // Admins and coop officers use admin endpoint to see all farms
            endpoint = '/admin/farms';
            console.log('getFarms - Using admin endpoint');
        } else if (isFarmer) {
            endpoint = '/farmer/farm';
            console.log('getFarms - Using farmer endpoint');
        } else {
            // Default fallback - try farmer endpoint
            endpoint = '/farmer/farm';
            console.log('getFarms - Using default farmer endpoint, role:', role);
        }
        
        const params = new URLSearchParams(filters);
        return this.request(`${endpoint}?${params}`, { optional: true, default: [] });
    }
    
    async getAllFarms(filters = {}) {
        const params = new URLSearchParams(filters);
        return this.request(`/admin/farms?${params}`);
    }

    async getFarm(farmId) {
        return this.request(`/admin/farms/${farmId}`);
    }
    
    async createFarm(data) {
        console.log('Creating farm with data:', data);
        return this.request('/farmer/farm', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    async updateFarmPolygon(farmId, data) {
        return this.request(`/farmer/farm/${farmId}`, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
    }

    async updateFarm(farmId, data) {
        return this.request(`/farmer/farm/${farmId}`, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
    }

    async getFarmById(farmId) {
        return this.request(`/farmer/farm/${farmId}`, { optional: true });
    }

    // Parcels
    async getParcels(farmId) {
        return this.request(`/farmer/farm/${farmId}/parcels`, { optional: true, default: [] });
    }
    
    async addParcel(farmId, data) {
        return this.request(`/farmer/farm/${farmId}/parcels`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    async updateParcel(farmId, parcelId, data) {
        return this.request(`/farmer/farm/${farmId}/parcels/${parcelId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }
    
    async deleteParcel(farmId, parcelId) {
        return this.request(`/farmer/farm/${farmId}/parcels/${parcelId}`, {
            method: 'DELETE'
        });
    }
    
    async getParcel(farmId, parcelId) {
        return this.request(`/farmer/farm/${farmId}/parcels/${parcelId}`);
    }
    
    // Deliveries
    async getDeliveries(filters = {}) {
        const user = JSON.parse(localStorage.getItem('plotra_user') || '{}');
        const role = (user.role || '').toLowerCase();
        const isAdmin = ['plotra_admin','super_admin','platform_admin','admin'].includes(role);
        const isCoop = ['coop_admin','cooperative_admin','coop_officer','cooperative_officer','factor'].includes(role);
        // farmer: uses /farmer/deliveries to see own deliveries (recorded by coop)

        let endpoint = '/farmer/deliveries';
        if (isAdmin) endpoint = '/admin/deliveries';
        else if (isCoop) endpoint = '/coop/deliveries';

        const params = new URLSearchParams(filters);
        return this.request(`${endpoint}?${params}`, { optional: true, default: [] });
    }

    async recordDelivery(data) {
        return this.request('/coop/deliveries', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    // Batches
    async getBatches(filters = {}) {
        const params = new URLSearchParams(filters);
        return this.request(`/coop/batches?${params}`);
    }
    
    async createBatch(data) {
        return this.request('/coop/batches', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    // Verification (Admin)
    async getPendingVerifications(filters = {}) {
        const params = new URLSearchParams(filters);
        return this.request(`/admin/verification/pending?${params}`);
    }

    async approveVerification(recordId, data) {
        return this.request(`/admin/farms/${recordId}/approve`, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
    }

    async rejectVerification(recordId, data) {
        return this.request(`/admin/farms/${recordId}/reject`, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
    }

    // Farmer Approvals
    async getAdminPendingFarmers() {
        return this.request('/admin/farmers/pending');
    }
    async getCoopAllFarmers() {
        return this.request('/coop/farmers');
    }
    async getCoopPendingFarmers() {
        return this.request('/coop/farmers/pending');
    }
    async adminApproveFarmer(farmerId, notes) {
        return this.request(`/admin/farmers/${farmerId}/approve`, { method: 'PATCH', body: JSON.stringify({ notes }) });
    }
    async adminRejectFarmer(farmerId, notes) {
        return this.request(`/admin/farmers/${farmerId}/reject`, { method: 'PATCH', body: JSON.stringify({ notes }) });
    }
    async coopApproveFarmerAccount(farmerId, reason) {
        return this.request(`/coop/farmers/${farmerId}/approve`, { method: 'PATCH', body: JSON.stringify({ reason }) });
    }
    async coopRejectFarmerAccount(farmerId, reason) {
        return this.request(`/coop/farmers/${farmerId}/reject`, { method: 'PATCH', body: JSON.stringify({ reason }) });
    }
    async coopRequestFarmerUpdate(farmerId, issue) {
        return this.request(`/coop/farmers/${farmerId}/request-update`, { method: 'PATCH', body: JSON.stringify({ issue }) });
    }
    async adminRequestFarmerUpdate(farmerId, issue) {
        return this.request(`/admin/farmers/${farmerId}/request-update`, { method: 'PATCH', body: JSON.stringify({ issue }) });
    }

    // Verification (Cooperative)
    async getCoopPendingFarms() {
        return this.request('/coop/farms/pending');
    }

    async coopApproveFarm(farmId, reason) {
        return this.request(`/coop/farms/${farmId}/approve`, {
            method: 'PATCH',
            body: JSON.stringify({ reason })
        });
    }

    async coopRejectFarm(farmId, reason) {
        return this.request(`/coop/farms/${farmId}/reject`, {
            method: 'PATCH',
            body: JSON.stringify({ reason })
        });
    }

    // Notifications
    async getNotifications() {
        return this.request('/farmer/notifications');
    }

    async markNotificationRead(notifId) {
        return this.request(`/farmer/notifications/${notifId}/read`, { method: 'PATCH' });
    }
    
    // Satellite
    async triggerSatelliteAnalysis(parcelIds) {
        return this.request('/admin/satellite/analyze', {
            method: 'POST',
            body: JSON.stringify({ parcel_ids: parcelIds })
        });
    }
    
    async getRiskReport(filters = {}) {
        const params = new URLSearchParams(filters);
        return this.request(`/admin/farms/risk-report?${params}`);
    }
    
    // EUDR Compliance
    async generateDDS(data) {
        return this.request('/admin/eudr/dds', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    async getDDS(ddsId) {
        return this.request(`/admin/eudr/dds/${ddsId}`);
    }
    
    async getDDSList() {
        return this.request('/admin/eudr/dds');
    }
    
    async exportDDS(ddsId) {
        const response = await fetch(this.baseUrl + `/admin/eudr/export/xml/${ddsId}`, {
            method: 'GET',
            headers: this.getHeaders(),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Get XML content
        const xmlContent = await response.text();
        
        // Create download
        const blob = new Blob([xmlContent], { type: 'application/xml' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `dds_${ddsId}.xml`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }
    
    // Users
    async getUsers(filters = {}) {
        const params = new URLSearchParams(filters);
        return this.request(`/admin/users?${params}`);
    }

    // Cooperatives
    async getCooperatives(filters = {}) {
        const params = new URLSearchParams(filters);
        return this.request(`/admin/cooperatives?${params}`);
    }

    async getCooperative(coopId) {
        return this.request(`/admin/cooperatives/${coopId}`);
    }

    async createCooperative(coopData, adminData) {
        return this.request('/admin/cooperatives', {
            method: 'POST',
            body: JSON.stringify(coopData)
        });
    }

    async createCooperativeWithDocs(formData) {
        const url = `${this.baseUrl}/admin/cooperatives`;
        console.log(`[API Request] POST ${url}`);
        
        const headers = {};
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        const response = await fetch(url, {
            method: 'POST',
            headers,
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            console.error('[API Error Response]', error);
            let msg = 'Failed to create cooperative';
            if (Array.isArray(error.detail)) {
                msg = error.detail.map(e => e.msg || JSON.stringify(e)).join(', ');
            } else if (typeof error.detail === 'string') {
                msg = error.detail;
            } else if (error.message) {
                msg = error.message;
            } else if (typeof error === 'object') {
                msg = JSON.stringify(error);
            }
            throw new Error(msg);
        }
        
        return response.json();
    }

    async updateCooperative(coopId, data) {
        return this.request(`/admin/cooperatives/${coopId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async verifyCooperative(coopId) {
        return this.request(`/admin/cooperatives/${coopId}/verify`, {
            method: 'POST'
        });
    }

    async getCooperativeUsers(coopId) {
        return this.request(`/coop/cooperatives/${coopId}/users`);
    }

    async addCooperativeUser(coopId, userData) {
        return this.request(`/coop/cooperatives/${coopId}/users`, {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    }

    async updateCooperativeUser(coopId, userId, roleData) {
        return this.request(`/coop/cooperatives/${coopId}/users/${userId}`, {
            method: 'PUT',
            body: JSON.stringify(roleData)
        });
    }

    async removeCooperativeUser(coopId, userId) {
        return this.request(`/coop/cooperatives/${coopId}/users/${userId}`, {
            method: 'DELETE'
        });
    }

    async assignCooperativeAdmin(coopId, userId) {
        return this.request(`/admin/cooperatives/${coopId}/assign-admin`, {
            method: 'POST',
            body: JSON.stringify({ user_id: userId })
        });
    }

    async getPendingFarmers(filters = {}) {
        const params = new URLSearchParams(filters);
        return this.request(`/admin/farmers/pending?${params}`);
    }

    async verifyFarmer(userId) {
        return this.request(`/admin/farmers/${userId}/verify`, {
            method: 'PUT'
        });
    }

    async rejectFarmer(userId, reason) {
        return this.request(`/admin/farmers/${userId}/reject?reason=${encodeURIComponent(reason)}`, {
            method: 'PUT'
        });
    }

    // Cooperative Members (for Coop Admins)
    async addCoopMember(data) {
        return this.request('/coop/members', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    async getDocuments(farmId) {
        const params = farmId ? `?farm_id=${farmId}` : '';
        return this.request(`/farmer/documents${params}`, { optional: true, default: [] });
    }

    async uploadLandDocument(formData) {
        return this.request('/farmer/documents', {
            method: 'POST',
            body: formData,
            headers: {
                // Let the browser set the Content-Type with boundary for FormData
                'Content-Type': null
            }
        });
    }

    // Dashboard Stats
    async getDashboardStats() {
        return this.request('/admin/dashboard/stats');
    }
    
    async getComplianceOverview() {
        return this.request('/admin/compliance/overview');
    }
    
    async getComplianceOverviewChart() {
        try {
            const result = await this.request('/admin/compliance/overview/chart');
            return result;
        } catch (e) {
            console.warn('Compliance chart not available:', e.message);
            return { categories: [], values: [], satellite_verified: { verified: 0, pending: 0 } };
        }
    }
    
    async getCoopStats() {
        return this.request('/coop/stats');
    }
    
    async getFarmerStats() {
        return this.request('/farmer/stats', { optional: true, default: {} });
    }
    
    // Sustainability & Incentives (Layers 3-7)
    async getPracticeLogs(parcelId) {
        const params = parcelId ? `?parcel_id=${parcelId}` : '';
        return this.request(`/sustainability/practice-logs${params}`);
    }
    
    async createPracticeLog(data) {
        return this.request('/sustainability/practice-log', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    async getIncentiveRules(cooperativeId) {
        const params = cooperativeId ? `?cooperative_id=${cooperativeId}` : '';
        return this.request(`/sustainability/incentive-rules${params}`);
    }
    
    async getIncentiveClaims(statusFilter) {
        const params = statusFilter ? `?status_filter=${statusFilter}` : '';
        return this.request(`/sustainability/incentive-claims${params}`);
    }
    
    async getEscrowPayments(statusFilter) {
        const params = statusFilter ? `?status_filter=${statusFilter}` : '';
        return this.request(`/sustainability/escrow${params}`);
    }
    
    async getCarbonProjects(statusFilter) {
        const params = statusFilter ? `?status_filter=${statusFilter}` : '';
        return this.request(`/sustainability/carbon-projects${params}`);
    }
    
    async getCarbonTokens(farmerId, projectId) {
        let params = '';
        if (farmerId || projectId) {
            params = '?' + new URLSearchParams({ farmer_id: farmerId, project_id: projectId }).toString();
        }
        return this.request(`/sustainability/carbon-tokens${params}`);
    }
    
    // Dashboard Summary - Aggregated sustainability data
    async getDashboardSummary(cooperativeId) {
        const params = cooperativeId ? `?cooperative_id=${cooperativeId}` : '';
        return this.request(`/sustainability/dashboard-summary${params}`);
    }

    // Tree Management
    async addTree(farmId, parcelId, treeData) {
        return this.request(`/farmer/farm/${farmId}/parcel/${parcelId}/trees`, {
            method: 'POST',
            body: JSON.stringify(treeData)
        });
    }

    async getParcelTrees(farmId, parcelId) {
        return this.request(`/farmer/farm/${farmId}/parcel/${parcelId}/trees`);
    }

    async updateTree(farmId, parcelId, treeId, treeData) {
        return this.request(`/farmer/farm/${farmId}/parcel/${parcelId}/trees/${treeId}`, {
            method: 'PUT',
            body: JSON.stringify(treeData)
        });
    }

    async deleteTree(farmId, parcelId, treeId) {
        return this.request(`/farmer/farm/${farmId}/parcel/${parcelId}/trees/${treeId}`, {
            method: 'DELETE'
        });
    }

    // Crop Management
    async addCropArea(farmId, parcelId, cropData) {
        return this.request(`/farmer/farm/${farmId}/parcel/${parcelId}/crops`, {
            method: 'POST',
            body: JSON.stringify(cropData)
        });
    }

    async getParcelCrops(farmId, parcelId) {
        return this.request(`/farmer/farm/${farmId}/parcel/${parcelId}/crops`);
    }

    // Historical Analysis
    async getHistoricalFarmAnalysis(farmId, startYear, endYear) {
        let params = '';
        if (startYear || endYear) {
            params = '?' + new URLSearchParams({
                start_year: startYear,
                end_year: endYear
            }).toString();
        }
        return this.request(`/farmer/farm/${farmId}/historical-analysis${params}`);
    }

    async storeHistoricalAnalysis(farmId, analysisData) {
        return this.request(`/farmer/farm/${farmId}/store-historical-analysis`, {
            method: 'POST',
            body: JSON.stringify(analysisData)
        });
    }

    // Crop Management
    async getCropTypes(category) {
        let params = '';
        if (category) {
            params = `?category=${category}`;
        }
        return this.request(`/farmer/crop-types${params}`);
    }

    async updateCropArea(farmId, parcelId, cropId, cropData) {
        return this.request(`/farmer/farm/${farmId}/parcel/${parcelId}/crops/${cropId}`, {
            method: 'PUT',
            body: JSON.stringify(cropData)
        });
    }

    async deleteCropArea(farmId, parcelId, cropId) {
        return this.request(`/farmer/farm/${farmId}/parcel/${parcelId}/crops/${cropId}`, {
            method: 'DELETE'
        });
    }

    async analyzeCropHealth(farmId, parcelId, cropId) {
        return this.request(`/farmer/farm/${farmId}/parcel/${parcelId}/crop-analysis`, {
            method: 'POST',
            body: JSON.stringify({ crop_id: cropId })
        });
    }

    // Wallet & Payments
    async getWalletStats() {
        return this.request('/admin/wallet/stats');
    }

    async getPayments(filters = {}) {
        const params = new URLSearchParams(filters);
        return this.request(`/admin/payments?${params}`);
    }

    async getPaymentChartData() {
        return this.request('/admin/payments/chart');
    }
}

// Global API instance
window.api = new PlotraAPI();

// PlotraAPI extensions for System Configuration
PlotraAPI.prototype.getSystemSettings = async function() {
    return this.request('/admin/config/settings', { optional: true, default: {} });
};
PlotraAPI.prototype.updateSystemSettings = async function(section, values) {
    return this.request('/admin/config/settings', {
        method: 'PUT',
        body: JSON.stringify({ section, values })
    });
};

PlotraAPI.prototype.getRequiredDocuments = async function() {
    return this.request('/admin/config/required-documents', { optional: true, default: [] });
};

PlotraAPI.prototype.createRequiredDocument = async function(docData) {
    return this.request('/admin/config/required-documents', {
        method: 'POST',
        body: JSON.stringify(docData)
    });
};

PlotraAPI.prototype.updateRequiredDocument = async function(docId, docData) {
    return this.request(`/admin/config/required-documents/${docId}`, {
        method: 'PUT',
        body: JSON.stringify(docData)
    });
};

PlotraAPI.prototype.deleteRequiredDocument = async function(docId) {
    return this.request(`/admin/config/required-documents/${docId}`, {
        method: 'DELETE'
    });
};

PlotraAPI.prototype.getSessionTimeout = async function() {
    return this.request('/admin/config/session-timeout', { optional: true, default: { timeout_minutes: 30 } });
};

PlotraAPI.prototype.updateSessionTimeout = async function(timeoutMinutes) {
    return this.request('/admin/config/session-timeout', {
        method: 'PUT',
        body: JSON.stringify({ session_timeout_minutes: timeoutMinutes, max_login_attempts: 5, lockout_duration_minutes: 15 })
    });
};

PlotraAPI.prototype.getEnvCredentials = async function() {
    return this.request('/admin/config/env-credentials', { optional: true, default: { credentials: {} } });
};

PlotraAPI.prototype.updateEnvCredential = async function(key, value, description = '', isPublic = false) {
    return this.request('/admin/config/env-credentials', {
        method: 'PUT',
        body: JSON.stringify({ key, value, description, is_public: isPublic })
    });
};

PlotraAPI.prototype.deleteEnvCredential = async function(key) {
    return this.request(`/admin/config/env-credentials/${key}`, {
        method: 'DELETE'
    });
};
