/**
 * Plotra Dashboard - Core Module
 * Main PlotraDashboard class
 */

class PlotraDashboard {
    constructor() {
        this.currentUser = null;
        this.currentPage = 'dashboard';
        this.map = null;
        this.charts = {};
        this.resetToken = null;
        this.adminPages = ['cooperatives', 'farmers', 'wallet', 'users', 'sustainability', 'system'];
        this._sessionTimer = null;
        this._sessionCheckInterval = null;
        this._sessionWarningShown = false;

        this.init();
    }
    
    init() {
        this.checkResetPasswordToken();
        this.checkAuth();
        this.setupEventListeners();
        this.setupOfflineDetection();
        this.initFarmMapping();
        this.setupNavigation();
        this.initScrollAnimations();
    }
    
    checkResetPasswordToken() {
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        const email = urlParams.get('email');
        
        if (token) {
            this.resetToken = token;
            if (email) {
                sessionStorage.setItem('pending_login_email', email);
            }
        }
    }
    
    checkAuth() {
        const token = localStorage.getItem('plotra_token');
        if (token && token.length > 10) {
            this.showApp();
        } else {
            if (token) {
                localStorage.removeItem('plotra_token');
                localStorage.removeItem('plotra_user');
            }
            if (this.resetToken) {
                this.showResetPasswordStep();
            } else {
                this.showLandingPage();
            }
        }
    }
    
    showResetPasswordStep() {
        document.body.classList.add('auth-active');
        const modal = new bootstrap.Modal(document.getElementById('loginModal'));
        modal.show();
        setTimeout(() => {
            document.querySelectorAll('#loginModal .step-content').forEach(s => s.classList.remove('active'));
            document.getElementById('loginStepReset').classList.add('active');
        }, 200);
    }
    
    showLandingPage() {
        document.body.classList.remove('auth-active');
        const landingPage = document.getElementById('landing-page');
        const appContainer = document.getElementById('app-container');
        if (landingPage) landingPage.classList.remove('d-none');
        if (appContainer) appContainer.classList.add('d-none');
    }
    
    showApp() {
        document.body.classList.remove('auth-active');
        const appContainer = document.getElementById('app-container');
        const landingPage = document.getElementById('landing-page');
        if (appContainer) appContainer.classList.remove('d-none');
        if (landingPage) landingPage.classList.add('d-none');

        this.loadCurrentUser().then(() => {
            this.updateSidebarNavigation();
            this.loadPage('dashboard');
            this.loadNotifications();
            this._startSessionWatcher();
        });
    }
    
    async loadCurrentUser() {
        this.currentUser = await api.getCurrentUser();
        localStorage.setItem('plotra_user', JSON.stringify(this.currentUser));
        
        const roleBadge = document.getElementById('userRole');
        if (roleBadge) roleBadge.textContent = this.formatRole(this.currentUser.role);
        
        const headerBrandTitle = document.getElementById('headerBrandTitle');
        if (headerBrandTitle) {
            const r = (this.currentUser.role || '').toLowerCase();
            if (r === 'plotra_admin') {
                headerBrandTitle.textContent = 'Platform Management';
            } else if (r === 'farmer') {
                headerBrandTitle.textContent = 'Farmers Workplace';
            } else {
                headerBrandTitle.textContent = 'Plotra Platform';
            }
        }
        
        const userProfile = document.getElementById('userProfile');
        if (userProfile) {
            userProfile.style.display = 'flex';
            const firstName = this.currentUser.first_name || '';
            const lastName = this.currentUser.last_name || '';
            const initials = (firstName.charAt(0) + lastName.charAt(0)).toUpperCase() || 'U';
            const userAvatar = document.getElementById('userAvatar');
            const userName = document.getElementById('userName');
            if (userName) userName.textContent = firstName || this.currentUser.email || 'User';
            if (userAvatar) {
                userAvatar.textContent = initials;
            }
        }
    }
    
    formatRole(role) {
        const roles = {
            'farmer': 'Farmer',
            'cooperative_officer': 'Cooperative Officer',
            'plotra_admin': 'Platform Admin',
            'eudr_reviewer': 'EUDR Reviewer'
        };
        return roles[role] || role || 'User';
    }
    
    getRoleBadgeClass(role) {
        const classes = {
            'farmer': 'bg-success',
            'cooperative_officer': 'bg-primary',
            'plotra_admin': 'bg-dark',
            'eudr_reviewer': 'bg-warning text-dark'
        };
        return classes[role] || 'bg-secondary';
    }
    
    setupOfflineDetection() {
        window.addEventListener('offline', () => {
            const indicator = document.getElementById('offlineStatus');
            if (indicator) indicator.classList.remove('d-none');
        });
        window.addEventListener('online', () => {
            const indicator = document.getElementById('offlineStatus');
            if (indicator) indicator.classList.add('d-none');
        });
    }
    
    setupEventListeners() {
        // Logout button
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.logout());
        }
        
        // Subscribe newsletter
        const subForm = document.getElementById('newsletterForm');
        if (subForm) {
            subForm.addEventListener('submit', e => {
                e.preventDefault();
                this.subscribeNewsletter();
            });
        }
    }
    
    subscribeNewsletter() {
        this.showToast('Thank you for subscribing!', 'success');
    }
    
    logout() {
        localStorage.removeItem('plotra_token');
        localStorage.removeItem('plotra_user');
        this._stopSessionWatcher();
        api.logout();
        this.showLandingPage();
    }
    
    // Session Management
    _startSessionWatcher() {
        this._stopSessionWatcher();
        this._sessionCheckInterval = setInterval(() => this._checkSession(), 10000);
    }
    
    _stopSessionWatcher() {
        if (this._sessionCheckInterval) {
            clearInterval(this._sessionCheckInterval);
            this._sessionCheckInterval = null;
        }
        if (this._sessionTimer) {
            clearTimeout(this._sessionTimer);
            this._sessionTimer = null;
        }
    }
    
    _checkSession() {
        const expiresAt = parseInt(localStorage.getItem('session_expires_at') || '0');
        const now = Date.now();
        const remaining = expiresAt - now;
        const warningTime = 5 * 60 * 1000; // 5 minutes
        
        if (remaining <= 0) {
            this._doAutoLogout();
        } else if (remaining < warningTime && !this._sessionWarningShown) {
            this._showSessionWarning(remaining);
        }
    }
    
    _showSessionWarning(remaining) {
        this._sessionWarningShown = true;
        const mins = Math.floor(remaining / 60000);
        this.showToast(`Session expires in ${mins} minute${mins !== 1 ? 's' : ''}. Save your work.`, 'warning');
        
        this._sessionTimer = setTimeout(() => {
            this._doAutoLogout();
        }, remaining);
    }
    
    _doAutoLogout() {
        this._stopSessionWatcher();
        sessionStorage.setItem('logout_reason', 'Session expired');
        this.logout();
        this.showToast('Session expired. Please login again.', 'error');
    }
    
    // Navigation
    setupNavigation() {
        document.querySelectorAll('[data-page]').forEach(el => {
            el.addEventListener('click', e => {
                e.preventDefault();
                const page = el.dataset.page;
                this.navigateTo(page);
            });
        });
    }
    
    updateSidebarNavigation() {
        const sidebar = document.getElementById('sidebar-nav');
        if (!sidebar) return;
        
        const role = (this.currentUser?.role || '').toLowerCase();
        sidebar.querySelectorAll('[data-role-required]').forEach(el => {
            const required = el.dataset.roleRequired.split(',');
            el.style.display = required.includes(role) || required.includes('any') ? '' : 'none';
        });
    }
    
    navigateTo(page) {
        this.currentPage = page;
        this.loadPage(page);
    }
    
    async loadPage(page) {
        const content = document.getElementById('pageContent');
        if (!content) return;
        
        // Update active nav
        document.querySelectorAll('.sidebar-nav a').forEach(a => {
            a.classList.remove('active');
            if (a.dataset.page === page) a.classList.add('active');
        });
        
        // Show loading
        content.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        
        try {
            switch (page) {
                case 'dashboard':
                    await this.renderDashboard();
                    break;
                case 'farmers':
                case 'farmer-management':
                    await this.renderFarmerManagement();
                    break;
                case 'verification':
                    await this.renderVerification();
                    break;
                case 'wallet':
                case 'payments':
                    await this.renderWallet();
                    break;
                case 'compliance':
                    await this.renderCompliance();
                    break;
                case 'monitoring':
                    await this.renderMonitoring();
                    break;
                case 'deliveries':
                case 'batches':
                    await this.renderDeliveries();
                    break;
                case 'sustainability':
                    await this.renderSustainability();
                    break;
                case 'satellite':
                    await this.renderSatellite();
                    break;
                default:
                    content.innerHTML = `<div class="alert alert-info">Page: ${page}</div>`;
            }
        } catch (err) {
            console.error('Page load error:', err);
            content.innerHTML = `<div class="alert alert-danger">Error loading page: ${err.message}</div>`;
        }
    }
    
    // Dashboard rendering placeholder
    async renderDashboard() {
        const content = document.getElementById('pageContent');
        if (content) {
            content.innerHTML = `
                <div class="container-fluid">
                    <h4 class="mb-4">Dashboard</h4>
                    <p>Welcome, ${this.currentUser?.first_name || 'User'}!</p>
                </div>
            `;
        }
    }
    
    async renderFarmerManagement() { this._loadFarmersPage(); }
    async renderVerification() { this._loadVerificationPage(); }
    async renderWallet() { this._loadWalletPage(); }
    async renderCompliance() { this._loadCompliancePage(); }
    async renderMonitoring() { this._loadMonitoringPage(); }
    async renderDeliveries() { this._loadDeliveriesPage(); }
    async renderSustainability() { this._loadSustainabilityPage(); }
    async renderSatellite() { this._loadSatellitePage(); }
    
    // Placeholder methods - implemented in other modules
    _loadFarmersPage() {}
    _loadVerificationPage() {}
    _loadWalletPage() {}
    _loadCompliancePage() {}
    _loadMonitoringPage() {}
    _loadDeliveriesPage() {}
    _loadSustainabilityPage() {}
    _loadSatellitePage() {}
    
    async loadNotifications() {
        try {
            const notifs = await api.getNotifications();
            const badge = document.getElementById('notifBadge');
            if (badge && notifs.length > 0) {
                badge.textContent = notifs.length;
                badge.classList.remove('d-none');
            }
        } catch (e) {
            console.error('Notifications error:', e);
        }
    }
    
    // Utilities
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast show align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 5000);
    }
    
    initScrollAnimations() {
        const reveals = document.querySelectorAll('.reveal');
        if ('IntersectionObserver' in window) {
            const io = new IntersectionObserver(entries => {
                entries.forEach(e => {
                    if (e.isIntersecting) {
                        e.target.classList.add('in');
                        io.unobserve(e.target);
                    }
                });
            }, { threshold: 0.1 });
            reveals.forEach(el => io.observe(el));
        } else {
            reveals.forEach(el => el.classList.add('in'));
        }
    }
    
    canAccessPage(page) {
        const role = (this.currentUser?.role || '').toLowerCase();
        const restrictions = {
            'admin-pages': ['plotra_admin', 'cooperative_officer', 'eudr_reviewer'],
            'wallet': ['farmer', 'plotra_admin'],
            'satellite': ['farmer', 'cooperative_officer', 'plotra_admin']
        };
        return true;
    }
    
    toggleSidebar() {
        document.body.classList.toggle('sidebar-open');
    }
}

// Global instance
let plotraDashboard = null;

function initPlotraDashboard() {
    if (!plotraDashboard) {
        plotraDashboard = new PlotraDashboard();
    }
    return plotraDashboard;
}

function getPlotraDashboard() {
    return plotraDashboard;
}