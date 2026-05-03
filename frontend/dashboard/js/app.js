/**
 * Plotra Dashboard - Main Application
 * Bootstrap-based dashboard with role-based access
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
        this.gpsInitialized = false; // For GPS button one-time setup
        this.currentViewedDDSId = null; // For DDS detail modal

        this.init();
    }
    
    init() {
        // Check for reset password token in URL
        this.checkResetPasswordToken();

        this.checkAuth();
        this.setupEventListeners();
        this.setupOfflineDetection();
        this.initFarmMapping(); // Initialize farm mapping system
        this.setupNavigation(); // Initialize navigation
        this.initScrollAnimations();
    }
    
    checkResetPasswordToken() {
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        const email = urlParams.get('email');
        
        if (token) {
            this.resetToken = token;
            console.log('Reset password token detected:', token.substring(0, 8) + '...');
            
            // If email is also provided, store it for auto-login after password reset
            if (email) {
                sessionStorage.setItem('pending_login_email', email);
                console.log('Stored email for auto-login:', email);
            }
        }
    }
    
    checkAuth() {
        const token = localStorage.getItem('plotra_token');
        if (token && token.length > 10) {
            // Validate token exists and has minimum length before attempting to show app
            this.showApp();
        } else {
            // Clear any invalid tokens
            if (token) {
                localStorage.removeItem('plotra_token');
                localStorage.removeItem('plotra_user');
            }

            // If we have a reset password token, show reset password step
            if (this.resetToken) {
                this.showResetPasswordStep();
            } else {
                this.showLandingPage();
            }
        }
    }
    
    showResetPasswordStep() {
        document.body.classList.add('auth-active');
        
        // Show the login modal but switch to reset password step
        const modal = new bootstrap.Modal(document.getElementById('loginModal'));
        modal.show();
        
        // Wait for modal to be shown, then switch to reset step
        setTimeout(() => {
            document.querySelectorAll('#loginModal .step-content').forEach(s => s.classList.remove('active'));
            document.getElementById('loginStepReset').classList.add('active');
        }, 200);
    }
    
    showLogin() {
        document.body.classList.add('auth-active');
        const modal = new bootstrap.Modal(document.getElementById('loginModal'));
        modal.show();
    }

    showLandingPage() {
        console.log('Showing landing page...');
        document.body.classList.remove('auth-active');
        const landingPage = document.getElementById('landing-page');
        const appContainer = document.getElementById('app-container');
        if (landingPage) landingPage.classList.remove('d-none');
        if (appContainer) appContainer.classList.add('d-none');

        const reason = sessionStorage.getItem('logout_reason');
        if (reason) {
            sessionStorage.removeItem('logout_reason');
            setTimeout(() => this.showToast(reason, 'warning', 6000), 400);
        }
    }

    subscribeNewsletter() {
        const email = document.getElementById('newsletterEmail').value;
        if (!email) {
            this.showToast('Please enter your email address', 'warning');
            return;
        }

        if (!email.includes('@')) {
            this.showToast('Please enter a valid email address', 'warning');
            return;
        }

        // For demo purposes, just show success message
        this.showToast('Thank you for subscribing! We\'ll keep you updated on coffee farming insights.', 'success');
        document.getElementById('newsletterEmail').value = '';
    }

    showRegisterModal() {
        document.body.classList.add('auth-active');
        
        // Blur any focused element to prevent aria-hidden conflict
        if (document.activeElement && document.activeElement !== document.body) {
            document.activeElement.blur();
        }
        
        // Hide login modal first if open
        const loginEl = document.getElementById('loginModal');
        const loginModal = bootstrap.Modal.getInstance(loginEl);
        if (loginModal) loginModal.hide();
        
        // Reset to step 1
        document.querySelectorAll('#registerModal .step-content').forEach(s => s.classList.remove('active'));
        document.getElementById('regStep1').classList.add('active');
        
        const registerEl = document.getElementById('registerModal');
        registerEl.removeAttribute('aria-hidden');
        const modal = new bootstrap.Modal(registerEl);
        modal.show();
    }
    
    showLoginModal() {
        document.body.classList.add('auth-active');
        
        // Blur any focused element to prevent aria-hidden conflict
        if (document.activeElement && document.activeElement !== document.body) {
            document.activeElement.blur();
        }
        
        // Hide register modal first if open
        const registerEl = document.getElementById('registerModal');
        const registerModal = bootstrap.Modal.getInstance(registerEl);
        if (registerModal) registerModal.hide();
        
        // Reset to step 1
        document.querySelectorAll('#loginModal .step-content').forEach(s => s.classList.remove('active'));
        document.getElementById('loginStep1').classList.add('active');
        
        const loginEl = document.getElementById('loginModal');
        loginEl.removeAttribute('aria-hidden');
        const modal = new bootstrap.Modal(loginEl);
        modal.show();
    }
    
    showForgotStep() {
        document.querySelectorAll('#loginModal .step-content').forEach(s => s.classList.remove('active'));
        document.getElementById('loginStepForgot').classList.add('active');
    }

    async handleForgot() {
        const digits = (document.getElementById('forgotEmail')?.value || '').replace(/\D/g, '');
        if (digits.length < 7) {
            this.showToast('Please enter your phone number', 'error');
            return;
        }
        const phone = this.buildPhoneNumber('forgotPrefix', 'forgotEmail');
        const btn = document.getElementById('btnForgotSend');
        const msg = document.getElementById('msgForgot');
        if (btn) { btn.disabled = true; btn.textContent = 'Checking...'; }
        if (msg) msg.textContent = '';

        try {
            const formData = new FormData();
            formData.append('phone', phone);
            const res = await api.request('/auth/forgot-password-otp', { method: 'POST', body: formData, headers: { 'Content-Type': null } });

            // Store phone for OTP verification step
            this._forgotPhone = phone;

            // Show OTP banner in dev mode
            if (res.dev_code) {
                const banner = document.getElementById('devForgotOtpBanner');
                const code = document.getElementById('devForgotOtpCode');
                if (banner) banner.style.display = 'block';
                if (code) code.textContent = res.dev_code;
            }

            // Init OTP boxes
            const grid = document.getElementById('forgotOtpGrid');
            if (grid) this._initOTPBoxes(grid);

            const desc = document.getElementById('forgotOtpDesc');
            if (desc) desc.textContent = `We sent a 6-digit code to ${phone}.`;

            document.querySelectorAll('#loginModal .step-content').forEach(s => s.classList.remove('active'));
            document.getElementById('loginStepForgotOTP').classList.add('active');
        } catch (error) {
            if (msg) { msg.textContent = error.message; msg.style.color = 'red'; }
            else this.showToast(error.message, 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = 'Send OTP'; }
        }
    }

    async handleForgotOTPVerify() {
        const grid = document.getElementById('forgotOtpGrid');
        const code = Array.from(grid?.querySelectorAll('.otp-box') || []).map(i => i.value).join('');
        const msg = document.getElementById('msgForgotOtp');
        if (code.length < 6) {
            if (msg) { msg.textContent = 'Enter the 6-digit code'; msg.style.color = 'red'; }
            return;
        }
        const btn = document.getElementById('btnVerifyForgotOTP');
        if (btn) { btn.disabled = true; btn.textContent = 'Verifying...'; }
        if (msg) msg.textContent = '';

        try {
            const formData = new FormData();
            formData.append('phone', this._forgotPhone);
            formData.append('code', code);
            const res = await api.request('/auth/verify-otp', { method: 'POST', body: formData, headers: { 'Content-Type': null } });

            // Store reset token returned by verify-otp
            if (res.reset_token) this.resetToken = res.reset_token;

            document.querySelectorAll('#loginModal .step-content').forEach(s => s.classList.remove('active'));
            document.getElementById('loginStepReset').classList.add('active');
        } catch (error) {
            if (msg) { msg.textContent = error.message; msg.style.color = 'red'; }
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = 'Verify'; }
        }
    }

    _initOTPBoxes(grid) {
        const boxes = grid.querySelectorAll('.otp-box');
        boxes.forEach((box, i) => {
            box.value = '';
            box.addEventListener('input', () => {
                if (box.value && i < boxes.length - 1) boxes[i + 1].focus();
            });
            box.addEventListener('keydown', e => {
                if (e.key === 'Backspace' && !box.value && i > 0) boxes[i - 1].focus();
            });
        });
        boxes[0].focus();
    }
    
    async handleReset() {
        const pass = document.getElementById('resetPassword').value;
        const confirm = document.getElementById('resetConfirmPassword').value;
        
        if (pass.length < 8) {
            this.showToast('Password must be at least 8 characters', 'error');
            return;
        }
        
        if (pass !== confirm) {
            this.showToast('Passwords do not match', 'error');
            return;
        }
        
        if (!this.resetToken) {
            this.showToast('Invalid reset token. Please request a new password reset.', 'error');
            return;
        }
        
        try {
            await api.resetPassword(this.resetToken, pass, confirm);
            this.showToast('Password set successfully! Redirecting to your dashboard...', 'success');
            
            // Clear the URL token parameter
            window.history.replaceState({}, document.title, window.location.pathname);
            this.resetToken = null;
            
            // Get user info from URL or stored data to login automatically
            // For cooperative admin creation, we stored user email in sessionStorage
            const userEmail = sessionStorage.getItem('pending_login_email');
            const userRole = sessionStorage.getItem('pending_login_role');
            
            if (userEmail) {
                // Auto-login with the same credentials
                try {
                    const loginData = await api.login(userEmail, pass);
                    if (loginData && loginData.access_token) {
                        localStorage.setItem('plotra_token', loginData.access_token);
                        sessionStorage.removeItem('pending_login_email');
                        sessionStorage.removeItem('pending_login_role');
                        // Show the app - will redirect to appropriate dashboard based on role
                        this.showApp();
                        return;
                    }
                } catch (loginErr) {
                    console.error('Auto-login failed:', loginErr);
                }
            }
            
            // Fallback: Show login modal if auto-login not possible
            this.showLoginModal();
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }
    
    previewRegPhoto(input) {
        if (!input.files || !input.files[0]) return;
        const reader = new FileReader();
        reader.onload = e => {
            const preview = document.getElementById('regPhotoPreview');
            if (preview) preview.src = e.target.result;
            // Store for later saving to profile
            this._pendingProfilePhoto = e.target.result;
        };
        reader.readAsDataURL(input.files[0]);
    }

    togglePassword(inputId, iconId) {
        const input = document.getElementById(inputId);
        const icon = document.getElementById(iconId);
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
    
    showApp() {
        console.log('Showing app...');
        document.body.classList.remove('auth-active');
        const appContainer = document.getElementById('app-container');
        const landingPage = document.getElementById('landing-page');
        if (appContainer) appContainer.classList.remove('d-none');
        if (landingPage) landingPage.classList.add('d-none');

        // Immediately restore cached user so sidebar renders instantly on refresh
        const cachedUser = localStorage.getItem('plotra_user');
        if (cachedUser) {
            try {
                this.currentUser = JSON.parse(cachedUser);
                this.updateSidebarNavigation();
                this._applyUserUI();
            } catch (e) { /* ignore corrupt cache */ }
        }

        this.loadCurrentUser().then(() => {
            this.updateSidebarNavigation();
            this.loadPage('dashboard');
            this.loadNotifications();
            // Load session timeout setting (inactivity limit)
            api.getSessionTimeout().then(st => {
                this._sessionTimeoutMinutes = st?.session_timeout_minutes || st?.timeout_minutes || 60;
            }).catch(() => { this._sessionTimeoutMinutes = 60; });
            this._startSessionWatcher();
        }).catch(err => {
            console.error('Failed to show app:', err);
            this.showToast('Failed to load user data', 'error');
        });
    }
    
    _applyUserUI() {
        if (!this.currentUser) return;
        const roleBadge = document.getElementById('userRole');
        const userRoleDisplay = document.getElementById('userRoleDisplay');
        const userProfile = document.getElementById('userProfile');
        const userName = document.getElementById('userName');
        const userAvatar = document.getElementById('userAvatar');

        if (roleBadge) roleBadge.textContent = this.formatRole(this.currentUser.role);
        if (userRoleDisplay) userRoleDisplay.textContent = this.formatRole(this.currentUser.role);

        const headerBrandTitle = document.getElementById('headerBrandTitle');
        if (headerBrandTitle) {
            const r = (this.currentUser.role || '').toLowerCase();
            if (r === 'plotra_admin' || r === 'kipawa_admin') {
                headerBrandTitle.textContent = 'Platform Management';
            } else if (r === 'farmer') {
                headerBrandTitle.textContent = 'Farmers Workplace';
            } else if (r === 'cooperative_officer') {
                headerBrandTitle.textContent = 'Cooperative Workplace';
            } else {
                headerBrandTitle.textContent = 'Plotra Platform';
            }
        }

        if (userProfile) {
            userProfile.style.display = 'flex';
            const firstName = this.currentUser.first_name || '';
            const lastName = this.currentUser.last_name || '';
            const initials = (firstName.charAt(0) + lastName.charAt(0)).toUpperCase() || (this.currentUser.email || 'U').charAt(0).toUpperCase();
            if (userName) userName.textContent = firstName || this.currentUser.email || 'User';
            if (userAvatar) {
                userAvatar.textContent = initials;
                userAvatar.style.background = 'linear-gradient(135deg, #6f4e37, #4a2c1a)';
                userAvatar.style.color = 'white';
                userAvatar.style.fontWeight = 'bold';
                userAvatar.style.fontSize = initials.length > 1 ? '0.85rem' : '1rem';
                userAvatar.style.letterSpacing = '1px';
            }
        }

        const roleStr = (this.currentUser.role || '').toUpperCase();
        const isFarmerUser = roleStr === 'FARMER';
        const adminOnlyItems = ['nav-farmer-approvals'];
        adminOnlyItems.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = isFarmerUser ? 'none' : '';
        });

        // Navbar search area: coop officers see cooperative name; others see nothing
        const searchArea = document.getElementById('navbarSearchArea');
        if (searchArea) {
            if (roleStr === 'COOPERATIVE_OFFICER') {
                searchArea.outerHTML = `<div id="navbarSearchArea" class="d-none d-lg-flex align-items-center gap-2">
                    <i class="bi bi-building" style="color:#daa520;font-size:1.1rem;"></i>
                    <span id="navCoopName" style="color:#f5f5dc;font-weight:600;font-size:0.95rem;white-space:nowrap;">Loading...</span>
                </div>`;
                // Fetch and display cooperative name
                api.request('/coop/me').then(res => {
                    const el = document.getElementById('navCoopName');
                    if (el && res?.cooperative_name) el.textContent = res.cooperative_name;
                    // Cache for later use
                    if (res?.cooperative_id && this.currentUser) {
                        this.currentUser.cooperative_id = res.cooperative_id;
                        this.currentUser.cooperative_name = res.cooperative_name;
                        localStorage.setItem('plotra_user', JSON.stringify(this.currentUser));
                    }
                }).catch(() => {
                    const el = document.getElementById('navCoopName');
                    if (el) el.textContent = 'Cooperative';
                });
            } else {
                searchArea.outerHTML = `<div id="navbarSearchArea"></div>`;
            }
        }
    }

    async loadCurrentUser() {
        try {
            this.currentUser = await api.getCurrentUser();
            localStorage.setItem('plotra_user', JSON.stringify(this.currentUser));
            console.log('Current user loaded:', this.currentUser);
            console.log('User role:', this.currentUser?.role);

            if (!this.currentUser || !this.currentUser.id) {
                throw new Error('Invalid user data');
            }

            this._applyUserUI();
        } catch (error) {
            console.error('Failed to load user:', error);
            // Clear invalid token and show landing page
            localStorage.removeItem('plotra_token');
            localStorage.removeItem('plotra_user');
            this.showToast('Session expired. Please login again.', 'error');
            this.showLandingPage();
        }
    }

    formatRole(role) {
        const roleMap = {
            'farmer': 'FARMER WORKPLACE',
            'plotra_admin': 'PLOTRA SYSTEM MANAGEMENT',
            'platform_admin': 'PLOTRA SYSTEM MANAGEMENT',
            'super_admin': 'PLOTRA SYSTEM MANAGEMENT',
            'admin': 'PLOTRA SYSTEM MANAGEMENT',
            'cooperative_admin': 'COOPERATIVE WORKPLACE',
            'coop_admin': 'COOPERATIVE WORKPLACE',
            'cooperative_officer': 'COOPERATIVE WORKPLACE',
            'coop_officer': 'COOPERATIVE WORKPLACE',
            'eudr_reviewer': 'EUDR REVIEWER',
            'belgian_team': 'BELGIAN TEAM'
        };

        const mappedRole = roleMap[role] || role.replace(/_/g, ' ').toUpperCase();
        return mappedRole;
    }
    
    getRoleBadgeClass(role) {
        const r = role?.toLowerCase();
        if (r === 'farmer') return 'bg-success-subtle text-success border';
        if (r === 'cooperative_officer' || r === 'coop_admin') return 'bg-primary-subtle text-primary border';
        if (r === 'plotra_admin' || r === 'kipaca_admin' || r === 'super_admin') return 'bg-danger-subtle text-danger border';
        if (r === 'eudr_reviewer') return 'bg-info-subtle text-info border';
        return 'bg-secondary-subtle text-secondary border';
    }
    
    // Role-based navigation configuration
    getRoleNavigation(role) {
        const roleUpper = role?.toUpperCase();
        
        // Define navigation items for each role
        const farmerNav = [
            { id: 'dashboard', icon: 'bi-speedometer2', label: 'Dashboard' },
            { id: 'farms', icon: 'bi-geo-alt', label: 'My Farms' },
            { id: 'deliveries', icon: 'bi-box-seam', label: 'Deliveries' },
            { id: 'documents', icon: 'bi-file-earmark-text', label: 'KYC Documents' },
            { id: 'compliance', icon: 'bi-file-earmark-check', label: 'EUDR Compliance' },
            { id: 'profile', icon: 'bi-person-circle', label: 'My Profile' }
        ];

        const coopAdminNav = [
            { id: 'dashboard', icon: 'bi-speedometer2', label: 'Dashboard' },
            { id: 'farms', icon: 'bi-geo-alt', label: 'Farms' },
            { id: 'farmers', icon: 'bi-people', label: 'Farmers' },
            { id: 'farmer-approvals', icon: 'bi-shield-check', label: 'Farmer Approvals' },
            { id: 'deliveries', icon: 'bi-box-seam', label: 'Deliveries' },
            { id: 'batches', icon: 'bi-layers', label: 'Batches' },
            { id: 'verification', icon: 'bi-check-circle', label: 'Verification' },
            { id: 'satellite', icon: 'bi-satellite', label: 'Satellite' },
            { id: 'compliance', icon: 'bi-file-earmark-check', label: 'EUDR' },
            { id: 'users', icon: 'bi-people', label: 'Users' }
        ];

        const coopOfficerNav = [
            { id: 'dashboard', icon: 'bi-speedometer2', label: 'Dashboard' },
            { id: 'coop-farmers', icon: 'bi-people', label: 'Farmers' },
            { id: 'coop-farms', icon: 'bi-geo-alt', label: 'Farms' },
            { id: 'farm-approvals', icon: 'bi-geo-alt-fill', label: 'Farm Approvals' },
            { id: 'farmer-approvals', icon: 'bi-shield-check', label: 'Farmer Approvals' },
            { id: 'deliveries', icon: 'bi-box-seam', label: 'Deliveries' },
            { id: 'coop-team', icon: 'bi-people-fill', label: 'Cooperative Team' },
            { id: 'profile', icon: 'bi-person-circle', label: 'My Profile' }
        ];
        
        const eudrReviewerNav = [
            { id: 'dashboard', icon: 'bi-speedometer2', label: 'Dashboard' },
            { id: 'verification', icon: 'bi-check-circle', label: 'Verification' },
            { id: 'compliance', icon: 'bi-file-earmark-check', label: 'EUDR Review' }
        ];
        
        const adminNav = [
            { id: 'dashboard', icon: 'bi-speedometer2', label: 'Dashboard' },
            { id: 'farms', icon: 'bi-geo-alt', label: 'Farms' },
            { id: 'cooperatives', icon: 'bi-building', label: 'Cooperatives' },
            { id: 'farmers', icon: 'bi-people', label: 'Farmers' },
            { id: 'farmer-approvals', icon: 'bi-shield-check', label: 'Farmer Approvals' },
            { id: 'wallet', icon: 'bi-wallet2', label: 'Wallet & Payments' },
            { id: 'users', icon: 'bi-people', label: 'Users' },
            { id: 'verification', icon: 'bi-check-circle', label: 'Verification EUDR' },
            { id: 'sustainability', icon: 'bi-leaf', label: 'Sustainability' },
            { id: 'system', icon: 'bi-gear', label: 'System Configure' }
        ];
        
        // Return navigation based on role
        // Note: Backend roles are lowercase (farmer, cooperative_officer, plotra_admin, eudr_reviewer)
        // They get converted to uppercase here
        if (roleUpper === 'COOP_ADMIN' || roleUpper === 'COOPERATIVE_ADMIN') {
            return coopAdminNav;
        } else if (roleUpper === 'COOP_OFFICER' || roleUpper === 'FACTOR' || roleUpper === 'COOPERATIVE_OFFICER') {
            return coopOfficerNav;
        } else if (roleUpper === 'EUDR_REVIEWER' || roleUpper === 'BELGIAN_TEAM') {
            return eudrReviewerNav;
        } else if (roleUpper === 'PLATFORM_ADMIN' || roleUpper === 'SUPER_ADMIN' || roleUpper === 'ADMIN' || roleUpper === 'PLOTRA_ADMIN') {
            return adminNav;
        } else {
            // Default to farmer navigation (includes 'FARMER' role)
            return farmerNav;
        }
    }
    
    // Update sidebar navigation based on user role
    updateSidebarNavigation() {
        const role = this.currentUser?.role || 'FARMER';
        console.log('updateSidebarNavigation: role =', role);
        const navItems = this.getEffectiveNavItems(this.getRoleNavigation(role));
        const navContainer = document.getElementById('sidebar-menu');
        
        if (!navContainer) {
            console.error('Sidebar menu container not found!');
            return;
        }
        
        // Build new navigation HTML
        let navHtml = `
            <li class="nav-item static-item">
                <a class="nav-link static-item disabled" href="#" tabindex="-1">
                    <span class="default-icon">Menu</span>
                    <span class="mini-icon">-</span>
                </a>
            </li>
        `;

        navItems.forEach(item => {
            const isActive = this.currentPage === item.id ? 'active' : '';
            navHtml += `
                <li class="nav-item">
                    <a class="nav-link ${isActive}" href="#" data-page="${item.id}">
                        <i class="icon">
                           <i class="bi ${item.icon}"></i>
                        </i>
                        <span class="item-name">${item.label}</span>
                    </a>
                </li>
            `;
        });
        
        // Add logout button at the end
        navHtml += `
            <li class="nav-item mt-2">
                <hr class="hr-horizontal">
            </li>
            <li class="nav-item">
                <a class="nav-link" href="#" id="logoutBtn">
                    <i class="icon">
                        <svg width="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="icon-20">
                            <path opacity="0.4" d="M12.0001 2C6.48608 2 2.00008 6.486 2.00008 12C2.00008 17.514 6.48608 22 12.0001 22C17.5141 22 22.0001 17.514 22.0001 12C22.0001 6.486 17.5141 2 12.0001 2Z" fill="currentColor"></path>
                            <path d="M12.0001 15C11.4481 15 11.0001 14.552 11.0001 14V10C11.0001 9.448 11.4481 9 12.0001 9C12.5521 9 13.0001 9.448 13.0001 10V14C13.0001 14.552 12.5521 15 12.0001 15Z" fill="currentColor"></path>
                            <path d="M12.0001 8C11.4481 8 11.0001 7.552 11.0001 7C11.0001 6.448 11.4481 6 12.0001 6C12.5521 6 13.0001 6.448 13.0001 7C13.0001 7.552 12.5521 8 12.0001 8Z" fill="currentColor"></path>
                        </svg>
                    </i>
                    <span class="item-name">Logout</span>
                </a>
            </li>
        `;
        
        navContainer.innerHTML = navHtml;
        
        // Re-attach event listeners
        this.setupNavigationListeners();
    }
    
    setupNavigationListeners() {
        console.log('Setting up navigation listeners...');
        // Sidebar navigation - Use #sidebar-menu to be specific
        document.querySelectorAll('#sidebar-menu .nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = link.dataset.page;
                console.log('Navigation clicked:', page);
                if (page) {
                    this.navigateTo(page);
                }
            });
        });
        
        // Re-attach logout button listener
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('Logout clicked');
                this.logout();
            });
        }
    }
    
    setupEventListeners() {
        // Update hamburger icon based on sidebar state
        const updateHamburgerIcon = () => {
            const btn = document.getElementById('navbarSidebarToggle');
            if (!btn) return;
            const icon = btn.querySelector('i');
            if (!icon) return;
            const sidebar = document.getElementById('sidebar');
            const isOpen = window.innerWidth >= 1200
                ? !document.body.classList.contains('sidebar-collapsed')
                : sidebar && sidebar.classList.contains('show');
            icon.className = isOpen ? 'bi bi-x' : 'bi bi-list';
            icon.style.fontSize = '1.25rem';
        };

        // Sidebar Toggle Functionality
        const toggleSidebar = () => {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.querySelector('.sidebar-overlay');
            const body = document.body;

            if (sidebar) {
                // Desktop: collapse/expand
                if (window.innerWidth >= 1200) {
                    body.classList.toggle('sidebar-collapsed');
                    sidebar.classList.toggle('collapsed');
                    localStorage.setItem('sidebarCollapsed', body.classList.contains('sidebar-collapsed'));
                }
                // Mobile: slide in/out
                else {
                    sidebar.classList.toggle('show');
                    if (overlay) overlay.classList.toggle('show');
                }
                updateHamburgerIcon();
            }
        };

        // Restore sidebar state on desktop
        if (window.innerWidth >= 1200) {
            const wasCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
            if (wasCollapsed) {
                document.body.classList.add('sidebar-collapsed');
                const sidebar = document.getElementById('sidebar');
                if (sidebar) sidebar.classList.add('collapsed');
            }
        }
        // Set correct icon on load
        updateHamburgerIcon();

        // Delegate sidebar toggle to document to handle dynamically added buttons
        document.addEventListener('click', (e) => {
            const toggleBtn = e.target.closest('[data-toggle="sidebar"], #sidebarToggle, #navbarSidebarToggle');
            if (toggleBtn) {
                e.preventDefault();
                e.stopPropagation();
                toggleSidebar();
            }
        });

        // Close sidebar when clicking overlay (mobile)
        document.addEventListener('click', (e) => {
            const overlay = document.querySelector('.sidebar-overlay');
            const sidebar = document.getElementById('sidebar');

            if (overlay && overlay.classList.contains('show') &&
                !sidebar.contains(e.target) &&
                !e.target.closest('#navbarSidebarToggle')) {
                sidebar.classList.remove('show');
                overlay.classList.remove('show');
                updateHamburgerIcon();
            }
        });

        // Safe helper to add listener
        const safeAddListener = (id, event, callback) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener(event, callback);
        };

        // Close phone country menus when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.phone-input-wrap')) {
                document.querySelectorAll('.phone-country-menu.open').forEach(m => m.classList.remove('open'));
            }
        });

        // Login form
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const step2 = document.getElementById('loginStep2');
                if (step2 && step2.classList.contains('active')) {
                    this.handleLogin();
                } else {
                    const btnNext = document.getElementById('btnNextLogin');
                    if (btnNext) btnNext.click();
                }
            });
        }

        safeAddListener('btnNextLogin', 'click', () => {
            const digits = (document.getElementById('loginUsername')?.value || '').replace(/\D/g, '');
            if (digits.length >= 7) {
                const fullPhone = this.buildPhoneNumber('loginPrefix', 'loginUsername');
                const displayIdentifier = document.getElementById('displayLoginEmail');
                if (displayIdentifier) displayIdentifier.textContent = fullPhone;
                document.getElementById('loginStep1')?.classList.remove('active');
                document.getElementById('loginStep2')?.classList.add('active');
            } else {
                this.showToast('Please enter a valid phone number', 'error');
            }
        });

        safeAddListener('btnBackLogin', 'click', () => {
            const step1 = document.getElementById('loginStep1');
            const step2 = document.getElementById('loginStep2');
            if (step1) step1.classList.add('active');
            if (step2) step2.classList.remove('active');
        });

        // Registration form navigation — Step 1 → OTP
        safeAddListener('btnNextReg1', 'click', async () => {
            const firstName = document.getElementById('regFirstName').value.trim();
            const lastName  = document.getElementById('regLastName').value.trim();
            const rawPhone  = (document.getElementById('regPhone')?.value || '').replace(/\D/g, '');

            if (!firstName || !lastName) {
                this.showToast('Please fill in your first and last name', 'error'); return;
            }
            if (rawPhone.length < 9) {
                this.showToast('Please enter a valid phone number', 'error'); return;
            }

            const btn = document.getElementById('btnNextReg1');
            btn.disabled = true; btn.textContent = 'Sending…';
            try {
                const fullPhone = this.buildPhoneNumber('regPrefix', 'regPhone');
                const otpRes = await api.sendOTP(fullPhone);
                const desc = document.getElementById('otpDesc');
                if (desc) desc.textContent = `We sent a 6-digit code to ${fullPhone}. It expires in 10 minutes.`;
                // DEV: show code in UI
                if (otpRes?.dev_code) {
                    const banner = document.getElementById('devOtpBanner');
                    const codeEl = document.getElementById('devOtpCode');
                    if (banner) banner.style.display = 'block';
                    if (codeEl) codeEl.textContent = otpRes.dev_code;
                }
                document.getElementById('regStep1').classList.remove('active');
                document.getElementById('regStepOTP').classList.add('active');
                document.querySelector('#otpInputGrid .otp-box')?.focus();
            } catch(e) {
                this.showToast('Could not send OTP. Please try again.', 'error');
            } finally {
                btn.disabled = false; btn.textContent = 'Next';
            }
        });

        // OTP — back button
        safeAddListener('btnBackOTP', 'click', () => {
            document.getElementById('regStepOTP').classList.remove('active');
            document.getElementById('regStep1').classList.add('active');
        });

        // OTP — auto-advance between boxes
        document.getElementById('otpInputGrid')?.addEventListener('input', e => {
            if (!e.target.classList.contains('otp-box')) return;
            const boxes = [...document.querySelectorAll('.otp-box')];
            const idx = boxes.indexOf(e.target);
            e.target.value = e.target.value.replace(/\D/g,'').slice(-1);
            if (e.target.value) {
                e.target.classList.add('filled');
                boxes[idx + 1]?.focus();
            } else {
                e.target.classList.remove('filled');
            }
        });
        document.getElementById('otpInputGrid')?.addEventListener('keydown', e => {
            if (!e.target.classList.contains('otp-box')) return;
            const boxes = [...document.querySelectorAll('.otp-box')];
            const idx = boxes.indexOf(e.target);
            if (e.key === 'Backspace' && !e.target.value) boxes[idx - 1]?.focus();
            if (e.key === 'ArrowLeft')  boxes[idx - 1]?.focus();
            if (e.key === 'ArrowRight') boxes[idx + 1]?.focus();
        });

        // OTP — verify button
        safeAddListener('btnVerifyOTP', 'click', async () => {
            const code = [...document.querySelectorAll('.otp-box')].map(b => b.value).join('');
            if (code.length < 6) { this.showToast('Please enter all 6 digits', 'error'); return; }
            const msgEl = document.getElementById('msgOTP');
            const btn   = document.getElementById('btnVerifyOTP');
            btn.disabled = true; btn.textContent = 'Verifying…';
            try {
                const fullPhone = this.buildPhoneNumber('regPrefix', 'regPhone');
                await api.verifyOTP(fullPhone, code);
                document.querySelectorAll('.otp-box').forEach(b => { b.classList.remove('error'); b.classList.add('filled'); });
                if (msgEl) { msgEl.textContent = '✓ Phone verified'; msgEl.className = 'reg-field-msg free text-center'; }
                setTimeout(() => {
                    document.getElementById('regStepOTP').classList.remove('active');
                    document.getElementById('regStep2').classList.add('active');
                }, 600);
            } catch(e) {
                document.querySelectorAll('.otp-box').forEach(b => b.classList.add('error'));
                const msg = e?.message || 'Invalid code. Please try again.';
                if (msgEl) { msgEl.textContent = msg; msgEl.className = 'reg-field-msg taken text-center'; }
            } finally {
                btn.disabled = false; btn.textContent = 'Verify';
            }
        });

        // OTP — resend
        safeAddListener('btnResendOTP', 'click', async () => {
            const btn = document.getElementById('btnResendOTP');
            btn.disabled = true; btn.textContent = 'Sending…';
            try {
                const fullPhone = this.buildPhoneNumber('regPrefix', 'regPhone');
                const resendRes = await api.sendOTP(fullPhone);
                document.querySelectorAll('.otp-box').forEach(b => { b.value=''; b.classList.remove('filled','error'); });
                document.getElementById('msgOTP').textContent = 'New code sent!';
                document.getElementById('msgOTP').className = 'reg-field-msg free text-center';
                if (resendRes?.dev_code) {
                    const codeEl = document.getElementById('devOtpCode');
                    const banner = document.getElementById('devOtpBanner');
                    if (banner) banner.style.display = 'block';
                    if (codeEl) codeEl.textContent = resendRes.dev_code;
                }
                document.querySelector('#otpInputGrid .otp-box')?.focus();
            } catch(e) { this.showToast('Could not resend OTP.', 'error'); }
            finally { setTimeout(() => { btn.disabled=false; btn.textContent='Resend code'; }, 30000); }
        });

        // OTP — back from step 2 now goes to step 1 (not OTP, phone already verified)
        document.querySelectorAll('.btnBackReg1').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('regStep2').classList.remove('active');
                document.getElementById('regStep1').classList.add('active');
            });
        });

        // Real-time field availability checks
        this.setupRegFieldChecks();

        safeAddListener('btnNextReg2', 'click', async () => {
            // Step 2 is now Location (County, Subcounty) with required Cooperative Code
            const county = document.getElementById('regCounty').value;
            const subcounty = document.getElementById('regSubcounty').value;
            const cooperativeCode = document.getElementById('regCooperativeCode').value;
            
            if (!county || !subcounty) {
                this.showToast('Please fill in county and subcounty', 'error');
                return;
            }
            
            if (!cooperativeCode) {
                this.showToast('Please enter your cooperative code', 'error');
                return;
            }
            
            // Validate cooperative code with backend
            try {
                const response = await fetch((window.api ? window.api.baseUrl : '/api/v2') + `/coop/cooperatives/validate-code?code=` + encodeURIComponent(cooperativeCode), {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    // Store the cooperative ID from validation
                    document.getElementById('regCooperativeId').value = data.cooperative_id;
                    document.getElementById('regStep2').classList.remove('active');
                    document.getElementById('regStep3').classList.add('active');
                } else if (response.status === 404) {
                    this.showToast('Invalid cooperative code. Please check and try again.', 'error');
                } else {
                    this.showToast('Error validating cooperative code. Please try again.', 'error');
                }
            } catch (error) {
                console.error('Error validating cooperative code:', error);
                this.showToast('Error validating cooperative code. Please try again.', 'error');
            }
        });

        // Cooperative code autocomplete
        const cooperativeCodeInput = document.getElementById('regCooperativeCode');
        const cooperativeDropdown = document.getElementById('cooperativeDropdown');
        let searchTimeout = null;
        
        if (cooperativeCodeInput && cooperativeDropdown) {
            cooperativeCodeInput.addEventListener('input', (e) => {
                const searchTerm = e.target.value.trim();
                
                // Clear previous timeout
                if (searchTimeout) {
                    clearTimeout(searchTimeout);
                }
                
                // Hide dropdown if search term is too short
                if (searchTerm.length < 2) {
                    cooperativeDropdown.style.display = 'none';
                    return;
                }
                
                // Debounce search
                searchTimeout = setTimeout(async () => {
                    try {
                        const response = await fetch((window.api ? window.api.baseUrl : '/api/v2') + `/coop/cooperatives/search?code=` + encodeURIComponent(searchTerm), {
                            method: 'GET',
                            headers: {
                                'Content-Type': 'application/json'
                            }
                        });
                        
                        if (response.ok) {
                            const data = await response.json();
                            
                            if (data.cooperatives && data.cooperatives.length > 0) {
                                cooperativeDropdown.innerHTML = '';
                                data.cooperatives.forEach(coop => {
                                    const item = document.createElement('div');
                                    item.className = 'p-2 border-bottom cursor-pointer';
                                    item.style.cursor = 'pointer';
                                    item.innerHTML = `
                                        <div class="fw-bold">${coop.code}</div>
                                        <div class="text-muted small">${coop.name}${coop.county ? ' - ' + coop.county : ''}</div>
                                    `;
                                    item.addEventListener('click', () => {
                                        cooperativeCodeInput.value = coop.code;
                                        document.getElementById('regCooperativeId').value = coop.id;
                                        cooperativeDropdown.style.display = 'none';
                                    });
                                    cooperativeDropdown.appendChild(item);
                                });
                                cooperativeDropdown.style.display = 'block';
                            } else {
                                cooperativeDropdown.style.display = 'none';
                            }
                        }
                    } catch (error) {
                        console.error('Error searching cooperatives:', error);
                    }
                }, 300); // 300ms debounce
            });
            
            // Hide dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!cooperativeCodeInput.contains(e.target) && !cooperativeDropdown.contains(e.target)) {
                    cooperativeDropdown.style.display = 'none';
                }
            });
        }

        document.querySelectorAll('.btnBackReg2').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('regStep2').classList.add('active');
                document.getElementById('regStep3').classList.remove('active');
            });
        });

        safeAddListener('btnNextReg3', 'click', () => {
            // Step 3 is now Gender & ID - go to Step 4 (Password)
            const gender = document.getElementById('regGender').value;
            if (gender) {
                document.getElementById('regStep3').classList.remove('active');
                document.getElementById('regStep4').classList.add('active');
            } else {
                this.showToast('Please select your gender', 'error');
            }
        });

        document.querySelectorAll('.btnBackReg3').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('regStep3').classList.add('active');
                document.getElementById('regStep4').classList.remove('active');
            });
        });

        // Registration submit
        const registerForm = document.getElementById('registerForm');
        if (registerForm) {
            registerForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleRegister();
            });
        }

        const addCooperativeForm = document.getElementById('addCooperativeForm');
        if (addCooperativeForm) {
            // Single page form - show all sections
            const sections = document.querySelectorAll('.form-section');
            sections.forEach(section => {
                section.classList.add('active');
            });
            
            // Hide step indicators for single page form
            const stepIndicator = document.querySelector('.step-indicator');
            if (stepIndicator) {
                stepIndicator.style.display = 'none';
            }
            
            // Contact person checkbox toggle
            const addContactPersonCheckbox = document.getElementById('addContactPerson');
            const contactPersonFields = document.querySelector('.contact-person-fields');
            const noContactNote = document.querySelector('.no-contact-note');
            
            if (addContactPersonCheckbox && contactPersonFields && noContactNote) {
                addContactPersonCheckbox.addEventListener('change', function() {
                    if (this.checked) {
                        contactPersonFields.style.display = 'block';
                        noContactNote.style.display = 'none';
                        contactPersonFields.style.animation = 'fadeIn 0.3s ease-out';
                    } else {
                        contactPersonFields.style.display = 'none';
                        noContactNote.style.display = 'block';
                    }
                });
            }
            
            // Reset form when modal is closed
            const modal = document.getElementById('addCooperativeModal');
            if (modal) {
                modal.addEventListener('hidden.bs.modal', () => {
                    addCooperativeForm.reset();
                    // Remove validation classes
                    addCooperativeForm.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
                    // Reset contact person toggle
                    if (addContactPersonCheckbox && contactPersonFields && noContactNote) {
                        addContactPersonCheckbox.checked = false;
                        contactPersonFields.style.display = 'none';
                        noContactNote.style.display = 'block';
                    }
                });
                
                modal.addEventListener('shown.bs.modal', async () => {
                    await this.loadCooperativeRequiredDocs();
                });
            }
            
            addCooperativeForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleCreateCooperative();
            });
        }

        const addDeliveryForm = document.getElementById('addDeliveryForm');
        if (addDeliveryForm) {
            addDeliveryForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleRecordDelivery();
            });
        }

        const createBatchForm = document.getElementById('createBatchForm');
        if (createBatchForm) {
            createBatchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleCreateBatch();
            });
        }

        const generateDDSForm = document.getElementById('generateDDSForm');
        if (generateDDSForm) {
            generateDDSForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleGenerateDDS();
            });
        }

        const addParcelForm = document.getElementById('addParcelForm');
        if (addParcelForm) {
            addParcelForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleAddParcel();
            });
        }

        const uploadDocumentForm = document.getElementById('uploadDocumentForm');
        if (uploadDocumentForm) {
            uploadDocumentForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleUploadDocument();
            });
        }

        const addFarmForm = document.getElementById('addFarmForm');
        if (addFarmForm) {
            addFarmForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleCreateFarm();
            });
        }
    }
    
    setupOfflineDetection() {
        const updateStatus = () => {
            const offlineIndicator = document.getElementById('offlineStatus');
            if (offlineIndicator) {
                if (navigator.onLine) {
                    offlineIndicator.classList.add('d-none');
                } else {
                    offlineIndicator.classList.remove('d-none');
                }
            }
        };
        
        window.addEventListener('online', updateStatus);
        window.addEventListener('offline', updateStatus);
        updateStatus();
    }
    
    setupRegFieldChecks() {
        const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

        const setIcon = (iconId, state, title = '') => {
            const el = document.getElementById(iconId); if (!el) return;
            el.className = `reg-field-icon${iconId.includes('Phone') ? ' reg-field-icon--outside' : ''} ${state}`;
            el.title = title;
            if (state === 'valid')   el.innerHTML = '&#9749;'; // ☕
            else if (state === 'invalid') el.innerHTML = '&#10005;'; // ✕
            else if (state === 'checking') el.innerHTML = '';
            else el.innerHTML = '';
        };
        const setMsg = (msgId, text, cls) => {
            const el = document.getElementById(msgId); if (!el) return;
            el.textContent = text; el.className = `reg-field-msg ${cls}`;
        };

        // Name check (both fields together)
        const checkName = debounce(async () => {
            const fn = document.getElementById('regFirstName')?.value.trim();
            const ln = document.getElementById('regLastName')?.value.trim();
            if (!fn || !ln) { setIcon('iconLastName', ''); setMsg('msgName','',''); return; }
            setIcon('iconLastName', 'checking');
            try {
                const r = await api.checkField({ field:'name', first_name:fn, last_name:ln });
                if (r.available) { setIcon('iconLastName','valid','Name available'); setMsg('msgName','',''); }
                else { setIcon('iconLastName','invalid'); setMsg('msgName','⚠ This name is already registered','taken'); }
            } catch(e) { setIcon('iconLastName',''); }
        }, 700);

        document.getElementById('regFirstName')?.addEventListener('input', checkName);
        document.getElementById('regLastName')?.addEventListener('input', checkName);

        // Phone check
        const checkPhone = debounce(async () => {
            const raw = (document.getElementById('regPhone')?.value || '').replace(/\D/g,'');
            if (raw.length < 9) { setIcon('iconPhone',''); setMsg('msgPhone','',''); return; }
            setIcon('iconPhone','checking');
            try {
                const full = this.buildPhoneNumber('regPrefix','regPhone');
                const r = await api.checkField({ field:'phone', value: full });
                if (r.available) { setIcon('iconPhone','valid','Number available'); setMsg('msgPhone','',''); }
                else { setIcon('iconPhone','invalid'); setMsg('msgPhone','⚠ Phone number already registered','taken'); }
            } catch(e) { setIcon('iconPhone',''); }
        }, 700);
        document.getElementById('regPhone')?.addEventListener('input', checkPhone);

        // Email check
        const checkEmail = debounce(async () => {
            const val = document.getElementById('regEmail')?.value.trim();
            if (!val || !val.includes('@')) { setIcon('iconEmail',''); setMsg('msgEmail','',''); return; }
            setIcon('iconEmail','checking');
            try {
                const r = await api.checkField({ field:'email', value: val });
                if (r.available) { setIcon('iconEmail','valid','Email available'); setMsg('msgEmail','',''); }
                else { setIcon('iconEmail','invalid'); setMsg('msgEmail','⚠ Email already registered','taken'); }
            } catch(e) { setIcon('iconEmail',''); }
        }, 700);
        document.getElementById('regEmail')?.addEventListener('input', checkEmail);
    }

    initScrollAnimations() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); observer.unobserve(e.target); } });
        }, { threshold: 0.12 });
        document.querySelectorAll('.fade-up').forEach(el => observer.observe(el));

        // Count-up animation for stat numbers
        const statObserver = new IntersectionObserver((entries) => {
            entries.forEach(e => {
                if (!e.isIntersecting) return;
                statObserver.unobserve(e.target);
                const el = e.target;
                const raw = el.dataset.target;
                const suffix = el.dataset.suffix || '';
                const prefix = el.dataset.prefix || '';
                const end = parseFloat(raw);
                const duration = 1600;
                const start = performance.now();
                const step = (now) => {
                    const p = Math.min((now - start) / duration, 1);
                    const ease = 1 - Math.pow(1 - p, 3);
                    const cur = Math.round(ease * end);
                    el.textContent = prefix + (cur >= 1000 ? (cur / 1000).toFixed(cur % 1000 === 0 ? 0 : 1) + 'K' : cur) + suffix;
                    if (p < 1) requestAnimationFrame(step);
                    else el.textContent = prefix + el.dataset.final;
                };
                requestAnimationFrame(step);
            });
        }, { threshold: 0.4 });
        document.querySelectorAll('.lp-stat-num[data-target]').forEach(el => statObserver.observe(el));
    }

    toggleCountryMenu(btn) {
        // menu is the next sibling of the button inside .phone-input-wrap
        const menu = btn.nextElementSibling;
        const isOpen = menu && menu.classList.contains('open');
        document.querySelectorAll('.phone-country-menu.open').forEach(m => m.classList.remove('open'));
        if (!isOpen && menu) menu.classList.add('open');
    }

    selectCountry(context, code, prefix, country) {
        const flagImg = document.getElementById(`${context}FlagImg`);
        if (flagImg) { flagImg.src = `https://flagcdn.com/w40/${code}.png`; flagImg.alt = code.toUpperCase(); }
        const prefixEl = document.getElementById(`${context}Prefix`);
        if (prefixEl) prefixEl.textContent = prefix;
        const countryEl = document.getElementById(`${context}Country`);
        if (countryEl) countryEl.value = country;

        // Country-specific phone rules: all 3 use 10-digit local format (0XXXXXXXXX)
        const rules = {
            ke: { placeholder: '0712 345 678', maxlen: 10 },
            ug: { placeholder: '0701 234 567', maxlen: 10 },
            tz: { placeholder: '0621 234 567', maxlen: 10 },
        };
        const inputIds = { login: 'loginUsername', forgot: 'forgotEmail', reg: 'regPhone' };
        const input = document.getElementById(inputIds[context]);
        if (input) {
            const rule = rules[code] || rules.ke;
            input.placeholder = rule.placeholder;
            input.maxLength = rule.maxlen;
            // Clear value if it exceeds new maxlen
            if (input.value.replace(/\D/g,'').length > rule.maxlen) input.value = '';
        }

        document.querySelectorAll('.phone-country-menu.open').forEach(m => m.classList.remove('open'));
    }

    buildPhoneNumber(prefixId, inputId) {
        const prefix = document.getElementById(prefixId)?.textContent?.trim() || '+254';
        const raw = (document.getElementById(inputId)?.value || '').replace(/\D/g, '');
        const digits = raw.startsWith('0') ? raw.slice(1) : raw;
        return prefix + digits;
    }

    async handleLogin() {
        const digits = (document.getElementById('loginUsername')?.value || '').replace(/\D/g, '');
        const pass = document.getElementById('loginPassword').value;

        if (digits.length < 7) {
            this.showToast('Please enter a valid phone number', 'error');
            return;
        }

        const identifier = this.buildPhoneNumber('loginPrefix', 'loginUsername');

        try {
            this.showToast('Logging in...', 'info');
            await api.login(identifier, pass);
            
            // Close login modal
            const loginEl = document.getElementById('loginModal');
            const loginModal = bootstrap.Modal.getInstance(loginEl);
            if (loginModal) loginModal.hide();
            
            // Update display in step 2 if needed
            document.getElementById('displayLoginEmail').textContent = identifier;
            
            this.showApp();
            this.showToast('Login successful!', 'success');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }
    
    async handleRegister() {
        const email = document.getElementById('regEmail')?.value.trim();
        const password = document.getElementById('regPassword').value;
        const confirmPassword = document.getElementById('regConfirmPassword').value;
        const firstName = document.getElementById('regFirstName').value;
        const lastName = document.getElementById('regLastName').value;
        const role = document.getElementById('regRole').value;
        const county = document.getElementById('regCounty')?.value;
        const subcounty = document.getElementById('regSubcounty')?.value;
        
        // Country and phone — built from the flag/prefix picker
        const country = document.getElementById('regCountry')?.value || 'Kenya';
        const phoneDigits = (document.getElementById('regPhone')?.value || '').replace(/\D/g, '');
        const fullPhone = phoneDigits.length >= 7 ? this.buildPhoneNumber('regPrefix', 'regPhone') : null;
        
        // Additional fields
        const gender = document.getElementById('regGender')?.value;
        const idType = document.getElementById('regIdType')?.value;
        const idNumber = document.getElementById('regIdNumber')?.value;
        // Payment info - use defaults if fields not present (step 4 was removed)
        const payoutMethodEl = document.getElementById('regPayoutMethod');
        const payoutRecipientEl = document.getElementById('regPayoutRecipient');
        const payoutBankNameEl = document.getElementById('regBankName');
        const payoutAccountNumberEl = document.getElementById('regAccountNumber');
        const payoutMethod = payoutMethodEl ? payoutMethodEl.value : 'mpesa';
        const payoutRecipientId = payoutRecipientEl ? payoutRecipientEl.value : undefined;
        const payoutBankName = payoutBankNameEl ? payoutBankNameEl.value : undefined;
        const payoutAccountNumber = payoutAccountNumberEl ? payoutAccountNumberEl.value : undefined;
        
        // Password validation
        if (!password || password.length < 8) {
            this.showToast('Password must be at least 8 characters', 'error');
            return;
        }
        
        if (password !== confirmPassword) {
            this.showToast('Passwords do not match', 'error');
            return;
        }
        
        if (!firstName || !lastName || !role) {
            this.showToast('Please fill in all required fields', 'error');
            return;
        }
        
        // Phone is required as primary identifier
        if (!fullPhone) {
            this.showToast('Phone number is required', 'error');
            return;
        }
        
        try {
            // Get cooperative code field
            const cooperativeCode = document.getElementById('regCooperativeCode')?.value || '';
            
            const identifier = email || fullPhone;
            console.log('Attempting registration for:', identifier, 'with role:', role);
            await api.register({
                email: email || undefined,
                password: password,
                first_name: firstName,
                last_name: lastName,
                role: role,
                country: country,
                county: county || undefined,
                subcounty: subcounty || undefined,
                // New fields
                gender: gender || undefined,
                id_type: idType || undefined,
                id_number: idNumber || undefined,
                phone_number: fullPhone || undefined,
                payout_method: payoutMethod || 'mpesa',
                payout_recipient_id: payoutRecipientId || undefined,
                payout_bank_name: payoutBankName || undefined,
                payout_account_number: payoutAccountNumber || undefined,
                // Cooperative membership (required)
                cooperative_code: cooperativeCode
            });
            
            console.log('Registration request sent successfully');

            // Close register modal and clear form
            const registerEl = document.getElementById('registerModal');
            const registerModal = bootstrap.Modal.getInstance(registerEl);
            if (registerModal) registerModal.hide();
            document.getElementById('registerForm').reset();

            // Flash toast then open login modal
            this.showToast('Account created! Please log in to continue.', 'success');
            setTimeout(() => this.showLoginModal(), 1200);
        } catch (error) {
            console.error('Registration/Login Error:', error);
            this.showToast(error.message || 'Registration failed', 'error');
        }
    }
    
    logout() {
        this._stopSessionWatcher();
        api.logout();
        location.reload();
    }

    _getTokenExpiry() {
        const token = localStorage.getItem('plotra_token');
        if (!token) return null;
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            return payload.exp ? payload.exp * 1000 : null;
        } catch { return null; }
    }

    _startSessionWatcher() {
        this._stopSessionWatcher();
        this._lastActivity = Date.now();

        // Track user activity to reset inactivity timer
        const resetActivity = () => { this._lastActivity = Date.now(); };
        ['click', 'keydown', 'mousemove', 'touchstart'].forEach(ev =>
            document.addEventListener(ev, resetActivity, { passive: true })
        );
        this._activityListeners = resetActivity;

        // Check every 30 seconds
        this._sessionCheckInterval = setInterval(() => this._checkSession(), 30000);
        this._scheduleTokenExpiry();
    }

    _stopSessionWatcher() {
        clearInterval(this._sessionCheckInterval);
        clearTimeout(this._sessionTimer);
        this._sessionWarningShown = false;
    }

    _scheduleTokenExpiry() {
        const expiry = this._getTokenExpiry();
        if (!expiry) return;
        const msLeft = expiry - Date.now();
        if (msLeft <= 0) { this._doAutoLogout('session_expired'); return; }

        // Warn 2 minutes before expiry
        const warnAt = msLeft - 120000;
        if (warnAt > 0) {
            setTimeout(() => this._showSessionWarning(Math.round((expiry - Date.now()) / 1000)), warnAt);
        }
        // Hard logout at expiry
        this._sessionTimer = setTimeout(() => this._doAutoLogout('session_expired'), msLeft);
    }

    _checkSession() {
        const expiry = this._getTokenExpiry();
        if (!expiry) { this._doAutoLogout('session_expired'); return; }
        if (Date.now() >= expiry) { this._doAutoLogout('session_expired'); return; }

        // Inactivity: read timeout from config (default 60 min)
        const inactivityMs = (this._sessionTimeoutMinutes || 60) * 60 * 1000;
        if (Date.now() - this._lastActivity > inactivityMs) {
            this._doAutoLogout('inactivity');
        }
    }

    _showSessionWarning(secondsLeft) {
        if (this._sessionWarningShown) return;
        this._sessionWarningShown = true;
        const mins = Math.ceil(secondsLeft / 60);
        this.showToast(`Your session expires in ~${mins} minute${mins !== 1 ? 's' : ''}. Save your work.`, 'warning', 8000);
    }

    _doAutoLogout(reason) {
        this._stopSessionWatcher();
        const msg = reason === 'inactivity'
            ? 'You were logged out due to inactivity.'
            : 'Your session has expired. Please log in again.';
        // Store message to show after reload
        sessionStorage.setItem('logout_reason', msg);
        api.logout();
        location.reload();
    }
    
    // Check if user can access a page based on their role
    canAccessPage(page) {
        const role = (this.currentUser?.role || '').toUpperCase();
        console.log('canAccessPage checking page:', page, 'with role:', role);
        
        // Allow all adminPages for admins, coop officers, and EUDR reviewers - check using original role value
        if (this.adminPages.includes(page)) {
            const roleLower = role.toLowerCase();
            // Check for specific known admin-type roles (original values from backend)
            const adminRoles = ['plotra_admin', 'platform_admin', 'super_admin', 'admin', 'cooperative_officer', 'coop_admin', 'eudr_reviewer', 'belgian_team'];
            const hasAdminRole = adminRoles.some(r => roleLower === r.toLowerCase() || roleLower.includes(r.toLowerCase()));
            if (hasAdminRole) {
                console.log('canAccessPage: allowing admin page for role:', role);
                return true;
            }
            // Also try substring matching as fallback
            if (roleLower.includes('admin') || roleLower.includes('officer') || roleLower.includes('reviewer') || roleLower.includes('coop')) {
                console.log('canAccessPage: allowing admin page via substring for role:', role);
                return true;
            }
            console.log('canAccessPage: denying admin page, role:', role);
            return false;
        }
        
        // Farmer-only pages
        const farmerPages = ['farms', 'parcels', 'documents'];
        if (farmerPages.includes(page) && role === 'FARMER') {
            return true;
        }
        
        // All authenticated users can access dashboard
        if (page === 'dashboard') return true;
        
        // Verification page for admins and officers
        if (page === 'verification') {
            if (role === 'PLOTRA_ADMIN' || role === 'PLATFORM_ADMIN' || role === 'SUPER_ADMIN' || 
                role === 'ADMIN' || role === 'COOPERATIVE_OFFICER' || 
                role === 'COOP_ADMIN' || role === 'EUDR_REVIEWER' || role === 'BELGIAN_TEAM') {
                return true;
            }
            return false;
        }
        
        // Deliveries and batches for farmers and officers
        if (page === 'deliveries' || page === 'batches') {
            if (role === 'FARMER' || role === 'COOPERATIVE_OFFICER' || role === 'COOP_ADMIN' ||
                role === 'PLOTRA_ADMIN' || role === 'PLATFORM_ADMIN' || role === 'SUPER_ADMIN') {
                return true;
            }
            return false;
        }
        
        // Satellite analysis for admins and eudr reviewers
        if (page === 'satellite') {
            if (role === 'PLOTRA_ADMIN' || role === 'PLATFORM_ADMIN' || role === 'SUPER_ADMIN' || 
                role === 'ADMIN' || role === 'EUDR_REVIEWER') {
                return true;
            }
            return false;
        }
        
        // Compliance page - for all users (farmers see simplified view, admins see full DDS)
        if (page === 'compliance') {
            return true; // All users can access compliance page
        }
        
        // Cooperative-only pages
        if (page === 'farm-approvals' || page === 'coop-team' || page === 'coop-farms' || page === 'coop-farmers') {
            return role === 'COOPERATIVE_OFFICER';
        }

        return true; // Default allow
    }

    getEffectiveNavItems(navItems) {
        const perms = this.currentUser?.page_permissions;
        if (!perms || perms.length === 0) return navItems;
        // Always show dashboard and profile
        return navItems.filter(item => item.id === 'dashboard' || item.id === 'profile' || perms.includes(item.id));
    }

    toggleSidebar() {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        const body = document.body;

        if (sidebar) {
            // Desktop: collapse/expand
            if (window.innerWidth >= 1200) {
                body.classList.toggle('sidebar-collapsed');
                sidebar.classList.toggle('collapsed');
                localStorage.setItem('sidebarCollapsed', body.classList.contains('sidebar-collapsed'));
            }
            // Mobile: slide in/out
            else {
                sidebar.classList.toggle('show');
                if (overlay) overlay.classList.toggle('show');
            }
            // Update hamburger icon
            const btn = document.getElementById('navbarSidebarToggle');
            if (btn) {
                const icon = btn.querySelector('i');
                if (icon) {
                    const isOpen = window.innerWidth >= 1200
                        ? !body.classList.contains('sidebar-collapsed')
                        : sidebar.classList.contains('show');
                    icon.className = isOpen ? 'bi bi-x' : 'bi bi-list';
                    icon.style.fontSize = '1.25rem';
                }
            }
        }
    }
    
    navigateTo(page) {
        // Check if user has permission to access this page
        if (!this.canAccessPage(page)) {
            this.showToast('You do not have permission to access this page', 'error');
            return;
        }
        
        // Update active nav
        document.querySelectorAll('.sidebar .nav-link').forEach(link => {
            link.classList.toggle('active', link.dataset.page === page);
        });
        
        // Close sidebar on mobile
        const sidebar = document.getElementById('sidebar');
        if (sidebar) {
            sidebar.classList.remove('show');
            const overlay = document.querySelector('.sidebar-overlay');
            if (overlay) overlay.classList.remove('show');
            const btn = document.getElementById('navbarSidebarToggle');
            if (btn) {
                const icon = btn.querySelector('i');
                if (icon) { icon.className = 'bi bi-list'; icon.style.fontSize = '1.25rem'; }
            }
        }
        
        this.loadPage(page);
    }
    
    async loadPage(page) {
        this.currentPage = page;
        const content = document.getElementById('pageContent');
        const title = document.getElementById('pageTitle');
        
        if (!content) {
            console.error('Page content container (#pageContent) not found!');
            return;
        }

        // Show loading
        content.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        
        try {
            switch(page) {
                case 'dashboard':
                    if (title) title.textContent = 'Dashboard';
                    await this.loadDashboard(content);
                    break;
                case 'cooperatives':
                    if (title) title.textContent = 'Cooperatives';
                    await this.loadCooperatives(content);
                    break;
                case 'farmers':
                    if (title) title.textContent = 'Farmers Management';
                    await this.loadFarmers(content);
                    break;
                case 'farmer-approvals':
                    if (title) title.textContent = 'Farmer Approvals';
                    await this.loadFarmerApprovals(content);
                    break;
                case 'coop-farmers':
                    if (title) title.textContent = 'Farmers';
                    await this.loadCoopFarmersList(content);
                    break;
                case 'coop-farms':
                    if (title) title.textContent = 'Farms';
                    await this.loadCoopFarms(content);
                    break;
                case 'farm-approvals':
                    if (title) title.textContent = 'Farm Approvals';
                    if ((this.currentUser?.role || '').toLowerCase() === 'cooperative_officer') {
                        await this.loadCoopFarmApprovals(content);
                    } else {
                        await this.loadFarms(content);
                    }
                    break;
                case 'coop-team':
                    if (title) title.textContent = 'Cooperative Team';
                    await this.loadCoopTeam(content);
                    break;
                case 'farms': {
                    const farmsRole = (this.currentUser?.role || '').toUpperCase();
                    const isFarmerRole = ['FARMER'].includes(farmsRole);
                    if (title) title.textContent = isFarmerRole ? 'My Farms' : 'Farms';
                    if (isFarmerRole) {
                        await this.loadFarmsPage();
                    } else {
                        await this.loadFarms(content);
                    }
                    break;
                }
                case 'wallet':
                    if (title) title.textContent = 'Wallet & Payments';
                    await this.loadWallet(content);
                    break;
                case 'parcels':
                    if (title) title.textContent = 'Farm Parcels';
                    await this.loadParcels(content);
                    break;
                case 'deliveries':
                    if (title) title.textContent = 'Deliveries';
                    await this.loadDeliveries(content);
                    break;
                case 'batches':
                    if (title) title.textContent = 'Batches';
                    await this.loadBatches(content);
                    break;
                case 'verification':
                    if (title) title.textContent = 'Verification';
                    await this.loadVerification(content);
                    break;
                case 'satellite':
                    if (title) title.textContent = 'Satellite Analysis';
                    await this.loadSatellite(content);
                    break;
                case 'compliance':
                    if (title) title.textContent = 'EUDR Compliance';
                    await this.loadCompliance(content);
                    break;
                case 'users':
                    if (title) title.textContent = 'User Management';
                    await this.loadUsers(content);
                    break;
                case 'sustainability':
                    if (title) title.textContent = 'Sustainability & Incentives';
                    await this.loadSustainability(content);
                    break;
                case 'documents':
                    if (title) title.textContent = 'KYC Documents';
                    await this.loadDocuments(content);
                    break;
                case 'system':
                    if (title) title.textContent = 'System Configure';
                    await this.loadSystemConfig(content);
                    break;
                case 'profile':
                    if (title) title.textContent = 'My Profile';
                    await this.loadProfile(content);
                    break;
                default:
                    console.log('loadPage: unknown page requested:', page);
                    content.innerHTML = `<div class="alert alert-info">Page not found: '${page}'</div>`;
            }
        } catch (error) {
            console.error('Failed to load page:', error);
            if (content) {
                content.innerHTML = `<div class="alert alert-danger">Error: ${error.message}</div>`;
            }
            this.showToast('Failed to load page', 'error');
        }
    }
    
    async loadDashboard(content) {
        const role = (this.currentUser?.role || 'FARMER').toUpperCase();
        console.log('Loading dashboard for role:', role);
        
        if (role === 'EUDR_REVIEWER') {
            await this.renderEUDRReviewerDashboard(content);
        } else if (role === 'COOP_ADMIN' || role === 'COOPERATIVE_ADMIN') {
            await this.renderCoopAdminDashboard(content);
        } else if (role === 'COOP_OFFICER' || role === 'FACTOR' || role === 'COOPERATIVE_OFFICER') {
            await this.renderCoopOfficerDashboard(content);
        } else if (role === 'PLATFORM_ADMIN' || role === 'SUPER_ADMIN' || role === 'ADMIN' || role === 'PLOTRA_ADMIN') {
            await this.renderAdminDashboard(content);
        } else {
            await this.renderFarmerDashboard(content);
        }
    }

    async renderAdminDashboard(content) {
        if (!content) {
            console.error('Content element not provided to renderAdminDashboard');
            return;
        }
        console.log('Rendering Admin Dashboard...');
        try {
            console.log('Fetching dashboard stats...');
            const stats = await api.getDashboardStats() || {};
            console.log('Stats received:', stats);
            
            console.log('Fetching compliance overview...');
            const overview = await api.getComplianceOverview() || {};
            console.log('Overview received:', overview);
            
            console.log('Fetching compliance chart data...');
            let chartData = {};
            try {
                chartData = await api.getComplianceOverviewChart() || {};
                console.log('Chart data received:', chartData);
            } catch (chartError) {
                console.warn('Chart data fetch failed, using defaults:', chartError.message);
            }
            
            content.innerHTML = `
                <div class="row g-0 mt-0 admin-dashboard">
                    <div class="col-6 col-xl-3">
                        <div class="card card-slide" data-aos="fade-up" data-aos-delay="700" onclick="app.navigateTo('cooperatives')" style="cursor: pointer;">
                            <div class="card-body p-1 m-0">
                                <div class="progress-widget">
                                    <div id="circle-progress-01" class="text-center circle-progress-01 circle-progress circle-progress-primary" data-min-value="0" data-max-value="100" data-value="80" data-type="percent">
                                        <svg class="card-slie-arrow icon-16" width="16" viewBox="0 0 24 24">
                                            <path fill="currentColor" d="M5,17.59L15.59,7H9V5H19V15H17V8.41L6.41,19L5,17.59Z" />
                                        </svg>
                                    </div>
                                    <div class="progress-detail">
                                        <p class="mb-0 text-muted small">Cooperatives</p>
                                        <h4 class="counter">${stats.total_cooperatives || 0}</h4>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-6 col-xl-3">
                        <div class="card card-slide" data-aos="fade-up" data-aos-delay="800" onclick="app.navigateTo('farms')" style="cursor: pointer;">
                            <div class="card-body p-1 m-0">
                                <div class="progress-widget">
                                    <div id="circle-progress-02" class="text-center circle-progress-01 circle-progress circle-progress-info" data-min-value="0" data-max-value="100" data-value="70" data-type="percent">
                                        <svg class="card-slie-arrow icon-16" width="16" viewBox="0 0 24 24">
                                            <path fill="currentColor" d="M19,6.41L17.59,5L7,15.59V9H5V19H15V17H8.41L19,6.41Z" />
                                        </svg>
                                    </div>
                                    <div class="progress-detail">
                                        <p class="mb-0 text-muted small">Verified Farms</p>
                                        <h4 class="counter">${stats.verified_farms ?? stats.total_farms ?? 0}</h4>
                                        <div class="d-flex gap-1 flex-wrap mt-1">
                                            <span class="badge bg-success" style="font-size:10px;">${stats.verified_farms ?? 0} ✓</span>
                                            <span class="badge bg-warning text-dark" style="font-size:10px;">${stats.pending_farms ?? 0} ⏳</span>
                                            <span class="badge bg-secondary" style="font-size:10px;">${stats.draft_farms ?? 0} ✎</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-6 col-xl-3">
                        <div class="card card-slide" data-aos="fade-up" data-aos-delay="900" onclick="app.navigateTo('farmers')" style="cursor: pointer;">
                            <div class="card-body p-1 m-0">
                                <div class="progress-widget">
                                    <div id="circle-progress-03" class="text-center circle-progress-01 circle-progress circle-progress-primary" data-min-value="0" data-max-value="100" data-value="60" data-type="percent">
                                        <svg class="card-slie-arrow icon-16" width="16" viewBox="0 0 24 24">
                                            <path fill="currentColor" d="M5,17.59L15.59,7H9V5H19V15H17V8.41L6.41,19L5,17.59Z" />
                                        </svg>
                                    </div>
                                    <div class="progress-detail">
                                        <p class="mb-0 text-muted small">Farmers</p>
                                        <h4 class="counter">${stats.total_farmers || 0}</h4>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-6 col-xl-3">
                        <div class="card card-slide" data-aos="fade-up" data-aos-delay="1000" onclick="app.navigateTo('compliance')" style="cursor: pointer;">
                            <div class="card-body p-1 m-0">
                                <div class="progress-widget">
                                    <div id="circle-progress-04" class="text-center circle-progress-01 circle-progress circle-progress-info" data-min-value="0" data-max-value="100" data-value="40" data-type="percent">
                                        <svg class="card-slie-arrow icon-16" width="16" viewBox="0 0 24 24">
                                            <path fill="currentColor" d="M19,6.41L17.59,5L7,15.59V9H5V19H15V17H8.41L19,6.41Z" />
                                        </svg>
                                    </div>
                                    <div class="progress-detail">
                                        <p class="mb-0 text-muted small">Compliance</p>
                                        <h4 class="counter">${stats.compliance_rate || 0}%</h4>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row g-0 mt-0">
                    <div class="col-lg-8">
                        <div class="card h-100" data-aos="fade-up" data-aos-delay="1100">
                            <div class="card-header d-flex justify-content-between flex-wrap">
                                <div class="header-title">
                                    <h4 class="card-title">EUDR Compliance Overview</h4>
                                    <p class="mb-0">Satellite verified farm analysis</p>
                                </div>
                                <div class="d-flex align-items-center align-self-center">
                                    <div class="d-flex align-items-center text-primary">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="12" viewBox="0 0 24 24" fill="currentColor">
                                            <g><circle cx="12" cy="12" r="8" fill="currentColor"></circle></g>
                                        </svg>
                                        <div class="ms-2">
                                            <span class="text-secondary small">Compliant</span>
                                        </div>
                                    </div>
                                    <div class="d-flex align-items-center ms-3 text-info">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="12" viewBox="0 0 24 24" fill="currentColor">
                                            <g><circle cx="12" cy="12" r="8" fill="currentColor"></circle></g>
                                        </svg>
                                        <div class="ms-2">
                                            <span class="text-secondary small">Pending</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="card-body">
                                <div id="compliance-chart" style="min-height: 245px;"></div>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-4">
                        <div class="card h-100" data-aos="fade-up" data-aos-delay="1200">
                            <div class="card-header d-flex justify-content-between">
                                <div class="header-title">
                                    <h4 class="card-title">Recent Verifications</h4>
                                </div>
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover mb-0">
                                        <thead>
                                            <tr>
                                                <th class="small">FARM</th>
                                                <th class="small">STATUS</th>
                                                <th class="text-end small">DATE</th>
                                            </tr>
                                        </thead>
                                        <tbody id="recent-verifications-list">
                                            <tr><td colspan="3" class="text-center py-4">Loading...</td></tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row g-4 mt-1">
                    <div class="col-lg-8">
                        <div class="card" data-aos="fade-up" data-aos-delay="1300">
                            <div class="card-header d-flex justify-content-between">
                                <div class="header-title">
                                    <h4 class="card-title">Cooperative Performance</h4>
                                </div>
                                <button class="btn btn-sm btn-primary" onclick="app.loadPage('cooperatives')">View All</button>
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    <table class="table table-hover mb-0">
                                        <thead>
                                            <tr>
                                                <th class="small">COOPERATIVE</th>
                                                <th class="small">COOPERATIVE NAME</th>
                                                <th class="small">USERS</th>
                                                <th class="small">VIEW</th>
                                            </tr>
                                        </thead>
                                        <tbody id="coop-performance-list">
                                            <tr><td colspan="4" class="text-center py-4 text-muted">No data available</td></tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-4">
                        <div class="card" data-aos="fade-up" data-aos-delay="1400">
                            <div class="card-header d-flex justify-content-between">
                                <div class="header-title">
                                    <h4 class="card-title">System Management</h4>
                                </div>
                            </div>
                            <div class="card-body">
                                <div class="d-grid gap-3">
                                    <button class="btn btn-soft-primary w-100" onclick="app.showCreateCooperativeModal()">
                                        <i class="bi bi-building-plus me-2"></i> Create Cooperative
                                    </button>
                                    <button class="btn btn-soft-primary w-100" onclick="app.navigateTo('verification')">
                                        <i class="bi bi-shield-check me-2"></i> Pending Verifications
                                    </button>
                                    <button class="btn btn-soft-info w-100" onclick="app.triggerGlobalSatelliteAnalysis()">
                                        <i class="bi bi-satellite me-2"></i> Global Satellite Sync
                                    </button>
                                    <button class="btn btn-soft-warning w-100" onclick="app.loadPage('sustainability')">
                                        <i class="bi bi-leaf me-2"></i> Sustainability Audit
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Re-initialize UI components synchronously
            console.log('Initializing charts and sub-lists...');
            try {
                this.initAdminDashboardCharts(overview, chartData);
            } catch (chartError) {
                console.error('Error initializing charts:', chartError);
            }

            try {
                this.loadRecentVerifications();
            } catch (verifError) {
                console.error('Error loading verifications:', verifError);
            }

            try {
                this.loadCoopPerformance();
            } catch (coopError) {
                console.error('Error loading coop performance:', coopError);
            }

            if (window.CircleProgress) {
                document.querySelectorAll('.circle-progress').forEach(el => {
                    try { new CircleProgress(el); } catch(circleError) {
                        console.error('Error initializing circle progress:', circleError);
                    }
                });
            }
            
        } catch (error) {
            console.error('Failed to load admin dashboard:', error);
            console.error('Error details:', {
                message: error?.message,
                stack: error?.stack,
                name: error?.name,
                error: error
            });
            this.renderOfflineAlert(content);
        }
    }

    renderOfflineAlert(content) {
        if (!content) {
            console.error('Content element not provided to renderOfflineAlert');
            return;
        }
        content.innerHTML = `
            <div class="alert alert-warning p-5 text-center">
                <i class="bi bi-cloud-slash fs-1 d-block mb-3"></i>
                <h5>Backend Offline or Session Expired</h5>
                <p>We are having trouble connecting to the Plotra API server. Please check your connection or sign in again.</p>
                <div class="d-flex justify-content-center gap-2 mt-4">
                    <button class="btn btn-primary" onclick="window.location.reload()">Retry Connection</button>
                    <button class="btn btn-outline-secondary" onclick="app.logout()">Sign Out</button>
                </div>
            </div>
        `;
    }

    initAdminDashboardCharts(overview, chartData) {
        const chartContainer = document.querySelector("#compliance-chart");
        if (!chartContainer) {
            console.log('Chart container not found');
            return;
        }
        console.log('Chart container found, checking ApexCharts...');
        console.log('ApexCharts defined:', typeof ApexCharts);
        
        // Use real data from API if available, fallback to mock data
        const compliantCount = chartData?.values?.[0] || overview?.compliance_breakdown?.compliant || 0;
        const pendingCount = chartData?.values?.[1] || overview?.compliance_breakdown?.under_review || 0;
        
        const options = {
            series: [{
                name: 'Compliant',
                data: [compliantCount]  // Single value for bar/pie chart
            }, {
                name: 'Pending',
                data: [pendingCount]  // Single value for bar/pie chart
            }],
            chart: {
                height: 245,
                type: 'bar',
                toolbar: { show: false },
                sparkline: { enabled: false }
            },
            plotOptions: {
                bar: {
                    horizontal: false,
                    columnWidth: '55%',
                    borderRadius: 4,
                    dataLabels: {
                        position: 'top'
                    }
                }
            },
            dataLabels: { enabled: true },
            stroke: { show: true, curve: 'smooth', width: 2 },
            colors: ["#198754", "#0dcaf0"],
            fill: {
                type: 'gradient',
                gradient: {
                    shadeIntensity: 1,
                    opacityFrom: 0.3,
                    opacityTo: 0.1,
                    stops: [0, 90, 100]
                }
            },
            xaxis: {
                categories: ["Compliant", "Pending"],
                axisBorder: { show: false },
                axisTicks: { show: false },
                labels: {
                    minHeight: 20,
                    maxHeight: 20,
                    style: { colors: "#8A92A6" }
                }
            },
            yaxis: {
                labels: {
                    minWidth: 20,
                    maxWidth: 20,
                    style: { colors: "#8A92A6" }
                }
            },
            legend: { show: true, position: 'top' },
            grid: { show: true, strokeDashArray: 3 }
        };

        console.log('ApexCharts library status:', typeof ApexCharts);
        if (typeof ApexCharts === 'undefined') {
            console.error('ApexCharts library not loaded');
            return;
        }

        try {
            const chart = new ApexCharts(document.querySelector("#compliance-chart"), options);
            chart.render();
            this.charts['compliance'] = chart;
            console.log('Chart rendered successfully');
            
            // Debug: Check chart dimensions
            setTimeout(() => {
                const chartEl = document.querySelector("#compliance-chart");
                const svg = chartEl?.querySelector('svg');
                console.log('Chart container dimensions:', chartEl?.getBoundingClientRect());
                console.log('Chart SVG dimensions:', svg?.getBoundingClientRect());
                console.log('Chart innerHTML:', chartEl?.innerHTML?.substring(0, 200));
            }, 500);
        } catch (e) {
            console.error('Error rendering chart:', e);
        }
    }

    async loadRecentVerifications() {
        const list = document.getElementById('recent-verifications-list');
        if (!list) return;
        
        try {
            const raw = await api.getPendingVerifications({ limit: 5 });
            const verifications = Array.isArray(raw) ? raw : (raw?.verifications || []);
            if (verifications.length > 0) {
                list.innerHTML = verifications.map(v => `
                    <tr>
                        <td class="small">
                            <div class="fw-bold">${v.farmer_name || (v.first_name ? v.first_name + ' ' + v.last_name : 'N/A')}</div>
                            <div class="text-muted x-small-text">${v.cooperative_name || v.cooperative_code || 'Individual'}</div>
                        </td>
                        <td>
                            <span class="badge bg-warning-subtle text-warning" style="font-size: 0.6rem;">Pending</span>
                        </td>
                        <td class="text-end small text-muted">
                            ${v.created_at ? new Date(v.created_at).toLocaleDateString() : 'N/A'}
                        </td>
                    </tr>
                `).join('');
            } else {
                list.innerHTML = '<tr><td colspan="3" class="text-center py-4 text-muted small">No recent verifications</td></tr>';
            }
        } catch (error) {
            console.error('Failed to load recent verifications:', error);
            list.innerHTML = '<tr><td colspan="3" class="text-center py-4 text-danger small">Error loading data</td></tr>';
        }
    }

    async loadCoopPerformance() {
        const list = document.getElementById('coop-performance-list');
        if (!list) return;
        
        try {
            const coops = await api.getCooperatives();
            if (coops && coops.length > 0) {
                list.innerHTML = coops.map(coop => {
                    return `
                        <tr>
                            <td><span class="badge bg-secondary">${coop.code || 'N/A'}</span></td>
                            <td>${coop.name}</td>
                            <td><span class="badge bg-primary">${coop.member_count || 0}</span></td>
                            <td>
                                <button class="btn btn-sm btn-info" onclick="app.showCooperativeDetails('${coop.id}')">
                                    <i class="bi bi-eye me-1"></i> View
                                </button>
                            </td>
                        </tr>
                    `;
                }).join('');
            } else {
                list.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-muted">No cooperatives found</td></tr>';
            }
        } catch (error) {
            console.error('Failed to load coop performance:', error);
            list.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-danger">Error loading data</td></tr>';
        }
    }

    async triggerGlobalSatelliteAnalysis() {
        if (!confirm('This will trigger satellite analysis for all registered parcels. Proceed?')) return;
        try {
            this.showToast('Triggering global analysis...', 'info');
            await api.triggerSatelliteAnalysis([]); 
            this.showToast('Global analysis started successfully', 'success');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async triggerGlobalSatelliteAnalysis() {
        try {
            const deliveries = await api.getDeliveries();
            content.innerHTML = `
                <div class="row g-4 mb-4">
                    <div class="col-md-4">
                        <div class="card border-0 shadow-sm rounded-3">
                            <div class="card-body p-4">
                                <div class="d-flex align-items-center justify-content-between mb-3">
                                    <div>
                                        <p class="text-muted mb-1 small">Daily Deliveries</p>
                                        <h4 class="mb-0">${deliveries.length}</h4>
                                    </div>
                                    <div class="bg-primary text-white rounded-circle p-2"><i class="bi bi-truck"></i></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } catch (error) {
            this.renderOfflineAlert(content);
        }
    }

    async renderFarmerDashboard(content) {
        try {
            const [farmsResponse, deliveries, stats] = await Promise.all([
                api.getFarms(),
                api.getDeliveries(),
                api.getFarmerStats()
            ]);

            const farms = farmsResponse.farms || farmsResponse || [];
            const farmList = Array.isArray(farms) ? farms : (farms ? [farms] : []);
            const deliveryList = Array.isArray(deliveries) ? deliveries : [];
            const totalWeight = deliveryList.reduce((sum, d) => sum + (d.net_weight_kg || 0), 0);
            const verifiedFarms = farmList.filter(f => f.verification_status === 'verified').length;
            const pendingFarms  = farmList.filter(f => f.verification_status === 'pending').length;
            const draftFarms    = farmList.filter(f => !f.verification_status || f.verification_status === 'draft').length;

            const coopApprovedFarms = farmList.filter(f => f.coop_status === 'coop_approved' && f.verification_status !== 'verified').length;

            // Farmer's own account verification status badge
            const u = this.currentUser || {};
            const uCoopStatus = u.coop_status || '';
            const uAdminStatus = u.verification_status || 'pending';
            const coopApproved = uCoopStatus === 'coop_approved' || uAdminStatus === 'verified';
            const adminApproved = uAdminStatus === 'verified';
            const coopRejected = uCoopStatus === 'coop_rejected';
            const adminRejected = uAdminStatus === 'rejected' && !coopRejected;

            let farmerBadge, farmerDotColor, farmerBy;
            if (adminApproved && coopApproved) {
                farmerBadge = `<i class="bi bi-check-circle-fill me-1"></i>Fully Approved`;
                farmerDotColor = '#198754';
                farmerBy = `Cooperative${u.coop_verified_by_name ? ' (' + u.coop_verified_by_name + ')' : ''} &amp; Plotra${u.admin_verified_by_name ? ' (' + u.admin_verified_by_name + ')' : ''}`;
            } else if (coopRejected) {
                farmerBadge = `<i class="bi bi-x-circle-fill me-1"></i>Rejected by Cooperative`;
                farmerDotColor = '#dc3545';
                farmerBy = u.coop_notes ? `Reason: ${u.coop_notes}` : (u.coop_verified_by_name || '');
            } else if (adminRejected) {
                farmerBadge = `<i class="bi bi-x-circle-fill me-1"></i>Rejected by Plotra`;
                farmerDotColor = '#dc3545';
                farmerBy = u.admin_notes ? `Reason: ${u.admin_notes}` : (u.admin_verified_by_name || '');
            } else if (coopApproved && !adminApproved) {
                farmerBadge = `<i class="bi bi-check-circle-fill me-1"></i>Cooperative Approved`;
                farmerDotColor = '#0dcaf0';
                farmerBy = `by ${u.coop_verified_by_name || 'Cooperative'} — Pending Plotra Review &amp; Approval`;
            } else {
                farmerBadge = `<i class="bi bi-hourglass-split me-1"></i>Pending Verification`;
                farmerDotColor = '#ffc107';
                farmerBy = 'Awaiting Cooperative approval';
            }

            const farmerStatusBadge = `
            <div class="mb-3" style="background:#fff;border-radius:10px;padding:10px 14px;box-shadow:0 1px 4px rgba(0,0,0,.07);border-left:4px solid ${farmerDotColor};display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px">
                <div>
                    <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#6f4e37;margin-bottom:4px">Your Verification Status</div>
                    <span style="background:${farmerDotColor};color:${farmerDotColor==='#ffc107'||farmerDotColor==='#0dcaf0'?'#000':'#fff'};border-radius:20px;padding:4px 12px;font-size:0.78rem;font-weight:600">${farmerBadge}</span>
                </div>
                <div style="font-size:0.75rem;color:#6c757d;text-align:right">${farmerBy}</div>
            </div>`;

            content.innerHTML = `
                ${farmerStatusBadge}
                <div class="row g-4 mb-4">
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body">
                                <div class="d-flex align-items-center mb-2">
                                    <div class="avatar-sm bg-soft-primary text-primary rounded-circle me-3">
                                        <i class="bi bi-tree fs-4"></i>
                                    </div>
                                    <h6 class="card-title mb-0">My Farms</h6>
                                </div>
                                <h2 class="mb-2">${farmList.length}</h2>
                                <div class="d-flex gap-1 mt-1" style="flex-wrap:nowrap">
                                    <span class="badge bg-success d-flex align-items-center gap-1" style="font-size:.72rem;flex:1;justify-content:center"><i class="bi bi-check-circle"></i>${verifiedFarms}</span>
                                    <span class="badge bg-info text-dark d-flex align-items-center gap-1" style="font-size:.72rem;flex:1;justify-content:center"><i class="bi bi-hourglass-split"></i>${coopApprovedFarms}</span>
                                    <span class="badge bg-warning text-dark d-flex align-items-center gap-1" style="font-size:.72rem;flex:1;justify-content:center"><i class="bi bi-clock"></i>${pendingFarms}</span>
                                    <span class="badge bg-secondary d-flex align-items-center gap-1" style="font-size:.72rem;flex:1;justify-content:center"><i class="bi bi-pencil"></i>${draftFarms}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body">
                                <div class="d-flex align-items-center mb-3">
                                    <div class="avatar-sm bg-soft-success text-success rounded-circle me-3">
                                        <i class="bi bi-box-seam fs-4"></i>
                                    </div>
                                    <h6 class="card-title mb-0">Deliveries</h6>
                                </div>
                                <h2 class="mb-0">${deliveryList.length}</h2>
                                <p class="text-muted small mt-2 mb-0">${totalWeight.toFixed(1)} kg total weight</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body">
                                <div class="d-flex align-items-center mb-3">
                                    <div class="avatar-sm bg-soft-info text-info rounded-circle me-3">
                                        <i class="bi bi-wallet2 fs-4"></i>
                                    </div>
                                    <h6 class="card-title mb-0">Wallet Balance</h6>
                                </div>
                                <h2 class="mb-0">$${stats.mbt_balance || '0.00'}</h2>
                                <p class="text-success small mt-2 mb-0"><i class="bi bi-arrow-up me-1"></i> ${stats.returns_trend || '+0%'}</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body">
                                <div class="d-flex align-items-center mb-3">
                                    <div class="avatar-sm bg-soft-warning text-warning rounded-circle me-3">
                                        <i class="bi bi-shield-check fs-4"></i>
                                    </div>
                                    <h6 class="card-title mb-0">Compliance</h6>
                                </div>
                                <h2 class="mb-0">${stats.compliance_score ?? 'N/A'}%</h2>
                                <p class="text-muted small mt-2 mb-0">EUDR Readiness Score</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row g-4 mb-4">
                    <div class="col-lg-8">
                        <div class="card h-100">
                            <div class="card-header d-flex justify-content-between align-items-center bg-transparent">
                                <h4 class="card-title mb-0">Production History</h4>
                                <select class="form-select form-select-sm" style="width: auto;">
                                    <option>Last 6 Months</option>
                                    <option>Last Year</option>
                                </select>
                            </div>
                            <div class="card-body">
                                <div id="production-chart" style="min-height: 300px;"></div>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-4">
                        <div class="card h-100">
                            <div class="card-header bg-transparent">
                                <h4 class="card-title mb-0">Wallet & Payments</h4>
                            </div>
                            <div class="card-body">
                                <div class="mb-4">
                                    <label class="text-muted small text-uppercase fw-bold mb-2 d-block">Staked MBT</label>
                                    <div class="d-flex justify-content-between align-items-end">
                                        <h3 class="mb-0">$${stats.staked_mbt || '0.00'}</h3>
                                        <span class="badge bg-soft-success text-success">${stats.staked_trend || '+0%'}</span>
                                    </div>
                                </div>
                                <div class="mb-4">
                                    <label class="text-muted small text-uppercase fw-bold mb-2 d-block">Annual Interest</label>
                                    <div class="d-flex justify-content-between align-items-end">
                                        <h3 class="mb-0">$${stats.annual_interest || '0.00'}</h3>
                                        <span class="badge bg-soft-info text-info">${stats.interest_trend || '+0%'}</span>
                                    </div>
                                </div>
                                <div class="d-grid gap-2">
                                    <button class="btn btn-primary" onclick="app.showPaymentModal()">
                                        <i class="bi bi-plus-circle me-2"></i> Add Funds
                                    </button>
                                    <button class="btn btn-outline-primary">
                                        <i class="bi bi-arrow-up-right me-2"></i> Withdraw
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row g-4">
                    <div class="col-lg-7">
                        <div class="card h-100">
                            <div class="card-header d-flex justify-content-between align-items-center bg-transparent">
                                <h5 class="card-title mb-0">My Farms</h5>
                                <button class="btn btn-sm btn-primary" onclick="app.navigateTo('farms')">Manage</button>
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    <table class="table table-hover mb-0" style="font-size:0.85rem">
                                        <thead class="table-light">
                                            <tr>
                                                <th>Farm Name</th>
                                                <th class="text-center">Ha</th>
                                                <th>Verification Status</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${farmList.length > 0 ? farmList.map(f => {
                                                const vs = f.verification_status || 'draft';
                                                const cs = f.coop_status || '';
                                                let badge, byWho;
                                                if (vs === 'verified') {
                                                    badge = `<span class="badge bg-success">Approved</span>`;
                                                    byWho = `by Plotra`;
                                                } else if (vs === 'rejected') {
                                                    badge = `<span class="badge bg-danger">Rejected</span>`;
                                                    byWho = cs === 'coop_rejected' ? 'by Cooperative' : 'by Plotra';
                                                } else if (cs === 'coop_approved') {
                                                    badge = `<span class="badge bg-info text-dark">Coop ✓</span>`;
                                                    byWho = `Pending Plotra Review`;
                                                } else if (cs === 'coop_rejected') {
                                                    badge = `<span class="badge bg-danger">Coop Rejected</span>`;
                                                    byWho = f.coop_notes ? `"${f.coop_notes.slice(0,30)}"` : '';
                                                } else if (vs === 'pending') {
                                                    badge = `<span class="badge bg-warning text-dark">Pending</span>`;
                                                    byWho = `Awaiting Cooperative`;
                                                } else {
                                                    badge = `<span class="badge bg-secondary">Draft</span>`;
                                                    byWho = `Not submitted`;
                                                }
                                                return `<tr>
                                                    <td class="fw-semibold">${f.farm_name || 'Unnamed Farm'}</td>
                                                    <td class="text-center text-muted">${f.total_area_hectares || '—'}</td>
                                                    <td>
                                                        ${badge}
                                                        <div class="text-muted" style="font-size:0.75rem;margin-top:2px">${byWho}</div>
                                                    </td>
                                                </tr>`;
                                            }).join('') : '<tr><td colspan="3" class="text-center py-4 text-muted">No farms registered yet</td></tr>'}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-5">
                        <div class="card h-100">
                            <div class="card-header d-flex justify-content-between align-items-center bg-transparent">
                                <h5 class="card-title mb-0">Recent Deliveries</h5>
                                <button class="btn btn-sm btn-primary" onclick="app.navigateTo('deliveries')">View All</button>
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    <table class="table table-hover mb-0" style="font-size:0.85rem">
                                        <thead class="table-light">
                                            <tr>
                                                <th>Ref</th>
                                                <th>Weight</th>
                                                <th>Grade</th>
                                                <th>Date</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${deliveryList.length > 0 ? deliveryList.slice(0, 5).map(d => `
                                                <tr>
                                                    <td class="text-muted">#${(d.delivery_number || d.id || '').toString().slice(-6)}</td>
                                                    <td>${d.net_weight_kg || 0} kg</td>
                                                    <td><span class="badge bg-info text-dark bg-opacity-75">${d.quality_grade || 'PB'}</span></td>
                                                    <td>${new Date(d.created_at).toLocaleDateString('en-GB', {day:'2-digit',month:'short'})}</td>
                                                </tr>
                                            `).join('') : '<tr><td colspan="4" class="text-center py-4 text-muted">No deliveries yet</td></tr>'}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Initialize charts
            setTimeout(() => {
                this.initFarmerDashboardCharts(deliveryList);
            }, 100);

        } catch (error) {
            console.error('Failed to load farmer dashboard:', error);
            this.renderOfflineAlert(content);
        }
    }

    initFarmerDashboardCharts(deliveries) {
        if (!document.querySelector("#production-chart")) return;
        if (typeof ApexCharts === 'undefined') return;

        // Group deliveries by month or day
        const sortedDeliveries = [...deliveries].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
        const labels = sortedDeliveries.slice(-7).map(d => new Date(d.created_at).toLocaleDateString(undefined, { weekday: 'short' }));
        const values = sortedDeliveries.slice(-7).map(d => d.net_weight_kg || 0);

        const options = {
            series: [{
                name: 'Delivery Weight (kg)',
                data: values.length > 0 ? values : [0, 0, 0, 0, 0, 0, 0]
            }],
            chart: {
                height: 300,
                type: 'area',
                toolbar: { show: false }
            },
            dataLabels: { enabled: false },
            stroke: { curve: 'smooth', width: 3 },
            colors: ["#6f4e37"],
            fill: {
                type: 'gradient',
                gradient: {
                    shadeIntensity: 1,
                    opacityFrom: 0.3,
                    opacityTo: 0.1,
                    stops: [0, 90, 100]
                }
            },
            xaxis: {
                categories: labels.length > 0 ? labels : ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                axisBorder: { show: false },
                axisTicks: { show: false }
            }
        };

        const chart = new ApexCharts(document.querySelector("#production-chart"), options);
        chart.render();
    }

    async renderEUDRReviewerDashboard(content) {
        try {
            const overview = await api.getComplianceOverview();
            const rawVerif = await api.getPendingVerifications({ limit: 5 });
            const verifications = Array.isArray(rawVerif) ? rawVerif : (rawVerif?.verifications || []);

            content.innerHTML = `
                <div class="row g-4 mb-4">
                    <div class="col-md-3">
                        <div class="card bg-soft-primary text-primary border-0 shadow-sm h-100">
                            <div class="card-body">
                                <h6 class="small text-uppercase mb-2">Total Farms</h6>
                                <h2 class="mb-0">${overview.total_farms || 0}</h2>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-soft-success text-success border-0 shadow-sm h-100">
                            <div class="card-body">
                                <h6 class="small text-uppercase mb-2">Compliant</h6>
                                <h2 class="mb-0">${overview.compliance_breakdown?.compliant || 0}</h2>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-soft-warning text-warning border-0 shadow-sm h-100">
                            <div class="card-body">
                                <h6 class="small text-uppercase mb-2">Under Review</h6>
                                <h2 class="mb-0">${overview.compliance_breakdown?.under_review || 0}</h2>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-soft-danger text-danger border-0 shadow-sm h-100">
                            <div class="card-body">
                                <h6 class="small text-uppercase mb-2">Non-Compliant</h6>
                                <h2 class="mb-0">${overview.compliance_breakdown?.non_compliant || 0}</h2>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row g-4">
                    <div class="col-lg-8">
                        <div class="card border-0 shadow-sm">
                            <div class="card-header d-flex justify-content-between align-items-center bg-transparent">
                                <h4 class="card-title mb-0">Recent Pending Verifications</h4>
                                <button class="btn btn-sm btn-link" onclick="app.navigateTo('verification')">View All</button>
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    <table class="table table-hover mb-0">
                                        <thead>
                                            <tr>
                                                <th>Farm/Farmer</th>
                                                <th>Type</th>
                                                <th>Date</th>
                                                <th>Action</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${verifications.length > 0 ? verifications.map(v => `
                                                <tr>
                                                    <td>
                                                        <div class="fw-bold">${v.farm_name || v.farmer_name}</div>
                                                        <div class="text-muted small">${v.farmer_email || ''}</div>
                                                    </td>
                                                    <td><span class="badge bg-soft-info text-info">${v.type || 'Farm'}</span></td>
                                                    <td>${new Date(v.created_at).toLocaleDateString()}</td>
                                                    <td>
                                                        <button class="btn btn-sm btn-primary" onclick="app.navigateTo('verification')">Review</button>
                                                    </td>
                                                </tr>
                                            `).join('') : '<tr><td colspan="4" class="text-center py-4">No pending verifications</td></tr>'}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-4">
                        <div class="card border-0 shadow-sm h-100">
                            <div class="card-header bg-transparent">
                                <h4 class="card-title mb-0">Compliance Rate</h4>
                            </div>
                            <div class="card-body d-flex flex-column align-items-center justify-content-center">
                                <div class="position-relative mb-4">
                                    <h1 class="display-4 fw-bold text-primary mb-0">${overview.compliance_rate || 0}%</h1>
                                </div>
                                <p class="text-muted text-center small">Overall system compliance rate for EUDR regulation</p>
                                <div class="w-100 mt-4">
                                    <div class="progress" style="height: 10px;">
                                        <div class="progress-bar bg-primary" role="progressbar" style="width: ${overview.compliance_rate || 0}%"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } catch (error) {
            console.error(error);
            content.innerHTML = `<div class="alert alert-danger">Error loading reviewer dashboard: ${error.message}</div>`;
        }
    }

    async renderCoopAdminDashboard(content) {
        try {
            const [stats, deliveries, overview] = await Promise.all([
                api.getCoopStats(),
                api.getDeliveries({ limit: 5 }),
                api.getComplianceOverview()
            ]);
            
            content.innerHTML = `
                <div class="row g-4 mb-4">
                    <div class="col-md-3">
                        <div class="card bg-soft-primary text-primary h-100 border-0 shadow-sm">
                            <div class="card-body">
                                <h6 class="text-uppercase small mb-2">Total Farmers</h6>
                                <h2 class="mb-0">${stats.total_members || 0}</h2>
                                <p class="text-muted small mt-2 mb-0">Registered members</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-soft-success text-success h-100 border-0 shadow-sm">
                            <div class="card-body">
                                <h6 class="text-uppercase small mb-2">Total Weight</h6>
                                <h2 class="mb-0">${stats.total_weight_kg || 0} kg</h2>
                                <p class="text-muted small mt-2 mb-0">Total cherry collected</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-soft-info text-info h-100 border-0 shadow-sm">
                            <div class="card-body">
                                <h6 class="text-uppercase small mb-2">Verified Farms</h6>
                                <h2 class="mb-1">${stats.verified_farms ?? stats.compliant_farms ?? 0}</h2>
                                <div class="d-flex gap-1 flex-wrap mt-1">
                                    <span class="badge bg-success bg-opacity-75" style="font-size:10px;"><i class="bi bi-check-circle me-1"></i>${stats.verified_farms ?? stats.compliant_farms ?? 0} Verified</span>
                                    <span class="badge bg-warning text-dark bg-opacity-75" style="font-size:10px;"><i class="bi bi-hourglass-split me-1"></i>${stats.pending_verification ?? 0} Pending</span>
                                    <span class="badge bg-secondary bg-opacity-75" style="font-size:10px;"><i class="bi bi-pencil me-1"></i>${stats.draft_farms ?? 0} Draft</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-soft-warning text-warning h-100 border-0 shadow-sm">
                            <div class="card-body">
                                <h6 class="text-uppercase small mb-2">Pending Verification</h6>
                                <h2 class="mb-0">${stats.pending_verification || 0}</h2>
                                <p class="text-muted small mt-2 mb-0">Awaiting inspection</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row g-4 mb-4">
                    <div class="col-lg-8">
                        <div class="card h-100 border-0 shadow-sm">
                            <div class="card-header bg-transparent d-flex justify-content-between">
                                <h4 class="card-title mb-0">Recent Deliveries</h4>
                                <button class="btn btn-sm btn-outline-primary" onclick="app.navigateTo('deliveries')">View All</button>
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    <table class="table table-hover mb-0">
                                        <thead>
                                            <tr>
                                                <th>Farmer</th>
                                                <th>Weight</th>
                                                <th>Status</th>
                                                <th>Date</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${deliveries.map(d => `
                                                <tr>
                                                    <td><div class="fw-bold">${d.farmer_name || 'Farmer #'+d.farmer_id}</div></td>
                                                    <td>${d.net_weight_kg} kg</td>
                                                    <td><span class="badge ${this.getDeliveryStatusClass(d.status)}">${d.status}</span></td>
                                                    <td>${new Date(d.created_at).toLocaleDateString()}</td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-4">
                        <div class="card h-100 border-0 shadow-sm">
                            <div class="card-header bg-transparent">
                                <h4 class="card-title mb-0">Compliance Overview</h4>
                            </div>
                            <div class="card-body">
                                <div id="coop-compliance-chart" style="min-height: 250px;"></div>
                                <div class="mt-4">
                                    <div class="d-flex justify-content-between mb-1 small">
                                        <span>Overall Compliance</span>
                                        <span class="fw-bold">${overview.compliance_rate || 0}%</span>
                                    </div>
                                    <div class="progress" style="height: 6px;">
                                        <div class="progress-bar bg-success" style="width: ${overview.compliance_rate || 0}%"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            if (typeof ApexCharts !== 'undefined') {
                new ApexCharts(document.querySelector("#coop-compliance-chart"), {
                    series: [
                        overview.compliance_breakdown?.compliant || 0,
                        overview.compliance_breakdown?.under_review || 0,
                        overview.compliance_breakdown?.non_compliant || 0
                    ],
                    chart: { type: 'donut', height: 250 },
                    labels: ['Compliant', 'Under Review', 'Non-Compliant'],
                    colors: ['#1aa053', '#f86441', '#c03221'],
                    legend: { position: 'bottom' }
                }).render();
            }
        } catch (error) {
            console.error(error);
            content.innerHTML = `<div class="alert alert-danger">Error loading coop dashboard: ${error.message}</div>`;
        }
    }

    async renderCoopOfficerDashboard(content) {
        const coopId = this.currentUser?.cooperative_id;
        const userName = `${this.currentUser?.first_name || ''} ${this.currentUser?.last_name || ''}`.trim();
        try {
            const [farmerApprovals, farmApprovals, pendingFarmerApprovals, deliveries] = await Promise.allSettled([
                api.getCoopAllFarmers(),
                api.request('/coop/farms'),
                api.getCoopPendingFarmers(),
                api.getDeliveries({ limit: 5 })
            ]);

            const farmers = Array.isArray(farmerApprovals.value) ? farmerApprovals.value : [];
            const farms = farmApprovals.value?.farms || (Array.isArray(farmApprovals.value) ? farmApprovals.value : []);
            const pendingFarmersList = Array.isArray(pendingFarmerApprovals.value) ? pendingFarmerApprovals.value : [];
            const recentDeliveries = Array.isArray(deliveries.value) ? deliveries.value : [];

            const pendingFarmers = pendingFarmersList.length;
            const pendingFarms = farms.filter(f => !f.coop_status || f.coop_status === 'pending' || f.coop_status === 'update_requested').length;
            const totalFarmers = farmers.length;
            const totalDeliveries = recentDeliveries.length;

            content.innerHTML = `
                <div class="d-flex align-items-center justify-content-between mb-4">
                    <div>
                        <p class="text-muted mb-0">Welcome back, ${userName}</p>
                    </div>
                    <div class="d-flex gap-2">
                        <button class="btn btn-sm btn-outline-warning fw-semibold" onclick="app.navigateTo('farmer-approvals')">
                            <i class="bi bi-shield-check me-1"></i>Approve Farmers
                            ${pendingFarmers > 0 ? `<span class="badge bg-warning text-dark ms-1">${pendingFarmers}</span>` : ''}
                        </button>
                        <button class="btn btn-sm btn-outline-primary fw-semibold" onclick="app.navigateTo('farm-approvals')">
                            <i class="bi bi-geo-alt-fill me-1"></i>Approve Farms
                            ${pendingFarms > 0 ? `<span class="badge bg-primary text-white ms-1">${pendingFarms}</span>` : ''}
                        </button>
                    </div>
                </div>

                <div class="row g-3 mb-4">
                    <div class="col-6 col-md-3">
                        <div class="card border-0 shadow-sm h-100" style="border-left:4px solid #6f4e37 !important;">
                            <div class="card-body text-center py-3">
                                <i class="bi bi-people-fill fs-2 mb-2" style="color:#6f4e37;"></i>
                                <h3 class="fw-bold mb-0">${totalFarmers}</h3>
                                <small class="text-muted">Total Farmers</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-6 col-md-3">
                        <div class="card border-0 shadow-sm h-100" style="border-left:4px solid #f86441 !important;">
                            <div class="card-body text-center py-3">
                                <i class="bi bi-hourglass-split fs-2 mb-2" style="color:#f86441;"></i>
                                <h3 class="fw-bold mb-0">${pendingFarmers}</h3>
                                <small class="text-muted">Pending Farmer Approvals</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-6 col-md-3">
                        <div class="card border-0 shadow-sm h-100" style="border-left:4px solid #1aa053 !important;">
                            <div class="card-body text-center py-3">
                                <i class="bi bi-geo-alt-fill fs-2 mb-2" style="color:#1aa053;"></i>
                                <h3 class="fw-bold mb-0">${pendingFarms}</h3>
                                <small class="text-muted">Farms Awaiting Approval</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-6 col-md-3">
                        <div class="card border-0 shadow-sm h-100" style="border-left:4px solid #0d6efd !important;">
                            <div class="card-body text-center py-3">
                                <i class="bi bi-box-seam fs-2 mb-2" style="color:#0d6efd;"></i>
                                <h3 class="fw-bold mb-0">${totalDeliveries}</h3>
                                <small class="text-muted">Recent Deliveries</small>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row g-4">
                    <div class="col-lg-8">
                        <div class="card border-0 shadow-sm">
                            <div class="card-header bg-transparent d-flex justify-content-between align-items-center">
                                <h5 class="mb-0 fw-semibold"><i class="bi bi-clock-history me-2 text-primary"></i>Recent Deliveries</h5>
                                <button class="btn btn-sm btn-outline-primary" onclick="app.navigateTo('deliveries')">View All</button>
                            </div>
                            <div class="card-body p-0">
                                ${recentDeliveries.length === 0 ? `<p class="text-muted text-center py-4">No deliveries yet</p>` : `
                                <div class="table-responsive">
                                    <table class="table table-hover mb-0">
                                        <thead><tr><th>Farmer</th><th>Weight (kg)</th><th>Status</th><th>Date</th></tr></thead>
                                        <tbody>
                                            ${recentDeliveries.map(d => `<tr>
                                                <td class="fw-semibold">${d.farmer_name || 'Farmer'}</td>
                                                <td>${d.net_weight_kg || 0}</td>
                                                <td><span class="badge ${this.getDeliveryStatusClass(d.status)}">${d.status}</span></td>
                                                <td>${new Date(d.created_at).toLocaleDateString()}</td>
                                            </tr>`).join('')}
                                        </tbody>
                                    </table>
                                </div>`}
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-4">
                        <div class="card border-0 shadow-sm">
                            <div class="card-header bg-transparent">
                                <h5 class="mb-0 fw-semibold"><i class="bi bi-lightning-charge-fill me-2 text-warning"></i>Quick Actions</h5>
                            </div>
                            <div class="card-body d-grid gap-2">
                                <button class="btn btn-outline-warning text-start" onclick="app.navigateTo('farmer-approvals')">
                                    <i class="bi bi-person-check me-2"></i>Review Farmer Applications
                                </button>
                                <button class="btn btn-outline-primary text-start" onclick="app.navigateTo('farm-approvals')">
                                    <i class="bi bi-map me-2"></i>Review Farm Submissions
                                </button>
                                <button class="btn btn-outline-success text-start" onclick="app.navigateTo('deliveries')">
                                    <i class="bi bi-plus-circle me-2"></i>Record Delivery
                                </button>
                                <button class="btn btn-outline-secondary text-start" onclick="app.navigateTo('coop-team')">
                                    <i class="bi bi-people me-2"></i>Manage Team
                                </button>
                            </div>
                        </div>
                    </div>
                </div>`;
        } catch (error) {
            console.error(error);
            content.innerHTML = `<div class="alert alert-danger">Error loading dashboard: ${error.message}</div>`;
        }
    }

    async loadCoopFarms(content) {
        const statusBadge = (s) => {
            const map = { draft: 'bg-secondary', pending: 'bg-warning text-dark', verified: 'bg-success', coop_approved: 'bg-info text-dark', rejected: 'bg-danger', coop_rejected: 'bg-danger' };
            return `<span class="badge ${map[s] || 'bg-secondary'} text-capitalize">${s?.replace(/_/g,' ') || 'draft'}</span>`;
        };
        const coopBadge = (s) => {
            if (s === 'coop_approved') return `<span class="badge bg-info text-dark">Coop ✓</span>`;
            if (s === 'coop_rejected') return `<span class="badge bg-danger">Coop ✗</span>`;
            return `<span class="badge bg-secondary bg-opacity-50">Awaiting Coop</span>`;
        };

        content.innerHTML = `
            <div class="row g-3 mb-4">
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Total Farms</div><h3 class="mb-0" id="cfl-total">—</h3></div></div></div>
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Pending Review</div><h3 class="mb-0 text-warning" id="cfl-pending">—</h3></div></div></div>
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Verified</div><h3 class="mb-0 text-success" id="cfl-verified">—</h3></div></div></div>
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Draft</div><h3 class="mb-0 text-secondary" id="cfl-draft">—</h3></div></div></div>
            </div>
            <div class="card">
                <div class="card-header d-flex align-items-center flex-wrap gap-2">
                    <span class="fw-semibold me-auto">Farms in Cooperative</span>
                    <button class="btn btn-sm btn-outline-secondary" onclick="app.loadCoopFarms(document.getElementById('pageContent'))">
                        <i class="bi bi-arrow-clockwise me-1"></i>Refresh
                    </button>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0" style="min-width:700px">
                            <thead class="table-light">
                                <tr><th>Farmer</th><th>Farm Name</th><th>Area</th><th>Coop Status</th><th>Status</th><th>Registered</th><th>Actions</th></tr>
                            </thead>
                            <tbody id="cfl-tbody">
                                <tr><td colspan="7" class="text-center py-4"><div class="spinner-border spinner-border-sm text-primary me-2"></div>Loading...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>`;

        try {
            const res = await api.request('/coop/farms');
            const farms = res.farms || [];
            document.getElementById('cfl-total').textContent = farms.length;
            document.getElementById('cfl-pending').textContent = farms.filter(f => f.verification_status === 'pending').length;
            document.getElementById('cfl-verified').textContent = farms.filter(f => f.verification_status === 'verified').length;
            document.getElementById('cfl-draft').textContent = farms.filter(f => f.verification_status === 'draft').length;

            const tbody = document.getElementById('cfl-tbody');
            if (!farms.length) {
                tbody.innerHTML = `<tr><td colspan="7" class="text-center py-5 text-muted"><i class="bi bi-geo-alt fs-3 d-block mb-2"></i>No farms in your cooperative yet</td></tr>`;
                return;
            }
            tbody.innerHTML = farms.map(f => `
                <tr>
                    <td>
                        <div class="fw-semibold">${f.farmer_name || 'N/A'}</div>
                        <div class="text-muted" style="font-size:.75rem">${f.farmer_phone || ''}</div>
                    </td>
                    <td>
                        <div>${f.farm_name || 'Unnamed Farm'}</div>
                        <div class="text-muted" style="font-size:.75rem">${f.farm_code || ''}</div>
                    </td>
                    <td class="text-nowrap">${f.total_area_hectares ? f.total_area_hectares + ' ha' : '—'}</td>
                    <td>${coopBadge(f.coop_status)}</td>
                    <td>${statusBadge(f.verification_status)}</td>
                    <td class="text-muted" style="font-size:.8rem">${f.created_at ? new Date(f.created_at).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}) : '—'}</td>
                    <td>
                        <div class="d-flex gap-1 flex-wrap">
                            <button class="btn btn-sm btn-outline-primary" onclick="app.adminViewFarm('${f.id}')"><i class="bi bi-eye me-1"></i>View</button>
                            <button class="btn btn-sm btn-outline-info" onclick="app.requestSatelliteAnalysis('${f.id}')" ${!f.centroid_lat ? 'disabled title="No polygon for this farm"' : ''}><i class="bi bi-satellite-fill me-1"></i>Analyse</button>
                        </div>
                    </td>
                </tr>`).join('');
        } catch(e) {
            console.error(e);
            this.showToast('Error loading farms', 'error');
        }
    }

    async loadCoopFarmApprovals(content) {
        const statusBadge = (s) => {
            const map = { draft: 'bg-secondary', pending: 'bg-warning text-dark', verified: 'bg-success', coop_approved: 'bg-info text-dark', rejected: 'bg-danger', coop_rejected: 'bg-danger' };
            return `<span class="badge ${map[s] || 'bg-secondary'} text-capitalize">${s?.replace('_', ' ') || 'draft'}</span>`;
        };
        const coopStatusBadge = (s) => {
            if (s === 'coop_approved') return `<span class="badge bg-info text-dark">Coop Approved</span>`;
            if (s === 'coop_rejected') return `<span class="badge bg-danger">Coop Rejected</span>`;
            if (s === 'update_requested') return `<span class="badge bg-warning text-dark"><i class="bi bi-exclamation-triangle me-1"></i>Update Requested</span>`;
            return `<span class="badge bg-warning text-dark">Awaiting Coop</span>`;
        };

        content.innerHTML = `
            <div class="row g-3 mb-4">
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Total Farms</div><h3 class="mb-0" id="cf-total">—</h3></div></div></div>
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Awaiting Review</div><h3 class="mb-0 text-warning" id="cf-pending">—</h3></div></div></div>
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Coop Approved</div><h3 class="mb-0 text-info" id="cf-approved">—</h3></div></div></div>
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Rejected</div><h3 class="mb-0 text-danger" id="cf-rejected">—</h3></div></div></div>
            </div>
            <div class="card">
                <div class="card-header d-flex align-items-center flex-wrap gap-2">
                    <span class="fw-semibold me-auto">Cooperative Farms</span>
                    <button class="btn btn-sm btn-outline-secondary" onclick="app.loadCoopFarmApprovals(document.getElementById('pageContent'))">
                        <i class="bi bi-arrow-clockwise me-1"></i>Refresh
                    </button>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0" style="min-width:700px">
                            <thead class="table-light">
                                <tr><th>Farmer</th><th>Farm Name</th><th>Area</th><th>Status</th><th>Coop Status</th><th>Registered</th><th>Actions</th></tr>
                            </thead>
                            <tbody id="cf-tbody">
                                <tr><td colspan="7" class="text-center py-4"><div class="spinner-border spinner-border-sm text-primary me-2"></div>Loading...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>`;

        try {
            const res = await api.request('/coop/farms');
            const farms = res.farms || [];
            document.getElementById('cf-total').textContent = res.total || farms.length;
            document.getElementById('cf-pending').textContent = farms.filter(f => !f.coop_status || f.coop_status === 'pending' || f.coop_status === 'update_requested').length;
            document.getElementById('cf-approved').textContent = farms.filter(f => f.coop_status === 'coop_approved').length;
            document.getElementById('cf-rejected').textContent = farms.filter(f => f.coop_status === 'coop_rejected').length;

            const tbody = document.getElementById('cf-tbody');
            if (!farms.length) {
                tbody.innerHTML = `<tr><td colspan="7" class="text-center py-5 text-muted"><i class="bi bi-geo-alt fs-3 d-block mb-2"></i>No farms in your cooperative yet</td></tr>`;
                return;
            }
            this._farmsApprovalMap = this._farmsApprovalMap || {};
            farms.forEach(f => { this._farmsApprovalMap[f.id] = { ...f, _actor: 'coop' }; });

            tbody.innerHTML = farms.map(f => {
                return `<tr>
                    <td>
                        <div class="fw-semibold">${f.farmer_name || 'Unknown'}</div>
                        <div class="text-muted" style="font-size:.75rem">${f.farmer_phone || ''}</div>
                    </td>
                    <td>
                        <div>${f.farm_name || 'Unnamed Farm'}</div>
                        ${f.update_requested ? `<span class="badge bg-warning text-dark mt-1"><i class="bi bi-exclamation-triangle me-1"></i>Update Requested</span>` : ''}
                    </td>
                    <td class="text-nowrap">${f.total_area_hectares ? f.total_area_hectares + ' ha' : '—'}</td>
                    <td>${statusBadge(f.verification_status)}</td>
                    <td>${coopStatusBadge(f.coop_status)}</td>
                    <td class="text-muted" style="font-size:.8rem">${f.created_at ? new Date(f.created_at).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}) : '—'}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="app._showFarmDetailsModal('${f.id}')">
                            <i class="bi bi-eye me-1"></i>View
                        </button>
                    </td>
                </tr>`;
            }).join('');
        } catch (e) {
            console.error(e);
            this.showToast('Error loading farms', 'error');
        }
    }

    async coopApproveFarm(farmId) {
        if (!confirm('Approve this farm for your cooperative?')) return;
        try {
            await api.request(`/coop/farms/${farmId}/approve`, { method: 'PATCH' });
            this.showToast('Farm approved', 'success');
            this.loadCoopFarmApprovals(document.getElementById('pageContent'));
        } catch(e) { this.showToast(e.message || 'Failed to approve', 'error'); }
    }

    async coopRejectFarm(farmId) {
        const reason = prompt('Reason for rejection (optional):') ?? '';
        if (reason === null) return;
        try {
            await api.request(`/coop/farms/${farmId}/reject?reason=${encodeURIComponent(reason)}`, { method: 'PATCH' });
            this.showToast('Farm rejected', 'warning');
            this.loadCoopFarmApprovals(document.getElementById('pageContent'));
        } catch(e) { this.showToast(e.message || 'Failed to reject', 'error'); }
    }

    async loadCoopFarmersList(content) {
        const statusBadge = (f) => {
            const vs = f.verification_status;
            const cs = f.coop_status;
            if (vs === 'verified') return `<span class="badge bg-soft-success text-success">Verified</span>`;
            if (vs === 'rejected') return `<span class="badge bg-soft-danger text-danger">Rejected</span>`;
            if (cs === 'coop_rejected') return `<span class="badge bg-soft-danger text-danger">Coop Rejected</span>`;
            if (cs === 'coop_approved') return `<span class="badge bg-soft-info text-info">Coop Approved</span>`;
            return `<span class="badge bg-soft-warning text-warning">Pending</span>`;
        };

        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-3">
                    <div class="card bg-soft-primary text-primary h-100">
                        <div class="card-body">
                            <h6 class="text-uppercase small mb-2">Total Farmers</h6>
                            <h3 class="mb-0" id="cfl-stat-total">...</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card bg-soft-success text-success h-100">
                        <div class="card-body">
                            <h6 class="text-uppercase small mb-2">Fully Verified</h6>
                            <h3 class="mb-0" id="cfl-stat-verified">...</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card bg-soft-info text-info h-100">
                        <div class="card-body">
                            <h6 class="text-uppercase small mb-2">Coop Approved</h6>
                            <h3 class="mb-0" id="cfl-stat-coop">...</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card bg-soft-warning text-warning h-100">
                        <div class="card-body">
                            <h6 class="text-uppercase small mb-2">Pending Review</h6>
                            <h3 class="mb-0" id="cfl-stat-pending">...</h3>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2">
                    <h4 class="card-title mb-0">Farmers in Cooperative</h4>
                    <button class="btn btn-sm btn-outline-secondary" onclick="app.loadCoopFarmersList(document.getElementById('pageContent'))">
                        <i class="bi bi-arrow-clockwise me-1"></i>Refresh
                    </button>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0" style="min-width:700px">
                            <thead class="table-light">
                                <tr>
                                    <th>Name</th>
                                    <th>Phone / ID</th>
                                    <th>County</th>
                                    <th>Farms</th>
                                    <th>Status</th>
                                    <th>Registered</th>
                                </tr>
                            </thead>
                            <tbody id="cfl-farmers-tbody">
                                <tr><td colspan="6" class="text-center py-4"><div class="spinner-border spinner-border-sm text-primary me-2"></div>Loading farmers...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>`;

        try {
            const farmers = await api.getCoopAllFarmers();
            const list = Array.isArray(farmers) ? farmers : [];

            document.getElementById('cfl-stat-total').textContent = list.length;
            document.getElementById('cfl-stat-verified').textContent = list.filter(f => f.verification_status === 'verified').length;
            document.getElementById('cfl-stat-coop').textContent = list.filter(f => f.coop_status === 'coop_approved' && f.verification_status !== 'verified').length;
            document.getElementById('cfl-stat-pending').textContent = list.filter(f => !f.coop_status || f.coop_status === 'pending').length;

            const tbody = document.getElementById('cfl-farmers-tbody');
            if (!list.length) {
                tbody.innerHTML = `<tr><td colspan="6" class="text-center py-5 text-muted"><i class="bi bi-people fs-3 d-block mb-2"></i>No farmers in your cooperative yet</td></tr>`;
                return;
            }
            tbody.innerHTML = list.map(f => {
                const name = `${f.first_name || ''} ${f.last_name || ''}`.trim() || 'Unknown';
                const date = f.created_at ? new Date(f.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';
                return `
                    <tr>
                        <td>
                            <div class="fw-bold">${name}</div>
                            <div class="text-muted small">${f.email || ''}</div>
                        </td>
                        <td>
                            <div>${f.phone || '—'}</div>
                            <div class="text-muted small">ID: ${f.national_id || '—'}</div>
                        </td>
                        <td>${f.county || '—'}</td>
                        <td>${f.farm_count ?? 0}</td>
                        <td>${statusBadge(f)}</td>
                        <td class="text-muted small">${date}</td>
                    </tr>`;
            }).join('');
        } catch(e) {
            console.error(e);
            const tbody = document.getElementById('cfl-farmers-tbody');
            if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-4">Error loading farmers: ${e.message}</td></tr>`;
        }
    }

    async loadCoopTeam(content) {
        let coopId = this.currentUser?.cooperative_id;
        if (!coopId) {
            try {
                const info = await api.request('/coop/me');
                coopId = info.cooperative_id;
                if (coopId && this.currentUser) {
                    this.currentUser.cooperative_id = coopId;
                    localStorage.setItem('plotra_user', JSON.stringify(this.currentUser));
                }
            } catch(e) {}
        }
        if (!coopId) {
            content.innerHTML = `<div class="alert alert-warning">No cooperative linked to your account.</div>`;
            return;
        }

        const availablePages = [
            { id: 'farm-approvals', label: 'Farm Approvals' },
            { id: 'farmer-approvals', label: 'Farmer Approvals' },
            { id: 'deliveries', label: 'Deliveries' },
        ];

        let members = [];
        try { members = await api.request(`/admin/cooperatives/${coopId}/team`); } catch(e) {}

        content.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h4 class="fw-bold mb-1">Cooperative Team</h4>
                    <p class="text-muted mb-0">Manage team members and their page access</p>
                </div>
                <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addTeamMemberModal">
                    <i class="bi bi-person-plus-fill me-1"></i>Add Team Member
                </button>
            </div>
            <div class="card border-0 shadow-sm">
                <div class="card-body p-0">
                    ${members.length === 0 ? `<p class="text-muted text-center py-5">No team members yet. Add your first team member.</p>` : `
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Role/Title</th><th>Pages Access</th><th>Status</th><th>Actions</th></tr></thead>
                            <tbody>
                                ${members.map(m => `<tr>
                                    <td class="fw-semibold">${m.first_name} ${m.last_name}</td>
                                    <td>${m.email}</td>
                                    <td>${m.phone || '-'}</td>
                                    <td><span class="badge bg-soft-primary text-primary">${m.job_title || 'Team Member'}</span></td>
                                    <td>${m.page_permissions ? m.page_permissions.map(p => `<span class="badge bg-soft-info text-info me-1">${p}</span>`).join('') : '<span class="badge bg-soft-success text-success">All Pages</span>'}</td>
                                    <td><span class="badge ${m.status === 'active' ? 'bg-soft-success text-success' : 'bg-soft-warning text-warning'}">${m.status}</span></td>
                                    <td>
                                        <button class="btn btn-xs btn-outline-primary" onclick="app.showEditPermissionsModal('${m.id}', '${m.first_name} ${m.last_name}', ${JSON.stringify(m.page_permissions || [])})">
                                            <i class="bi bi-pencil"></i> Permissions
                                        </button>
                                    </td>
                                </tr>`).join('')}
                            </tbody>
                        </table>
                    </div>`}
                </div>
            </div>`;

        // Inject modals directly into body so Bootstrap backdrop/positioning works correctly
        ['addTeamMemberModal', 'editPermissionsModal'].forEach(id => {
            const old = document.getElementById(id);
            if (old) { bootstrap.Modal.getInstance(old)?.dispose(); old.remove(); }
        });

        const addModalHTML = `
            <div class="modal fade" id="addTeamMemberModal" tabindex="-1">
                <div class="modal-dialog modal-dialog-scrollable">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-person-plus-fill me-2"></i>Add Team Member</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <form id="addTeamMemberForm">
                                <div class="row g-3">
                                    <div class="col-6"><label class="form-label">First Name <span class="text-danger">*</span></label><input class="form-control" id="tmFirstName" required></div>
                                    <div class="col-6"><label class="form-label">Last Name <span class="text-danger">*</span></label><input class="form-control" id="tmLastName" required></div>
                                    <div class="col-12"><label class="form-label">Email <span class="text-danger">*</span></label><input class="form-control" type="email" id="tmEmail" required></div>
                                    <div class="col-12"><label class="form-label">Phone <span class="text-danger">*</span></label><input class="form-control" id="tmPhone" required></div>
                                    <div class="col-12"><label class="form-label">Job Title</label><input class="form-control" id="tmJobTitle" placeholder="e.g. Contact Person, Field Officer"></div>
                                    <div class="col-12">
                                        <label class="form-label fw-semibold">Page Access</label>
                                        <div class="border rounded p-3">
                                            ${availablePages.map(p => `
                                            <div class="form-check">
                                                <input class="form-check-input tm-page-perm" type="checkbox" value="${p.id}" id="perm_${p.id}">
                                                <label class="form-check-label" for="perm_${p.id}">${p.label}</label>
                                            </div>`).join('')}
                                        </div>
                                        <small class="text-muted">Leave all unchecked to give full access.</small>
                                    </div>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="addTeamMemberSubmitBtn">
                                <i class="bi bi-person-plus-fill me-1"></i>Add & Send Email
                            </button>
                        </div>
                    </div>
                </div>
            </div>`;

        const editModalHTML = `
            <div class="modal fade" id="editPermissionsModal" tabindex="-1">
                <div class="modal-dialog modal-dialog-scrollable">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Edit Page Permissions</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p class="text-muted fw-semibold" id="editPermMemberName"></p>
                            <div class="border rounded p-3" id="editPermChecks">
                                ${availablePages.map(p => `
                                <div class="form-check">
                                    <input class="form-check-input edit-perm-check" type="checkbox" value="${p.id}" id="eperm_${p.id}">
                                    <label class="form-check-label" for="eperm_${p.id}">${p.label}</label>
                                </div>`).join('')}
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="savePermissionsBtn">Save Permissions</button>
                        </div>
                    </div>
                </div>
            </div>`;

        const addEl = document.createElement('div');
        addEl.innerHTML = addModalHTML;
        document.body.appendChild(addEl.firstElementChild);

        const editEl = document.createElement('div');
        editEl.innerHTML = editModalHTML;
        document.body.appendChild(editEl.firstElementChild);

        // Wire submit button now that element is in DOM
        document.getElementById('addTeamMemberSubmitBtn').addEventListener('click', () => this.submitAddTeamMember(coopId));
    }

    async submitAddTeamMember(coopId) {
        const firstName = document.getElementById('tmFirstName')?.value?.trim();
        const lastName = document.getElementById('tmLastName')?.value?.trim();
        const email = document.getElementById('tmEmail')?.value?.trim();
        const phone = document.getElementById('tmPhone')?.value?.trim();
        const jobTitle = document.getElementById('tmJobTitle')?.value?.trim();
        const checked = [...document.querySelectorAll('.tm-page-perm:checked')].map(c => c.value);

        if (!firstName || !lastName || !email || !phone) {
            this.showToast('Please fill in all required fields', 'error');
            return;
        }

        try {
            const formData = new FormData();
            formData.append('first_name', firstName);
            formData.append('last_name', lastName);
            formData.append('email', email);
            formData.append('phone', phone);
            formData.append('job_title', jobTitle || '');
            formData.append('page_permissions', checked.join(','));

            await api.request(`/admin/cooperatives/${coopId}/team`, { method: 'POST', body: formData, headers: {} });
            bootstrap.Modal.getInstance(document.getElementById('addTeamMemberModal'))?.hide();
            this.showToast(`Team member added. Setup email sent to ${email}`, 'success');
            await this.loadCoopTeam(document.getElementById('main-content'));
        } catch (e) {
            this.showToast(e.message, 'error');
        }
    }

    showEditPermissionsModal(userId, name, currentPerms) {
        document.getElementById('editPermMemberName').textContent = `Editing permissions for: ${name}`;
        document.querySelectorAll('.edit-perm-check').forEach(cb => {
            cb.checked = currentPerms.includes(cb.value);
        });
        document.getElementById('savePermissionsBtn').onclick = async () => {
            const perms = [...document.querySelectorAll('.edit-perm-check:checked')].map(c => c.value);
            try {
                await api.request(`/admin/users/${userId}/page-permissions`, {
                    method: 'PUT',
                    body: JSON.stringify(perms)
                });
                bootstrap.Modal.getInstance(document.getElementById('editPermissionsModal'))?.hide();
                this.showToast('Permissions updated', 'success');
                await this.loadCoopTeam(document.getElementById('main-content'));
            } catch (e) {
                this.showToast(e.message, 'error');
            }
        };
        new bootstrap.Modal(document.getElementById('editPermissionsModal')).show();
    }

    async loadFarmers(content) {
        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-4">
                    <div class="card bg-soft-primary text-primary h-100">
                        <div class="card-body">
                            <h6 class="text-uppercase small mb-2">Total Farmers</h6>
                            <h3 class="mb-0" id="total-farmers-count">...</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card bg-soft-success text-success h-100">
                        <div class="card-body">
                            <h6 class="text-uppercase small mb-2">Verified Farmers</h6>
                            <h3 class="mb-0" id="verified-farmers-count">...</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card bg-soft-warning text-warning h-100">
                        <div class="card-body">
                            <h6 class="text-uppercase small mb-2">Pending Verification</h6>
                            <h3 class="mb-0" id="pending-farmers-count">...</h3>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-lg-8">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between">
                            <h4 class="card-title">Farmers List</h4>
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>Name</th>
                                            <th>Region</th>
                                            <th>Cooperative</th>
                                            <th>Farms</th>
                                            <th>Status</th>
                                        </tr>
                                    </thead>
                                    <tbody id="farmers-list">
                                        <tr><td colspan="5" class="text-center py-4">Loading farmers...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-lg-4">
                    <div class="card">
                        <div class="card-header">
                            <h4 class="card-title">Gender Distribution</h4>
                        </div>
                        <div class="card-body">
                            <div id="farmer-gender-chart" style="min-height: 250px;"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        try {
            const response = await api.getUsers({ role: 'FARMER' });
            const users = response.users || [];
            const list = document.getElementById('farmers-list');
            
            if (users && users.length > 0) {
                const totalCount = document.getElementById('total-farmers-count');
                const verifiedCount = document.getElementById('verified-farmers-count');
                const pendingCount = document.getElementById('pending-farmers-count');
                
                if (totalCount) totalCount.textContent = users.length;
                if (verifiedCount) verifiedCount.textContent = users.filter(u => u.verification_status === 'verified').length;
                if (pendingCount) pendingCount.textContent = users.filter(u => u.verification_status !== 'verified').length;

                if (list) {
                    list.innerHTML = users.map(u => `
                        <tr>
                            <td>
                                <div class="fw-bold">${u.first_name} ${u.last_name}</div>
                                <div class="text-muted small">${u.email}</div>
                            </td>
                            <td>${u.county || 'N/A'}</td>
                            <td>${u.cooperative_name || 'Individual'}</td>
                            <td>${u.farm_count || 0}</td>
                            <td><span class="badge ${u.verification_status === 'verified' ? 'bg-soft-success text-success' : 'bg-soft-warning text-warning'}">${u.verification_status || 'pending'}</span></td>
                        </tr>
                    `).join('');
                }

                // Render Gender Chart
                if (typeof ApexCharts !== 'undefined') {
                    const genderChartEl = document.querySelector("#farmer-gender-chart");
                    if (genderChartEl) {
                        const males = users.filter(u => u.gender?.toLowerCase() === 'male').length;
                        const females = users.filter(u => u.gender?.toLowerCase() === 'female').length;
                        const others = (users.length || 0) - males - females;

                        new ApexCharts(genderChartEl, {
                            series: [males, females, others],
                            chart: { type: 'donut', height: 250 },
                            labels: ['Male', 'Female', 'Other'],
                            colors: ['#6f4e37', '#a67b5b', '#c4a77d'],
                            legend: { position: 'bottom' }
                        }).render();
                    }
                }
            } else {
                list.innerHTML = '<tr><td colspan="5" class="text-center py-4">No farmers found</td></tr>';
            }
        } catch (e) {
            console.error(e);
            this.showToast('Error loading farmers', 'error');
        }
    }

    async loadFarmerApprovals(content) {
        const role = (this.currentUser?.role || '').toUpperCase();
        const isCoop = role === 'COOP_ADMIN' || role === 'COOPERATIVE' || role === 'COOPERATIVE_OFFICER';
        const isAdmin = role === 'ADMIN' || role === 'KIPAWA' || role === 'SUPER_ADMIN' || role === 'PLOTRA_ADMIN' || role === 'PLATFORM_ADMIN';

        const farmerStatusBadge = (f) => {
            const cs = f.coop_status;
            const vs = f.verification_status;
            if (vs === 'verified') return `<span class="badge bg-success">Fully Verified</span>`;
            if (vs === 'rejected') return `<span class="badge bg-danger">Admin Rejected</span>`;
            if (cs === 'coop_rejected') return `<span class="badge bg-danger">Coop Rejected</span>`;
            if (f.update_requested || cs === 'update_requested') {
                const tip = f.update_request_notes ? ` title="${f.update_request_notes.replace(/"/g,"'")}"` : '';
                return `<span class="badge bg-warning text-dark"${tip}><i class="bi bi-exclamation-triangle-fill me-1"></i>Update Requested</span>`;
            }
            if (cs === 'coop_approved') return `<span class="badge bg-info text-dark">Coop Approved <small class="ms-1 opacity-75">(awaiting admin)</small></span>`;
            return `<span class="badge bg-warning text-dark">Pending Review</span>`;
        };

        content.innerHTML = `
            <div class="row g-3 mb-4" id="fa-stats">
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Pending Review</div><h3 class="mb-0 text-warning" id="fa-stat-pending">—</h3></div></div></div>
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Coop Approved</div><h3 class="mb-0 text-info" id="fa-stat-coop">—</h3></div></div></div>
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Fully Verified</div><h3 class="mb-0 text-success" id="fa-stat-verified">—</h3></div></div></div>
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Rejected</div><h3 class="mb-0 text-danger" id="fa-stat-rejected">—</h3></div></div></div>
            </div>
            <div class="card">
                <div class="card-header d-flex align-items-center flex-wrap gap-2">
                    <h5 class="mb-0 me-auto">Farmers Pending Approval</h5>
                    <button class="btn btn-sm btn-outline-secondary" onclick="app.loadFarmerApprovals(document.getElementById('pageContent'))">
                        <i class="bi bi-arrow-clockwise me-1"></i>Refresh
                    </button>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0" style="min-width:650px">
                            <thead class="table-light">
                                <tr>
                                    <th>Farmer</th>
                                    <th>Phone / ID</th>
                                    <th>County</th>
                                    <th>Registered</th>
                                    <th>Status</th>
                                    <th class="text-end">Actions</th>
                                </tr>
                            </thead>
                            <tbody id="fa-tbody">
                                <tr><td colspan="6" class="text-center py-4"><div class="spinner-border spinner-border-sm text-primary me-2"></div>Loading...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        try {
            let farmers = [];
            let allFarmers = [];
            if (isCoop) {
                farmers = await api.getCoopPendingFarmers();
                farmers = Array.isArray(farmers) ? farmers : [];
                allFarmers = await api.getCoopAllFarmers();
                allFarmers = Array.isArray(allFarmers) ? allFarmers : farmers;
            } else if (isAdmin) {
                const res = await api.getAdminPendingFarmers();
                farmers = Array.isArray(res) ? res : (res.users || res.farmers || []);
                const allRes = await api.getUsers({ role: 'FARMER' });
                allFarmers = allRes?.users || farmers;
            }

            // Stats
            document.getElementById('fa-stat-pending').textContent = farmers.filter(f => !f.coop_status || f.coop_status === 'pending').length;
            document.getElementById('fa-stat-coop').textContent = allFarmers.filter(f => f.coop_status === 'coop_approved' && f.verification_status !== 'verified').length;
            document.getElementById('fa-stat-verified').textContent = allFarmers.filter(f => f.verification_status === 'verified').length;
            document.getElementById('fa-stat-rejected').textContent = allFarmers.filter(f => f.verification_status === 'rejected' || f.coop_status === 'coop_rejected').length;

            const tbody = document.getElementById('fa-tbody');
            if (!farmers || farmers.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" class="text-center py-5 text-muted"><i class="bi bi-check2-circle fs-3 d-block mb-2"></i>No farmers pending approval</td></tr>`;
                return;
            }

            // Store farmers map for the view modal
            this._farmersApprovalMap = {};
            farmers.forEach(f => { this._farmersApprovalMap[f.id] = f; });

            tbody.innerHTML = farmers.map(f => {
                const name = `${f.first_name || ''} ${f.last_name || ''}`.trim() || 'Unknown';
                const date = f.created_at ? new Date(f.created_at).toLocaleDateString() : '—';
                const farmerName = `${f.first_name || ''} ${f.last_name || ''}`.trim();
                const actor = isCoop ? 'coop' : 'admin';
                return `
                    <tr>
                        <td>
                            <div class="fw-semibold">${name}</div>
                            <div class="text-muted small">${f.email || ''}</div>
                        </td>
                        <td>
                            <div>${f.phone || '—'}</div>
                            <div class="text-muted small">ID: ${f.national_id || '—'}</div>
                        </td>
                        <td>${f.county || '—'}</td>
                        <td class="text-muted small">${date}</td>
                        <td>${farmerStatusBadge(f)}</td>
                        <td class="text-end">
                            <div class="d-flex gap-1 justify-content-end">
                                <button class="btn btn-sm btn-outline-primary" title="View Details" onclick="app._showFarmerDetailsModal('${f.id}','${actor}')"><i class="bi bi-eye me-1"></i>View</button>
                            </div>
                        </td>
                    </tr>`;
            }).join('');
        } catch (e) {
            console.error(e);
            const tbody = document.getElementById('fa-tbody');
            if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-4">Error loading farmers: ${e.message}</td></tr>`;
        }
    }

    _farmerApprovalState = {};

    _showFarmerApprovalModal(farmerId, action, actor) {
        this._farmerApprovalState = { farmerId, action, actor };
        // Close details modal if open
        const details = document.getElementById('farmerDetailsModal');
        if (details) bootstrap.Modal.getInstance(details)?.hide();
        const modal = document.getElementById('verificationReasonModal');
        if (!modal) return;
        const label = modal.querySelector('.modal-title');
        const confirmBtn = document.getElementById('verificationModalConfirmBtn');
        const input = document.getElementById('verificationReasonInput');
        if (label) label.textContent = action === 'approve' ? 'Approve Farmer' : 'Reject Farmer';
        if (confirmBtn) {
            confirmBtn.className = `btn ${action === 'approve' ? 'btn-success' : 'btn-danger'}`;
            confirmBtn.textContent = action === 'approve' ? 'Confirm Approval' : 'Confirm Rejection';
            confirmBtn.onclick = () => this._confirmFarmerApproval();
        }
        if (input) input.value = '';
        bootstrap.Modal.getOrCreateInstance(modal).show();
    }

    async _confirmFarmerApproval() {
        const { farmerId, action, actor } = this._farmerApprovalState;
        const notes = document.getElementById('verificationReasonInput')?.value?.trim() || '';
        const modal = document.getElementById('verificationReasonModal');
        if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
        try {
            if (actor === 'coop') {
                if (action === 'approve') await api.coopApproveFarmerAccount(farmerId, notes);
                else await api.coopRejectFarmerAccount(farmerId, notes);
            } else {
                if (action === 'approve') await api.adminApproveFarmer(farmerId, notes);
                else await api.adminRejectFarmer(farmerId, notes);
            }
            this.showToast(`Farmer ${action === 'approve' ? 'approved' : 'rejected'} successfully`, 'success');
            await this.loadFarmerApprovals(document.getElementById('pageContent'));
        } catch (e) {
            this.showToast(`Error: ${e.message}`, 'error');
        }
    }

    _requestUpdateState = {};

    _showRequestUpdateModal(farmerId, farmerName, actor) {
        this._requestUpdateState = { farmerId, actor };
        // Close any open details modal first
        ['farmerDetailsModal','farmDetailsModal'].forEach(id => {
            const m = document.getElementById(id);
            if (m) bootstrap.Modal.getInstance(m)?.hide();
        });
        // Remove any stale modal first
        const old = document.getElementById('requestUpdateModal');
        if (old) { bootstrap.Modal.getInstance(old)?.dispose(); old.remove(); }

        const el = document.createElement('div');
        el.innerHTML = `
            <div class="modal fade" id="requestUpdateModal" tabindex="-1">
                <div class="modal-dialog modal-dialog-scrollable">
                    <div class="modal-content">
                        <div class="modal-header bg-warning bg-opacity-10 border-bottom-0">
                            <h5 class="modal-title"><i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>Request Update from Farmer</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p class="text-muted mb-3">Describe the issue that <strong>${farmerName || 'this farmer'}</strong> needs to correct before you can approve their account. They will receive a notification with your message.</p>
                            <label class="form-label fw-semibold">Issue / Action Required <span class="text-danger">*</span></label>
                            <textarea id="requestUpdateIssueInput" class="form-control" rows="4" placeholder="e.g. Please upload a clear photo of your national ID. The current document is blurry and unreadable."></textarea>
                            <div class="form-text">Be specific so the farmer knows exactly what to fix.</div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-warning" id="requestUpdateConfirmBtn">
                                <i class="bi bi-send me-1"></i>Send Request
                            </button>
                        </div>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(el.firstElementChild);
        document.getElementById('requestUpdateConfirmBtn').addEventListener('click', () => this._confirmRequestUpdate());
        bootstrap.Modal.getOrCreateInstance(document.getElementById('requestUpdateModal')).show();
    }

    async _confirmRequestUpdate() {
        const { farmerId, actor } = this._requestUpdateState;
        const issue = document.getElementById('requestUpdateIssueInput')?.value?.trim() || '';
        if (!issue) { this.showToast('Please describe the issue before sending.', 'error'); return; }
        const modal = document.getElementById('requestUpdateModal');
        if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
        try {
            if (actor === 'coop') {
                await api.coopRequestFarmerUpdate(farmerId, issue);
            } else {
                await api.adminRequestFarmerUpdate(farmerId, issue);
            }
            this.showToast('Update request sent to farmer via notification', 'success');
            await this.loadFarmerApprovals(document.getElementById('pageContent'));
        } catch(e) {
            this.showToast(`Error: ${e.message}`, 'error');
        }
    }

    _showFarmerDetailsModal(farmerId, actor) {
        const f = (this._farmersApprovalMap || {})[farmerId];
        if (!f) { this.showToast('Farmer data not found', 'error'); return; }

        const name = `${f.first_name || ''} ${f.last_name || ''}`.trim() || 'Unknown';
        const farmerName = name.replace(/'/g, "\\'");
        const kycData = f.kyc_data || {};
        const date = f.created_at ? new Date(f.created_at).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' }) : '—';

        const row = (label, value) => value
            ? `<div class="col-6 mb-3"><div class="text-muted small">${label}</div><div class="fw-semibold">${value}</div></div>`
            : '';

        const updateBanner = f.update_requested
            ? `<div class="alert alert-warning d-flex gap-2 align-items-start mb-3">
                   <i class="bi bi-exclamation-triangle-fill text-warning mt-1 flex-shrink-0"></i>
                   <div><strong>Update Requested</strong>${f.update_requested_by_name ? ` by ${f.update_requested_by_name}` : ''}<br><span class="small">${f.update_request_notes || ''}</span></div>
               </div>` : '';

        const old = document.getElementById('farmerDetailsModal');
        if (old) { bootstrap.Modal.getInstance(old)?.dispose(); old.remove(); }

        const el = document.createElement('div');
        el.innerHTML = `
            <div class="modal fade" id="farmerDetailsModal" tabindex="-1">
                <div class="modal-dialog modal-lg modal-dialog-scrollable">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-person-circle me-2 text-primary"></i>${name}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            ${updateBanner}
                            <h6 class="text-uppercase text-muted small fw-bold mb-3 border-bottom pb-2">Personal Information</h6>
                            <div class="row">
                                ${row('First Name', f.first_name)}
                                ${row('Last Name', f.last_name)}
                                ${row('Email', f.email)}
                                ${row('Phone', f.phone)}
                                ${row('National ID', f.national_id)}
                                ${row('Date of Birth', f.date_of_birth ? new Date(f.date_of_birth).toLocaleDateString('en-GB') : null)}
                                ${row('Gender', f.gender)}
                                ${row('Registered', date)}
                            </div>
                            <h6 class="text-uppercase text-muted small fw-bold mb-3 border-bottom pb-2 mt-2">Location</h6>
                            <div class="row">
                                ${row('County', f.county)}
                                ${row('Sub-County', f.subcounty)}
                                ${row('Ward', f.ward)}
                            </div>
                            ${kycData.cooperative_code ? `
                            <h6 class="text-uppercase text-muted small fw-bold mb-3 border-bottom pb-2 mt-2">Cooperative</h6>
                            <div class="row">
                                ${row('Cooperative Code', kycData.cooperative_code)}
                                ${row('Payout Method', kycData.payout_method)}
                                ${row('Payout ID / Account', kycData.payout_recipient_id || kycData.payout_account_number)}
                            </div>` : ''}
                            <h6 class="text-uppercase text-muted small fw-bold mb-3 border-bottom pb-2 mt-2">Verification Status</h6>
                            <div class="row">
                                ${row('Coop Status', f.coop_status || 'Pending')}
                                ${row('Admin Status', f.verification_status || 'Pending')}
                                ${f.coop_notes ? row('Coop Notes', f.coop_notes) : ''}
                                ${f.admin_notes ? row('Admin Notes', f.admin_notes) : ''}
                            </div>
                        </div>
                        <div class="modal-footer flex-wrap gap-2">
                            <button type="button" class="btn btn-secondary me-auto" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-outline-warning" onclick="app._showRequestUpdateModal('${farmerId}','${farmerName}','${actor}')">
                                <i class="bi bi-exclamation-triangle me-1"></i>Request Update
                            </button>
                            <button type="button" class="btn btn-outline-danger" onclick="app._showFarmerApprovalModal('${farmerId}','reject','${actor}')">
                                <i class="bi bi-x-lg me-1"></i>Reject
                            </button>
                            <button type="button" class="btn btn-success" onclick="app._showFarmerApprovalModal('${farmerId}','approve','${actor}')">
                                <i class="bi bi-check-lg me-1"></i>Approve
                            </button>
                        </div>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(el.firstElementChild);
        bootstrap.Modal.getOrCreateInstance(document.getElementById('farmerDetailsModal')).show();
    }

    _showFarmDetailsModal(farmId) {
        const f = (this._farmsApprovalMap || {})[farmId];
        if (!f) { this.showToast('Farm data not found', 'error'); return; }

        const actor = f._actor || 'coop';
        const isAdmin = actor === 'admin';
        const farmName = (f.farm_name || f.name || 'Unnamed Farm').replace(/'/g, "\\'");
        const date = f.created_at ? new Date(f.created_at).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' }) : '—';

        const row = (label, value) => value
            ? `<div class="col-6 mb-3"><div class="text-muted small">${label}</div><div class="fw-semibold">${value}</div></div>`
            : '';

        const coopStatusLabel = { coop_approved:'Coop Approved', coop_rejected:'Coop Rejected', update_requested:'Update Requested' }[f.coop_status] || 'Pending Coop Review';
        const verificationLabel = { verified:'Verified', rejected:'Rejected', pending:'Pending', draft:'Draft', coop_approved:'Coop Approved' }[f.verification_status] || f.verification_status || 'Draft';

        const updateBanner = f.update_requested
            ? `<div class="alert alert-warning d-flex gap-2 align-items-start mb-3">
                   <i class="bi bi-exclamation-triangle-fill text-warning mt-1 flex-shrink-0"></i>
                   <div><strong>Update Requested</strong>${f.update_requested_by_name ? ` by ${f.update_requested_by_name}` : ''}<br><span class="small">${f.update_request_notes || ''}</span></div>
               </div>` : '';

        const old = document.getElementById('farmDetailsModal');
        if (old) { bootstrap.Modal.getInstance(old)?.dispose(); old.remove(); }

        const el = document.createElement('div');
        el.innerHTML = `
            <div class="modal fade" id="farmDetailsModal" tabindex="-1">
                <div class="modal-dialog modal-lg modal-dialog-scrollable">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-geo-alt-fill me-2 text-success"></i>${f.farm_name || f.name || 'Unnamed Farm'}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            ${updateBanner}
                            <h6 class="text-uppercase text-muted small fw-bold mb-3 border-bottom pb-2">Farmer Identity</h6>
                            <div class="row">
                                ${row('Full Name', f.farmer_name)}
                                ${row('Phone', f.farmer_phone)}
                                ${row('National ID', f.farmer_national_id)}
                                ${row('Gender', f.farmer_gender)}
                                ${row('Coop Member No.', f.coop_member_no)}
                                ${row('Registered', date)}
                            </div>
                            <h6 class="text-uppercase text-muted small fw-bold mb-3 border-bottom pb-2 mt-2">Farm Basics</h6>
                            <div class="row">
                                ${row('Farm Name', f.farm_name || f.name)}
                                ${row('Location / Subcounty', f.farmer_location)}
                                ${row('Total Area', f.total_area_hectares ? f.total_area_hectares + ' ha' : null)}
                                ${row('Coffee Area', f.coffee_area_hectares ? f.coffee_area_hectares + ' ha' : null)}
                                ${row('Land Ownership', ({'owned':'Title Deed (Owned)','leased':'Lease Agreement','inherited':'Family Plot / Inherited','customary':'Customary Tenure','community':'Community Land','tenant':'Tenant'}[(f.parcels||[])[0]?.ownership_type] || (f.parcels||[])[0]?.ownership_type || '—'))}
                                ${row('Land Use Type', ({'agroforestry':'Agroforestry','monocrop':'Monocrop','mixed_cropping':'Mixed Cropping','forest_reserve':'Forest Reserve','buffer_zone':'Buffer Zone','other':'Other'}[f.land_use_type] || f.land_use_type || '—'))}
                            </div>
                            <h6 class="text-uppercase text-muted small fw-bold mb-3 border-bottom pb-2 mt-2">Coffee Production</h6>
                            <div class="row">
                                ${row('Coffee Varieties', Array.isArray(f.coffee_varieties) ? f.coffee_varieties.join(', ') : f.coffee_varieties)}
                                ${row('Years Farming', f.years_farming != null ? f.years_farming + ' yrs' : null)}
                                ${row('Est. Annual Yield', f.average_annual_production_kg != null ? f.average_annual_production_kg + ' kg' : null)}
                                ${row('Shade Trees', f.shade_trees_present ? 'Yes' : (f.shade_trees_present === false ? 'No' : null))}
                                ${row('Shade Canopy', f.shade_tree_canopy_percent != null ? f.shade_tree_canopy_percent + '%' : null)}
                            </div>
                            <h6 class="text-uppercase text-muted small fw-bold mb-3 border-bottom pb-2 mt-2">Verification Status</h6>
                            <div class="row">
                                ${row('Coop Status', coopStatusLabel)}
                                ${row('Admin Status', verificationLabel)}
                                ${row('Compliance', f.compliance_status)}
                                ${f.coop_notes ? row('Coop Notes', f.coop_notes) : ''}
                                ${f.admin_notes ? row('Admin Notes', f.admin_notes) : ''}
                            </div>
                        </div>
                        <div class="modal-footer flex-wrap gap-2">
                            <button type="button" class="btn btn-secondary me-auto" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-outline-warning" onclick="app._showFarmUpdateRequestModal('${farmId}','${farmName}','${actor}')">
                                <i class="bi bi-exclamation-triangle me-1"></i>Request Update
                            </button>
                            <button type="button" class="btn btn-outline-danger" onclick="app._farmDetailsReject('${farmId}',${isAdmin})">
                                <i class="bi bi-x-lg me-1"></i>Reject
                            </button>
                            <button type="button" class="btn btn-success" onclick="app._farmDetailsApprove('${farmId}',${isAdmin})">
                                <i class="bi bi-check-lg me-1"></i>Approve
                            </button>
                        </div>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(el.firstElementChild);
        bootstrap.Modal.getOrCreateInstance(document.getElementById('farmDetailsModal')).show();
    }

    _farmDetailsApprove(farmId, isAdmin) {
        const modal = document.getElementById('farmDetailsModal');
        if (modal) bootstrap.Modal.getInstance(modal)?.hide();
        if (isAdmin) {
            this.showVerificationApproveModal(farmId, true);
        } else {
            this.coopApproveFarm(farmId);
        }
    }

    _farmDetailsReject(farmId, isAdmin) {
        const modal = document.getElementById('farmDetailsModal');
        if (modal) bootstrap.Modal.getInstance(modal)?.hide();
        if (isAdmin) {
            this.showVerificationRejectModal(farmId, true);
        } else {
            this.coopRejectFarm(farmId);
        }
    }

    _showFarmUpdateRequestModal(farmId, farmName, actor) {
        this._farmUpdateRequestState = { farmId, actor };
        const old = document.getElementById('farmUpdateRequestModal');
        if (old) { bootstrap.Modal.getInstance(old)?.dispose(); old.remove(); }

        const el = document.createElement('div');
        el.innerHTML = `
            <div class="modal fade" id="farmUpdateRequestModal" tabindex="-1">
                <div class="modal-dialog modal-dialog-scrollable">
                    <div class="modal-content">
                        <div class="modal-header bg-warning bg-opacity-10 border-bottom-0">
                            <h5 class="modal-title"><i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>Request Farm Update</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p class="text-muted mb-3">Describe the issue with <strong>${farmName || 'this farm'}</strong> that the farmer needs to correct before you can approve. They will receive a notification with your message.</p>
                            <label class="form-label fw-semibold">Issue / Action Required <span class="text-danger">*</span></label>
                            <textarea id="farmUpdateRequestIssueInput" class="form-control" rows="4" placeholder="e.g. The farm boundary on the map appears incorrect. Please re-capture the farm polygon accurately."></textarea>
                            <div class="form-text">Be specific so the farmer knows exactly what to fix.</div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-warning" id="farmUpdateRequestConfirmBtn">
                                <i class="bi bi-send me-1"></i>Send Request
                            </button>
                        </div>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(el.firstElementChild);
        document.getElementById('farmUpdateRequestConfirmBtn').addEventListener('click', () => this._confirmFarmUpdateRequest());
        bootstrap.Modal.getOrCreateInstance(document.getElementById('farmUpdateRequestModal')).show();
    }

    async _confirmFarmUpdateRequest() {
        const { farmId, actor } = this._farmUpdateRequestState;
        const issue = document.getElementById('farmUpdateRequestIssueInput')?.value?.trim() || '';
        if (!issue) { this.showToast('Please describe the issue before sending.', 'error'); return; }
        const modal = document.getElementById('farmUpdateRequestModal');
        if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
        try {
            if (actor === 'coop') {
                await api.coopRequestFarmUpdate(farmId, issue);
            } else {
                await api.adminRequestFarmUpdate(farmId, issue);
            }
            this.showToast('Update request sent to farmer via notification', 'success');
            if (actor === 'coop') {
                await this.loadCoopFarmApprovals(document.getElementById('pageContent'));
            } else {
                await this.loadVerification(document.getElementById('pageContent'));
            }
        } catch(e) {
            this.showToast(`Error: ${e.message}`, 'error');
        }
    }

    async resubmitFarmForReview(farmId) {
        if (!confirm('Resubmit this farm for cooperative review? Make sure you have updated the necessary details first.')) return;
        try {
            await api.resubmitFarmForReview(farmId);
            this.showToast('Farm resubmitted for review. The cooperative officer has been notified.', 'success');
            await this.loadFarmerFarms();
        } catch(e) {
            this.showToast(`Error: ${e.message}`, 'error');
        }
    }

    async loadFarms(content, statusFilter = null) {
        const statusBadge = (s) => {
            const map = { draft: 'bg-secondary', pending: 'bg-warning text-dark', verified: 'bg-success', rejected: 'bg-danger' };
            return `<span class="badge ${map[s] || 'bg-secondary'} text-capitalize">${s || 'draft'}</span>`;
        };

        content.innerHTML = `
            <div class="row g-3 mb-4">
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Total Farms</div><h3 class="mb-0" id="stat-total">—</h3></div></div></div>
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Pending Review</div><h3 class="mb-0 text-warning" id="stat-pending">—</h3></div></div></div>
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Verified</div><h3 class="mb-0 text-success" id="stat-verified">—</h3></div></div></div>
                <div class="col-6 col-md-3"><div class="card text-center h-100"><div class="card-body py-3"><div class="text-muted small">Draft</div><h3 class="mb-0 text-secondary" id="stat-draft">—</h3></div></div></div>
            </div>
            <div class="card">
                <div class="card-header d-flex align-items-center flex-wrap gap-2">
                    <span class="fw-semibold me-2">Filter:</span>
                    <div class="d-flex gap-2 flex-wrap">
                        <button class="btn btn-sm ${!statusFilter ? 'btn-primary' : 'btn-outline-primary'}" onclick="app.loadFarms(document.getElementById('pageContent'), null)">All</button>
                        <button class="btn btn-sm ${statusFilter==='pending' ? 'btn-warning' : 'btn-outline-warning'}" onclick="app.loadFarms(document.getElementById('pageContent'), 'pending')">Pending</button>
                        <button class="btn btn-sm ${statusFilter==='verified' ? 'btn-success' : 'btn-outline-success'}" onclick="app.loadFarms(document.getElementById('pageContent'), 'verified')">Verified</button>
                        <button class="btn btn-sm ${statusFilter==='rejected' ? 'btn-danger' : 'btn-outline-danger'}" onclick="app.loadFarms(document.getElementById('pageContent'), 'rejected')">Rejected</button>
                        <button class="btn btn-sm ${statusFilter==='draft' ? 'btn-secondary' : 'btn-outline-secondary'}" onclick="app.loadFarms(document.getElementById('pageContent'), 'draft')">Draft</button>
                    </div>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0" style="min-width:700px">
                            <thead class="table-light">
                                <tr>
                                    <th>Farmer</th>
                                    <th>Farm Name</th>
                                    <th>Area</th>
                                    <th>Coop Status</th>
                                    <th>Status</th>
                                    <th>Registered</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="farms-admin-list">
                                <tr><td colspan="7" class="text-center py-4">Loading...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        try {
            const qs = statusFilter ? `?status_filter=${statusFilter}` : '';
            const response = await api.request(`/admin/farms${qs}`);
            const farms = response.farms || [];

            document.getElementById('stat-total').textContent = response.total || farms.length;
            Promise.all([
                api.request('/admin/farms?status_filter=pending'),
                api.request('/admin/farms?status_filter=verified'),
                api.request('/admin/farms?status_filter=draft'),
            ]).then(([p, v, d]) => {
                document.getElementById('stat-pending').textContent = p.total || 0;
                document.getElementById('stat-verified').textContent = v.total || 0;
                document.getElementById('stat-draft').textContent = d.total || 0;
            }).catch(() => {});

            const list = document.getElementById('farms-admin-list');
            if (farms.length > 0) {
                list.innerHTML = farms.map(f => {
                    const coopBadge = f.coop_status === 'coop_approved'
                        ? `<span class="badge bg-info text-dark">Coop ✓</span>`
                        : f.coop_status === 'coop_rejected'
                        ? `<span class="badge bg-danger">Coop ✗</span>`
                        : `<span class="badge bg-secondary bg-opacity-50">Awaiting Coop</span>`;
                    return `
                    <tr>
                        <td>
                            <div class="fw-semibold">${f.owner_name || 'N/A'}</div>
                            <div class="text-muted" style="font-size:.75rem">${f.owner_phone || ''}</div>
                        </td>
                        <td>
                            <div>${f.farm_name || 'Unnamed Farm'}</div>
                            <div class="text-muted" style="font-size:.75rem">${f.farm_code || ''}</div>
                        </td>
                        <td class="text-nowrap">${f.total_area_hectares ? f.total_area_hectares + ' ha' : '—'}</td>
                        <td>${coopBadge}</td>
                        <td>${statusBadge(f.verification_status)}</td>
                        <td class="text-muted" style="font-size:.8rem">${f.created_at ? new Date(f.created_at).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}) : '—'}</td>
                        <td>
                            <div class="d-flex gap-1 flex-wrap">
                                <button class="btn btn-sm btn-outline-primary" onclick="app.adminViewFarm('${f.id}')"><i class="bi bi-eye me-1"></i>View</button>
                                <button class="btn btn-sm btn-outline-info" onclick="app.requestSatelliteAnalysis('${f.id}')" ${!f.centroid_lat ? 'disabled title="No polygon captured for this farm"' : ''}><i class="bi bi-satellite-fill me-1"></i>Analyse</button>
                            </div>
                        </td>
                    </tr>`;
                }).join('');
            } else {
                list.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">No farms found${statusFilter ? ` with status "${statusFilter}"` : ''}</td></tr>`;
            }
        } catch (e) {
            console.error(e);
            this.showToast('Error loading farms', 'error');
        }
    }

    async adminViewFarm(farmId) {
        try {
            const f = await api.request(`/admin/farms/${farmId}`);
            const statusBadge = (s) => {
                const map = { draft: 'secondary', pending: 'warning', verified: 'success', rejected: 'danger' };
                return `<span class="badge bg-${map[s] || 'secondary'} text-${s==='pending'?'dark':''}">${s||'draft'}</span>`;
            };
            const modalEl = document.getElementById('viewFarmModal');
            const bodyEl = document.getElementById('farmDetailsContent');
            if (!modalEl || !bodyEl) { this.showToast('Modal not found', 'error'); return; }

            const ownershipLabel = {'owned':'Title Deed (Owned)','leased':'Lease Agreement','inherited':'Family Plot / Inherited','customary':'Customary Tenure','community':'Community Land','tenant':'Tenant'};
            const landUseLabel = {'agroforestry':'Agroforestry','monocrop':'Monocrop','mixed_cropping':'Mixed Cropping','forest_reserve':'Forest Reserve','buffer_zone':'Buffer Zone','other':'Other'};
            bodyEl.innerHTML = `
                <div class="row g-3">
                    <div class="col-12"><h6 class="text-primary border-bottom pb-1">Farmer Identity</h6></div>
                    <div class="col-md-6"><small class="text-muted d-block">Full Name</small><strong>${f.owner?.name || f.farmer_name || '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Phone</small><strong>${f.owner?.phone || f.farmer_phone || '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">National ID</small><strong>${f.owner?.national_id || f.farmer_national_id || '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Gender</small><strong>${f.owner?.gender || f.farmer_gender || '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Coop Member No.</small><strong>${f.membership?.membership_number || f.coop_member_no || '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Registered</small><strong>${f.created_at ? new Date(f.created_at).toLocaleDateString() : '—'}</strong></div>

                    <div class="col-12 mt-2"><h6 class="text-primary border-bottom pb-1">Farm Basics</h6></div>
                    <div class="col-md-6"><small class="text-muted d-block">Farm Name</small><strong>${f.farm_name || '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Location / Subcounty</small><strong>${f.owner?.subcounty || f.farmer_location || '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Total Area</small><strong>${f.total_area_hectares ? f.total_area_hectares + ' ha' : '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Coffee Area</small><strong>${f.coffee_area_hectares ? f.coffee_area_hectares + ' ha' : '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Land Ownership</small><strong>${ownershipLabel[(f.parcels||[])[0]?.ownership_type] || (f.parcels||[])[0]?.ownership_type || '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Land Use Type</small><strong>${landUseLabel[f.land_use_type] || f.land_use_type || '—'}</strong></div>

                    <div class="col-12 mt-2"><h6 class="text-primary border-bottom pb-1">Coffee Production</h6></div>
                    <div class="col-md-6"><small class="text-muted d-block">Coffee Varieties</small><strong>${(f.coffee_varieties||[]).join(', ') || '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Est. Annual Yield</small><strong>${f.average_annual_production_kg != null ? f.average_annual_production_kg + ' kg' : '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Years Farming</small><strong>${f.years_farming != null ? f.years_farming : '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Shade Trees</small><strong>${f.shade_trees_present ? 'Yes' : 'No'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Shade Canopy</small><strong>${f.shade_tree_canopy_percent != null ? f.shade_tree_canopy_percent + '%' : '—'}</strong></div>
                    <div class="col-md-6"><small class="text-muted d-block">Status</small>${statusBadge(f.verification_status)}</div>
                    <div class="col-md-6"><small class="text-muted d-block">Compliance</small><strong>${f.compliance_status || '—'}</strong></div>

                    ${f.parcels?.length ? `
                    <div class="col-12 mt-2"><h6 class="text-primary border-bottom pb-1">Parcels (${f.parcels.length})</h6></div>
                    ${f.parcels.map(p => `
                        <div class="col-md-6"><div class="border rounded p-2">
                            <div class="fw-bold">${p.parcel_name || 'Parcel '+p.parcel_number}</div>
                            <div class="text-muted small">${p.area_hectares ? p.area_hectares+' ha' : ''} · ${landUseLabel[p.land_use_type] || p.land_use_type || ''} · ${statusBadge(p.verification_status)}</div>
                            ${p.boundary_geojson ? '<div class="text-success small"><i class="bi bi-check-circle"></i> GPS polygon captured</div>' : '<div class="text-muted small"><i class="bi bi-circle"></i> No polygon</div>'}
                        </div></div>
                    `).join('')}
                    ` : '<div class="col-12 text-muted small">No parcels recorded</div>'}

                    ${f.verification_status === 'pending' ? `
                    <div class="col-12 mt-3 d-flex gap-2">
                        <button class="btn btn-success" onclick="app.adminApproveFarm('${f.id}');bootstrap.Modal.getInstance(document.getElementById('viewFarmModal'))?.hide()">
                            <i class="bi bi-check-lg me-1"></i> Approve Farm
                        </button>
                        <button class="btn btn-danger" onclick="app.adminRejectFarm('${f.id}');bootstrap.Modal.getInstance(document.getElementById('viewFarmModal'))?.hide()">
                            <i class="bi bi-x-lg me-1"></i> Reject Farm
                        </button>
                    </div>
                    ` : ''}
                </div>
            `;
            new bootstrap.Modal(modalEl).show();
        } catch(e) {
            this.showToast('Failed to load farm details', 'error');
        }
    }

    async adminApproveFarm(farmId) {
        try {
            await api.request(`/admin/farms/${farmId}/approve`, { method: 'PATCH' });
            this.showToast('Farm approved successfully', 'success');
            this.loadFarms(document.getElementById('pageContent'));
        } catch(e) {
            this.showToast('Failed to approve farm', 'error');
        }
    }

    async adminRejectFarm(farmId) {
        const reason = prompt('Reason for rejection (optional):') || '';
        try {
            await api.request(`/admin/farms/${farmId}/reject?reason=${encodeURIComponent(reason)}`, { method: 'PATCH' });
            this.showToast('Farm rejected', 'warning');
            this.loadFarms(document.getElementById('pageContent'));
        } catch(e) {
            this.showToast('Failed to reject farm', 'error');
        }
    }

    async loadWallet(content) {
        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-3">
                    <div class="card bg-primary text-white h-100">
                        <div class="card-body">
                            <h6 class="text-uppercase small mb-2 opacity-75">Platform Balance</h6>
                            <h2 class="mb-0" id="platform-balance">KES ...</h2>
                            <div class="mt-3 x-small-text opacity-75">Total funds in ecosystem</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card bg-success text-white h-100">
                        <div class="card-body">
                            <h6 class="text-uppercase small mb-2 opacity-75">Total Payouts</h6>
                            <h2 class="mb-0" id="total-payouts">KES ...</h2>
                            <div class="mt-3 x-small-text opacity-75">Processed this month</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card bg-info text-white h-100">
                        <div class="card-body">
                            <h6 class="text-uppercase small mb-2 opacity-75">Escrow Balance</h6>
                            <h2 class="mb-0" id="escrow-balance">KES ...</h2>
                            <div class="mt-3 x-small-text opacity-75">Pending verification</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card bg-warning text-white h-100">
                        <div class="card-body">
                            <h6 class="text-uppercase small mb-2 opacity-75">Pending Incentives</h6>
                            <h2 class="mb-0" id="pending-incentives">KES ...</h2>
                            <div class="mt-3 x-small-text opacity-75">Climate smart actions</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-lg-8">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between">
                            <h4 class="card-title">Recent Payments</h4>
                            <div class="dropdown">
                                <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown">All Roles</button>
                                <ul class="dropdown-menu">
                                    <li><a class="dropdown-item" href="#">Farmers</a></li>
                                    <li><a class="dropdown-item" href="#">Cooperatives</a></li>
                                </ul>
                            </div>
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>Recipient</th>
                                            <th>Type</th>
                                            <th>Amount</th>
                                            <th>Method</th>
                                            <th>Status</th>
                                            <th>Date</th>
                                        </tr>
                                    </thead>
                                    <tbody id="payments-list">
                                        <tr><td colspan="6" class="text-center py-4">Loading payments...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-lg-4">
                    <div class="card">
                        <div class="card-header">
                            <h4 class="card-title">Payment Trends</h4>
                        </div>
                        <div class="card-body">
                            <div id="payment-trends-chart" style="min-height: 300px;"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        try {
            const stats = await api.getWalletStats() || {};
            const platformBalanceEl = document.getElementById('platform-balance');
            if (platformBalanceEl) platformBalanceEl.textContent = `KES ${stats.platform_balance?.toLocaleString() || '0'}`;
            
            const totalPayoutsEl = document.getElementById('total-payouts');
            if (totalPayoutsEl) totalPayoutsEl.textContent = `KES ${stats.total_payouts?.toLocaleString() || '0'}`;
            
            const escrowBalanceEl = document.getElementById('escrow-balance');
            if (escrowBalanceEl) escrowBalanceEl.textContent = `KES ${stats.escrow_balance?.toLocaleString() || '0'}`;
            
            const pendingIncentivesEl = document.getElementById('pending-incentives');
            if (pendingIncentivesEl) pendingIncentivesEl.textContent = `KES ${stats.pending_incentives?.toLocaleString() || '0'}`;

            const payments = await api.getPayments();
            const list = document.getElementById('payments-list');
            
            if (payments && payments.length > 0) {
                list.innerHTML = payments.map(p => `
                    <tr>
                        <td><div class="fw-bold">${p.recipient_name}</div><div class="text-muted x-small-text">${p.recipient_role}</div></td>
                        <td><span class="small">${p.payment_type}</span></td>
                        <td class="fw-bold">KES ${p.amount?.toLocaleString()}</td>
                        <td><span class="badge bg-soft-dark text-dark">${p.method}</span></td>
                        <td><span class="badge ${p.status === 'completed' ? 'bg-soft-success text-success' : 'bg-soft-warning text-warning'}">${p.status}</span></td>
                        <td class="small">${new Date(p.created_at).toLocaleDateString()}</td>
                    </tr>
                `).join('');
            } else {
                list.innerHTML = '<tr><td colspan="6" class="text-center py-4">No recent payments</td></tr>';
            }

            if (typeof ApexCharts !== 'undefined') {
                const chartData = await api.getPaymentChartData() || { categories: [], values: [] };
                new ApexCharts(document.querySelector("#payment-trends-chart"), {
                    series: [{ name: 'Payouts', data: chartData.values || [30, 40, 35, 50, 49, 60] }],
                    chart: { type: 'line', height: 300, toolbar: { show: false } },
                    stroke: { curve: 'smooth', width: 3 },
                    colors: ['#6f4e37'],
                    xaxis: { categories: chartData.categories || ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'] },
                    grid: { strokeDashArray: 3 }
                }).render();
            }
        } catch (e) {
            console.error(e);
            this.showToast('Error loading wallet data', 'error');
        }
    }

    async loadParcels(content) {
        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h4 class="card-title">My Farm Parcels</h4>
                            <button class="btn btn-primary btn-sm" onclick="app.navigateTo('farms')">
                                <i class="bi bi-plus-lg me-1"></i> Add Parcel
                            </button>
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>Farm</th>
                                            <th>Parcel #</th>
                                            <th>Area (Ha)</th>
                                            <th>Risk Score</th>
                                            <th>Status</th>
                                            <th>Last Analysis</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody id="parcels-list">
                                        <tr><td colspan="7" class="text-center py-4">Loading parcels...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div id="parcel-map-container" class="row g-4 d-none">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h4 class="card-title">Parcel Boundary Map</h4>
                            <div id="parcel-meta-info" class="small"></div>
                        </div>
                        <div class="card-body">
                            <div id="parcel-map" style="height: 400px; border-radius: 8px;"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        try {
            const response = await api.getFarms();
            const farms = response.farms || [];
            const list = document.getElementById('parcels-list');
            let allParcels = [];
            
            farms.forEach(farm => {
                if (farm.parcels && farm.parcels.length > 0) {
                    farm.parcels.forEach(parcel => {
                        allParcels.push({
                            ...parcel,
                            farm_name: farm.farm_name,
                            farm_id: farm.id,
                            compliance_status: farm.compliance_status,
                            risk_score: farm.deforestation_risk_score
                        });
                    });
                }
            });

            if (allParcels.length > 0) {
                list.innerHTML = allParcels.map(p => `
                    <tr>
                        <td>${p.farm_name || 'Farm #'+p.farm_id}</td>
                        <td><span class="fw-bold">${p.parcel_number}</span></td>
                        <td>${p.area_hectares || 0} Ha</td>
                        <td>
                            <span class="badge ${p.risk_score > 70 ? 'bg-danger' : (p.risk_score > 30 ? 'bg-warning' : 'bg-success')}">
                                ${p.risk_score || 0}% Risk
                            </span>
                        </td>
                        <td><span class="badge bg-soft-info text-info">${p.land_use_type}</span></td>
                        <td class="small text-muted">${p.last_satellite_analysis ? new Date(p.last_satellite_analysis).toLocaleDateString() : 'Pending'}</td>
                        <td>
                            <button class="btn btn-sm btn-outline-primary" onclick="app.viewParcelMap('${p.id}')">
                                <i class="bi bi-geo-alt"></i> View Map
                            </button>
                            <button class="btn btn-sm btn-outline-info" onclick="app.loadMonitoring('${p.id}', 'parcel')">
                                <i class="bi bi-satellite"></i> Monitor
                            </button>
                        </td>
                    </tr>
                `).join('');
                
                // Store parcels for map viewing
                this.currentParcels = allParcels;
            } else {
                list.innerHTML = '<tr><td colspan="6" class="text-center py-4">No parcels found. Please add parcels to your farms.</td></tr>';
            }
        } catch (error) {
            console.error(error);
            list.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-danger">Error: ${error.message}</td></tr>`;
        }
    }

    viewParcelMap(parcelId) {
        const parcel = this.currentParcels.find(p => p.id == parcelId);
        if (!parcel || !parcel.boundary_geojson) {
            this.showToast('No boundary data available for this parcel', 'warning');
            return;
        }

        const mapContainer = document.getElementById('parcel-map-container');
        mapContainer.classList.remove('d-none');
        
        document.getElementById('parcel-meta-info').innerHTML = `
            <span class="badge bg-soft-primary text-primary me-2">Code: ${parcel.parcel_number}</span>
            <span class="badge bg-soft-success text-success me-2">Area: ${parcel.area_hectares} Ha</span>
            <span class="badge ${parcel.risk_score > 70 ? 'bg-soft-danger text-danger' : 'bg-soft-success text-success'}">Risk: ${parcel.risk_score || 0}%</span>
        `;

        // Initialize Leaflet map if not already done
        if (!this.parcelMap) {
            const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: 'Esri'
            });
            const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap'
            });

            this.parcelMap = L.map('parcel-map', {
                center: [0, 0],
                zoom: 2,
                layers: [satellite]
            });

            L.control.layers({ "Satellite": satellite, "OpenStreetMap": osm }).addTo(this.parcelMap);
        }

        // Clear existing layers
        if (this.currentLayer) {
            this.parcelMap.removeLayer(this.currentLayer);
        }

        try {
            this.currentLayer = L.geoJSON(parcel.boundary_geojson, {
                style: {
                    color: parcel.risk_score > 70 ? '#c03221' : '#1aa053',
                    weight: 3,
                    fillOpacity: 0.2
                }
            }).addTo(this.parcelMap);
            this.parcelMap.fitBounds(this.currentLayer.getBounds());
            
            mapContainer.scrollIntoView({ behavior: 'smooth' });
        } catch (e) {
            console.error('Error rendering GeoJSON:', e);
            this.showToast('Invalid boundary data', 'error');
        }
    }
    async loadMonitoring(id, type) {
        const content = document.getElementById('page-content');
        if (!content) return;

        // Set current page to 'monitoring' so navigation state is preserved
        this.currentPage = 'monitoring';

        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-12">
                    <div class="card shadow-sm border-0 overflow-hidden">
                        <div class="card-header bg-dark text-white d-flex justify-content-between align-items-center py-3">
                            <h4 class="card-title mb-0">
                                <i class="bi bi-satellite me-2 text-info"></i> 
                                Farm Monitoring Console: <span id="monitor-title" class="text-info">Loading...</span>
                            </h4>
                            <div class="d-flex gap-2">
                                <button class="btn btn-sm btn-light" onclick="app.takeScreenshot()">
                                    <i class="bi bi-camera me-1"></i> Screenshot
                                </button>
                                <button class="btn btn-sm btn-outline-light" onclick="app.navigateTo('${type === 'farm' ? 'farms' : 'parcels'}')">
                                    <i class="bi bi-arrow-left me-1"></i> Back
                                </button>
                            </div>
                        </div>
                        <div class="card-body p-0 position-relative" id="capture-area">
                            <div id="monitoring-map" style="height: 600px; width: 100%;"></div>
                            
                            <!-- Floating Stats Overlay -->
                            <div class="position-absolute bottom-0 start-0 m-3 z-index-1000 bg-dark text-white p-3 rounded shadow-lg border border-secondary" style="opacity: 0.9; min-width: 250px;">
                                <h6 class="text-uppercase small border-bottom border-secondary pb-2 mb-3">Live Analysis</h6>
                                <div class="mb-2 d-flex justify-content-between">
                                    <span class="text-muted small">NDVI Health:</span>
                                    <span id="monitor-ndvi" class="fw-bold text-success">0.78 (Optimal)</span>
                                </div>
                                <div class="mb-2 d-flex justify-content-between">
                                    <span class="text-muted small">Tree Canopy:</span>
                                    <span id="monitor-canopy" class="fw-bold text-info">65% Coverage</span>
                                </div>
                                <div class="mb-2 d-flex justify-content-between">
                                    <span class="text-muted small">Soil Moisture:</span>
                                    <span id="monitor-moisture" class="fw-bold text-warning">Medium</span>
                                </div>
                                <div class="mb-0 d-flex justify-content-between">
                                    <span class="text-muted small">Risk Alert:</span>
                                    <span id="monitor-risk" class="badge bg-success">Low Risk</span>
                                </div>
                            </div>

                            <!-- Floating Tools Overlay -->
                            <div class="position-absolute top-0 end-0 m-3 z-index-1000 d-flex flex-column gap-2">
                                <div class="bg-white p-2 rounded shadow-sm border">
                                    <div class="form-check form-switch small">
                                        <input class="form-check-input" type="checkbox" id="layerDeforestation" checked>
                                        <label class="form-check-label" for="layerDeforestation">Deforestation Layer</label>
                                    </div>
                                    <div class="form-check form-switch small mt-2">
                                        <input class="form-check-input" type="checkbox" id="layerBuildings">
                                        <label class="form-check-label" for="layerBuildings">Structure Detection</label>
                                    </div>
                                    <div class="form-check form-switch small mt-2">
                                        <input class="form-check-input" type="checkbox" id="layerCadastral">
                                        <label class="form-check-label" for="layerCadastral">Cadastral View</label>
                                    </div>
                                </div>
                                <button class="btn btn-primary btn-sm shadow" onclick="app.showToast('Starting real-time monitoring update...', 'info')">
                                    <i class="bi bi-play-fill me-1"></i> Start Live Sync
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-md-4">
                    <div class="card h-100">
                        <div class="card-header"><h5 class="card-title mb-0">Farm Metadata</h5></div>
                        <div class="card-body" id="monitor-details">
                            <div class="text-center py-4 text-muted small">Loading details...</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-8">
                    <div class="card h-100">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h5 class="card-title mb-0">Environmental Trends</h5>
                            <select class="form-select form-select-sm w-auto">
                                <option>Last 3 Months</option>
                                <option>Last Year</option>
                            </select>
                        </div>
                        <div class="card-body">
                            <div id="monitoring-trend-chart" style="height: 250px;"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        try {
            let data;
            if (type === 'farm') {
                data = await api.getFarm(id);
                document.getElementById('monitor-title').textContent = data.farm_name || data.name || 'Unnamed Farm';
            } else {
                const response = await api.getFarms();
                const farms = response.farms || [];
                data = null;
                for (const f of farms) {
                    const p = f.parcels?.find(p => p.id == id);
                    if (p) {
                        data = p;
                        data.farm_name = f.farm_name;
                        break;
                    }
                }
                document.getElementById('monitor-title').textContent = `Parcel ${data?.parcel_number || id} (${data?.farm_name || 'N/A'})`;
            }

            if (!data) throw new Error('Resource not found');

            // Initialize Map
            const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Esri' });
            const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' });
            
            this.monitorMap = L.map('monitoring-map', {
                center: [0, 0],
                zoom: 2,
                layers: [satellite]
            });

            L.control.layers({ "High Res Satellite": satellite, "Street View": osm }).addTo(this.monitorMap);

            // Add boundary
            const boundary = type === 'farm' ? data.boundary_geojson : data.boundary_geojson;
            if (boundary) {
                const layer = L.geoJSON(boundary, {
                    style: { color: '#00d2ff', weight: 4, fillOpacity: 0.1, dashArray: '5, 5' }
                }).addTo(this.monitorMap);
                this.monitorMap.fitBounds(layer.getBounds());
            }

            // Fill details
            document.getElementById('monitor-details').innerHTML = `
                <ul class="list-group list-group-flush">
                    <li class="list-group-item d-flex justify-content-between"><span>Area:</span> <strong>${data.total_area || data.area_hectares || 0} Ha</strong></li>
                    <li class="list-group-item d-flex justify-content-between"><span>County:</span> <strong>${data.county || 'N/A'}</strong></li>
                    <li class="list-group-item d-flex justify-content-between"><span>Land Use:</span> <strong>${data.land_use_type || 'Agroforestry'}</strong></li>
                    <li class="list-group-item d-flex justify-content-between"><span>DDS Status:</span> <span class="badge bg-success">Valid</span></li>
                    <li class="list-group-item d-flex justify-content-between"><span>Last Scan:</span> <strong>${new Date().toLocaleDateString()}</strong></li>
                </ul>
                <div class="mt-3">
                    <button class="btn btn-sm btn-outline-primary w-100" onclick="app.showToast('Generating full report...', 'info')">
                        <i class="bi bi-file-pdf me-1"></i> Export Full Report
                    </button>
                </div>
            `;

            // Render Chart
            if (typeof ApexCharts !== 'undefined') {
                new ApexCharts(document.querySelector("#monitoring-trend-chart"), {
                    series: [{
                        name: 'Health Index (NDVI)',
                        data: [0.65, 0.68, 0.72, 0.70, 0.75, 0.78]
                    }, {
                        name: 'Canopy Coverage',
                        data: [58, 60, 61, 62, 64, 65]
                    }],
                    chart: { height: 250, type: 'area', toolbar: { show: false } },
                    colors: ['#1aa053', '#00d2ff'],
                    dataLabels: { enabled: false },
                    stroke: { curve: 'smooth', width: 2 },
                    xaxis: { categories: ['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'] }
                }).render();
            }

        } catch (e) {
            console.error(e);
            this.showToast('Error loading monitoring console', 'error');
        }
    }

    takeScreenshot() {
        const target = document.getElementById('capture-area');
        if (!target) return;

        this.showToast('Capturing monitoring console...', 'info');
        
        html2canvas(target, {
            useCORS: true,
            allowTaint: true,
            backgroundColor: '#000',
            scale: 2 // Higher quality
        }).then(canvas => {
            const link = document.createElement('a');
            link.download = `plotra-monitor-${new Date().getTime()}.png`;
            link.href = canvas.toDataURL('image/png');
            link.click();
            this.showToast('Screenshot saved!', 'success');
        }).catch(err => {
            console.error('Screenshot error:', err);
            this.showToast('Failed to take screenshot', 'error');
        });
    }

    async loadDeliveries(content) {
        const role = (this.currentUser?.role || '').toUpperCase();
        const isCoop = ['COOPERATIVE_OFFICER', 'FACTOR', 'COOP_ADMIN', 'COOP_OFFICER'].includes(role);
        const isAdmin = ['PLATFORM_ADMIN', 'SUPER_ADMIN', 'ADMIN', 'PLOTRA_ADMIN'].includes(role);
        const isFarmer = !isCoop && !isAdmin;

        const headerLabel = isCoop ? 'Farm Deliveries — Monitoring' : isAdmin ? 'All Deliveries' : 'My Deliveries';
        const cols = isCoop || isAdmin
            ? `<th>Delivery #</th><th>Farmer</th><th>Farm</th><th>Gross (kg)</th><th>Net (kg)</th><th>Grade</th><th>Moisture</th><th>Status</th><th>Date</th>`
            : `<th>Delivery #</th><th>Farm</th><th>Net Weight</th><th>Grade</th><th>Status</th><th>Date</th>`;
        const colspan = isCoop || isAdmin ? 9 : 6;

        content.innerHTML = `
            <div class="row g-4 mb-4">
                ${isCoop ? `
                <div class="col-md-3"><div class="card border-0 shadow-sm text-center"><div class="card-body py-3">
                    <div class="text-muted small text-uppercase mb-1">Total Deliveries</div>
                    <h3 class="mb-0" id="deliv-total">—</h3>
                </div></div></div>
                <div class="col-md-3"><div class="card border-0 shadow-sm text-center"><div class="card-body py-3">
                    <div class="text-muted small text-uppercase mb-1">Total Weight (kg)</div>
                    <h3 class="mb-0 text-success" id="deliv-weight">—</h3>
                </div></div></div>
                <div class="col-md-3"><div class="card border-0 shadow-sm text-center"><div class="card-body py-3">
                    <div class="text-muted small text-uppercase mb-1">Pending</div>
                    <h3 class="mb-0 text-warning" id="deliv-pending">—</h3>
                </div></div></div>
                <div class="col-md-3"><div class="card border-0 shadow-sm text-center"><div class="card-body py-3">
                    <div class="text-muted small text-uppercase mb-1">Processed</div>
                    <h3 class="mb-0 text-primary" id="deliv-processed">—</h3>
                </div></div></div>
                ` : ''}
                <div class="col-12">
                    <div class="card border-0 shadow-sm">
                        <div class="card-header d-flex justify-content-between align-items-center" style="background:linear-gradient(135deg,#2c1a0e,#6f4e37);color:white;">
                            <h5 class="mb-0"><i class="bi bi-box-seam me-2"></i>${headerLabel}</h5>
                            ${isCoop ? `
                            <button class="btn btn-sm" style="background:#daa520;color:#3d2515;" onclick="app.showRecordDeliveryModal()">
                                <i class="bi bi-plus-circle me-1"></i>Record Delivery
                            </button>` : ''}
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead class="table-light">
                                        <tr>${cols}</tr>
                                    </thead>
                                    <tbody id="deliveries-list">
                                        <tr><td colspan="${colspan}" class="text-center py-4">
                                            <div class="spinner-border spinner-border-sm me-2"></div>Loading deliveries...
                                        </td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        try {
            const deliveries = await api.getDeliveries();
            const list = document.getElementById('deliveries-list');

            if (isCoop) {
                const total = deliveries.length;
                const weight = deliveries.reduce((s, d) => s + (d.net_weight_kg || 0), 0);
                const pending = deliveries.filter(d => d.status?.toLowerCase() === 'pending').length;
                const processed = deliveries.filter(d => ['received','processed','completed'].includes(d.status?.toLowerCase())).length;
                document.getElementById('deliv-total').textContent = total;
                document.getElementById('deliv-weight').textContent = weight.toFixed(1);
                document.getElementById('deliv-pending').textContent = pending;
                document.getElementById('deliv-processed').textContent = processed;
            }

            if (deliveries && deliveries.length > 0) {
                list.innerHTML = deliveries.map(d => {
                    const sc = this.getDeliveryStatusClass(d.status);
                    if (isCoop || isAdmin) {
                        return `<tr>
                            <td class="fw-semibold">${d.delivery_number || 'D-'+d.id}</td>
                            <td>${d.farmer_name || d.farmer_id || '—'}</td>
                            <td>${d.farm_name || 'Farm #'+d.farm_id}</td>
                            <td>${d.gross_weight_kg || 0}</td>
                            <td class="fw-bold">${d.net_weight_kg || 0}</td>
                            <td><span class="badge bg-soft-primary text-primary">${d.quality_grade || 'N/A'}</span></td>
                            <td>${d.moisture_content ? d.moisture_content+'%' : '—'}</td>
                            <td><span class="badge ${sc}">${d.status || 'pending'}</span></td>
                            <td>${new Date(d.created_at).toLocaleDateString()}</td>
                        </tr>`;
                    } else {
                        return `<tr>
                            <td class="fw-semibold">${d.delivery_number || 'D-'+d.id}</td>
                            <td>${d.farm_name || 'Farm #'+d.farm_id}</td>
                            <td class="fw-bold">${d.net_weight_kg || 0} kg</td>
                            <td><span class="badge bg-soft-primary text-primary">${d.quality_grade || 'N/A'}</span></td>
                            <td><span class="badge ${sc}">${d.status || 'pending'}</span></td>
                            <td>${new Date(d.created_at).toLocaleDateString()}</td>
                        </tr>`;
                    }
                }).join('');
            } else {
                list.innerHTML = `<tr><td colspan="${colspan}" class="text-center py-5 text-muted">
                    <i class="bi bi-box-seam fs-2 d-block mb-2"></i>No deliveries found.</td></tr>`;
            }
        } catch (error) {
            console.error(error);
            const list = document.getElementById('deliveries-list');
            if (list) list.innerHTML = `<tr><td colspan="${colspan}" class="text-center py-4 text-danger">Error: ${error.message}</td></tr>`;
        }
    }

    getDeliveryStatusClass(status) {
        const s = status?.toLowerCase();
        if (s === 'received' || s === 'completed' || s === 'processed') return 'bg-soft-success text-success';
        if (s === 'pending' || s === 'weighed') return 'bg-soft-warning text-warning';
        if (s === 'rejected') return 'bg-soft-danger text-danger';
        return 'bg-soft-secondary text-secondary';
    }

    async showRecordDeliveryModal() {
        try {
            // Load coop members (farmers) into the farmer dropdown
            const members = await api.request('/coop/members', { optional: true, default: [] });
            const farmerSelect = document.getElementById('deliveryFarmer');
            if (farmerSelect) {
                farmerSelect.innerHTML = '<option value="">— select farmer —</option>' +
                    (members || []).map(m => `<option value="${m.id}">${m.full_name || m.first_name+' '+m.last_name} (${m.phone || m.email || m.id})</option>`).join('');
            }
            document.getElementById('deliveryFarm').innerHTML = '<option value="">— select farm —</option>';
            const modalEl = document.getElementById('addDeliveryModal');
            if (modalEl) new bootstrap.Modal(modalEl).show();
        } catch (error) {
            this.showToast('Failed to load members: ' + error.message, 'error');
        }
    }

    async loadFarmerFarms(farmerId) {
        const farmSelect = document.getElementById('deliveryFarm');
        if (!farmerId || !farmSelect) return;
        farmSelect.innerHTML = '<option value="">Loading...</option>';
        try {
            const resp = await api.request(`/admin/farmers/${farmerId}/farms`, { optional: true, default: [] });
            const farms = Array.isArray(resp) ? resp : (resp?.farms || []);
            farmSelect.innerHTML = '<option value="">— select farm —</option>' +
                farms.map(f => `<option value="${f.id}">${f.farm_name || 'Farm #'+f.id}</option>`).join('');
        } catch {
            // Fallback: load all farms and let coop pick
            farmSelect.innerHTML = '<option value="">— no farms found —</option>';
        }
    }

    calcNetWeight() {
        const gross = parseFloat(document.getElementById('deliveryGrossWeight')?.value) || 0;
        const tare  = parseFloat(document.getElementById('deliveryTareWeight')?.value) || 0;
        const netEl = document.getElementById('deliveryNetWeight');
        if (netEl) netEl.value = Math.max(0, gross - tare).toFixed(2);
    }

    async handleRecordDelivery() {
        try {
            const gross = parseFloat(document.getElementById('deliveryGrossWeight').value) || 0;
            const tare  = parseFloat(document.getElementById('deliveryTareWeight').value) || 0;
            const data = {
                farm_id: document.getElementById('deliveryFarm').value,
                quality_grade: document.getElementById('deliveryGrade').value,
                gross_weight_kg: gross,
                tare_weight_kg: tare,
                moisture_content: parseFloat(document.getElementById('deliveryMoisture').value) || null,
                cherry_type: document.getElementById('deliveryCherryType').value || null,
                picking_date: document.getElementById('deliveryPickingDate').value || null,
            };
            if (!data.farm_id) { this.showToast('Please select a farm', 'warning'); return; }
            if (!gross) { this.showToast('Gross weight is required', 'warning'); return; }

            await api.recordDelivery(data);
            this.showToast('Delivery recorded successfully!', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('addDeliveryModal'));
            if (modal) modal.hide();
            if (this.currentPage === 'deliveries') this.loadPage('deliveries');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async showCreateBatchModal() {
        try {
            const deliveries = await api.getDeliveries({ status: 'received' });
            const deliveryContainer = document.getElementById('batchDeliveries');
            if (deliveryContainer) {
                if (deliveries.length > 0) {
                    deliveryContainer.innerHTML = deliveries.map(d => `
                        <div class="form-check">
                            <input class="form-check-input batch-delivery-check" type="checkbox" value="${d.id}" id="delivery-${d.id}">
                            <label class="form-check-label" for="delivery-${d.id}">
                                ${d.delivery_number} - ${d.net_weight_kg}kg (${d.quality_grade})
                            </label>
                 </div>
              `).join('');
        }
        }
    } catch (error) {
            this.showToast('Failed to load deliveries: ' + error.message, 'error');
        }
    }

    async handleCreateBatch() {
        try {
            const checkedDeliveries = Array.from(document.querySelectorAll('.batch-delivery-check:checked')).map(cb => parseInt(cb.value));
            if (checkedDeliveries.length === 0) {
                this.showToast('Please select at least one delivery', 'warning');
                return;
            }

            const data = {
                batch_number: 'BAT-' + Date.now(),
                crop_year: new Date().getFullYear(),
                quality_grade: document.getElementById('batchGrade').value,
                delivery_ids: checkedDeliveries
            };

            await api.createBatch(data);
            this.showToast('Batch created successfully', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('createBatchModal'));
            if (modal) modal.hide();
            if (this.currentPage === 'batches') this.loadPage('batches');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async handleGenerateDDS() {
        try {
            // Get selected farm IDs
            const farmSelect = document.getElementById('ddsFarmIds');
            const selectedOptions = Array.from(farmSelect.selectedOptions);
            const farmIds = selectedOptions.map(option => parseInt(option.value));

            const data = {
                operator_name: document.getElementById('ddsOperatorName').value,
                operator_id: document.getElementById('ddsOperatorId').value,
                contact_name: document.getElementById('ddsContactName').value,
                contact_email: document.getElementById('ddsContactEmail').value,
                contact_address: document.getElementById('ddsContactAddress').value,
                commodity_type: document.getElementById('ddsCommodityType').value,
                hs_code: document.getElementById('ddsHSCode').value,
                country_of_origin: document.getElementById('ddsCountry').value,
                quantity: parseFloat(document.getElementById('ddsQuantity').value),
                unit: document.getElementById('ddsUnit').value,
                supplier_name: document.getElementById('ddsSupplierName').value,
                supplier_country: document.getElementById('ddsSupplierCountry').value,
                first_placement_country: document.getElementById('ddsFirstPlacementCountry').value,
                first_placement_date: document.getElementById('ddsFirstPlacementDate').value || null,
                farm_ids: farmIds
            };

            await api.generateDDS(data);
            this.showToast('DDS generated successfully', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('generateDDSModal'));
            if (modal) modal.hide();
            if (this.currentPage === 'compliance') this.loadPage('compliance');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async showAddParcelModal(farmId) {
        this.currentFarmIdForParcel = farmId;
        this.drawnItems = new L.FeatureGroup();
        this.parcelGeoJSON = null;
        
        const modalEl = document.getElementById('addParcelModal');
        if (modalEl) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
            
            // Wait for modal animation to finish before initializing map
            setTimeout(() => this.initParcelDrawMap(), 500);
        }
    }

    initParcelDrawMap() {
        if (this.drawMap) {
            this.drawMap.remove();
        }

        this.walkPoints = [];
        this.walkLayer = L.polyline([], { color: '#1aa053', weight: 3 }).addTo(this.drawnItems);
        this.walkMarkers = L.layerGroup().addTo(this.drawMap || this.drawnItems);

        const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
        });

        const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        });

        this.drawMap = L.map('parcelDrawMap', {
            center: [-1.286389, 36.817223], // Default to Kenya (Nairobi) area
            zoom: 13,
            layers: [satellite]
        });

        const baseMaps = {
            "Satellite": satellite,
            "OpenStreetMap": osm
        };

        L.control.layers(baseMaps).addTo(this.drawMap);
        this.drawMap.addLayer(this.drawnItems);

        const drawControl = new L.Control.Draw({
            edit: {
                featureGroup: this.drawnItems
            },
            draw: {
                polygon: {
                    allowIntersection: false,
                    showArea: true,
                    drawError: {
                        color: '#e1e100',
                        message: '<strong>Error:</strong> Boundary cannot overlap itself!'
                    },
                    shapeOptions: {
                        color: '#6f4e37'
                    }
                },
                polyline: false,
                circle: false,
                circlemarker: false,
                marker: false,
                rectangle: false
            }
        });

        this.drawMap.addControl(drawControl);

        this.drawMap.on(L.Draw.Event.CREATED, (e) => {
            const layer = e.layer;
            this.drawnItems.clearLayers();
            this.drawnItems.addLayer(layer);
            
            this.parcelGeoJSON = layer.toGeoJSON();
            
            // Calculate area in hectares
            const areaM2 = L.GeometryUtil.geodesicArea(layer.getLatLngs()[0]);
            const areaHa = (areaM2 / 10000).toFixed(2);
            
            document.getElementById('parcelArea').value = areaHa;
            document.getElementById('saveParcelBtn').disabled = false;
        });
    }

    startWalking() {
        if (!navigator.geolocation) {
            this.showToast('Geolocation is not supported by your browser', 'error');
            return;
        }

        this.walkPoints = [];
        this.drawnItems.clearLayers();
        this.walkLayer = L.polyline([], { color: '#1aa053', weight: 3, dashArray: '5, 10' }).addTo(this.drawnItems);
        
        document.getElementById('btnStartWalking').classList.add('d-none');
        document.getElementById('btnCapturePoint').classList.remove('d-none');
        document.getElementById('btnStopWalking').classList.remove('d-none');
        
        this.showToast('Walking mode started. Click "Capture Point" at each corner of the farm.', 'success');
        
        // Track current position visually
        this.watchId = navigator.geolocation.watchPosition(
            (pos) => {
                const latlng = [pos.coords.latitude, pos.coords.longitude];
                if (!this.userMarker) {
                    this.userMarker = L.circleMarker(latlng, { radius: 8, color: '#6f4e37', fillOpacity: 0.8 }).addTo(this.drawMap);
                } else {
                    this.userMarker.setLatLng(latlng);
                }
                this.drawMap.panTo(latlng);
            },
            (err) => console.error(err),
            { enableHighAccuracy: true }
        );
    }

    capturePoint() {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const latlng = [pos.coords.latitude, pos.coords.longitude];
                this.walkPoints.push(latlng);
                
                // Update line and add marker
                this.walkLayer.setLatLngs(this.walkPoints);
                L.circleMarker(latlng, { radius: 4, color: '#1aa053' }).addTo(this.drawnItems);
                
                this.showToast(`Point #${this.walkPoints.length} captured`, 'info');
                
                if (this.walkPoints.length >= 3) {
                    document.getElementById('saveParcelBtn').disabled = false;
                }
            },
            (err) => this.showToast('Failed to capture point: ' + err.message, 'error'),
            { enableHighAccuracy: true }
        );
    }

    stopWalking() {
        if (this.watchId) {
            navigator.geolocation.clearWatch(this.watchId);
        }
        
        if (this.walkPoints.length < 3) {
            this.showToast('Need at least 3 points to form a parcel', 'warning');
            return;
        }

        // Close the polygon
        const polygonPoints = [...this.walkPoints, this.walkPoints[0]];
        const polygon = L.polygon(this.walkPoints, { color: '#6f4e37' }).addTo(this.drawnItems);
        this.parcelGeoJSON = polygon.toGeoJSON();
        
        // Calculate area
        const areaM2 = L.GeometryUtil.geodesicArea(polygon.getLatLngs()[0]);
        const areaHa = (areaM2 / 10000).toFixed(2);
        document.getElementById('parcelArea').value = areaHa;

        document.getElementById('btnStartWalking').classList.remove('d-none');
        document.getElementById('btnCapturePoint').classList.add('d-none');
        document.getElementById('btnStopWalking').classList.add('d-none');
        
        this.showToast('Walking boundary completed and closed.', 'success');
    }

    async handleAddParcel() {
        try {
            if (!this.currentFarmIdForParcel || !this.parcelGeoJSON) {
                this.showToast('Please draw the parcel boundary on the map', 'error');
                return;
            }

            const data = {
                parcel_number: document.getElementById('parcelCode').value,
                area_hectares: parseFloat(document.getElementById('parcelArea').value),
                land_use_type: document.getElementById('parcelLandUse').value,
                boundary_geojson: this.parcelGeoJSON
            };

            this.showToast('Saving parcel and syncing with satellite data...', 'info');
            await api.addParcel(this.currentFarmIdForParcel, data);
            
            this.showToast('Parcel mapped and saved successfully', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('addParcelModal'));
            if (modal) modal.hide();
            
            if (this.currentPage === 'parcels') this.loadPage('parcels');
            else if (this.currentPage === 'farms') this.loadPage('farms');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }
    
    async saveParcelEUDR(parcelId, farmId) {
        try {
            const getMultiSelectValues = (selectId) => {
                const select = document.getElementById(selectId);
                if (!select) return [];
                return Array.from(select.selectedOptions).map(opt => opt.value);
            };
            
            const getCheckboxValue = (checkboxId) => {
                const checkbox = document.getElementById(checkboxId);
                return checkbox && checkbox.checked ? 1 : 0;
            };
            
            const data = {
                parcel_name: document.getElementById(`parcelName_${parcelId}`)?.value,
                land_registration_number: document.getElementById(`landRegNumber_${parcelId}`)?.value,
                altitude_meters: parseFloat(document.getElementById(`altitude_${parcelId}`)?.value) || null,
                soil_type: document.getElementById(`soilType_${parcelId}`)?.value || null,
                terrain_slope: document.getElementById(`terrainSlope_${parcelId}`)?.value || null,
                ownership_type: document.getElementById(`ownershipType_${parcelId}`)?.value || null,
                year_coffee_first_planted: parseInt(document.getElementById(`yearPlanted_${parcelId}`)?.value) || null,
                estimated_coffee_plants: parseInt(document.getElementById(`coffeePlants_${parcelId}`)?.value) || null,
                farm_status: document.getElementById(`farmStatus_${parcelId}`)?.value || null,
                planting_method: document.getElementById(`plantingMethod_${parcelId}`)?.value || null,
                irrigation_type: document.getElementById(`irrigation_${parcelId}`)?.value || null,
                coffee_area_hectares: parseFloat(document.getElementById(`coffeeArea_${parcelId}`)?.value) || null,
                practice_mixed_farming: document.getElementById(`mixedFarming_${parcelId}`)?.value ? parseInt(document.getElementById(`mixedFarming_${parcelId}`).value) : null,
                other_crops: getMultiSelectValues(`otherCrops_${parcelId}`),
                livestock_on_parcel: document.getElementById(`livestock_${parcelId}`)?.value ? parseInt(document.getElementById(`livestock_${parcelId}`).value) : null,
                livestock_type: getMultiSelectValues(`livestockType_${parcelId}`),
                coffee_percentage: parseInt(document.getElementById(`coffeePercent_${parcelId}`)?.value) || null,
                crop_rotation_practiced: document.getElementById(`cropRotation_${parcelId}`)?.value ? parseInt(document.getElementById(`cropRotation_${parcelId}`).value) : null,
                trees_planted_last_5_years: document.getElementById(`treesPlanted_${parcelId}`)?.value ? parseInt(document.getElementById(`treesPlanted_${parcelId}`).value) : null,
                tree_species_planted: getMultiSelectValues(`treeSpecies_${parcelId}`),
                trees_planted_count: parseInt(document.getElementById(`treesCount_${parcelId}`)?.value) || null,
                reason_for_planting: getMultiSelectValues(`plantingReason_${parcelId}`),
                trees_cleared_last_5_years: document.getElementById(`treesCleared_${parcelId}`)?.value ? parseInt(document.getElementById(`treesCleared_${parcelId}`).value) : null,
                reason_for_clearing: document.getElementById(`clearingReason_${parcelId}`)?.value || null,
                canopy_cover: document.getElementById(`canopyCover_${parcelId}`)?.value || null,
                consent_satellite_monitoring: getCheckboxValue(`consentSatellite_${parcelId}`),
                consent_historical_imagery: getCheckboxValue(`consentHistorical_${parcelId}`),
                monitoring_frequency: document.getElementById(`monitorFreq_${parcelId}`)?.value || null,
                certifications: getMultiSelectValues(`certifications_${parcelId}`),
                certificate_expiry_date: document.getElementById(`certExpiry_${parcelId}`)?.value || null,
                previously_flagged: document.getElementById(`previouslyFlagged_${parcelId}`)?.value ? parseInt(document.getElementById(`previouslyFlagged_${parcelId}`).value) : null,
                cooperative_registration_number: document.getElementById(`coopRegNum_${parcelId}`)?.value || null
            };
            
            await api.updateParcel(farmId, parcelId, data);
            this.showToast('Parcel EUDR details saved successfully!', 'success');
            
            if (this.currentPage === 'profile') {
                this.loadProfile(document.getElementById('pageContent'));
            }
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }
    async loadBatches(content) {
        const role = (this.currentUser?.role || '').toUpperCase();
        const isCoop = ['COOPERATIVE_OFFICER', 'FACTOR', 'COOP_ADMIN', 'COOP_OFFICER'].includes(role);
        const isAdmin = ['PLATFORM_ADMIN', 'SUPER_ADMIN', 'ADMIN', 'PLOTRA_ADMIN'].includes(role);

        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h4 class="card-title">Processing Batches</h4>
                            ${(isCoop || isAdmin) ? `
                                <button class="btn btn-primary btn-sm" onclick="app.showCreateBatchModal()">
                                    <i class="bi bi-plus-lg me-1"></i> Create Batch
                                </button>
                            ` : ''}
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>Batch #</th>
                                            <th>Year</th>
                                            <th>Weight</th>
                                            <th>Grade</th>
                                            <th>Compliance</th>
                                            <th>Date</th>
                                        </tr>
                                    </thead>
                                    <tbody id="batches-list">
                                        <tr><td colspan="6" class="text-center py-4">Loading batches...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        try {
            const batches = await api.getBatches();
            const list = document.getElementById('batches-list');
            
            if (batches && batches.length > 0) {
                list.innerHTML = batches.map(b => `
                    <tr>
                        <td><span class="fw-bold">${b.batch_number}</span></td>
                        <td>${b.crop_year}</td>
                        <td class="fw-bold">${b.total_weight_kg || 0} kg</td>
                        <td><span class="badge bg-soft-primary text-primary">${b.quality_grade || 'N/A'}</span></td>
                        <td><span class="badge ${b.compliance_status === 'Compliant' ? 'bg-soft-success text-success' : 'bg-soft-warning text-warning'}">${b.compliance_status}</span></td>
                        <td>${new Date(b.created_at).toLocaleDateString()}</td>
                    </tr>
                `).join('');
            } else {
                list.innerHTML = '<tr><td colspan="6" class="text-center py-4">No batches found.</td></tr>';
            }
        } catch (error) {
            console.error(error);
            list.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-danger">Error: ${error.message}</td></tr>`;
        }
    }

    showCreateBatchModal() {
        this.showToast('Batch creation modal would open here', 'info');
    }
    async loadVerification(content) {
        const role = (this.currentUser?.role || '').toUpperCase();
        const isAdmin = ['PLATFORM_ADMIN', 'SUPER_ADMIN', 'ADMIN', 'PLOTRA_ADMIN', 'EUDR_REVIEWER'].includes(role);
        const isCoop = ['COOPERATIVE_OFFICER', 'FACTOR', 'COOP_ADMIN'].includes(role);

        if (!isAdmin && !isCoop) {
            content.innerHTML = `<div class="alert alert-warning">You do not have permission to view this page.</div>`;
            return;
        }

        const pageTitle = isAdmin ? 'Farms Pending Admin Approval' : 'Farms Pending Cooperative Review';

        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h4 class="card-title">${pageTitle}</h4>
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>Farm</th>
                                            <th>Farmer</th>
                                            <th>Location</th>
                                            <th>Area (Ha)</th>
                                            ${isAdmin ? '<th>Coop Review</th>' : ''}
                                            <th>Submitted</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody id="verifications-list">
                                        <tr><td colspan="7" class="text-center py-4">Loading pending verifications...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const list = document.getElementById('verifications-list');
        try {
            let farms = [];
            if (isAdmin) {
                const raw = await api.getPendingVerifications();
                farms = Array.isArray(raw) ? raw : (raw?.farms || raw?.verifications || []);
            } else {
                const raw = await api.getCoopPendingFarms();
                farms = Array.isArray(raw) ? raw : (raw?.farms || []);
            }

            if (farms.length > 0) {
                const cols = isAdmin ? 7 : 6;
                this._farmsApprovalMap = this._farmsApprovalMap || {};
                farms.forEach(f => { this._farmsApprovalMap[f.id] = { ...f, _actor: isAdmin ? 'admin' : 'coop' }; });

                list.innerHTML = farms.map(f => {
                    const coopBadge = f.coop_status === 'coop_approved'
                        ? `<span class="badge bg-success">Coop Approved</span>`
                        : f.coop_status === 'coop_rejected'
                        ? `<span class="badge bg-danger">Coop Rejected</span>`
                        : `<span class="badge bg-secondary">Awaiting Coop</span>`;
                    return `
                    <tr>
                        <td>
                            <div class="fw-bold">${f.farm_name || f.name || 'Unnamed Farm'}</div>
                            <div class="text-muted small">${f.crop_type || ''}</div>
                            ${f.update_requested ? `<span class="badge bg-warning text-dark mt-1"><i class="bi bi-exclamation-triangle me-1"></i>Update Requested</span>` : ''}
                        </td>
                        <td>
                            <div>${f.farmer_name || 'N/A'}</div>
                            <div class="text-muted small">${f.farmer_phone || ''}</div>
                        </td>
                        <td>${f.sub_county || f.county || 'N/A'}</td>
                        <td>${f.total_area_hectares || '—'}</td>
                        ${isAdmin ? `<td>${coopBadge}${f.coop_approver ? `<div class="text-muted small mt-1">by ${f.coop_approver}</div>` : ''}</td>` : ''}
                        <td>${f.created_at ? new Date(f.created_at).toLocaleDateString() : 'N/A'}</td>
                        <td>
                            <button class="btn btn-sm btn-outline-primary" onclick="app._showFarmDetailsModal('${f.id}')">
                                <i class="bi bi-eye me-1"></i>View
                            </button>
                        </td>
                    </tr>`;
                }).join('');
            } else {
                list.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">No pending verifications found.</td></tr>`;
            }
        } catch (error) {
            console.error(error);
            list.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Error: ${error.message}</td></tr>`;
        }
    }

    showVerificationApproveModal(farmId, isAdmin) {
        this._verificationAction = { farmId, isAdmin, type: 'approve' };
        document.getElementById('verificationReasonLabel').textContent = 'Approval Notes (optional)';
        document.getElementById('verificationReasonInput').value = '';
        document.getElementById('verificationModalTitle').textContent = 'Approve Farm';
        const confirmBtn = document.getElementById('verificationModalConfirmBtn');
        confirmBtn.className = 'btn btn-success btn-sm';
        confirmBtn.textContent = 'Confirm Approval';
        confirmBtn.onclick = () => app.confirmVerificationAction();
        bootstrap.Modal.getOrCreateInstance(document.getElementById('verificationReasonModal')).show();
    }

    showVerificationRejectModal(farmId, isAdmin) {
        this._verificationAction = { farmId, isAdmin, type: 'reject' };
        document.getElementById('verificationReasonLabel').textContent = 'Reason for Rejection (required)';
        document.getElementById('verificationReasonInput').value = '';
        document.getElementById('verificationModalTitle').textContent = 'Reject Farm';
        const confirmBtn = document.getElementById('verificationModalConfirmBtn');
        confirmBtn.className = 'btn btn-danger btn-sm';
        confirmBtn.textContent = 'Confirm Rejection';
        confirmBtn.onclick = () => app.confirmVerificationAction();
        bootstrap.Modal.getOrCreateInstance(document.getElementById('verificationReasonModal')).show();
    }

    async confirmVerificationAction() {
        const { farmId, isAdmin, type } = this._verificationAction || {};
        if (!farmId) return;
        const reason = document.getElementById('verificationReasonInput').value.trim();
        if (type === 'reject' && !reason) {
            this.showToast('Please provide a reason for rejection', 'error');
            return;
        }
        bootstrap.Modal.getInstance(document.getElementById('verificationReasonModal'))?.hide();
        try {
            if (isAdmin) {
                if (type === 'approve') {
                    await api.approveVerification(farmId, { notes: reason });
                } else {
                    await api.rejectVerification(farmId, { notes: reason });
                }
            } else {
                if (type === 'approve') {
                    await api.coopApproveFarm(farmId, reason);
                } else {
                    await api.coopRejectFarm(farmId, reason);
                }
            }
            const label = type === 'approve' ? 'approved' : 'rejected';
            this.showToast(`Farm ${label} successfully`, type === 'approve' ? 'success' : 'warning');
            this.loadPage('verification');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async loadNotifications() {
        const body = document.getElementById('notificationsModalBody');
        if (body) body.innerHTML = `<div class="text-center py-4"><div class="spinner-border spinner-border-sm text-primary"></div></div>`;
        try {
            const notifs = await api.getNotifications();
            const list = Array.isArray(notifs) ? notifs : [];
            const unread = list.filter(n => !n.is_read).length;

            const badge = document.getElementById('notifBadge');
            if (badge) {
                if (unread > 0) {
                    badge.textContent = unread > 99 ? '99+' : unread;
                    badge.classList.remove('d-none');
                } else {
                    badge.classList.add('d-none');
                }
            }

            if (!body) return;

            if (list.length === 0) {
                body.innerHTML = `
                    <div class="text-center py-5 text-muted">
                        <i class="bi bi-bell-slash fs-1 d-block mb-2 opacity-50"></i>
                        No notifications available
                    </div>`;
                return;
            }

            body.innerHTML = list.map(n => {
                const iconBg = n.type === 'success' ? 'bg-success' : n.type === 'error' ? 'bg-danger' : n.type === 'warning' ? 'bg-warning' : 'bg-primary';
                const icon = n.type === 'success' ? 'bi-check-circle' : n.type === 'error' ? 'bi-x-circle' : n.type === 'warning' ? 'bi-exclamation-triangle' : 'bi-bell';
                const timeAgo = this._timeAgo(n.created_at);
                return `
                <div class="d-flex align-items-start p-3 border-bottom ${n.is_read ? 'opacity-75' : 'bg-light bg-opacity-50'}"
                     style="cursor:pointer" onclick="app.markNotifRead('${n.id}', this)">
                    <div class="${iconBg} bg-opacity-15 rounded-circle d-flex align-items-center justify-content-center me-3"
                         style="width:38px;height:38px;flex-shrink:0">
                        <i class="bi ${icon} ${iconBg.replace('bg-','text-')}"></i>
                    </div>
                    <div class="flex-grow-1">
                        <div class="d-flex justify-content-between align-items-start">
                            <h6 class="mb-1 fw-semibold" style="font-size:0.85rem">${n.title}</h6>
                            ${!n.is_read ? '<span class="bg-primary rounded-circle ms-2" style="width:8px;height:8px;flex-shrink:0;margin-top:4px;display:inline-block"></span>' : ''}
                        </div>
                        <p class="mb-1 text-muted" style="font-size:0.82rem">${n.message}</p>
                        <small class="text-muted">${timeAgo}</small>
                    </div>
                </div>`;
            }).join('');
        } catch (e) {
            console.warn('Could not load notifications:', e.message);
            if (body) body.innerHTML = `<div class="text-center py-4 text-muted small">Could not load notifications</div>`;
        }
    }

    async markNotifRead(id, el) {
        try {
            await api.markNotificationRead(id);
            if (el) {
                el.classList.remove('bg-light', 'bg-opacity-50');
                el.classList.add('opacity-75');
                const dot = el.querySelector('.bg-primary.rounded-circle');
                if (dot) dot.remove();
            }
            const badge = document.getElementById('notifBadge');
            if (badge && !badge.classList.contains('d-none')) {
                const current = parseInt(badge.textContent) || 0;
                if (current <= 1) badge.classList.add('d-none');
                else badge.textContent = current - 1;
            }
        } catch (e) {}
    }

    _timeAgo(dateStr) {
        if (!dateStr) return '';
        const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000);
        if (diff < 60) return 'Just now';
        if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
        return `${Math.floor(diff/86400)}d ago`;
    }
    async loadSatellite(content) {
        const role = (this.currentUser?.role || '').toUpperCase();
        const canAnalyze = ['PLATFORM_ADMIN', 'SUPER_ADMIN', 'ADMIN', 'PLOTRA_ADMIN', 'EUDR_REVIEWER'].includes(role);

        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h4 class="card-title">Satellite Deforestation Analysis</h4>
                            ${canAnalyze ? `
                                <button class="btn btn-primary btn-sm" onclick="app.triggerGlobalSatelliteAnalysis()">
                                    <i class="bi bi-broadcast me-1"></i> Run Global Analysis
                                </button>
                            ` : ''}
                        </div>
                        <div class="card-body">
                            <div class="row g-4 mb-4" id="satellite-stats">
                                <div class="col-md-4">
                                    <div class="p-3 border rounded bg-light">
                                        <h6 class="text-muted small mb-1">Total Analyzed</h6>
                                        <h4 id="sat-total">...</h4>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="p-3 border rounded bg-soft-danger">
                                        <h6 class="text-danger small mb-1">High Risk Detected</h6>
                                        <h4 id="sat-high-risk">...</h4>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="p-3 border rounded bg-soft-success">
                                        <h6 class="text-success small mb-1">Compliant (No Deforestation)</h6>
                                        <h4 id="sat-compliant">...</h4>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>Farm Name</th>
                                            <th>Risk Score</th>
                                            <th>Status</th>
                                            <th>Last Analysis</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody id="satellite-list">
                                        <tr><td colspan="5" class="text-center py-4">Loading risk report...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        try {
            const report = await api.getRiskReport();
            const list = document.getElementById('satellite-list');
            
            document.getElementById('sat-total').textContent = report.total_farms || 0;
            document.getElementById('sat-high-risk').textContent = report.high_risk_count || 0;
            document.getElementById('sat-compliant').textContent = report.low_risk_count || 0;

            if (report.farms && report.farms.length > 0) {
                list.innerHTML = report.farms.map(f => `
                    <tr>
                        <td class="fw-bold">${f.farm_name}</td>
                        <td>
                            <div class="d-flex align-items-center">
                                <span class="me-2">${f.risk_score}%</span>
                                <div class="progress flex-grow-1" style="height: 4px; min-width: 100px;">
                                    <div class="progress-bar ${f.risk_score > 70 ? 'bg-danger' : (f.risk_score > 30 ? 'bg-warning' : 'bg-success')}" 
                                         style="width: ${f.risk_score}%"></div>
                                </div>
                            </div>
                        </td>
                        <td><span class="badge ${f.compliance_status === 'Compliant' ? 'bg-soft-success text-success' : 'bg-soft-warning text-warning'}">${f.compliance_status}</span></td>
                        <td class="small">${f.last_analysis ? new Date(f.last_analysis).toLocaleString() : 'Never'}</td>
                        <td>
                            <button class="btn btn-sm btn-outline-primary" onclick="app.analyzeSingleFarm('${f.id}')">
                                <i class="bi bi-play-fill"></i> Analyze
                            </button>
                        </td>
                    </tr>
                `).join('');
            } else {
                list.innerHTML = '<tr><td colspan="5" class="text-center py-4">No farms found in risk report.</td></tr>';
            }
        } catch (error) {
            console.error(error);
            list.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-danger">Error: ${error.message}</td></tr>`;
        }
    }

    async analyzeSingleFarm(farmId) {
        try {
            // We need parcel IDs for analysis
            const farm = await api.getFarms({ id: farmId });
            const parcelIds = farm[0]?.parcels?.map(p => p.id) || [];
            
            if (parcelIds.length === 0) {
                this.showToast('No parcels found for this farm to analyze', 'warning');
                return;
            }

            this.showToast('Starting analysis for ' + parcelIds.length + ' parcels...', 'info');
            await api.triggerSatelliteAnalysis(parcelIds);
            this.showToast('Analysis complete', 'success');
            this.loadPage('satellite');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }
    async loadCompliance(content) {
        const role = (this.currentUser?.role || '').toUpperCase();
        console.log('loadCompliance - User role:', role);
        
        // Farmers get simplified view
        if (role === 'FARMER') {
            console.log('loadCompliance - Loading farmer compliance view');
            await this.loadFarmerCompliance(content);
        } else {
            console.log('loadCompliance - Loading admin compliance view');
            await this.loadAdminCompliance(content);
        }
    }
    
    async loadFarmerCompliance(content) {
        // Guard against null content
        if (!content) {
            console.error('loadFarmerCompliance: content is null');
            return;
        }
        
        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h4 class="card-title">My EUDR Compliance Status</h4>
                        </div>
                        <div class="card-body">
                            <div class="alert alert-info">
                                <i class="bi bi-info-circle me-2"></i>
                                As a farmer, your compliance is tracked through your farm registrations and deliveries.
                            </div>
                            <div id="farmer-compliance-status">
                                <div class="text-center py-4">Loading compliance data...</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        try {
            const response = await api.getFarms();
            const farms = response.farms || [];
            const farmList = Array.isArray(farms) ? farms : (farms ? [farms] : []);
            const statusDiv = document.getElementById('farmer-compliance-status');
            
            // Guard against null statusDiv
            if (!statusDiv) {
                console.error('loadFarmerCompliance: statusDiv is null');
                return;
            }
            
            if (farmList.length > 0) {
                let compliantFarms = 0;
                let pendingFarms = 0;
                let nonCompliantFarms = 0;
                
                farmList.forEach(farm => {
                    const status = farm.compliance_status || 'pending';
                    if (status === 'compliant') compliantFarms++;
                    else if (status === 'non_compliant') nonCompliantFarms++;
                    else pendingFarms++;
                });
                
                statusDiv.innerHTML = `
                    <div class="row g-3">
                        <div class="col-md-4">
                            <div class="card bg-success-subtle border-success">
                                <div class="card-body text-center">
                                    <h3 class="mb-0">${compliantFarms}</h3>
                                    <p class="mb-0 text-success">Compliant</p>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="card bg-warning-subtle border-warning">
                                <div class="card-body text-center">
                                    <h3 class="mb-0">${pendingFarms}</h3>
                                    <p class="mb-0 text-warning">Pending</p>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="card bg-danger-subtle border-danger">
                                <div class="card-body text-center">
                                    <h3 class="mb-0">${nonCompliantFarms}</h3>
                                    <p class="mb-0 text-danger">Non-Compliant</p>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                statusDiv.innerHTML = `<div class="text-center py-4"><p class="text-muted">No farms registered yet.</p></div>`;
            }
        } catch (error) {
            console.error('loadFarmerCompliance error:', error);
            const statusDiv = document.getElementById('farmer-compliance-status');
            if (statusDiv) {
                statusDiv.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        ${error.message || 'Unable to load compliance data. Please try again later.'}
                        <br><small class="text-muted">Make sure you have registered your farm first.</small>
                    </div>
                `;
            }
        }
    }
    
    async loadAdminCompliance(content) {
        const role = (this.currentUser?.role || '').toUpperCase();
        const isAdmin = ['PLATFORM_ADMIN', 'SUPER_ADMIN', 'ADMIN', 'PLOTRA_ADMIN', 'EUDR_REVIEWER'].includes(role);
        
        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h4 class="card-title">EUDR Due Diligence Statements (DDS)</h4>
                            ${isAdmin ? `
                                <button class="btn btn-primary btn-sm" onclick="app.showGenerateDDSModal()">
                                    <i class="bi bi-file-earmark-plus me-1"></i> Generate DDS
                                </button>
                            ` : ''}
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>DDS Number</th>
                                            <th>Operator</th>
                                            <th>Commodity</th>
                                            <th>Quantity</th>
                                            <th>Risk Level</th>
                                            <th>Status</th>
                                            <th>Date</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody id="dds-list">
                                        <tr><td colspan="8" class="text-center py-4">Loading statements...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        try {
            // Fetch all DDS
            const response = await api.getDDSList();
            const ddsList = response.dds || [];
            const list = document.getElementById('dds-list');
            
            if (ddsList.length > 0) {
                list.innerHTML = ddsList.map(dds => `
                    <tr>
                        <td><a href="#" onclick="app.viewDDS('${dds.id}')">${dds.dds_number}</a></td>
                        <td>${dds.operator_name}</td>
                        <td>${dds.commodity_type}</td>
                        <td>${dds.quantity} ${dds.unit}</td>
                        <td><span class="badge bg-${this.getRiskBadgeClass(dds.risk_level)}">${dds.risk_level.toUpperCase()}</span></td>
                        <td><span class="badge bg-${this.getStatusBadgeClass(dds.submission_status)}">${dds.submission_status}</span></td>
                        <td>${new Date(dds.created_at).toLocaleDateString()}</td>
                        <td>
                            <button class="btn btn-sm btn-outline-primary" onclick="app.exportDDS('${dds.id}')">
                                <i class="bi bi-download"></i> Export
                            </button>
                        </td>
                    </tr>
                `).join('');
            } else {
                list.innerHTML = '<tr><td colspan="8" class="text-center py-4">No Due Diligence Statements found.</td></tr>';
            }
            
        } catch (error) {
            console.error(error);
            const list = document.getElementById('dds-list');
            list.innerHTML = `<tr><td colspan="8" class="text-center py-4 text-danger">Error: ${error.message}</td></tr>`;
        }
    }

    getRiskBadgeClass(riskLevel) {
        switch (riskLevel.toLowerCase()) {
            case 'low': return 'success';
            case 'medium': return 'warning';
            case 'high': return 'danger';
            default: return 'secondary';
        }
    }

    getStatusBadgeClass(status) {
        switch (status.toLowerCase()) {
            case 'draft': return 'secondary';
            case 'submitted': return 'primary';
            case 'approved': return 'success';
            case 'rejected': return 'danger';
            default: return 'secondary';
        }
    }

    async showGenerateDDSModal() {
        // Populate farm dropdown
        const farmSelect = document.getElementById('ddsFarmIds');
        try {
            const response = await api.getFarms();
            const farms = response.farms || [];
            farmSelect.innerHTML = '';
            farms.forEach(farm => {
                const option = document.createElement('option');
                option.value = farm.id;
                option.textContent = farm.farm_name || `Farm ${farm.id}`;
                farmSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading farms:', error);
            farmSelect.innerHTML = '<option value="">Failed to load farms</option>';
        }
        
        const modalEl = document.getElementById('generateDDSModal');
        if (modalEl) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
        }
    }

    async viewDDS(ddsId) {
        try {
            const dds = await api.getDDS(ddsId);
            const content = document.getElementById('viewDDSContent');
            
            // Build detailed view
            const farmCoords = dds.farm_coordinates || [];
            const evidence = dds.evidence_references || [];
            const mitigation = dds.mitigation_measures || [];
            
            content.innerHTML = `
                <div class="row">
                    <div class="col-md-6">
                        <h6 class="text-primary"><i class="bi bi-info-circle"></i> DDS Information</h6>
                        <table class="table table-borderless table-sm">
                            <tr><td><strong>DDS Number:</strong></td><td>${dds.dds_number}</td></tr>
                            <tr><td><strong>Version:</strong></td><td>${dds.version}</td></tr>
                            <tr><td><strong>Operator:</strong></td><td>${dds.operator_name} ${dds.operator_id ? '('+dds.operator_id+')' : ''}</td></tr>
                            <tr><td><strong>Contact:</strong></td><td>${dds.contact_name || '-'}<br>${dds.contact_email || '-'}<br>${dds.contact_address || ''}</td></tr>
                            <tr><td><strong>Commodity:</strong></td><td>${dds.commodity_type} (HS: ${dds.hs_code || '-'})</td></tr>
                            <tr><td><strong>Quantity:</strong></td><td>${dds.quantity} ${dds.unit}</td></tr>
                            <tr><td><strong>Origin:</strong></td><td>${dds.country_of_origin}</td></tr>
                            <tr><td><strong>Supplier:</strong></td><td>${dds.supplier_name || '-'}<br>${dds.supplier_country || ''}</td></tr>
                            <tr><td><strong>First Placement:</strong></td><td>${dds.first_placement_country || '-'}<br>${dds.first_placement_date ? new Date(dds.first_placement_date).toLocaleDateString() : '-'}</td></tr>
                            <tr><td><strong>Risk Level:</strong></td><td><span class="badge bg-${this.getRiskBadgeClass(dds.risk_level)}">${dds.risk_level.toUpperCase()}</span></td></tr>
                            <tr><td><strong>Status:</strong></td><td><span class="badge bg-${this.getStatusBadgeClass(dds.submission_status)}">${dds.submission_status}</span></td></tr>
                            <tr><td><strong>Created:</strong></td><td>${new Date(dds.created_at).toLocaleString()}</td></tr>
                        </table>
                    </div>
                    <div class="col-md-6">
                        <h6 class="text-primary"><i class="bi bi-geo-alt"></i> Farm Coordinates (${farmCoords.length})</h6>
                        ${farmCoords.length > 0 ? `
                            <ul class="list-group list-group-flush mb-3">
                                ${farmCoords.map(fc => `
                                    <li class="list-group-item">
                                        <strong>${fc.name}</strong><br>
                                        Lat: ${fc.lat.toFixed(6)}, Lon: ${fc.lon.toFixed(6)}
                                    </li>
                                `).join('')}
                            </ul>
                        ` : '<p class="text-muted">No farm coordinates linked.</p>'}
                        
                        <h6 class="text-primary mt-3"><i class="bi bi-shield-check"></i> Mitigation Measures</h6>
                        <ul class="list-group list-group-flush">
                            ${mitigation.length > 0 ? mitigation.map(m => `<li class="list-group-item">${m}</li>`).join('') : '<li class="list-group-item">None specified</li>'}
                        </ul>
                        
                        <h6 class="text-primary mt-3"><i class="bi bi-journal-text"></i> Evidence References</h6>
                        <ul class="list-group list-group-flush">
                            ${evidence.length > 0 ? evidence.map(e => `<li class="list-group-item">${e}</li>`).join('') : '<li class="list-group-item">None recorded</li>'}
                        </ul>
                    </div>
                </div>
            `;
            
            // Store current DDS ID for export
            this.currentViewedDDSId = ddsId;
            
            // Wire export button
            const exportBtn = document.getElementById('btnExportDDSFromView');
            if (exportBtn) {
                exportBtn.onclick = () => this.exportDDS(ddsId);
            }
            
            // Show modal
            const modalEl = document.getElementById('viewDDSModal');
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        } catch (error) {
            this.showToast(error.message || 'Failed to load DDS', 'error');
        }
    }

    async exportDDS(ddsId) {
        try {
            this.showToast('Generating XML export...', 'info');
            await api.exportDDS(ddsId);
            // File download is handled directly by the API method
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    };
    async loadDocuments(content) {
        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h4 class="card-title">KYC & Land Documents</h4>
                            <button class="btn btn-primary btn-sm" onclick="app.showUploadDocumentModal()">
                                <i class="bi bi-upload me-1"></i> Upload Document
                            </button>
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>Title</th>
                                            <th>Farm</th>
                                            <th>Type</th>
                                            <th>Ownership</th>
                                            <th>Status</th>
                                            <th>Date</th>
                                        </tr>
                                    </thead>
                                    <tbody id="documents-list">
                                        <tr><td colspan="6" class="text-center py-4">Loading documents...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        try {
            const documents = await api.getDocuments();
            const list = document.getElementById('documents-list');
            
            if (documents && documents.length > 0) {
                list.innerHTML = documents.map(d => `
                    <tr>
                        <td><div class="fw-bold">${d.title}</div><div class="text-muted x-small-text">${d.description || ''}</div></td>
                        <td>Farm #${d.farm_id}</td>
                        <td><span class="badge bg-soft-info text-info">${d.document_type.replace(/_/g, ' ')}</span></td>
                        <td>${d.ownership_type}</td>
                        <td>
                            <span class="badge ${d.verification_status === 'verified' ? 'bg-soft-success text-success' : (d.verification_status === 'rejected' ? 'bg-soft-danger text-danger' : 'bg-soft-warning text-warning')}">
                                ${d.verification_status}
                            </span>
                        </td>
                        <td>${new Date(d.created_at).toLocaleDateString()}</td>
                    </tr>
                `).join('');
            } else {
                list.innerHTML = '<tr><td colspan="6" class="text-center py-4">No documents uploaded yet.</td></tr>';
            }
        } catch (error) {
            console.error(error);
            list.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-danger">Error: ${error.message}</td></tr>`;
        }
    }

    getProfileCompletionStatus(user, farms) {
        const requiredFields = [
            'phone', 'id_number', 'date_of_birth', 'gender', 
            'county', 'ward'
        ];
        const missingFields = requiredFields.filter(f => !user || !user[f]);
        
        let farmComplete = 0;
        if (farms && farms.length > 0) {
            for (const farm of farms) {
                if (farm.ownership_type && farm.land_use_type) {
                    farmComplete++;
                }
            }
        }
        
        return {
            isComplete: missingFields.length === 0 && farmComplete > 0,
            missingUserFields: missingFields,
            farmComplete: farmComplete,
            totalFarms: farms?.length || 0
        };
    }

    async loadProfile(content) {
        const user = this.currentUser;
        try {
            const farmsResponse = await api.getFarms();
            const raw = farmsResponse?.farms ?? farmsResponse ?? [];
            const farmArray = Array.isArray(raw) ? raw : (raw ? [raw] : []);
            const kyc = user?.kyc_data || {};
            const photoSrc = user?.profile_photo_url || this._pendingProfilePhoto ||
                `https://ui-avatars.com/api/?name=${encodeURIComponent(user?.full_name || user?.first_name || 'U')}&background=6f4e37&color=fff&size=120`;

            const updateRequested = user?.update_requested;
        const updateNotes = user?.update_request_notes || '';
        const updateBy = user?.update_requested_by_name || 'your cooperative officer';

        content.innerHTML = `
                ${updateRequested ? `
                <div class="alert alert-warning border-warning d-flex gap-3 align-items-start mb-4 shadow-sm" style="border-left:5px solid #ffc107!important;">
                    <i class="bi bi-exclamation-triangle-fill text-warning fs-4 mt-1 flex-shrink-0"></i>
                    <div class="flex-grow-1">
                        <div class="fw-bold mb-1">Action Required — Update Requested by ${updateBy}</div>
                        <p class="mb-2">${updateNotes || 'Please review and update your profile details, then resubmit for approval.'}</p>
                        <div class="d-flex gap-2 flex-wrap">
                            <button class="btn btn-sm btn-warning fw-semibold" onclick="app.enableProfileEdit()">
                                <i class="bi bi-pencil me-1"></i>Edit Profile Now
                            </button>
                            <button class="btn btn-sm btn-success fw-semibold" id="resubmitBtn" onclick="app.resubmitForReview()">
                                <i class="bi bi-send-check me-1"></i>Resubmit for Review
                            </button>
                        </div>
                    </div>
                </div>` : ''}
                <div class="row g-4">
                    <!-- Profile Card -->
                    <div class="col-12">
                        <div class="card border-0 shadow-sm">
                            <div class="card-header d-flex justify-content-between align-items-center" style="background:linear-gradient(135deg,#2c1a0e,#6f4e37);color:white;">
                                <h5 class="mb-0"><i class="bi bi-person-circle me-2"></i>My Profile</h5>
                                <button class="btn btn-sm" style="background:#daa520;color:#3d2515;" onclick="app.enableProfileEdit()">
                                    <i class="bi bi-pencil me-1"></i>Edit
                                </button>
                            </div>
                            <div class="card-body">
                                <form id="profileForm">
                                    <div class="row g-4">
                                        <!-- Photo column -->
                                        <div class="col-md-3 text-center">
                                            <div style="position:relative;display:inline-block;">
                                                <img id="profilePhotoDisplay" src="${photoSrc}"
                                                    style="width:110px;height:110px;border-radius:50%;object-fit:cover;border:3px solid #6f4e37;">
                                                <label for="profilePhotoInput" id="profilePhotoEditBtn" style="display:none;position:absolute;bottom:0;right:0;background:#6f4e37;border-radius:50%;width:30px;height:30px;align-items:center;justify-content:center;cursor:pointer;">
                                                    <i class="bi bi-camera-fill text-white" style="font-size:13px;"></i>
                                                    <input type="file" id="profilePhotoInput" accept="image/*" class="d-none" onchange="app.previewProfilePhoto(this)">
                                                </label>
                                            </div>
                                            <div class="mt-2 fw-semibold">${user?.full_name || (user?.first_name + ' ' + user?.last_name) || '—'}</div>
                                            <div class="text-muted small">${user?.role || 'Farmer'}</div>
                                        </div>
                                        <!-- Fields column -->
                                        <div class="col-md-9">
                                            <div class="row g-3">
                                                <div class="col-md-6">
                                                    <label class="form-label small fw-semibold">First Name</label>
                                                    <input type="text" class="form-control profile-field" id="pFirstName" value="${user?.first_name || ''}" disabled>
                                                </div>
                                                <div class="col-md-6">
                                                    <label class="form-label small fw-semibold">Last Name</label>
                                                    <input type="text" class="form-control profile-field" id="pLastName" value="${user?.last_name || ''}" disabled>
                                                </div>
                                                <div class="col-md-6">
                                                    <label class="form-label small fw-semibold">Phone Number</label>
                                                    <input type="tel" class="form-control profile-field" id="pPhone" value="${user?.phone || user?.phone_number || ''}" disabled>
                                                </div>
                                                <div class="col-md-4">
                                                    <label class="form-label small fw-semibold">Gender</label>
                                                    <select class="form-select profile-field" id="pGender" disabled>
                                                        <option value="">Select...</option>
                                                        ${(() => { const g = (user?.gender || kyc.gender || '').toLowerCase(); const isM = g === 'm' || g === 'male'; const isF = g === 'f' || g === 'female'; return `<option value="Male" ${isM ? 'selected' : ''}>Male</option><option value="Female" ${isF ? 'selected' : ''}>Female</option>`; })()}
                                                    </select>
                                                </div>
                                                <div class="col-md-4">
                                                    <label class="form-label small fw-semibold">ID Type</label>
                                                    <select class="form-select profile-field" id="pIdType" disabled>
                                                        <option value="">Select...</option>
                                                        <option value="national_id" ${kyc.id_type === 'national_id' ? 'selected' : ''}>National ID</option>
                                                        <option value="passport" ${kyc.id_type === 'passport' ? 'selected' : ''}>Passport</option>
                                                    </select>
                                                </div>
                                                <div class="col-md-4">
                                                    <label class="form-label small fw-semibold">ID Number</label>
                                                    <input type="text" class="form-control profile-field" id="pIdNumber" value="${user?.national_id || kyc.id_number || ''}" disabled>
                                                </div>
                                                <div class="col-md-6">
                                                    <label class="form-label small fw-semibold">County</label>
                                                    <input type="text" class="form-control profile-field" id="pCounty" value="${user?.county || ''}" disabled>
                                                </div>
                                                <div class="col-md-6">
                                                    <label class="form-label small fw-semibold">Sub-County</label>
                                                    <input type="text" class="form-control profile-field" id="pSubcounty" value="${user?.subcounty || user?.district || ''}" disabled>
                                                </div>
                                                <div class="col-md-6">
                                                    <label class="form-label small fw-semibold">Cooperative</label>
                                                    <input type="text" class="form-control" id="pCoop" value="${kyc.cooperative_name || kyc.cooperative_code || user?.cooperative_code || ''}" disabled>
                                                </div>
                                                <div class="col-md-6">
                                                    <label class="form-label small fw-semibold">Email</label>
                                                    <input type="email" class="form-control" value="${user?.email || ''}" disabled>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <!-- Save button (hidden until Edit clicked) -->
                                    <div id="profileSaveRow" class="mt-3" style="display:none;">
                                        <button type="button" class="btn btn-primary me-2" onclick="app.saveProfileEdits()">
                                            <i class="bi bi-save me-1"></i>Save Changes
                                        </button>
                                        <button type="button" class="btn btn-outline-secondary" onclick="app.loadProfile(document.getElementById('pageContent'))">Cancel</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- Farms List -->
                    <div class="col-12">
                        <div class="card border-0 shadow-sm">
                            <div class="card-header d-flex justify-content-between align-items-center" style="background:linear-gradient(135deg,#3d2314,#6f4e37);color:white;">
                                <h5 class="mb-0"><i class="bi bi-tree-fill me-2"></i>My Farms</h5>
                                ${user?.verification_status === 'verified'
                                    ? `<button class="btn btn-sm" style="background:#daa520;color:#3d2515;" data-bs-toggle="modal" data-bs-target="#addFarmModal"><i class="bi bi-plus-circle me-1"></i>Add Farm</button>`
                                    : `<span class="badge" style="background:rgba(255,255,255,0.15);color:#fff;font-size:0.72rem;padding:6px 10px;border-radius:20px;"><i class="bi bi-hourglass-split me-1"></i>Pending Verification</span>`}
                            </div>
                            <div class="card-body p-0">
                                ${farmArray.length > 0 ? `
                                <div class="table-responsive">
                                    <table class="table table-hover mb-0">
                                        <thead class="table-light">
                                            <tr>
                                                <th>Farm Name</th>
                                                <th>Total Area</th>
                                                <th>Coffee Area</th>
                                                <th>Varieties</th>
                                                <th>Status</th>
                                                <th>Action</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${farmArray.map(f => {
                                                const sc = {verified:'success',pending:'warning',draft:'secondary',rejected:'danger'}[f.verification_status] || 'secondary';
                                                return `<tr>
                                                    <td class="fw-semibold">${f.farm_name || 'Unnamed Farm'}</td>
                                                    <td>${f.total_area_hectares || 0} ha</td>
                                                    <td>${f.coffee_area_hectares || 0} ha</td>
                                                    <td>${(f.coffee_varieties || []).join(', ') || '—'}</td>
                                                    <td><span class="badge bg-${sc} text-capitalize">${f.verification_status || 'draft'}</span></td>
                                                    <td><button class="btn btn-sm btn-outline-primary" onclick="app.viewFarmDetails('${f.id}')"><i class="bi bi-eye"></i></button></td>
                                                </tr>`;
                                            }).join('')}
                                        </tbody>
                                    </table>
                                </div>
                                ` : `
                                <div class="text-center py-5">
                                    <i class="bi bi-tree fs-1 text-muted"></i>
                                    <p class="text-muted mt-2">No farms registered yet.</p>
                                    ${user?.verification_status === 'verified'
                                        ? `<button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addFarmModal"><i class="bi bi-plus-circle me-1"></i>Register Your First Farm</button>`
                                        : `<div class="alert alert-warning d-inline-flex align-items-center gap-2 px-4 py-2 rounded-pill mt-1" style="font-size:0.85rem;">
                                                <i class="bi bi-hourglass-split fs-5"></i>
                                                <span><strong>Please wait to be verified.</strong> Your account must be approved by your Cooperative and Plotra admin before you can register a farm.</span>
                                            </div>`}
                                </div>`}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } catch (error) {
            console.error(error);
            content.innerHTML = `<div class="alert alert-danger">Error loading profile: ${error.message}</div>`;
        }
    }

    enableProfileEdit() {
        document.querySelectorAll('.profile-field').forEach(el => el.disabled = false);
        const btn = document.getElementById('profilePhotoEditBtn');
        if (btn) btn.style.display = 'flex';
        const saveRow = document.getElementById('profileSaveRow');
        if (saveRow) saveRow.style.display = 'block';
    }

    previewProfilePhoto(input) {
        if (!input.files || !input.files[0]) return;
        const reader = new FileReader();
        reader.onload = e => {
            const display = document.getElementById('profilePhotoDisplay');
            if (display) display.src = e.target.result;
            this._pendingProfilePhoto = e.target.result;
        };
        reader.readAsDataURL(input.files[0]);
    }

    async saveProfileEdits() {
        const get = id => document.getElementById(id)?.value || '';
        const formData = {
            first_name: get('pFirstName'),
            last_name: get('pLastName'),
            phone: get('pPhone'),
            gender: get('pGender'),
            id_type: get('pIdType'),
            id_number: get('pIdNumber'),
            county: get('pCounty'),
            subcounty: get('pSubcounty'),
        };
        if (this._pendingProfilePhoto) {
            formData.profile_photo_url = this._pendingProfilePhoto;
        }
        try {
            await api.updateProfile(formData);
            this._pendingProfilePhoto = null;
            this.showToast('Profile saved successfully!', 'success');
            // Refresh current user
            const me = await api.getCurrentUser();
            if (me) this.currentUser = me;
            this.loadProfile(document.getElementById('pageContent'));
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }


    async resubmitForReview() {
        const btn = document.getElementById('resubmitBtn');
        if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Submitting...'; }
        try {
            await api.resubmitForReview();
            this.showToast('Resubmitted! Your cooperative officer has been notified.', 'success');
            // Refresh user so the banner disappears
            const me = await api.getCurrentUser();
            if (me) { this.currentUser = me; localStorage.setItem('plotra_user', JSON.stringify(me)); }
            this.loadProfile(document.getElementById('pageContent'));
        } catch(e) {
            this.showToast(e.message || 'Failed to resubmit', 'error');
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-send-check me-1"></i>Resubmit for Review'; }
        }
    }

    async showUploadDocumentModal() {
        try {
            const response = await api.getFarms();
            const farms = response.farms || [];
            const farmSelect = document.getElementById('docFarm');
            if (farmSelect) {
                const farmArray = Array.isArray(farms) ? farms : (farms ? [farms] : []);
                farmSelect.innerHTML = '<option value="">Select Farm</option>' + 
                    farmArray.map(f => `<option value="${f.id}">${f.farm_name || f.name || 'Farm #'+f.id}</option>`).join('');
            }
            const modalEl = document.getElementById('uploadDocumentModal');
            if (modalEl) {
                const modal = new bootstrap.Modal(modalEl);
                modal.show();
            }
        } catch (error) {
            this.showToast('Failed to load farms: ' + error.message, 'error');
        }
    }

    async handleUploadDocument() {
        try {
            const fileInput = document.getElementById('docFile');
            if (!fileInput.files || fileInput.files.length === 0) {
                this.showToast('Please select a file to upload', 'error');
                return;
            }

            const formData = new FormData();
            formData.append('farm_id', document.getElementById('docFarm').value);
            formData.append('document_type', document.getElementById('docType').value);
            formData.append('title', document.getElementById('docTitle').value);
            formData.append('description', document.getElementById('docDescription').value);
            formData.append('ownership_type', document.getElementById('docOwnership').value);
            formData.append('issuing_authority', document.getElementById('docAuthority').value);
            formData.append('file', fileInput.files[0]);

            await api.uploadLandDocument(formData);
            this.showToast('Document uploaded successfully', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('uploadDocumentModal'));
            if (modal) modal.hide();
            if (this.currentPage === 'documents') this.loadPage('documents');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async loadUsers(content) { 
        content.innerHTML = `
            <div class="card">
                <div class="card-header d-flex justify-content-between">
                    <h4 class="card-title">User Management</h4>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Email</th>
                                    <th>Name</th>
                                    <th>Role</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody id="users-list">
                                <tr><td colspan="4" class="text-center">Loading...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
        try {
            const response = await api.getUsers();
            const users = response.users || [];
            const list = document.getElementById('users-list');
            if (users && users.length > 0) {
                list.innerHTML = users.map(u => `
                    <tr>
                        <td>${u.email}</td>
                        <td>${u.first_name} ${u.last_name}</td>
                        <td><span class="badge bg-soft-primary text-primary">${u.role}</span></td>
                        <td><span class="badge bg-soft-success text-success">${u.verification_status || 'active'}</span></td>
                    </tr>
                `).join('');
            } else {
                list.innerHTML = '<tr><td colspan="4" class="text-center">No users found</td></tr>';
            }
        } catch (e) {
            document.getElementById('users-list').innerHTML = `<tr><td colspan="4" class="text-center text-danger">Error: ${e.message}</td></tr>`;
        }
    }

    async loadCooperatives(content) { 
        const role = (this.currentUser?.role || '').toUpperCase();
        const isAdmin = ['PLATFORM_ADMIN', 'SUPER_ADMIN', 'ADMIN', 'PLOTRA_ADMIN'].includes(role);

        content.innerHTML = `
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h4 class="card-title">Cooperatives</h4>
                    ${isAdmin ? `
                        <button class="btn btn-primary btn-sm" onclick="app.showCreateCooperativeModal()">
                            <i class="bi bi-plus-lg me-1"></i> Create Cooperative
                        </button>
                    ` : ''}
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Code</th>
                                    <th>Name</th>
                                    <th>Type</th>
                                    <th>County</th>
                                    <th>Phone</th>
                                    <th>Members</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="coops-list">
                                <tr><td colspan="6" class="text-center">Loading...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
        try {
            const coops = await api.getCooperatives();
            const list = document.getElementById('coops-list');
            if (coops && coops.length > 0) {
                list.innerHTML = coops.map(c => `
                    <tr>
                        <td><span class="badge bg-secondary">${c.code || 'N/A'}</span></td>
                        <td>${c.name}</td>
                        <td>${c.cooperative_type ? c.cooperative_type.charAt(0).toUpperCase() + c.cooperative_type.slice(1) : 'N/A'}</td>
                        <td>${c.county || 'N/A'}</td>
                        <td>${c.phone || 'N/A'}</td>
                        <td><span class="badge bg-primary">${c.member_count || 0}</span></td>
                        <td>
                            <button class="btn btn-sm btn-info" onclick="app.showCooperativeDetails('${c.id}')">
                                <i class="bi bi-eye me-1"></i> View
                            </button>
                        </td>
                    </tr>
                `).join('');
            } else {
                list.innerHTML = '<tr><td colspan="7" class="text-center">No cooperatives found</td></tr>';
            }
        } catch (e) {
            const list = document.getElementById('coops-list');
            if (list) {
                list.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error: ${e.message}</td></tr>`;
            }
        }
    }
    async loadSustainability(content) {
        // Fetch dashboard summary data
        let dashboardData = null;
        try {
            dashboardData = await api.getDashboardSummary();
        } catch (error) {
            console.error('Error fetching dashboard summary:', error);
        }
        
        const totalTrees = dashboardData?.total_trees?.toLocaleString() || '0';
        const carbonStored = dashboardData?.carbon_stored_co2 ? `${dashboardData.carbon_stored_co2} T` : '0 T';
        const soilHealth = dashboardData?.soil_health_score ? `${dashboardData.soil_health_score}/10` : '0/10';
        const incentives = dashboardData?.total_incentives_kes ? `KES ${(dashboardData.total_incentives_kes).toLocaleString()}` : 'KES 0';
        
        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h4 class="card-title">Sustainability & Climate-Smart Actions</h4>
                            <button class="btn btn-primary btn-sm" onclick="app.showLogPracticeModal()">
                                <i class="bi bi-plus-lg me-1"></i> Log Practice
                            </button>
                        </div>
                        <div class="card-body">
                            <div class="row g-4 mb-4">
                                <div class="col-md-3">
                                    <div class="card bg-soft-success text-success border-0 shadow-none">
                                        <div class="card-body text-center">
                                            <h6 class="small text-uppercase">Total Trees</h6>
                                            <h3 class="mb-0">${totalTrees}</h3>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="card bg-soft-info text-info border-0 shadow-none">
                                        <div class="card-body text-center">
                                            <h6 class="small text-uppercase">Carbon Stored</h6>
                                            <h3 class="mb-0">${carbonStored}</h3>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="card bg-soft-primary text-primary border-0 shadow-none">
                                        <div class="card-body text-center">
                                            <h6 class="small text-uppercase">Soil Health</h6>
                                            <h3 class="mb-0">${soilHealth}</h3>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="card bg-soft-warning text-warning border-0 shadow-none">
                                        <div class="card-body text-center">
                                            <h6 class="small text-uppercase">Incentives</h6>
                                            <h3 class="mb-0">${incentives}</h3>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <h5 class="mb-3">Recent Practice Logs</h5>
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>Date</th>
                                            <th>Parcel</th>
                                            <th>Activity</th>
                                            <th>Description</th>
                                            <th>Status</th>
                                        </tr>
                                    </thead>
                                    <tbody id="practices-list">
                                        <tr><td colspan="5" class="text-center py-4">Loading practices...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const list = document.getElementById('practices-list');
        try {
            // Use practice logs from dashboard summary if available, otherwise fetch separately
            let practices = [];
            if (dashboardData?.recent_practice_logs && dashboardData.recent_practice_logs.length > 0) {
                practices = dashboardData.recent_practice_logs;
            } else {
                practices = await api.getPracticeLogs();
            }
            
            if (practices && practices.length > 0) {
                list.innerHTML = practices.map(p => `
                    <tr>
                        <td>${p.date ? new Date(p.date).toLocaleDateString() : 'N/A'}</td>
                        <td>${p.parcel || 'Parcel #'+p.parcel_id}</td>
                        <td><span class="badge bg-soft-primary text-primary">${p.activity || p.practice_type}</span></td>
                        <td class="small">${p.description || 'N/A'}</td>
                        <td><span class="badge bg-soft-success text-success">${p.status || 'Verified'}</span></td>
                    </tr>
                `).join('');
            } else {
                list.innerHTML = '<tr><td colspan="5" class="text-center py-4">No practice logs found.</td></tr>';
            }
        } catch (error) {
            console.error(error);
            list.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-danger">Error: ${error.message}</td></tr>`;
        }
    }

    showLogPracticeModal() {
        this.showToast('Log Practice modal would open here', 'info');
    }

    async showAddFarmModal() {
        if (this.currentUser?.verification_status !== 'verified') {
            this.showToast('Your account must be fully verified before you can register a farm.', 'error');
            return;
        }
        const modalEl = document.getElementById('addFarmModal');
        if (!modalEl) return;

        const form = document.getElementById('addFarmForm');
        if (form) form.reset();
        window.resetFarmFormSteps && window.resetFarmFormSteps();

        // Show modal first so fields are accessible
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();

        // Auto-fill from current user profile
        const u = this.currentUser;
        if (u) {
            const set = (id, val) => {
                const el = document.getElementById(id);
                if (el && val != null && val !== '') el.value = val;
            };
            const fullName = u.full_name || [u.first_name, u.last_name].filter(Boolean).join(' ');
            const phone = u.phone || u.phone_number;
            set('farmerFullName', fullName);
            set('farmerPhone', phone);
            set('farmerNationalId', u.national_id);
            set('farmLocation', u.subcounty || u.county || u.district);

            if (u.gender) {
                const genderEl = document.getElementById('farmerGender');
                if (genderEl) {
                    const match = [...genderEl.options].find(o =>
                        o.value.toLowerCase() === u.gender.toLowerCase()
                    );
                    if (match) genderEl.value = match.value;
                }
            }
        }

        // Auto-fill cooperative membership number (async, after modal is visible)
        try {
            const membership = await api.getMyMembership();
            const field = document.getElementById('cooperativeMemberNo');
            if (field) {
                if (membership?.membership_number) {
                    field.value = membership.membership_number;
                    field.readOnly = true;
                    field.style.background = '#f8f9fa';
                    field.title = `${membership.cooperative_name || ''} ${membership.cooperative_code ? '('+membership.cooperative_code+')' : ''}`.trim();
                } else if (membership?.cooperative_name) {
                    field.placeholder = `Member of ${membership.cooperative_name} — number pending`;
                }
            }
        } catch (e) {
            console.warn('Could not fetch membership number:', e.message);
        }

        // Map is on step 4 — initialise it only when step 4 becomes visible (see updateTab1Steps in index.html)
        // Nothing to do here; the step-navigation hook calls app.initFarmMap() / invalidateSize().

        // Clean up GPS watch when modal closes
        const onHide = () => {
            if (this._farmMapWatchId) {
                navigator.geolocation.clearWatch(this._farmMapWatchId);
                this._farmMapWatchId = null;
            }
            if (this.farmMap) {
                try { this.farmMap.remove(); } catch(e) {}
                this.farmMap = null;
            }
            modalEl.removeEventListener('hidden.bs.modal', onHide);
        };
        modalEl.addEventListener('hidden.bs.modal', onHide);
    }

    async loadSystemConfig(content) {
        try {
            const [requiredDocs, sessionTimeout, sysSettings] = await Promise.all([
                api.getRequiredDocuments(),
                api.getSessionTimeout(),
                api.getSystemSettings()
            ]);

            const documents = requiredDocs || [];
            const timeoutMinutes = sessionTimeout?.session_timeout_minutes || sessionTimeout?.timeout_minutes || 30;
            const sat = sysSettings?.satellite || {};
            const email = sysSettings?.email || {};
            const storage = sysSettings?.storage || {};
            const payments = sysSettings?.payments || {};
            const appCfg = sysSettings?.app || {};

            const fieldRow = (label, id, val, type = 'text', hint = '') => `
                <div class="col-md-6 mb-3">
                    <label class="form-label fw-semibold">${label}</label>
                    <input type="${type}" class="form-control form-control-sm" id="${id}" value="${val ?? ''}">
                    ${hint ? `<small class="text-muted">${hint}</small>` : ''}
                </div>`;

            const checkRow = (label, id, val) => `
                <div class="col-md-6 mb-3">
                    <div class="form-check form-switch mt-3">
                        <input class="form-check-input" type="checkbox" id="${id}" ${val ? 'checked' : ''}>
                        <label class="form-check-label" for="${id}">${label}</label>
                    </div>
                </div>`;

            content.innerHTML = `
                <div class="card">
                    <div class="card-header">
                        <h4 class="card-title mb-0">System Configuration</h4>
                    </div>
                    <div class="card-body">
                        <ul class="nav nav-tabs flex-wrap" id="systemConfigTabs" role="tablist">
                            <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tabDocs">Required Documents</button></li>
                            <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tabSession">Session</button></li>
                            <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tabSatellite">Satellite</button></li>
                            <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tabEmail">Email / SMTP</button></li>
                            <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tabStorage">Storage / S3</button></li>
                            <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tabPayments">Payments</button></li>
                            <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tabApp">App Settings</button></li>
                            <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tabCreds">API Credentials</button></li>
                        </ul>
                        <div class="tab-content mt-4">
                            <!-- Required Documents -->
                            <div class="tab-pane fade show active" id="tabDocs">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <h5 class="mb-0">Required Documents</h5>
                                    <button class="btn btn-primary btn-sm" onclick="app.showAddRequiredDocModal()"><i class="bi bi-plus-lg me-1"></i>Add Document</button>
                                </div>
                                <p class="text-muted small mb-3">Documents cooperatives must submit on registration.</p>
                                <div class="table-responsive">
                                    <table class="table table-hover">
                                        <thead><tr><th>Name</th><th>Display Name</th><th>Description</th><th>Required</th><th>Actions</th></tr></thead>
                                        <tbody id="requiredDocsList">
                                            ${documents.length > 0 ? documents.map(doc => `
                                                <tr>
                                                    <td>${doc.name || ''}</td>
                                                    <td>${doc.display_name || ''}</td>
                                                    <td>${doc.description || '-'}</td>
                                                    <td>${doc.is_required ? '<span class="badge bg-success">Yes</span>' : '<span class="badge bg-secondary">No</span>'}</td>
                                                    <td><button class="btn btn-sm btn-danger" onclick="app.deleteRequiredDocument('${doc.id}')"><i class="bi bi-trash"></i></button></td>
                                                </tr>`).join('') : '<tr><td colspan="5" class="text-center text-muted">No required documents configured</td></tr>'}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            <!-- Session -->
                            <div class="tab-pane fade" id="tabSession">
                                <h5 class="mb-3">Session Settings</h5>
                                <div class="col-md-5">
                                    <label class="form-label">Session Timeout (minutes)</label>
                                    <div class="input-group">
                                        <input type="number" class="form-control" id="sessionTimeoutInput" value="${timeoutMinutes}" min="5" max="1440">
                                        <button class="btn btn-primary" onclick="app.updateSessionTimeout()">Save</button>
                                    </div>
                                    <small class="text-muted">Between 5 and 1440 minutes</small>
                                </div>
                            </div>
                            <!-- Satellite -->
                            <div class="tab-pane fade" id="tabSatellite">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <h5 class="mb-0">Sentinel Hub API Configuration</h5>
                                    <button class="btn btn-primary btn-sm" onclick="app.saveSystemSection('satellite')"><i class="bi bi-save me-1"></i>Save</button>
                                </div>
                                <div class="alert alert-info py-2 mb-3" style="font-size:0.85rem;">
                                    <i class="bi bi-info-circle me-1"></i>
                                    <strong>Copernicus Data Space credentials:</strong><br>
                                    Go to <strong>dataspace.copernicus.eu → Dashboard → OAuth clients</strong>.<br>
                                    Your OAuth Client ID is: <code>sh-145d33f4-e992-4ada-a77e-0d9c94aebc5f</code><br>
                                    Click on the client named <strong>poll</strong> to reveal and copy the Client Secret.
                                </div>
                                <div class="row">
                                    ${fieldRow('OAuth Client ID', 'sat_oauth_client_id', sat.oauth_client_id || '', 'text', 'e.g. sh-145d33f4-e992-4ada-a77e-0d9c94aebc5f')}
                                    ${fieldRow('OAuth Client Secret', 'sat_oauth_client_secret', sat.oauth_client_secret || '', 'password', 'From Copernicus Dashboard → OAuth clients → poll')}
                                </div>
                                <div class="mt-3 d-flex align-items-center gap-3">
                                    <button class="btn btn-success btn-sm" onclick="app.saveSystemSection('satellite')"><i class="bi bi-save me-1"></i>Save Credentials</button>
                                    <button class="btn btn-outline-secondary btn-sm" onclick="app.testSatelliteConnection()"><i class="bi bi-wifi me-1"></i>Test Connection</button>
                                    <span id="satTestResult" class="small"></span>
                                </div>
                            </div>
                            <!-- Email -->
                            <div class="tab-pane fade" id="tabEmail">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <h5 class="mb-0">Email Configuration <span class="badge bg-success ms-2" style="font-size:0.7rem;">Resend API</span></h5>
                                    <button class="btn btn-primary btn-sm" onclick="app.saveSystemSection('email')"><i class="bi bi-save me-1"></i>Save</button>
                                </div>
                                <div class="alert alert-info py-2 mb-3" style="font-size:0.85rem;">
                                    <i class="bi bi-info-circle me-1"></i>
                                    Emails are sent via <strong>Resend</strong> (HTTPS API — no SMTP port required).
                                    Get your API key at <strong>resend.com</strong>.
                                </div>
                                <div class="row">
                                    ${fieldRow('Resend API Key', 'email_resend_api_key', email.resend_api_key, 'password', 'Leave *** to keep existing')}
                                    ${fieldRow('From Email', 'email_from_email', email.from_email)}
                                    ${fieldRow('From Name', 'email_from_name', email.from_name)}
                                </div>
                            </div>
                            <!-- Storage -->
                            <div class="tab-pane fade" id="tabStorage">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <h5 class="mb-0">Storage / S3 Settings</h5>
                                    <button class="btn btn-primary btn-sm" onclick="app.saveSystemSection('storage')"><i class="bi bi-save me-1"></i>Save</button>
                                </div>
                                <div class="row">
                                    ${fieldRow('S3 Bucket', 's3_bucket', storage.s3_bucket)}
                                    ${fieldRow('S3 Endpoint', 's3_endpoint', storage.s3_endpoint)}
                                    ${fieldRow('Access Key', 's3_access_key', storage.s3_access_key)}
                                    ${fieldRow('Secret Key', 's3_secret_key', storage.s3_secret_key, 'password', 'Leave *** to keep existing')}
                                    ${fieldRow('Region', 's3_region', storage.s3_region)}
                                </div>
                            </div>
                            <!-- Payments -->
                            <div class="tab-pane fade" id="tabPayments">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <h5 class="mb-0">Payments Configuration</h5>
                                    <button class="btn btn-primary btn-sm" onclick="app.saveSystemSection('payments')"><i class="bi bi-save me-1"></i>Save</button>
                                </div>
                                <div class="row">
                                    ${checkRow('Payments Enabled', 'pay_enabled', payments.enabled)}
                                    ${fieldRow('M-Pesa Consumer Key', 'pay_mpesa_consumer_key', payments.mpesa_consumer_key)}
                                    ${fieldRow('M-Pesa Consumer Secret', 'pay_mpesa_consumer_secret', payments.mpesa_consumer_secret, 'password', 'Leave *** to keep existing')}
                                    ${fieldRow('M-Pesa Shortcode', 'pay_mpesa_shortcode', payments.mpesa_shortcode)}
                                </div>
                            </div>
                            <!-- App Settings -->
                            <div class="tab-pane fade" id="tabApp">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <h5 class="mb-0">Application Settings</h5>
                                    <button class="btn btn-primary btn-sm" onclick="app.saveSystemSection('app')"><i class="bi bi-save me-1"></i>Save</button>
                                </div>
                                <div class="row">
                                    ${fieldRow('Platform Name', 'app_name', appCfg.name)}
                                    ${fieldRow('Frontend Base URL', 'app_frontend_base_url', appCfg.frontend_base_url)}
                                    ${fieldRow('Token Expiry (min)', 'app_access_token_expire_minutes', appCfg.access_token_expire_minutes, 'number')}
                                    ${checkRow('Debug Mode', 'app_debug', appCfg.debug)}
                                </div>
                            </div>
                            <!-- API Credentials -->
                            <div class="tab-pane fade" id="tabCreds">
                                <h5 class="mb-3">Custom API Credentials</h5>
                                <p class="text-muted small mb-3">Store additional API keys and secrets securely in the database.</p>
                                <div class="row g-2 mb-3">
                                    <div class="col-md-4"><input type="text" class="form-control form-control-sm" id="credKey" placeholder="Key name (e.g. OPENAI_KEY)"></div>
                                    <div class="col-md-4"><input type="password" class="form-control form-control-sm" id="credValue" placeholder="Value"></div>
                                    <div class="col-md-2"><button class="btn btn-primary btn-sm w-100" onclick="app.addEnvCredential()">Add</button></div>
                                </div>
                                <div id="credentialsList"></div>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            this.loadEnvCredentialsList();
        } catch (error) {
            console.error('Error loading system config:', error);
            content.innerHTML = `<div class="alert alert-danger">Error loading configuration: ${error.message}</div>`;
        }
    }

    async saveSystemSection(section) {
        const fieldMap = {
            satellite: { sat_provider: 'provider', sat_base_url: 'base_url', sat_account_id: 'account_id', sat_api_key: 'api_key', sat_oauth_client_id: 'oauth_client_id', sat_oauth_client_secret: 'oauth_client_secret' },
            email: { email_resend_api_key: 'resend_api_key', email_from_email: 'from_email', email_from_name: 'from_name' },
            storage: { s3_bucket: 'bucket', s3_endpoint: 'endpoint', s3_access_key: 'access_key', s3_secret_key: 'secret_key', s3_region: 'region' },
            payments: { pay_enabled: 'enabled', pay_mpesa_consumer_key: 'mpesa_consumer_key', pay_mpesa_consumer_secret: 'mpesa_consumer_secret', pay_mpesa_shortcode: 'mpesa_shortcode' },
            app: { app_name: 'name', app_frontend_base_url: 'frontend_base_url', app_access_token_expire_minutes: 'access_token_expire_minutes', app_debug: 'debug' },
        };
        const checkboxIds = new Set(['sat_simulation_mode', 'pay_enabled', 'app_debug']);
        const fields = fieldMap[section] || {};
        const values = {};
        for (const [elId, key] of Object.entries(fields)) {
            const el = document.getElementById(elId);
            if (!el) continue;
            values[key] = checkboxIds.has(elId) ? el.checked : el.value;
        }
        try {
            await api.updateSystemSettings(section, values);
            this.showToast(`${section} settings saved`, 'success');
        } catch (e) {
            this.showToast(e.message, 'error');
        }
    }

    async testSatelliteConnection() {
        const el = document.getElementById('satTestResult');
        if (el) el.innerHTML = '<span class="text-muted">Testing...</span>';
        try {
            const res = await api.request('/admin/config/satellite-test', { optional: true });
            if (res && res.success) {
                if (el) el.innerHTML = `<span class="text-success"><i class="bi bi-check-circle me-1"></i>${res.message}</span>`;
            } else {
                if (el) el.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle me-1"></i>${res?.message || 'Connection failed'}</span>`;
            }
        } catch (e) {
            if (el) el.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle me-1"></i>${e.message}</span>`;
        }
    }

    async showAddRequiredDocModal() {
        const html = `
            <div class="modal fade" id="addRequiredDocModal" tabindex="-1" data-bs-backdrop="static" data-bs-keyboard="false">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Add Required Document</h5>
                            <button type="button" class="btn-modal-close" data-bs-dismiss="modal"><i class="bi bi-x-lg"></i>Close</button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label class="form-label">Document Name (ID)</label>
                                <input type="text" class="form-control" id="docName" placeholder="e.g., title_deed">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Display Name</label>
                                <input type="text" class="form-control" id="docDisplayName" placeholder="e.g., Title Deed">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Description</label>
                                <textarea class="form-control" id="docDescription" rows="2"></textarea>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Document Type</label>
                                <input type="text" class="form-control" id="docType" placeholder="e.g., legal">
                            </div>
                            <div class="form-check">
                                <input type="checkbox" class="form-check-input" id="docRequired" checked>
                                <label class="form-check-label" for="docRequired">Required</label>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" onclick="app.createRequiredDocument()">Add Document</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', html);
        const modal = new bootstrap.Modal(document.getElementById('addRequiredDocModal'));
        modal.show();
        
        document.getElementById('addRequiredDocModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }

    async createRequiredDocument() {
        const name = document.getElementById('docName').value;
        const display_name = document.getElementById('docDisplayName').value;
        const description = document.getElementById('docDescription').value;
        
        if (!name || !display_name) {
            this.showToast('Please enter name and display name', 'error');
            return;
        }
        
        try {
            await api.createRequiredDocument({
                name,
                display_name,
                description,
                document_type: document.getElementById('docType').value,
                is_required: document.getElementById('docRequired').checked,
                sort_order: 0
            });
            
            this.showToast('Document added successfully', 'success');
            bootstrap.Modal.getInstance(document.getElementById('addRequiredDocModal')).hide();
            this.loadPage('system');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async deleteRequiredDocument(docId) {
        if (!confirm('Are you sure you want to delete this document?')) return;
        
        try {
            await api.deleteRequiredDocument(docId);
            this.showToast('Document deleted', 'success');
            this.loadPage('system');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async updateSessionTimeout() {
        const timeout = parseInt(document.getElementById('sessionTimeoutInput').value);
        
        if (timeout < 5 || timeout > 1440) {
            this.showToast('Value must be between 5 and 1440', 'error');
            return;
        }
        
        try {
            await api.updateSessionTimeout(timeout);
            this.showToast('Session timeout updated', 'success');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async loadEnvCredentialsList() {
        try {
            const data = await api.getEnvCredentials();
            const creds = data?.credentials || {};
            const listDiv = document.getElementById('credentialsList');
            
            if (listDiv) {
                const keys = Object.keys(creds);
                if (keys.length === 0) {
                    listDiv.innerHTML = '<p class="text-muted">No credentials stored</p>';
                } else {
                    listDiv.innerHTML = `
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>Key</th>
                                    <th>Description</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${keys.map(key => `
                                    <tr>
                                        <td>${key}</td>
                                        <td>${creds[key]?.description || '-'}</td>
                                        <td>
                                            <button class="btn btn-sm btn-danger" onclick="app.deleteEnvCredential('${key}')">
                                                <i class="bi bi-trash"></i>
                                            </button>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `;
                }
            }
        } catch (error) {
            console.error('Error loading credentials:', error);
        }
    }

    async addEnvCredential() {
        const key = document.getElementById('credKey').value;
        const value = document.getElementById('credValue').value;
        
        if (!key || !value) {
            this.showToast('Please enter key and value', 'error');
            return;
        }
        
        try {
            await api.updateEnvCredential(key, value);
            this.showToast('Credential added', 'success');
            document.getElementById('credKey').value = '';
            document.getElementById('credValue').value = '';
            this.loadEnvCredentialsList();
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async deleteEnvCredential(key) {
        if (!confirm(`Delete credential "${key}"?`)) return;
        
        try {
            await api.deleteEnvCredential(key);
            this.showToast('Credential deleted', 'success');
            this.loadEnvCredentialsList();
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    editFarm(farmId) {
        // Navigate to farms page with farm selected
        this.loadPage('farms');
        // Store selected farm ID for editing
        setTimeout(() => {
            const editBtn = document.querySelector(`[data-farm-id="${farmId}"]`);
            if (editBtn) editBtn.click();
        }, 500);
    }

    initFarmMap() {
        const mapDiv = document.getElementById('farmMap');
        if (!mapDiv) return;

        // Stop any previous GPS watch (new system)
        if (this._farmMapWatchId) {
            navigator.geolocation.clearWatch(this._farmMapWatchId);
            this._farmMapWatchId = null;
        }
        // Stop old legacy GPS watch to avoid parallel watches
        if (this.watchId) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
        if (this.farmMap) {
            try { this.farmMap.remove(); } catch (e) {}
            this.farmMap = null;
        }

        // Reset state (new system)
        this.gpsPoints = [];
        this._farmIsCapturing = false;
        this._farmAutoAddPoint1 = false;
        this._farmMapCurrentPos = null;
        // Reset legacy state so old handlers don't interfere
        this.isCapturing = false;
        this._gpsPoint1Set = false;
        this.lastKnownPosition = null;

        // Clone-replace all 4 capture buttons to strip any old addEventListener handlers
        ['startCaptureBtn', 'addPointBtn', 'finishCaptureBtn', 'clearPointsBtn'].forEach(id => {
            const el = document.getElementById(id);
            if (el && el.parentNode) el.parentNode.replaceChild(el.cloneNode(true), el);
        });

        // Read current mode from radio (Walk default)
        this._farmCaptureMode = document.getElementById('farmModeClick')?.checked ? 'click' : 'walk';
        const walkRadio  = document.getElementById('farmModeWalk');
        const clickRadio = document.getElementById('farmModeClick');
        if (walkRadio)  walkRadio.onchange  = () => { if (walkRadio.checked)  this._farmCaptureMode = 'walk'; };
        if (clickRadio) clickRadio.onchange = () => { if (clickRadio.checked) this._farmCaptureMode = 'click'; };

        try {
            this.farmMap = L.map('farmMap', { zoomControl: true });
            this.farmMap.setView([-0.0236, 37.9062], 13);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(this.farmMap);

            // Polygon + polyline layers
            this.farmPolygon = L.polygon([], {
                color: '#40916c', fillColor: '#52b788', fillOpacity: 0.3, weight: 2
            }).addTo(this.farmMap);
            this._farmPolyline = L.polyline([], { color: '#6f4e37', weight: 3, dashArray: '6,4' }).addTo(this.farmMap);
            this._farmMarkers  = L.layerGroup().addTo(this.farmMap);

            // Live GPS marker (not added to map until first fix)
            this._farmLiveMarker = L.marker([0, 0], {
                icon: L.divIcon({
                    className: '',
                    html: '<div style="background:#2563eb;color:#fff;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.4);width:34px;height:34px;display:flex;align-items:center;justify-content:center;font-size:16px;line-height:1;">📍</div>',
                    iconSize: [34, 34], iconAnchor: [17, 17]
                })
            });
            this._farmAccuracyCircle = L.circle([0, 0], {
                radius: 0, color: '#10b981', fillColor: '#d1fae5', fillOpacity: 0.3
            });

            this.farmMap.invalidateSize();

            // Two-stage GPS centering: fast coarse first, then precise
            if (navigator.geolocation) {
                const setView = (lat, lng) => { if (this.farmMap) this.farmMap.setView([lat, lng], 16); };
                navigator.geolocation.getCurrentPosition(
                    pos => setView(pos.coords.latitude, pos.coords.longitude),
                    () => {},
                    { enableHighAccuracy: false, timeout: 5000, maximumAge: 300000 }
                );
                navigator.geolocation.getCurrentPosition(
                    pos => setView(pos.coords.latitude, pos.coords.longitude),
                    () => {},
                    { enableHighAccuracy: true, timeout: 30000, maximumAge: 0 }
                );
            }

            // Continuous GPS watch for live marker + walk-mode auto-points
            if (navigator.geolocation) {
                this._farmMapWatchId = navigator.geolocation.watchPosition(pos => {
                    const { latitude: lat, longitude: lng, accuracy } = pos.coords;
                    this._farmMapCurrentPos = pos.coords;

                    // Update accuracy display
                    const accEl = document.getElementById('gpsAccuracy');
                    if (accEl) accEl.textContent = accuracy ? accuracy.toFixed(1) : '--';

                    // Move live marker
                    this._farmLiveMarker.setLatLng([lat, lng]);
                    if (this.farmMap && !this.farmMap.hasLayer(this._farmLiveMarker)) {
                        this._farmLiveMarker.addTo(this.farmMap);
                    }
                    if (this._farmAccuracyCircle) {
                        this._farmAccuracyCircle.setLatLng([lat, lng]).setRadius(accuracy || 0);
                        if (this.farmMap && !this.farmMap.hasLayer(this._farmAccuracyCircle)) {
                            this._farmAccuracyCircle.addTo(this.farmMap);
                        }
                    }

                    // Auto Point 1 when Start was pressed before GPS arrived
                    if (this._farmAutoAddPoint1 && this._farmIsCapturing) {
                        this._farmAutoAddPoint1 = false;
                        this._addFarmPoint(lat, lng, accuracy);
                    } else if (this._farmIsCapturing && this._farmCaptureMode === 'walk' && this.gpsPoints.length > 0) {
                        // Walk mode: auto-add every 5 m
                        const last = this.gpsPoints[this.gpsPoints.length - 1];
                        if (this._haversineDistance(last.lat, last.lon, lat, lng) >= 5) {
                            this._addFarmPoint(lat, lng, accuracy);
                        }
                    }

                    // Follow user while walking and capturing
                    if (this._farmIsCapturing && this._farmCaptureMode === 'walk' && this.farmMap) {
                        this.farmMap.panTo([lat, lng], { animate: true, duration: 0.3 });
                    }
                }, err => {
                    console.warn('Farm GPS error:', err.message);
                }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 30000 });
            }

            // Click-to-add-point (click mode only)
            this.farmMap.on('click', (e) => {
                if (!this._farmIsCapturing) return;
                if (this._farmCaptureMode !== 'click') return;
                this._addFarmPoint(e.latlng.lat, e.latlng.lng, 0);
            });

            // Wire up buttons
            const startBtn  = document.getElementById('startCaptureBtn');
            const addBtn    = document.getElementById('addPointBtn');
            const finishBtn = document.getElementById('finishCaptureBtn');
            const clearBtn  = document.getElementById('clearPointsBtn');
            if (startBtn) startBtn.onclick = () => this._startFarmCapture();
            if (addBtn)   addBtn.onclick   = () => {
                if (!this._farmMapCurrentPos) { this.showToast('Waiting for GPS fix…', 'warning'); return; }
                if (!this._farmIsCapturing)   { this.showToast('Press Start Capture first', 'warning'); return; }
                this._addFarmPoint(this._farmMapCurrentPos.latitude, this._farmMapCurrentPos.longitude, this._farmMapCurrentPos.accuracy);
            };
            if (finishBtn) finishBtn.onclick = () => {
                if (this.gpsPoints.length < 3) { this.showToast('Need at least 3 points', 'warning'); return; }
                this._farmIsCapturing = false;
                if (addBtn)   addBtn.disabled   = true;
                const inst = document.getElementById('captureInstructions');
                if (inst) inst.textContent = 'Capture complete. Continue to the next step.';
            };
            if (clearBtn) clearBtn.onclick = () => {
                this.gpsPoints = [];
                this._farmIsCapturing = false;
                if (this.farmPolygon)    this.farmPolygon.setLatLngs([]);
                if (this._farmPolyline)  this._farmPolyline.setLatLngs([]);
                if (this._farmMarkers)   this._farmMarkers.clearLayers();
                const pc = document.getElementById('pointCount');
                const ca = document.getElementById('calculatedArea');
                if (pc) pc.textContent = '0';
                if (ca) ca.textContent = '--';
                if (startBtn)  startBtn.disabled  = false;
                if (addBtn)    addBtn.disabled    = true;
                if (finishBtn) finishBtn.disabled  = true;
                if (clearBtn)  clearBtn.disabled  = true;
                const inst = document.getElementById('captureInstructions');
                if (inst) inst.textContent = 'Cleared. Press Start Capture to begin again.';
            };

            const inst = document.getElementById('captureInstructions');
            if (inst) inst.textContent = 'Choose Walk or Click mode, then press Start Capture.';

        } catch (error) {
            console.error('Map initialization error:', error);
            this.farmMap = null;
        }
    }

    _startFarmCapture() {
        this._farmIsCapturing = true;
        const mode = this._farmCaptureMode || 'walk';
        const startBtn  = document.getElementById('startCaptureBtn');
        const addBtn    = document.getElementById('addPointBtn');
        const finishBtn = document.getElementById('finishCaptureBtn');
        const clearBtn  = document.getElementById('clearPointsBtn');
        const inst      = document.getElementById('captureInstructions');
        if (startBtn)  startBtn.disabled  = true;
        if (addBtn)    addBtn.disabled    = false;
        if (finishBtn) finishBtn.disabled  = this.gpsPoints.length < 3;
        if (clearBtn)  clearBtn.disabled  = false;

        // Always auto-place Point 1 at current GPS location (both walk and click mode)
        if (this._farmMapCurrentPos) {
            this._addFarmPoint(this._farmMapCurrentPos.latitude, this._farmMapCurrentPos.longitude, this._farmMapCurrentPos.accuracy);
            if (inst) inst.textContent = mode === 'walk'
                ? 'Point 1 placed. Walking… points auto-add every 5 m. Press Add Point at key corners.'
                : 'Point 1 placed at your location. Tap the map to add boundary corners.';
        } else {
            this._farmAutoAddPoint1 = true;
            if (inst) inst.textContent = 'Waiting for GPS fix… Point 1 will be placed when location is found.';
        }
    }

    _addFarmPoint(lat, lng, accuracy) {
        this.gpsPoints.push({ lat, lon: lng, accuracy: accuracy || 0, timestamp: Date.now() });
        const count = this.gpsPoints.length;

        const icon = L.divIcon({
            className: '',
            html: `<div style="background:#40916c;color:#fff;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.5);">${count}</div>`,
            iconSize: [26, 26], iconAnchor: [13, 13]
        });
        if (this._farmMarkers) L.marker([lat, lng], { icon }).addTo(this._farmMarkers);

        const coords = this.gpsPoints.map(p => [p.lat, p.lon]);
        if (this._farmPolyline) this._farmPolyline.setLatLngs(coords);

        if (count >= 3) {
            if (this.farmPolygon) this.farmPolygon.setLatLngs(coords);
            const area = this._calcArea(coords);
            const ca = document.getElementById('calculatedArea');
            if (ca) ca.textContent = area.toFixed(2);
        }

        const pc  = document.getElementById('pointCount');
        const fb  = document.getElementById('finishCaptureBtn');
        const inst = document.getElementById('captureInstructions');
        if (pc)   pc.textContent  = count;
        if (fb)   fb.disabled     = count < 3;
        if (inst) inst.textContent = `${count} point(s). ${count >= 3 ? 'Press Finish or keep adding.' : 'Add more (min 3).'}`;
    }

    initGPSCapture() {
        // Set up event listeners only once
        if (!this.gpsInitialized) {
            this.gpsInitialized = true;
            const startBtn = document.getElementById('startCaptureBtn');
            const addPointBtn = document.getElementById('addPointBtn');
            const finishBtn = document.getElementById('finishCaptureBtn');
            const clearBtn = document.getElementById('clearPointsBtn');

            if (startBtn) startBtn.addEventListener('click', () => this.startGPSCapture());
            if (addPointBtn) addPointBtn.addEventListener('click', () => this.addGPSPoint());
            if (finishBtn) finishBtn.addEventListener('click', () => this.finishGPSCapture());
            if (clearBtn) clearBtn.addEventListener('click', () => this.clearGPSPoints());
        }
        
        // Reset state and UI each time modal opens
        this.clearGPSPoints();

        // Auto-start GPS watch so Point 1 is placed automatically
        this._startGPSWatch();
    }

    _startGPSWatch() {
        if (!navigator.geolocation) return;
        if (this.watchId) return; // already watching
        this.watchId = navigator.geolocation.watchPosition(
            (position) => this.handleGPSUpdate(position),
            (error) => this.handleGPSError(error),
            { enableHighAccuracy: true, maximumAge: 1000, timeout: 15000 }
        );
    }

    startGPSCapture() {
        // If GPS auto already placed Point 1, just enable Add Point (don't wipe gpsPoints)
        this.isCapturing = true;
        this._startGPSWatch(); // no-op if already running

        const getEl = id => document.getElementById(id);
        if (getEl('startCaptureBtn'))    getEl('startCaptureBtn').disabled    = true;
        if (getEl('addPointBtn'))        getEl('addPointBtn').disabled         = false;
        if (getEl('finishCaptureBtn'))   getEl('finishCaptureBtn').disabled    = true;
        if (getEl('clearPointsBtn'))     getEl('clearPointsBtn').disabled      = this.gpsPoints.length === 0;
        if (getEl('captureInstructions')) getEl('captureInstructions').textContent =
            'Walking around the farm boundary… click "Add Point" at each corner.';
    }

    handleGPSUpdate(position) {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        const accuracy = position.coords.accuracy;

        // Store last known position first so addGPSPoint can use it even if map isn't ready
        this.lastKnownPosition = { lat, lon, accuracy };

        const gpsAccuracyEl = document.getElementById('gpsAccuracy');
        if (gpsAccuracyEl) gpsAccuracyEl.textContent = accuracy.toFixed(1);

        if (!this.currentLocationMarker || !this.accuracyCircle) return;

        this.currentLocationMarker.setLatLng([lat, lon]);
        this.accuracyCircle.setLatLng([lat, lon]).setRadius(accuracy);

        // Centre map only on the FIRST GPS fix — never jump again while user is clicking
        if (this.farmMap && !this._gpsPoint1Set) {
            this.farmMap.setView([lat, lon], 16);

            // Auto-place Point 1 at the GPS location
            this._gpsPoint1Set = true;
            this.gpsPoints = [{ lat, lon, accuracy, timestamp: Date.now() }];

            const icon = L.divIcon({
                className: 'click-point-icon',
                html: `<div style="background:#6f4e37;color:#fff;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.5);line-height:1;">1</div>`,
                iconSize: [26, 26], iconAnchor: [13, 13]
            });
            const m = L.marker([lat, lon], { icon }).addTo(this.farmMap);
            this._clickMarkers = [m];

            const pc = document.getElementById('pointCount');
            if (pc) pc.textContent = '1';
            const cb = document.getElementById('clearPointsBtn');
            if (cb) cb.disabled = false;
            const inst = document.getElementById('captureInstructions');
            if (inst) inst.textContent = 'GPS Point 1 placed at your location. Click on the map (or walk and Add Point) to mark boundary corners.';
        }
    }

    handleGPSError(error) {
        const errorMessages = {
            1: 'GPS access denied by user',
            2: 'GPS position unavailable',
            3: 'GPS request timed out'
        };
        
        this.showToast(errorMessages[error.code] || 'GPS error', 'error');
        this.stopGPSCapture();
    }

    addGPSPoint() {
        if (!this.lastKnownPosition) {
            this.showToast('No GPS location available', 'error');
            return;
        }

        this.gpsPoints.push({
            lat: this.lastKnownPosition.lat,
            lon: this.lastKnownPosition.lon,
            accuracy: this.lastKnownPosition.accuracy,
            timestamp: Date.now()
        });

        // Update UI
        document.getElementById('pointCount').textContent = this.gpsPoints.length;
        document.getElementById('finishCaptureBtn').disabled = this.gpsPoints.length < 3;
        document.getElementById('clearPointsBtn').disabled = false;

        // Update polygon
        this.updateFarmPolygon();
    }

    updateFarmPolygon() {
        if (this.gpsPoints.length < 1) return;

        const coordinates = this.gpsPoints.map(point => [point.lat, point.lon]);
        
        if (this.farmPolygon) {
            this.farmPolygon.setLatLngs(coordinates);
        }

        // Calculate and display area
        if (this.gpsPoints.length > 2) {
            const area = this.calculatePolygonArea(coordinates);
            const hectares = parseFloat((area / 10000).toFixed(4)).toFixed(2); // 4dp precision, display 2dp
            const farmAreaEstimateEl = document.getElementById('farmAreaEstimate');
            if (farmAreaEstimateEl) farmAreaEstimateEl.value = hectares;

            // Dispatch event for step navigation to track GPS validation
            window.dispatchEvent(new CustomEvent('gpsPointsUpdated', {
                detail: { count: this.gpsPoints.length, area: hectares }
            }));

            // Update calculated area display
            const calculatedAreaEl = document.getElementById('calculatedArea');
            if (calculatedAreaEl) calculatedAreaEl.innerText = hectares;
            console.log('[Area Live] areaSqM:', area, 'ha:', hectares, 'pts:', coordinates.length);

            // Build GeoJSON Feature for form submission
            const geoJSONCoords = this.gpsPoints.map(p => [p.lon, p.lat]);
            // Ensure closed polygon
            if (geoJSONCoords[0][0] !== geoJSONCoords[geoJSONCoords.length-1][0] || 
                geoJSONCoords[0][1] !== geoJSONCoords[geoJSONCoords.length-1][1]) {
                geoJSONCoords.push(geoJSONCoords[0]);
            }
            this.currentPolygon = {
                type: 'Feature',
                geometry: {
                    type: 'Polygon',
                    coordinates: [geoJSONCoords]
                }
            };
        }
    }

    calculatePolygonArea(coordinates) {
        if (coordinates.length < 3) return 0;
        const toRad = d => d * Math.PI / 180;
        const R = 6378137; // WGS84 Earth radius in metres

        // Compute centroid to use as local origin (avoids floating-point cancellation)
        const latMean = coordinates.reduce((s, c) => s + c[0], 0) / coordinates.length;
        const lonMean = coordinates.reduce((s, c) => s + c[1], 0) / coordinates.length;
        const cosLat  = Math.cos(toRad(latMean));

        // Equirectangular projection to local metres, centred at polygon centroid
        const pts = coordinates.map(c => [
            R * toRad(c[1] - lonMean) * cosLat,  // x = easting
            R * toRad(c[0] - latMean)              // y = northing
        ]);

        // Shoelace formula on projected (flat) coordinates
        let area = 0;
        const n = pts.length;
        for (let i = 0; i < n; i++) {
            const j = (i + 1) % n;
            area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1];
        }
        return Math.abs(area) / 2; // result in m²
    }

    finishGPSCapture() {
        this.stopGPSCapture();
        const getEl = id => document.getElementById(id);

        if (this.gpsPoints.length < 3) {
            if (getEl('captureInstructions')) getEl('captureInstructions').textContent = 'Need at least 3 points to finish. Keep clicking on the map.';
            return;
        }

        // Ensure polygon is closed (first point repeated at end)
        const first = this.gpsPoints[0];
        const last  = this.gpsPoints[this.gpsPoints.length - 1];
        if (first.lat !== last.lat || first.lon !== last.lon) {
            this.gpsPoints.push({ ...first, timestamp: Date.now() });
        }

        // Calculate area
        const coordinates = this.gpsPoints.map(p => [p.lat, p.lon]);
        const areaSqM = this.calculatePolygonArea(coordinates);
        console.log('[Area Debug] points:', coordinates.length, 'coords:', JSON.stringify(coordinates), 'areaSqM:', areaSqM);
        const hectares = (areaSqM / 10000).toFixed(4);
        const hectaresDisplay = parseFloat(hectares).toFixed(2);

        // Update polygon on map
        if (this.farmPolygon) this.farmPolygon.setLatLngs(coordinates);

        // Build / store GeoJSON
        const geoCoords = this.gpsPoints.map(p => [p.lon, p.lat]);
        this.currentPolygon = {
            type: 'Feature',
            geometry: { type: 'Polygon', coordinates: [geoCoords] }
        };

        // Update all area display elements
        if (getEl('calculatedArea'))    getEl('calculatedArea').innerText = hectaresDisplay;
        if (getEl('farmAreaEstimate'))  getEl('farmAreaEstimate').value   = hectaresDisplay;
        if (getEl('farmArea'))          getEl('farmArea').value           = hectaresDisplay;

        // Dispatch event for step validation
        window.dispatchEvent(new CustomEvent('gpsPointsUpdated', {
            detail: { count: this.gpsPoints.length, area: hectaresDisplay }
        }));

        // Update UI state
        if (getEl('startCaptureBtn'))    getEl('startCaptureBtn').disabled    = false;
        if (getEl('addPointBtn'))        getEl('addPointBtn').disabled         = true;
        if (getEl('finishCaptureBtn'))   getEl('finishCaptureBtn').disabled    = true;
        if (getEl('clearPointsBtn'))     getEl('clearPointsBtn').disabled      = false;
        if (getEl('captureInstructions')) {
            getEl('captureInstructions').innerHTML =
                `Capture complete! <strong>Area: ${hectaresDisplay} ha</strong>. You can clear and re-capture if needed.`;
        }
    }

    stopGPSCapture() {
        if (this.watchId) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
        this.isCapturing = false;
    }

    clearGPSPoints() {
        this.stopGPSCapture();
        this.gpsPoints = [];
        this.currentPolygon = null;

        // Clear click-mode test markers
        if (this._clickMarkers && this.farmMap) {
            this._clickMarkers.forEach(m => { try { this.farmMap.removeLayer(m); } catch(e){} });
        }
        this._clickMarkers = [];
        if (this._clickPolyline) {
            try { this._clickPolyline.setLatLngs([]); } catch(e) {}
        }

        // Clear drawn items (manual polygon)
        if (this.drawnItems) {
            this.drawnItems.clearLayers();
        }
        
        // Reset UI
        const getEl = id => document.getElementById(id);
        if (getEl('pointCount')) getEl('pointCount').textContent = '0';
        if (getEl('gpsAccuracy')) getEl('gpsAccuracy').textContent = '--';
        if (getEl('farmArea')) getEl('farmArea').value = '';
        if (getEl('farmAreaEstimate')) getEl('farmAreaEstimate').value = '';
        if (getEl('calculatedArea')) getEl('calculatedArea').innerText = '--';
        if (getEl('startCaptureBtn')) getEl('startCaptureBtn').disabled = false;
        if (getEl('addPointBtn')) getEl('addPointBtn').disabled = true;
        if (getEl('finishCaptureBtn')) getEl('finishCaptureBtn').disabled = true;
        if (getEl('clearPointsBtn')) getEl('clearPointsBtn').disabled = true;
        if (getEl('captureInstructions')) getEl('captureInstructions').textContent = 'Click "Start Capture" to begin mapping your farm boundary. Walk around the perimeter and click "Add Point" at each corner (minimum 4 points required).';

        // Clear map polygon
        if (this.farmPolygon) {
            this.farmPolygon.setLatLngs([]);
        }

        // Reset GPS validation
        window.dispatchEvent(new CustomEvent('gpsPointsUpdated', { 
            detail: { count: 0, area: 0 } 
        }));
    }

    async handleCreateFarm() {
        try {
            // Collect all form data from Tab 1 (Basic Farm Information)
            const farmData = {
                // Farmer Identity (Section 1.1)
                full_name: document.getElementById('farmerFullName')?.value,
                phone_number: document.getElementById('farmerPhone')?.value,
                national_id: document.getElementById('farmerNationalId')?.value,
                gender: document.getElementById('farmerGender')?.value,
                cooperative_member_no: document.getElementById('cooperativeMemberNo')?.value,
                data_consent: document.getElementById('dataConsent')?.checked,
                consent_timestamp: document.getElementById('dataConsent')?.checked ? new Date().toISOString() : null,

                // Farm Basics (Section 1.2)
                farm_name: document.getElementById('farmName')?.value,
                location: document.getElementById('farmLocation')?.value,
                approximate_size_ha: parseFloat(document.getElementById('farmAreaEstimate')?.value) || null,
                land_ownership_type: document.getElementById('landOwnershipType')?.value,

                // GPS Polygon (Section 1.3)
                gps_points: this.gpsPoints || [],
                calculated_area_ha: null,

                // Coffee Production (Section 1.4)
                primary_crop: 'Coffee',
                coffee_variety: Array.from(document.querySelectorAll('input[name="coffeeVariety"]:checked')).map(cb => cb.value),
                estimated_annual_yield_kg: parseFloat(document.getElementById('estimatedYield')?.value) || null,
                farming_method: document.getElementById('farmingMethod')?.value,

                // Advanced Farm Information (Tab 2) - Optional
                // Land Documentation (Section 2.1)
                document_upload: null, // File handling needed separately
                parent_parcel_link: document.getElementById('parentParcelLink')?.value || null,

                // Agroforestry (Section 2.2)
                intercropped_species: Array.from(document.getElementById('intercroppedSpecies')?.selectedOptions || []).map(o => o.value),
                shade_trees_present: document.querySelector('input[name="shadeTrees"]:checked')?.value === 'yes',
                shade_tree_canopy_percent: parseInt(document.getElementById('shadeTreeCanopy')?.value) || null,
                estimated_coffee_trees: parseInt(document.getElementById('coffeeTreeCount')?.value) || null,
                agroforestry_start_year: parseInt(document.getElementById('agroforestryStartYear')?.value) || null,

                // Practice Log (Section 2.3)
                last_pruning_date: document.getElementById('lastPruningDate')?.value || null,
                last_harvesting_date: document.getElementById('lastHarvestingDate')?.value || null,
                planting_date: document.getElementById('plantingDate')?.value || null,
                planting_what: document.getElementById('plantingWhat')?.value || null,
                practice_photo: null, // File handling needed separately

                // Farm History and Heritage (Section 2.4)
                farm_established_year: parseInt(document.getElementById('farmEstablishedYear')?.value) || null,
                previous_land_use: document.getElementById('previousLandUse')?.value || null,
                certification_status: Array.from(document.getElementById('certificationStatus')?.selectedOptions || []).map(o => o.value),
                ngo_support: document.getElementById('ngoSupport')?.value || null,
                ngo_support_years: document.getElementById('ngoSupportYears')?.value || null
            };

            // Validate required fields from Tab 1
            const requiredFields = [
                'farmerFullName', 'farmerPhone', 'farmerNationalId', 'farmerGender',
                'cooperativeMemberNo', 'farmName', 'farmLocation', 'farmAreaEstimate',
                'landOwnershipType', 'estimatedYield', 'farmingMethod'
            ];

            const missingFields = requiredFields.filter(id => {
                const el = document.getElementById(id);
                return !el?.value?.trim();
            });

            const selectedVarieties = Array.from(document.querySelectorAll('input[name="coffeeVariety"]:checked'));
            if (selectedVarieties.length === 0) {
                const errEl = document.getElementById('coffeeVarietyError');
                if (errEl) errEl.style.display = 'block';
                missingFields.push('coffeeVariety');
            } else {
                const errEl = document.getElementById('coffeeVarietyError');
                if (errEl) errEl.style.display = 'none';
            }

            if (missingFields.length > 0) {
                this.showToast(`Please complete all required fields (${missingFields.length} missing)`, 'error');
                return;
            }

            // Check data consent
            if (!farmData.data_consent) {
                this.showToast('Data consent is required', 'error');
                return;
            }

            // Calculate area from GPS polygon if available (optional)
            if (this.gpsPoints && this.gpsPoints.length >= 3) {
                const polygonCoords = this.gpsPoints.map(point => [point.lat, point.lon]);
                farmData.calculated_area_ha = parseFloat((this.calculatePolygonArea(polygonCoords) / 10000).toFixed(4));
            }

            // farming_method values in the form already match LandUseTypeEnum directly
            // (monocrop, mixed_cropping, agroforestry, forest_reserve, buffer_zone)
            const landUseMap = {
                'agroforestry': 'agroforestry', 'monocrop': 'monocrop', 'mono crop': 'monocrop',
                'mono-crop': 'monocrop', 'mixed': 'mixed_cropping', 'mixed crop': 'mixed_cropping',
                'mixed cropping': 'mixed_cropping', 'mixed_cropping': 'mixed_cropping',
                'forest': 'forest_reserve', 'forest_reserve': 'forest_reserve',
                'buffer': 'buffer_zone', 'buffer_zone': 'buffer_zone',
                'other': 'other',
            };
            const landUseType = landUseMap[(farmData.farming_method || '').toLowerCase()] || farmData.farming_method || 'agroforestry';

            // coffee_variety is already an array from the checkboxes
            const coffeeVarieties = Array.isArray(farmData.coffee_variety)
                ? farmData.coffee_variety
                : [farmData.coffee_variety].filter(Boolean);

            // Build parcel list — require ≥ 3 GPS points (GPS auto-point + 2 boundary clicks)
            const hasPolygon = this.gpsPoints && this.gpsPoints.length >= 3;
            // Close polygon: ensure first point repeated at end
            let polygonPts = hasPolygon ? [...this.gpsPoints] : [];
            if (hasPolygon) {
                const f = polygonPts[0], l = polygonPts[polygonPts.length - 1];
                if (f.lat !== l.lat || f.lon !== l.lon) polygonPts.push({ ...f });
            }

            // Prepare API payload
            const farmCodeRaw = (document.getElementById('farmCode')?.value?.trim() || '').toUpperCase();
            const apiPayload = {
                farm_name: farmData.farm_name,
                farm_code: farmCodeRaw || undefined,
                total_area_hectares: farmData.calculated_area_ha || farmData.approximate_size_ha,
                coffee_varieties: coffeeVarieties,
                land_use_type: landUseType,
                years_farming: farmData.farm_established_year ? new Date().getFullYear() - farmData.farm_established_year : null,
                average_annual_production_kg: farmData.estimated_annual_yield_kg,
                centroid_lat: hasPolygon ? this.gpsPoints.reduce((s, p) => s + p.lat, 0) / this.gpsPoints.length : null,
                centroid_lon: hasPolygon ? this.gpsPoints.reduce((s, p) => s + p.lon, 0) / this.gpsPoints.length : null,
                parcels: hasPolygon ? [
                    {
                        parcel_number: '1',
                        parcel_name: farmData.farm_name || 'Main Parcel',
                        boundary_geojson: {
                            type: 'Polygon',
                            coordinates: [polygonPts.map(p => [p.lon, p.lat])]
                        },
                        area_hectares: farmData.calculated_area_ha || farmData.approximate_size_ha,
                        gps_accuracy_meters: Math.max(...this.gpsPoints.map(p => p.accuracy || 10)),
                        mapping_device: 'GPS',
                        land_use_type: landUseType
                    }
                ] : [],
                // Extended fields for EUDR compliance
                farmer: {
                    full_name: farmData.full_name,
                    phone_number: farmData.phone_number,
                    national_id_hash: this.hashString(farmData.national_id),
                    gender: farmData.gender,
                    cooperative_member_no: farmData.cooperative_member_no,
                    data_consent: farmData.data_consent,
                    consent_timestamp: farmData.consent_timestamp
                },
                land_parcel: {
                    display_name: farmData.farm_name,
                    administrative_area: farmData.location,
                    ownership_type: farmData.land_ownership_type,
                    entry_state: farmData.farming_method
                },
                delivery: {
                    crop_variety: farmData.coffee_variety,
                    estimated_yield_kg: farmData.estimated_annual_yield_kg
                },
                sustainability: {
                    agroforestry_start_year: farmData.agroforestry_start_year,
                    shade_trees_present: farmData.shade_trees_present,
                    shaded_crop: farmData.shade_trees_present,
                    previous_land_use: farmData.previous_land_use,
                    farm_established_year: farmData.farm_established_year,
                    certification_status: farmData.certification_status,
                    programme_support: farmData.ngo_support ? {
                        name: farmData.ngo_support,
                        years: farmData.ngo_support_years
                    } : null
                }
            };

            await api.createFarm(apiPayload);
            this.showToast('Farm created successfully', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('addFarmModal'));
            if (modal) modal.hide();
            setTimeout(() => {
                document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
            }, 300);

            if (this.currentPage === 'farms') {
                this.loadPage('farms');
            }
        } catch (error) {
            console.error('Failed to create farm:', error);
            this.showToast(error.message || 'Failed to create farm', 'error');
        }
    }

    // (duplicate calculatePolygonArea removed — single definition above)

    // Helper function to hash strings (simple hash for demo)
    hashString(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return hash.toString(16);
    }

    showCreateCooperativeModal() {
        const modalEl = document.getElementById('addCooperativeModal');
        if (modalEl) {
            const form = document.getElementById('addCooperativeForm');
            if (form) form.reset();
            // Dispose any stale instance before creating a fresh one so getInstance works later
            const existing = bootstrap.Modal.getInstance(modalEl);
            if (existing) existing.dispose();
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
        }
    }

    async showCooperativeDetails(coopId) {
        try {
            const coop = await api.getCooperative(coopId);
            
            // Create modal dynamically if it doesn't exist
            let modalEl = document.getElementById('coopDetailsModal');
            if (!modalEl) {
                modalEl = document.createElement('div');
                modalEl.id = 'coopDetailsModal';
                modalEl.className = 'modal fade';
                modalEl.tabIndex = -1;
                modalEl.style.maxHeight = '90vh';
                modalEl.innerHTML = `
                    <div class="modal-dialog modal-xl" style="max-height: 90vh; overflow-y: auto;">
                        <div class="modal-content">
                            <div class="modal-header sticky-top bg-light">
                                <h5 class="modal-title" id="coopDetailsModalTitle">Cooperative Details</h5>
                                <button type="button" class="btn-modal-close" data-bs-dismiss="modal"><i class="bi bi-x-lg"></i>Close</button>
                            </div>
                            <div class="modal-body" id="coopDetailsContent" style="max-height: 70vh; overflow-y: auto;">
                                <!-- Identification Section -->
                                <div class="mb-4">
                                    <h6 class="text-uppercase text-primary fw-bold mb-3"><i class="bi bi-building me-2"></i>Identification</h6>
                                    <div class="row g-3">
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Name</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsName"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Code</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsCode"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Registration Number</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsRegNumber"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Tax ID</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsTaxId"></p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Contact Information Section -->
                                <div class="mb-4">
                                    <h6 class="text-uppercase text-primary fw-bold mb-3"><i class="bi bi-telephone me-2"></i>Contact Information</h6>
                                    <div class="row g-3">
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Email</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsEmail"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Phone</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsPhone"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-12">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Address</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsAddress"></p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Contact Person Section -->
                                <div class="mb-4">
                                    <h6 class="text-uppercase text-primary fw-bold mb-3"><i class="bi bi-person me-2"></i>Contact Person</h6>
                                    <div class="row g-3">
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Name</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsContactPerson"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Phone</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsContactPhone"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Email</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsContactEmail"></p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Location Information Section -->
                                <div class="mb-4">
                                    <h6 class="text-uppercase text-primary fw-bold mb-3"><i class="bi bi-geo-alt me-2"></i>Location Information</h6>
                                    <div class="row g-3">
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Country</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsCountry"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">County</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsCounty"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">District</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsDistrict"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Subcounty</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsSubcounty"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Ward</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsWard"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Coordinates</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsCoordinates"></p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Organization Information Section -->
                                <div class="mb-4">
                                    <h6 class="text-uppercase text-primary fw-bold mb-3"><i class="bi bi-info-circle me-2"></i>Organization Information</h6>
                                    <div class="row g-3">
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Type</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsType"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Establishment Date</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsEstablishmentDate"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Legal Status</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsLegalStatus"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Members Count</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsMembers"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-12">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Governing Document</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsGoverningDocument"></p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Status Information Section -->
                                <div class="mb-4">
                                    <h6 class="text-uppercase text-primary fw-bold mb-3"><i class="bi bi-check-circle me-2"></i>Status</h6>
                                    <div class="row g-3">
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Is Active</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsActive"></p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-body">
                                                    <small class="text-muted text-uppercase">Verification Status</small>
                                                    <p class="mb-0 fw-semibold" id="coopDetailsVerificationStatus"></p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            </div>
                        </div>
                    </div>
                `;
                document.body.appendChild(modalEl);
            }
            
            // Helper function to set text content safely
            const setText = (elementId, value) => {
                const el = document.getElementById(elementId);
                if (el) el.textContent = value || 'N/A';
            };

            const formatDate = (dateString) => {
                if (!dateString) return 'N/A';
                return new Date(dateString).toLocaleDateString();
            };

            // Populate all cooperative details
            setText('coopDetailsName', coop.name);
            setText('coopDetailsCode', coop.code);
            setText('coopDetailsRegNumber', coop.registration_number);
            setText('coopDetailsTaxId', coop.tax_id);
            setText('coopDetailsEmail', coop.email);
            setText('coopDetailsPhone', coop.phone);
            setText('coopDetailsAddress', coop.address);
            setText('coopDetailsContactPerson', coop.contact_person);
            setText('coopDetailsContactPhone', coop.contact_person_phone);
            setText('coopDetailsContactEmail', coop.contact_person_email);
            setText('coopDetailsCountry', coop.country);
            setText('coopDetailsCounty', coop.county);
            setText('coopDetailsDistrict', coop.district);
            setText('coopDetailsSubcounty', coop.subcounty);
            setText('coopDetailsWard', coop.ward);
            
            // Format coordinates
            const coordinates = (coop.latitude && coop.longitude) 
                ? `${coop.latitude}, ${coop.longitude}` 
                : 'N/A';
            setText('coopDetailsCoordinates', coordinates);
            
            setText('coopDetailsType', coop.cooperative_type);
            setText('coopDetailsEstablishmentDate', formatDate(coop.establishment_date));
            setText('coopDetailsLegalStatus', coop.legal_status);
            setText('coopDetailsMembers', coop.member_count || 0);
            setText('coopDetailsGoverningDocument', coop.governing_document);
            setText('coopDetailsActive', coop.is_active ? 'Yes' : 'No');
            setText('coopDetailsVerificationStatus', coop.verification_status ? coop.verification_status.toUpperCase() : 'N/A');
            
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
        } catch (error) {
            console.error('Failed to load cooperative details:', error);
            this.showToast('Failed to load cooperative details', 'error');
        }
    }

    async handleCreateCooperative() {
        const submitBtn = document.querySelector('#addCooperativeForm [type="submit"], #addCooperativeModal .btn-primary');
        if (submitBtn) {
            if (submitBtn.disabled) return;
            submitBtn.disabled = true;
            submitBtn.dataset.originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Creating...';
        }
        try {
            const docFiles = {};
            document.querySelectorAll('#coopRequiredDocsList input[type="file"]').forEach(input => {
                if (input.files.length > 0) {
                    docFiles[input.dataset.docId] = input.files[0];
                }
            });
            
            const formData = new FormData();
            formData.append('name', document.getElementById('coopName').value);
            formData.append('registration_number', document.getElementById('coopRegNumber').value || '');
            formData.append('cooperative_type', document.getElementById('coopType').value || '');
            formData.append('email', document.getElementById('coopEmail').value || '');
            formData.append('phone', document.getElementById('coopPhone').value || '');
            formData.append('address', document.getElementById('coopAddress').value || '');
            formData.append('county', document.getElementById('coopCounty').value || '');
            formData.append('district', document.getElementById('coopDistrict').value || '');
            formData.append('subcounty', document.getElementById('coopSubcounty').value || '');
            formData.append('ward', document.getElementById('coopWard').value || '');
            formData.append('tax_id', '');
            formData.append('latitude', '');
            formData.append('longitude', '');
            formData.append('establishment_date', '');
            formData.append('contact_person', '');
            formData.append('contact_person_phone', '');
            formData.append('contact_person_email', '');
            formData.append('legal_status', '');
            formData.append('governing_document', '');
            formData.append('admin_email', document.getElementById('coopAdminEmail').value);
            formData.append('admin_first_name', document.getElementById('coopAdminFirstName').value || '');
            formData.append('admin_last_name', document.getElementById('coopAdminLastName').value || '');
            formData.append('admin_phone', document.getElementById('coopAdminPhone').value || '');
            
            // Collect document IDs as comma-separated string
            const docIdList = Object.keys(docFiles);
            if (docIdList.length > 0) {
                formData.append('document_ids', docIdList.join(','));
            }
            
            for (const [docId, file] of Object.entries(docFiles)) {
                formData.append('documents', file);
            }
            
            const nameVal = document.getElementById('coopName').value;
            const adminEmailVal = document.getElementById('coopAdminEmail').value;
            console.log('[DEBUG] Form values:', { name: nameVal, admin_email: adminEmailVal });
            console.log('[DEBUG] FormData entries:');
            for (let [key, value] of formData.entries()) {
                console.log('  ', key, ':', value);
            }
            
            if (!nameVal || !adminEmailVal) {
                this.showToast('Cooperative name and admin email are required', 'error');
                return;
            }

            const response = await api.createCooperativeWithDocs(formData);
            if (response) {
                this.showToast('Cooperative created successfully', 'success');
                const modalEl = document.getElementById('addCooperativeModal');
                const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                modal.hide();

                // Always navigate to cooperatives page so the new entry is visible
                this.navigateTo('cooperatives');
            }
        } catch (error) {
            console.error('Failed to create cooperative:', error);
            this.showToast(error.message || 'Failed to create cooperative', 'error');
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = submitBtn.dataset.originalText || 'Create Cooperative';
            }
        }
    }

    async loadCooperativeRequiredDocs() {
        const section = document.getElementById('coopRequiredDocsSection');
        const listDiv = document.getElementById('coopRequiredDocsList');
        if (!listDiv) return;
        
        try {
            const docs = await api.getRequiredDocuments();
            
            if (!docs || docs.length === 0) {
                section.style.display = 'none';
                return;
            }
            
            section.style.display = 'block';
            
            listDiv.innerHTML = docs.map(doc => `
                <div class="col-md-6 mb-3">
                    <div class="card h-100">
                        <div class="card-body">
                            <label class="form-label fw-bold">
                                ${doc.display_name}
                                ${doc.is_required ? '<span class="badge bg-warning text-dark ms-1">Required</span>' : ''}
                            </label>
                            ${doc.description ? `<small class="text-muted d-block mb-2">${doc.description}</small>` : ''}
                            <input type="file" class="form-control" id="coopDoc_${doc.id}" data-doc-id="${doc.id}" data-doc-name="${doc.name}" ${doc.is_required ? 'required' : ''} accept=".pdf,.jpg,.jpeg,.png,.doc,.docx">
                            <small class="text-muted">Accepted: PDF, JPG, PNG, DOC</small>
                        </div>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Error loading required docs:', error);
            section.style.display = 'none';
        }
    }

    // ==================== FARM MAPPING SYSTEM ====================

    setupNavigation() {
        // Set up navigation click handlers
        document.querySelectorAll('[data-page]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = e.currentTarget.getAttribute('data-page');
                this.loadPage(page);
            });
        });

        // Set up logout handler
        document.getElementById('logoutBtn').addEventListener('click', () => {
            api.logout();
            this.showLandingPage();
        });
    }

    initFarmMapping() {
        this.farmMap = null;
        this.drawnItems = null;
        this.captureMode = false;
        this.capturedPoints = [];
        this.gpsPoints = [];
        this.currentPolygon = null;
        this.gpsWatchId = null;
        this.isCapturing = false;
        this.lastKnownPosition = null;
        this._clickMarkers = [];
        this._clickPolyline = null;
        this.treeCaptureMode = false;
        this.capturedTrees = [];
        this.treeMarkers = [];
        this.cropCaptureMode = false;
        this.cropAreas = [];
        this.cropPolygons = [];
        this.availableCropTypes = [];
    }

    initMap() {
        if (this.farmMap) return; // Already initialized

        const mapElement = document.getElementById('farmMap');
        if (!mapElement) return;

        // Initialize Leaflet map
        this.farmMap = L.map('farmMap', {
            center: [-0.0236, 37.9062], // Default to Kenya center
            zoom: 8,
            zoomControl: true
        });

        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 18
        }).addTo(this.farmMap);

        // Add draw control
        this.drawnItems = new L.FeatureGroup();
        this.farmMap.addLayer(this.drawnItems);

        const drawControl = new L.Control.Draw({
            edit: {
                featureGroup: this.drawnItems,
                edit: false,
                remove: false
            },
            draw: {
                polygon: {
                    allowIntersection: false,
                    showArea: true,
                    drawError: {
                        color: '#e1e100',
                        message: '<strong>Error:</strong> Shape edges cannot cross!'
                    },
                    shapeOptions: {
                        color: '#6f4e37',
                        weight: 3,
                        opacity: 0.8,
                        fillColor: '#8b6914',
                        fillOpacity: 0.2
                    }
                },
                rectangle: false,
                circle: false,
                marker: false,
                polyline: false,
                circlemarker: false
            }
        });

        this.farmMap.addControl(drawControl);

        // Handle draw events
        this.farmMap.on(L.Draw.Event.CREATED, (event) => {
            const layer = event.layer;
            this.drawnItems.addLayer(layer);

            // Convert to GeoJSON and store
            const geojson = layer.toGeoJSON();
            this.currentPolygon = geojson;

            // Calculate area
            this.updateMapStats(geojson);

            // Enable finish button
            document.getElementById('finishCaptureBtn').disabled = false;
        });

        // Try to get user's location
        this.getUserLocation();
    }

    setupMappingEventListeners() {
        // GPS capture mode buttons
        document.getElementById('startCaptureBtn').addEventListener('click', () => {
            this.startGPSCapture();
        });

        document.getElementById('addPointBtn').addEventListener('click', () => {
            this.addGPSPoint();
        });

        document.getElementById('finishCaptureBtn').addEventListener('click', () => {
            this.finishCapture();
        });

        document.getElementById('clearPointsBtn').addEventListener('click', () => {
            this.clearCapture();
        });

        // Form submission - handled by event listener in constructor (handleCreateFarm)
    }

    getUserLocation() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const { latitude, longitude } = position.coords;
                    this.farmMap.setView([latitude, longitude], 15);

                    // Add a marker at user's location
                    L.marker([latitude, longitude])
                        .addTo(this.farmMap)
                        .bindPopup('Your Location')
                        .openPopup();
                },
                (error) => {
                    console.warn('Could not get user location:', error);
                    // Keep default view
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 300000
                }
            );
        }
    }

    _legacyStartGPSCapture() {
        this.captureMode = true;
        this.capturedPoints = [];

        document.getElementById('startCaptureBtn').disabled = true;
        document.getElementById('addPointBtn').disabled = false;
        document.getElementById('clearPointsBtn').disabled = false;
        document.getElementById('captureInstructions').textContent =
            'Walk to the first corner of your farm and click "Add Point". Continue around the perimeter.';

        this.showToast('GPS capture started. Walk to your farm boundary and add points.', 'info');
    }

    _legacyAddGPSPoint() {
        if (!this.captureMode) return;

        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const { latitude, longitude, accuracy } = position.coords;
                    const point = [latitude, longitude];

                    this.capturedPoints.push(point);

                    // Add marker to map
                    L.marker(point)
                        .addTo(this.drawnItems)
                        .bindPopup(`Point ${this.capturedPoints.length}<br>Accuracy: ${accuracy.toFixed(1)}m`)
                        .openPopup();

                    // Update point count
                    document.getElementById('pointCount').textContent = this.capturedPoints.length;
                    document.getElementById('gpsAccuracy').textContent = accuracy.toFixed(1);

                    // Draw line connecting points
                    if (this.capturedPoints.length > 1) {
                        this.updateCaptureLine();
                    }

                    // Enable finish button if we have at least 3 points
                    if (this.capturedPoints.length >= 3) {
                        document.getElementById('finishCaptureBtn').disabled = false;
                    }

                    this.showToast(`Point ${this.capturedPoints.length} added. Accuracy: ${accuracy.toFixed(1)}m`, 'success');
                },
                (error) => {
                    this.showToast('Could not get GPS location. Please try again.', 'error');
                },
                {
                    enableHighAccuracy: true,
                    timeout: 15000,
                    maximumAge: 10000
                }
            );
        } else {
            this.showToast('GPS not supported on this device.', 'error');
        }
    }

    updateCaptureLine() {
        // Remove existing line
        if (this.currentPolygon) {
            this.drawnItems.removeLayer(this.currentPolygon);
        }

        // Create new line
        const line = L.polyline(this.capturedPoints, {
            color: '#6f4e37',
            weight: 3,
            opacity: 0.8
        });

        this.drawnItems.addLayer(line);
        this.currentPolygon = line;
    }

    finishCapture() {
        if (this.capturedPoints.length < 3) {
            this.showToast('Need at least 3 points to create a farm boundary.', 'error');
            return;
        }

        // Close the polygon by adding first point at the end
        this.capturedPoints.push(this.capturedPoints[0]);

        // Create polygon
        const polygon = L.polygon(this.capturedPoints, {
            color: '#6f4e37',
            weight: 3,
            opacity: 0.8,
            fillColor: '#8b6914',
            fillOpacity: 0.2
        });

        // Clear existing layers and add polygon
        this.drawnItems.clearLayers();
        this.drawnItems.addLayer(polygon);

        // Convert to GeoJSON
        this.currentPolygon = polygon.toGeoJSON();

        // Calculate area
        this.updateMapStats(this.currentPolygon);

        // Reset capture mode
        this.captureMode = false;
        document.getElementById('startCaptureBtn').disabled = false;
        document.getElementById('addPointBtn').disabled = true;
        document.getElementById('finishCaptureBtn').disabled = true;
        document.getElementById('clearPointsBtn').disabled = true;

        this.showToast('Farm boundary captured successfully!', 'success');
    }

    clearCapture() {
        this.capturedPoints = [];
        this.captureMode = false;
        this.drawnItems.clearLayers();
        this.currentPolygon = null;

        document.getElementById('pointCount').textContent = '0';
        document.getElementById('gpsAccuracy').textContent = '--';
        document.getElementById('startCaptureBtn').disabled = false;
        document.getElementById('addPointBtn').disabled = true;
        document.getElementById('finishCaptureBtn').disabled = true;
        document.getElementById('clearPointsBtn').disabled = true;

        this.showToast('Capture cleared. Start again to map your farm.', 'info');
    }

    updateMapStats(geojson) {
        try {
            // Calculate area using Turf.js or simple approximation
            const area = this.calculateGeoJSONArea(geojson);
            const hectares = (area / 10000).toFixed(2); // Convert m² to hectares

            // Update area field if not set
            const areaInput = document.getElementById('farmArea');
            if (!areaInput.value) {
                areaInput.value = hectares;
            }

            this.showToast(`Farm area calculated: ${hectares} hectares`, 'info');
        } catch (error) {
            console.error('Error calculating area:', error);
        }
    }

    calculateGeoJSONArea(geojson) {
        // Simple area calculation for polygon
        // In production, use Turf.js or proper geospatial library
        if (!geojson.geometry || geojson.geometry.type !== 'Polygon') {
            return 0;
        }

        const coordinates = geojson.geometry.coordinates[0];
        let area = 0;

        for (let i = 0; i < coordinates.length - 1; i++) {
            const [lon1, lat1] = coordinates[i];
            const [lon2, lat2] = coordinates[i + 1];
            area += lon1 * lat2 - lon2 * lat1;
        }

        area = Math.abs(area) / 2;

        // Rough conversion to square meters (very approximate)
        // 1 degree² ≈ 111km² * 111km², but this is just for demo
        const lat_center = coordinates.reduce((sum, coord) => sum + coord[1], 0) / coordinates.length;
        const lat_rad = lat_center * Math.PI / 180;
        const meters_per_degree = 111320 * Math.cos(lat_rad);

        return Math.abs(area) * meters_per_degree * meters_per_degree;
    }

    async submitFarm() {
        try {
            const formData = new FormData(document.getElementById('addFarmForm'));
            const farmData = {
                farm_name: formData.get('farmName'),
                total_area_hectares: parseFloat(formData.get('farmAreaEstimate')) || null,
                coffee_varieties: formData.get('farmVarieties') ?
                    formData.get('farmVarieties').split(',').map(v => v.trim()) : [],
                years_farming: formData.get('farmYears') ? parseInt(formData.get('farmYears')) : null,
                average_annual_production_kg: formData.get('farmProduction') ? parseFloat(formData.get('farmProduction')) : null,
                parcels: []
            };

            // Add parcel if boundary was captured
            if (this.currentPolygon) {
                const parcel = {
                    parcel_number: 1,
                    parcel_name: 'Main Parcel',
                    boundary_geojson: this.currentPolygon.geometry,
                    area_hectares: farmData.total_area_hectares,
                    gps_accuracy_meters: document.getElementById('gpsAccuracy').textContent !== '--' ?
                        parseFloat(document.getElementById('gpsAccuracy').textContent) : null,
                    mapping_device: navigator.userAgent,
                    land_use_type: 'agroforestry'
                };

                // Add coffee area if specified
                if (farmData.total_area_hectares) {
                    parcel.coffee_area_hectares = farmData.total_area_hectares * 0.8; // Assume 80% coffee
                }

                farmData.parcels.push(parcel);
            }

            // Validate required fields
            if (!farmData.farm_name || !farmData.total_area_hectares) {
                throw new Error('Farm name and area are required');
            }

            const result = await api.createFarm(farmData);

            this.showToast('Farm created successfully!', 'success');

            // Close modal and refresh
            bootstrap.Modal.getInstance(document.getElementById('addFarmModal')).hide();
            setTimeout(() => {
                document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
            }, 300);
            this.loadFarmerFarms(); // Refresh farm list

        } catch (error) {
            this.showToast(`Error creating farm: ${error.message}`, 'error');
        }
    }

    // ==================== TREE CAPTURING SYSTEM ====================

    initTreeCapturing(farmId, parcelId) {
        this.currentFarmId = farmId;
        this.currentParcelId = parcelId;
        this.treeCaptureMode = false;
        this.capturedTrees = [];
        this.treeMarkers = [];

        // Add tree capture controls to the map
        this.addTreeCaptureControls();

        // Load existing trees
        this.loadExistingTrees();
    }

    addTreeCaptureControls() {
        if (!this.farmMap) return;

        // Create tree capture control panel
        const treeControl = L.control({ position: 'topright' });
        treeControl.onAdd = (map) => {
            const div = L.DomUtil.create('div', 'tree-capture-control');
            div.innerHTML = `
                <div class="card border-0 shadow-sm">
                    <div class="card-header bg-success text-white py-2">
                        <h6 class="mb-0"><i class="bi bi-tree me-2"></i>Tree Mapping</h6>
                    </div>
                    <div class="card-body p-2">
                        <div class="d-grid gap-2">
                            <button class="btn btn-sm btn-success" id="startTreeCaptureBtn">
                                <i class="bi bi-plus-circle me-1"></i>Start Tree Capture
                            </button>
                            <button class="btn btn-sm btn-info" id="viewTreesBtn">
                                <i class="bi bi-eye me-1"></i>View Trees
                            </button>
                            <button class="btn btn-sm btn-warning" id="editTreeBtn" disabled>
                                <i class="bi bi-pencil me-1"></i>Edit Tree
                            </button>
                        </div>
                        <div class="mt-2 text-xs">
                            <span id="treeCount">0 trees mapped</span>
                        </div>
                    </div>
                </div>
            `;
            return div;
        };
        treeControl.addTo(this.farmMap);

        // Add event listeners
        setTimeout(() => {
            document.getElementById('startTreeCaptureBtn').addEventListener('click', () => this.startTreeCapture());
            document.getElementById('viewTreesBtn').addEventListener('click', () => this.toggleTreeVisibility());
            document.getElementById('editTreeBtn').addEventListener('click', () => this.enableTreeEditing());
        }, 100);
    }

    startTreeCapture() {
        this.treeCaptureMode = true;
        document.getElementById('startTreeCaptureBtn').innerHTML = '<i class="bi bi-stop-circle me-1"></i>Stop Capture';
        document.getElementById('startTreeCaptureBtn').classList.remove('btn-success');
        document.getElementById('startTreeCaptureBtn').classList.add('btn-danger');

        this.showToast('Tree capture mode activated. Click on the map to add trees.', 'info');

        // Add click handler for tree placement
        this.farmMap.on('click', this.onTreeMapClick.bind(this));

        // Change cursor
        this.farmMap.getContainer().style.cursor = 'crosshair';
    }

    stopTreeCapture() {
        this.treeCaptureMode = false;
        document.getElementById('startTreeCaptureBtn').innerHTML = '<i class="bi bi-plus-circle me-1"></i>Start Tree Capture';
        document.getElementById('startTreeCaptureBtn').classList.remove('btn-danger');
        document.getElementById('startTreeCaptureBtn').classList.add('btn-success');

        this.farmMap.off('click', this.onTreeMapClick.bind(this));
        this.farmMap.getContainer().style.cursor = '';
    }

    onTreeMapClick(e) {
        if (!this.treeCaptureMode) return;

        const { lat, lng } = e.latlng;

        // Show tree details modal
        this.showTreeDetailsModal(lat, lng);
    }

    showTreeDetailsModal(lat, lng) {
        // Create modal for tree details
        const modalHtml = `
            <div class="modal fade" id="treeDetailsModal" tabindex="-1" data-bs-backdrop="static" data-bs-keyboard="false">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-tree me-2"></i>Add Tree</h5>
                            <button type="button" class="btn-modal-close" data-bs-dismiss="modal"><i class="bi bi-x-lg"></i>Close</button>
                        </div>
                        <form id="treeDetailsForm">
                            <div class="modal-body">
                                <div class="row g-3">
                                    <div class="col-12">
                                        <label class="form-label">Tree Type *</label>
                                        <select class="form-select" id="treeType" required>
                                            <option value="grevillea">Grevillea</option>
                                            <option value="macadamia">Macadamia</option>
                                            <option value="eucalyptus">Eucalyptus</option>
                                            <option value="indigenous">Indigenous</option>
                                            <option value="avocado">Avocado</option>
                                            <option value="mango">Mango</option>
                                            <option value="banana">Banana</option>
                                            <option value="citrus">Citrus</option>
                                            <option value="other">Other</option>
                                        </select>
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Height (meters)</label>
                                        <input type="number" class="form-control" id="treeHeight" step="0.1" min="0">
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Canopy Diameter (meters)</label>
                                        <input type="number" class="form-control" id="canopyDiameter" step="0.1" min="0">
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Age (years)</label>
                                        <input type="number" class="form-control" id="treeAge" min="0">
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Health Status</label>
                                        <select class="form-select" id="treeHealth">
                                            <option value="healthy">Healthy</option>
                                            <option value="stressed">Stressed</option>
                                            <option value="diseased">Diseased</option>
                                            <option value="dead">Dead</option>
                                        </select>
                                    </div>
                                    <div class="col-12">
                                        <label class="form-label">Planted Date</label>
                                        <input type="date" class="form-control" id="plantedDate">
                                    </div>
                                    <div class="col-12">
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="providesShade">
                                            <label class="form-check-label">Provides Shade</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="isFruitBearing">
                                            <label class="form-check-label">Fruit Bearing</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="isNativeSpecies">
                                            <label class="form-check-label">Native Species</label>
                                        </div>
                                    </div>
                                    <div class="col-12">
                                        <label class="form-label">Notes</label>
                                        <textarea class="form-control" id="treeNotes" rows="2"></textarea>
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="submit" class="btn btn-success">Save Tree</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if present
        const existingModal = document.getElementById('treeDetailsModal');
        if (existingModal) existingModal.remove();

        document.body.insertAdjacentHTML('beforeend', modalHtml);

        const modal = new bootstrap.Modal(document.getElementById('treeDetailsModal'));
        modal.show();

        // Handle form submission
        document.getElementById('treeDetailsForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.saveTree(lat, lng);
            modal.hide();
        });
    }

    async saveTree(lat, lng) {
        const treeData = {
            latitude: lat,
            longitude: lng,
            tree_type: document.getElementById('treeType').value,
            height_meters: document.getElementById('treeHeight').value || null,
            canopy_diameter_meters: document.getElementById('canopyDiameter').value || null,
            tree_age_years: document.getElementById('treeAge').value || null,
            health_status: document.getElementById('treeHealth').value,
            planted_date: document.getElementById('plantedDate').value || null,
            provides_shade: document.getElementById('providesShade').checked ? 1 : 0,
            is_fruit_bearing: document.getElementById('isFruitBearing').checked ? 1 : 0,
            is_native_species: document.getElementById('isNativeSpecies').checked ? 1 : 0,
            notes: document.getElementById('treeNotes').value
        };

        try {
            const result = await api.request(
                `/farmer/farm/${this.currentFarmId}/parcel/${this.currentParcelId}/trees`,
                {
                    method: 'POST',
                    body: JSON.stringify(treeData)
                }
            );

            // Add tree marker to map
            this.addTreeMarker(lat, lng, treeData, result.id);

            this.updateTreeCount();
            this.showToast('Tree added successfully!', 'success');

        } catch (error) {
            this.showToast(`Error saving tree: ${error.message}`, 'error');
        }
    }

    addTreeMarker(lat, lng, treeData, treeId) {
        // Determine marker color based on tree type and health
        let markerColor = 'green';
        if (treeData.health_status === 'diseased' || treeData.health_status === 'dead') {
            markerColor = 'red';
        } else if (treeData.health_status === 'stressed') {
            markerColor = 'orange';
        }

        // Create custom icon
        const treeIcon = L.divIcon({
            className: 'tree-marker',
            html: `<div style="background-color: ${markerColor}; border-radius: 50%; width: 20px; height: 20px; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;"><i class="bi bi-tree" style="color: white; font-size: 10px;"></i></div>`,
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        });

        const marker = L.marker([lat, lng], { icon: treeIcon })
            .addTo(this.farmMap)
            .bindPopup(`
                <div class="tree-popup">
                    <h6>${treeData.tree_type.charAt(0).toUpperCase() + treeData.tree_type.slice(1)}</h6>
                    <p class="mb-1"><strong>Health:</strong> ${treeData.health_status}</p>
                    ${treeData.height_meters ? `<p class="mb-1"><strong>Height:</strong> ${treeData.height_meters}m</p>` : ''}
                    ${treeData.canopy_diameter_meters ? `<p class="mb-1"><strong>Canopy:</strong> ${treeData.canopy_diameter_meters}m</p>` : ''}
                    ${treeData.provides_shade ? '<p class="mb-1"><i class="bi bi-sun"></i> Provides shade</p>' : ''}
                    ${treeData.is_fruit_bearing ? '<p class="mb-1"><i class="bi bi-apple"></i> Fruit bearing</p>' : ''}
                </div>
            `);

        // Store marker reference
        this.treeMarkers.push({
            id: treeId,
            marker: marker,
            data: treeData
        });
    }

    async loadExistingTrees() {
        if (!this.currentFarmId || !this.currentParcelId) return;

        try {
            const trees = await api.request(`/farmer/farm/${this.currentFarmId}/parcel/${this.currentParcelId}/trees`);

            trees.forEach(tree => {
                this.addTreeMarker(tree.latitude, tree.longitude, {
                    tree_type: tree.tree_type,
                    health_status: tree.health_status,
                    height_meters: tree.height_meters,
                    canopy_diameter_meters: tree.canopy_diameter_meters,
                    provides_shade: tree.provides_shade,
                    is_fruit_bearing: tree.is_fruit_bearing
                }, tree.id);
            });

            this.updateTreeCount();

        } catch (error) {
            console.error('Error loading trees:', error);
        }
    }

    updateTreeCount() {
        const count = this.treeMarkers.length;
        const countElement = document.getElementById('treeCount');
        if (countElement) {
            countElement.textContent = `${count} tree${count !== 1 ? 's' : ''} mapped`;
        }
    }

    toggleTreeVisibility() {
        const allVisible = this.treeMarkers.every(tm => this.farmMap.hasLayer(tm.marker));

        this.treeMarkers.forEach(tm => {
            if (allVisible) {
                this.farmMap.removeLayer(tm.marker);
            } else {
                tm.marker.addTo(this.farmMap);
            }
        });

        const btn = document.getElementById('viewTreesBtn');
        if (btn) {
            btn.innerHTML = allVisible ?
                '<i class="bi bi-eye-slash me-1"></i>Hide Trees' :
                '<i class="bi bi-eye me-1"></i>View Trees';
        }
    }

    enableTreeEditing() {
        // Enable editing mode for trees
        this.showToast('Tree editing mode - click on trees to edit', 'info');
        // Implementation would add click handlers to tree markers for editing
    }

    cleanupMap() {
        if (this.farmMap) {
            this.farmMap.remove();
            this.farmMap = null;
        }
        if (this.gpsWatchId) {
            navigator.geolocation.clearWatch(this.gpsWatchId);
            this.gpsWatchId = null;
        }
        this.captureMode = false;
        this.capturedPoints = [];
        this.currentPolygon = null;
        this.treeCaptureMode = false;
        this.capturedTrees = [];
        this.treeMarkers = [];
    }

    // ==================== SATELLITE ANALYSIS SYSTEM ====================

    async loadSatelliteAnalysis(farmId) {
        try {
            // Get farm calculations
            const calculations = await api.request(`/farmer/farm/${farmId}/calculations`);
            this.displayFarmCalculations(calculations);

            // Get satellite history
            const history = await api.request(`/farmer/farm/${farmId}/satellite-history`);
            this.displaySatelliteHistory(history);

            // Load satellite imagery if available
            this.loadSatelliteImagery(farmId);

        } catch (error) {
            console.error('Error loading satellite analysis:', error);
        }
    }

    async requestSatelliteAnalysis(farmId) {
        const btn = document.querySelector(`[onclick*="requestSatelliteAnalysis('${farmId}')"]`);
        if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Analysing…'; }

        try {
            const farm = await api.getFarmById(farmId);
            const parcels = (farm?.parcels || []).filter(p => p.boundary_geojson);
            if (!parcels.length) {
                this.showToast('Please capture the farm polygon first before running satellite analysis.', 'warning');
                return;
            }

            // Show a progress modal so the user sees parcel-by-parcel progress
            this._showAnalysisProgressModal(farm.farm_name || 'Farm', parcels.length);

            let completed = 0;
            let failed = 0;
            const acquisitionDate = new Date().toISOString();

            for (let i = 0; i < parcels.length; i++) {
                const parcel = parcels[i];
                const label = parcel.parcel_name || `Parcel ${i + 1}`;
                this._updateAnalysisProgress(i + 1, parcels.length, label, 'running');

                try {
                    const params = new URLSearchParams();
                    params.set('acquisition_date', acquisitionDate);
                    params.append('parcel_ids', parcel.id);
                    const result = await api.request(
                        `/farmer/farm/${farmId}/satellite-analysis?${params.toString()}`,
                        { method: 'POST' }
                    );
                    const ok = result.results?.some(r => r.status === 'completed');
                    if (ok) {
                        completed++;
                        this._updateAnalysisProgress(i + 1, parcels.length, label, 'done');
                    } else {
                        const err = result.results?.[0]?.error || 'No imagery found';
                        failed++;
                        this._updateAnalysisProgress(i + 1, parcels.length, label, 'failed', err);
                    }
                } catch (e) {
                    failed++;
                    this._updateAnalysisProgress(i + 1, parcels.length, label, 'failed', e.message);
                }
            }

            this._finaliseAnalysisProgress(completed, failed);

            if (completed > 0) {
                // Update selector to this farm and reload only this farm's analysis
                const selector = document.getElementById('analysisFarmSelector');
                if (selector) selector.value = farmId;
                this.switchAnalysisFarm(farmId);
            }

        } catch (error) {
            this.showToast(`Satellite analysis failed: ${error.message}`, 'error');
            this._closeAnalysisProgressModal();
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-satellite-fill me-1"></i>Analyse'; }
        }
    }

    _showAnalysisProgressModal(farmName, totalParcels) {
        let modal = document.getElementById('analysisProgressModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'analysisProgressModal';
            modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9999;display:flex;align-items:center;justify-content:center;';
            document.body.appendChild(modal);
        }
        modal.innerHTML = `
            <div class="card shadow-lg" style="min-width:360px;max-width:500px;width:90%;">
                <div class="card-header fw-semibold d-flex align-items-center gap-2">
                    <i class="bi bi-satellite-fill text-info"></i>
                    Satellite Analysis — ${farmName}
                </div>
                <div class="card-body">
                    <p class="text-muted small mb-3">Analysing ${totalParcels} parcel(s) one by one…</p>
                    <div id="analysisParcelList" class="d-flex flex-column gap-2"></div>
                </div>
                <div class="card-footer text-muted small" id="analysisProgressFooter">Starting…</div>
            </div>`;
        modal.style.display = 'flex';
    }

    _updateAnalysisProgress(index, total, label, state, errorMsg = '') {
        const list = document.getElementById('analysisParcelList');
        if (!list) return;
        let row = document.getElementById(`aprow-${index}`);
        if (!row) {
            row = document.createElement('div');
            row.id = `aprow-${index}`;
            row.className = 'd-flex align-items-center gap-2 p-2 rounded border';
            list.appendChild(row);
        }
        const icons = { running: '<span class="spinner-border spinner-border-sm text-info"></span>', done: '<i class="bi bi-check-circle-fill text-success"></i>', failed: '<i class="bi bi-x-circle-fill text-danger"></i>' };
        const colors = { running: 'border-info', done: 'border-success', failed: 'border-danger' };
        row.className = `d-flex align-items-start gap-2 p-2 rounded border ${colors[state] || ''}`;
        row.innerHTML = `
            <div style="min-width:20px;margin-top:1px">${icons[state] || ''}</div>
            <div>
                <div class="fw-semibold small">Parcel ${index} of ${total}: ${label}</div>
                ${errorMsg ? `<div class="text-danger" style="font-size:.75rem">${errorMsg}</div>` : ''}
            </div>`;
        const footer = document.getElementById('analysisProgressFooter');
        if (footer) footer.textContent = state === 'running' ? `Analysing parcel ${index} of ${total}…` : `Parcel ${index} of ${total} ${state}.`;
    }

    _finaliseAnalysisProgress(completed, failed) {
        const footer = document.getElementById('analysisProgressFooter');
        if (footer) footer.innerHTML = `<span class="text-success fw-semibold">${completed} completed</span>${failed ? `, <span class="text-danger">${failed} failed</span>` : ''} — <a href="#" onclick="document.getElementById('analysisProgressModal').style.display='none';return false;">Close</a>`;
        if (completed > 0) this.showToast(`Analysis complete — ${completed} parcel(s) processed.`, 'success');
        else this.showToast('No parcels could be analysed. Check parcel boundaries.', 'error');
    }

    _closeAnalysisProgressModal() {
        const modal = document.getElementById('analysisProgressModal');
        if (modal) modal.style.display = 'none';
    }

    async storeHistoricalAnalysis(farmId, analysisResults) {
        try {
            // Prepare historical data for storage
            const currentYear = new Date().getFullYear();

            for (const result of analysisResults) {
                if (result.status === 'completed') {
                    const historicalData = {
                        analysis_date: new Date().toISOString(),
                        analysis_year: currentYear,
                        analysis_period: 'quarterly', // Could be dynamic based on frequency
                        satellite_source: result.satellite_source || 'SENTINEL_2',
                        acquisition_date: result.acquisition_date,
                        cloud_cover_percentage: result.cloud_cover_percentage || 0,
                        ndvi_mean: result.ndvi_mean,
                        ndvi_min: result.ndvi_min,
                        ndvi_max: result.ndvi_max,
                        evi_mean: result.evi,
                        savi_mean: result.savi,
                        lai_mean: result.lai,
                        canopy_cover_percentage: result.canopy_cover_percentage,
                        tree_cover_percentage: result.tree_cover_percentage,
                        crop_cover_percentage: result.crop_cover_percentage,
                        bare_soil_percentage: result.bare_soil_percentage,
                        biomass_tons_hectare: result.biomass_tons_hectare,
                        carbon_stored_tons: result.carbon_stored_tons,
                        carbon_sequestered_kg_year: result.carbon_sequestered_kg_year,
                        deforestation_detected: result.deforestation_detected ? 1 : 0,
                        deforestation_area_ha: result.deforestation_area_ha || 0,
                        risk_level: result.risk_level,
                        risk_score: result.risk_score,
                        tree_count: result.tree_count,
                        tree_health_score: result.tree_health_score,
                        crop_health_score: result.crop_health_score,
                        analysis_metadata: {
                            analysis_type: result.analysis_type || 'standard',
                            seasonal_adjustment_applied: result.seasonal_adjustment_applied || false
                        }
                    };

                    await api.request(`/farmer/farm/${farmId}/store-historical-analysis`, {
                        method: 'POST',
                        body: JSON.stringify(historicalData)
                    });
                }
            }

        } catch (error) {
            console.error('Error storing historical analysis:', error);
            // Don't show error to user as this is background operation
        }
    }

    displayFarmCalculations(calculations) {
        const container = document.getElementById('farmCalculations');
        if (!container) return;

        container.innerHTML = `
            <div class="row g-3">
                <div class="col-md-3">
                    <div class="card border-0 shadow-sm">
                        <div class="card-body text-center">
                            <i class="bi bi-geo-alt-fill text-success fs-1"></i>
                            <h4 class="mt-2">${calculations.total_area_hectares || 0} ha</h4>
                            <small class="text-muted">Total Area</small>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card border-0 shadow-sm">
                        <div class="card-body text-center">
                            <i class="bi bi-cup-hot-fill text-warning fs-1"></i>
                            <h4 class="mt-2">${calculations.coffee_area_hectares || 0} ha</h4>
                            <small class="text-muted">Coffee Area</small>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card border-0 shadow-sm">
                        <div class="card-body text-center">
                            <i class="bi bi-graph-up text-info fs-1"></i>
                            <h4 class="mt-2">${calculations.average_ndvi || 0}</h4>
                            <small class="text-muted">Avg NDVI</small>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card border-0 shadow-sm">
                        <div class="card-body text-center">
                            <i class="bi bi-tree-fill text-success fs-1"></i>
                            <h4 class="mt-2">${calculations.total_biomass_tons || 0} t</h4>
                            <small class="text-muted">Biomass</small>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row mt-3">
                <div class="col-md-6">
                    <div class="card border-0 shadow-sm">
                        <div class="card-body">
                            <h6 class="card-title">Yield Estimation</h6>
                            <p class="mb-1">Estimated Annual Yield: <strong>${calculations.estimated_yearly_yield_tons || 0} tons</strong></p>
                            <p class="mb-0">Yield per Hectare: <strong>${calculations.yield_per_hectare || 0} t/ha</strong></p>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card border-0 shadow-sm">
                        <div class="card-body">
                            <h6 class="card-title">Carbon Storage</h6>
                            <p class="mb-1">Total CO2 Stored: <strong>${calculations.carbon_stored_co2 || 0} tons</strong></p>
                            <p class="mb-0">Last Analysis: <strong>${calculations.last_analysis_date ?
                                new Date(calculations.last_analysis_date).toLocaleDateString() : 'Never'}</strong></p>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    displaySatelliteHistory(history) {
        const container = document.getElementById('satelliteHistory');
        if (!container) return;

        if (!history || history.length === 0) {
            container.innerHTML = '<div class="text-muted">No satellite analysis history available</div>';
            return;
        }

        container.innerHTML = `
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Source</th>
                            <th>NDVI</th>
                            <th>Canopy Cover</th>
                            <th>Biomass</th>
                            <th>Risk Level</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${history.map(item => `
                            <tr>
                                <td>${new Date(item.acquisition_date).toLocaleDateString()}</td>
                                <td>${item.satellite_source || 'Unknown'}</td>
                                <td>${item.ndvi_mean ? item.ndvi_mean.toFixed(3) : '-'}</td>
                                <td>${item.canopy_cover_percentage ? item.canopy_cover_percentage.toFixed(1) + '%' : '-'}</td>
                                <td>${item.biomass_tons_hectare ? item.biomass_tons_hectare.toFixed(1) + ' t/ha' : '-'}</td>
                                <td>
                                    <span class="badge bg-${item.risk_level === 'high' ? 'danger' :
                                        item.risk_level === 'medium' ? 'warning' : 'success'}">
                                        ${item.risk_level || 'unknown'}
                                    </span>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    loadSatelliteImagery(farmId) {
        const container = document.getElementById('satelliteImagery');
        if (!container) return;

        // Create satellite imagery controls
        container.innerHTML = `
            <div class="card border-0 shadow-sm">
                <div class="card-header bg-light">
                    <h6 class="mb-0">Satellite Imagery</h6>
                </div>
                <div class="card-body">
                    <div class="row g-3">
                        <div class="col-md-4">
                            <select class="form-select" id="imageryType">
                                <option value="ndvi">NDVI (Health)</option>
                                <option value="true_color">True Color</option>
                                <option value="false_color">False Color</option>
                            </select>
                        </div>
                        <div class="col-md-4">
                            <input type="date" class="form-control" id="imageryDate"
                                   value="${new Date().toISOString().split('T')[0]}">
                        </div>
                        <div class="col-md-4">
                            <button class="btn btn-primary w-100" id="loadImageryBtn">
                                <i class="bi bi-eye"></i> Load Imagery
                            </button>
                        </div>
                    </div>
                    <div id="imageryContainer" class="mt-3" style="height: 400px; background: #f8f9fa; border-radius: 8px; display: flex; align-items: center; justify-content: center;">
                        <div class="text-muted text-center">
                            <i class="bi bi-image fs-1"></i>
                            <p class="mt-2">Select options above to load satellite imagery</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add event listener
        document.getElementById('loadImageryBtn').addEventListener('click', async () => {
            const type = document.getElementById('imageryType').value;
            const date = document.getElementById('imageryDate').value;

            try {
                const imageryData = await api.request(`/farmer/farm/${farmId}/satellite-imagery?image_type=${type}&date=${date}`);

                // Display imagery (placeholder for actual implementation)
                document.getElementById('imageryContainer').innerHTML = `
                    <div class="text-center">
                        <i class="bi bi-satellite fs-1 text-primary"></i>
                        <h5 class="mt-2">Satellite Imagery Loaded</h5>
                        <p class="text-muted">Type: ${type.toUpperCase()}</p>
                        <p class="text-muted">Date: ${new Date(date).toLocaleDateString()}</p>
                        <small class="text-muted">${imageryData.note}</small>
                    </div>
                `;

            } catch (error) {
                document.getElementById('imageryContainer').innerHTML = `
                    <div class="text-center text-danger">
                        <i class="bi bi-exclamation-triangle fs-1"></i>
                        <p class="mt-2">Failed to load imagery</p>
                        <small>${error.message}</small>
                    </div>
                `;
            }
        });
    }

    async loadPage(pageName) {
        const pageContent = document.getElementById('pageContent');
        const pageTitle = document.getElementById('pageTitle');

        // Update page title
        pageTitle.textContent = pageName.charAt(0).toUpperCase() + pageName.slice(1);

        // Load page content based on page name
        switch(pageName) {
            case 'dashboard':
                await this.loadDashboard(pageContent);
                break;
            case 'farms': {
                const fr = (this.currentUser?.role || '').toUpperCase();
                if (fr === 'FARMER') {
                    await this.loadFarmsPage();
                } else {
                    await this.loadFarms(pageContent);
                }
                break;
            }
            case 'parcels':
                await this.loadParcels(pageContent);
                break;
            case 'deliveries':
                await this.loadDeliveries(pageContent);
                break;
            case 'batches':
                await this.loadBatches(pageContent);
                break;
            case 'documents':
                await this.loadDocuments(pageContent);
                break;
            case 'satellite':
                await this.loadSatellite(pageContent);
                break;
            case 'cooperatives':
                await this.loadCooperatives(pageContent);
                break;
            case 'farmers':
                await this.loadFarmers(pageContent);
                break;
            case 'farmer-approvals':
                await this.loadFarmerApprovals(pageContent);
                break;
            case 'coop-farmers':
                await this.loadCoopFarmersList(pageContent);
                break;
            case 'coop-farms':
                await this.loadCoopFarms(pageContent);
                break;
            case 'farm-approvals':
                if ((this.currentUser?.role || '').toLowerCase() === 'cooperative_officer') {
                    await this.loadCoopFarmApprovals(pageContent);
                } else {
                    await this.loadFarms(pageContent);
                }
                break;
            case 'coop-team':
                await this.loadCoopTeam(pageContent);
                break;
            case 'wallet':
                await this.loadWallet(pageContent);
                break;
            case 'users':
                await this.loadUsers(pageContent);
                break;
            case 'verification':
            case 'pending_verification':
                await this.loadVerification(pageContent);
                break;
            case 'sustainability':
                await this.loadSustainability(pageContent);
                break;
            case 'system':
                await this.loadSystemConfig(pageContent);
                break;
            case 'compliance':
                await this.loadCompliance(pageContent);
                break;
            case 'profile':
                await this.loadProfile(pageContent);
                break;
            default:
                pageContent.innerHTML = '<div class="text-center mt-5"><h3>Page not found</h3></div>';
        }

        // Update active nav item
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        const activeLink = document.querySelector(`[data-page="${pageName}"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }
    }

    async loadFarmsPage() {
        const pageContent = document.getElementById('pageContent');

        pageContent.innerHTML = `
            <div class="row">
                <div class="col-12">
                    <div class="card border-0 shadow-sm">
                        <div class="card-header bg-white d-flex justify-content-between align-items-center">
                            <h5 class="mb-0"><i class="bi bi-geo-alt me-2"></i>My Farms</h5>
                            ${this.currentUser?.verification_status === 'verified'
                                ? `<button class="btn btn-primary" onclick="app.showAddFarmModal()"><i class="bi bi-plus-circle me-1"></i>Add Farm</button>`
                                : `<span class="badge bg-warning text-dark px-3 py-2" style="font-size:0.75rem;"><i class="bi bi-hourglass-split me-1"></i>Pending Verification</span>`}
                        </div>
                        <div class="card-body">
                            <div id="farmCalculations">
                                <div class="text-center py-3">
                                    <div class="spinner-border spinner-border-sm" role="status"></div>
                                    <span class="ms-2">Loading calculations...</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Analysis Farm Selector -->
                <div class="col-12">
                    <div class="card border-0 shadow-sm">
                        <div class="card-body py-2 d-flex align-items-center gap-3">
                            <label class="form-label mb-0 fw-semibold text-nowrap"><i class="bi bi-geo-alt-fill me-1" style="color:#6f4e37;"></i>View analysis for:</label>
                            <select class="form-select form-select-sm" id="analysisFarmSelector" style="max-width:320px;" onchange="app.switchAnalysisFarm(this.value)">
                                <option value="">— select a mapped farm —</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- Historical Analysis -->
                <div class="col-12">
                    <div class="card border-0 shadow-sm">
                        <div class="card-header bg-light d-flex justify-content-between align-items-center">
                            <h6 class="mb-0">Historical Analysis</h6>
                            <div class="d-flex align-items-center gap-2">
                                <select class="form-select form-select-sm" id="historyYearFilter" style="width: auto;">
                                    <option value="">All Years</option>
                                    <option value="2024">2024</option>
                                    <option value="2023">2023</option>
                                    <option value="2022">2022</option>
                                    <option value="2021">2021</option>
                                </select>
                                <button class="btn btn-sm btn-outline-success" onclick="app.exportAnalysisReport()" title="Export as PDF proof">
                                    <i class="bi bi-file-earmark-arrow-down me-1"></i>Export Report
                                </button>
                            </div>
                        </div>
                        <div class="card-body">
                            <div class="row g-3 mb-3">
                                <div class="col-md-5">
                                    <div class="card border-0 shadow-sm h-100">
                                        <div class="card-header py-2 fw-semibold small d-flex align-items-center gap-2" style="background:#f8f4f0;">
                                            <i class="bi bi-image text-success"></i> Satellite Image
                                        </div>
                                        <div class="card-body p-2" id="satelliteImagePanel">
                                            <div class="text-muted text-center py-3 small"><i class="bi bi-clock-history me-2"></i>No farm selected</div>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-7">
                                    <div id="historicalAnalysis">
                                        <div class="text-muted text-center py-3"><i class="bi bi-clock-history me-2"></i>No farm selected</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Tree & Crop Management -->
                <div class="col-12">
                    <div class="card border-0 shadow-sm">
                        <div class="card-header d-flex justify-content-between align-items-center" style="background: linear-gradient(135deg, #6f4e37 0%, #8b4513 100%); color: white;">
                            <h6 class="mb-0"><i class="bi bi-tree me-2"></i>Agroforestry Management</h6>
                            <button class="btn btn-sm" style="background-color: #daa520; color: #3d2515;" onclick="app.openTreeMapping()">
                                <i class="bi bi-plus-circle me-1"></i>Map Trees & Crops
                            </button>
                        </div>
                        <div class="card-body">
                            <div id="treeManagement">
                                <div class="text-muted text-center py-3"><i class="bi bi-tree me-2"></i>No farm selected</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Crop Analysis Results -->
                <div class="col-12">
                    <div class="card border-0 shadow-sm">
                        <div class="card-header" style="background-color: #daa520; color: #3d2515;">
                            <h6 class="mb-0"><i class="bi bi-seedling me-2"></i>Crop Differentiation Analysis</h6>
                        </div>
                        <div class="card-body">
                            <div id="cropAnalysis">
                                <div class="text-muted text-center py-3"><i class="bi bi-seedling me-2"></i>No farm selected</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Farm Details Modal -->
            <div class="modal fade" id="farmDetailsModal" tabindex="-1" data-bs-backdrop="static" data-bs-keyboard="false">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-geo-alt me-2"></i>Farm Details</h5>
                            <button type="button" class="btn-modal-close" data-bs-dismiss="modal"><i class="bi bi-x-lg"></i>Close</button>
                        </div>
                        <div class="modal-body">
                            <div id="farmDetailsContent">
                                <!-- Farm details will be loaded here -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        await this.loadFarmerFarms();
    }

    async loadFarmerFarms() {
        try {
            const farmsResponse = await api.getFarms();
            let farms = [];
            
            if (farmsResponse) {
                if (Array.isArray(farmsResponse)) {
                    farms = farmsResponse;
                } else if (farmsResponse.farms && Array.isArray(farmsResponse.farms)) {
                    farms = farmsResponse.farms;
                } else if (farmsResponse.id || farmsResponse.farm_name) {
                    farms = [farmsResponse];
                }
            }

            let farmsList = document.getElementById('farmCalculations');
            if (!farmsList) {
                // Not on farms page yet — navigate there first
                await this.loadFarmsPage();
                farmsList = document.getElementById('farmCalculations');
                if (!farmsList) return;
            }
            if (!farms || farms.length === 0) {
                farmsList.innerHTML = `
                    <div class="text-center py-5">
                        <i class="bi bi-geo-alt fs-1 text-muted"></i>
                        <h5 class="text-muted mt-2">No farms found</h5>
                        <p class="text-muted">Create your first farm to get started with satellite monitoring.</p>
                    </div>`;
            } else {
                farmsList.innerHTML = `<div class="row g-3">` + farms.map(farm => {
                    const hasPolygon = !!(farm.parcels && farm.parcels.length > 0 && farm.parcels[0].boundary_geojson);
                    const statusColor = { draft:'secondary', pending:'warning', verified:'success', rejected:'danger' }[farm.verification_status] || 'secondary';
                    const compColor = farm.compliance_status === 'Compliant' ? 'success' : farm.compliance_status === 'Under Review' ? 'warning' : 'secondary';
                    const updateBanner = farm.update_requested
                        ? `<div class="alert alert-warning py-2 px-3 mb-2 d-flex align-items-start gap-2" style="font-size:.82rem">
                               <i class="bi bi-exclamation-triangle-fill text-warning mt-1 flex-shrink-0"></i>
                               <div class="flex-grow-1">
                                   <strong>Update Required</strong>${farm.update_requested_by_name ? ` by ${farm.update_requested_by_name}` : ''}<br>
                                   ${farm.update_request_notes || ''}
                               </div>
                               <div class="d-flex gap-1 ms-2 flex-shrink-0">
                                   <button class="btn btn-sm btn-primary" onclick="app.viewFarmDetails('${farm.id}')">
                                       <i class="bi bi-pencil-fill me-1"></i>Edit
                                   </button>
                                   <button class="btn btn-sm btn-success" onclick="app.resubmitFarmForReview('${farm.id}')">
                                       <i class="bi bi-send-check me-1"></i>Resubmit
                                   </button>
                               </div>
                           </div>`
                        : '';
                    return `
                <div class="col-12 col-sm-6 col-xl-4">
                    <div class="card h-100 shadow-sm" style="border:none;border-left:4px solid var(--bs-${statusColor});min-width:240px;">
                        <div class="card-body d-flex flex-column p-3">
                            ${updateBanner}
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <h6 class="card-title mb-0 fw-semibold" style="word-break:break-word;flex:1;padding-right:8px">${farm.farm_name || 'Unnamed Farm'}</h6>
                                <span class="badge bg-${statusColor} text-capitalize flex-shrink-0">${farm.verification_status || 'draft'}</span>
                            </div>
                            <div class="flex-grow-1 mb-3">
                                <div class="text-muted small"><i class="bi bi-geo-alt me-1 text-success"></i>${farm.total_area_hectares || 0} ha total</div>
                                <div class="text-muted small"><i class="bi bi-cup-hot me-1 text-success"></i>${farm.coffee_area_hectares || 0} ha coffee</div>
                                <div class="text-muted small"><i class="bi bi-shield-check me-1 text-success"></i><span class="badge bg-${compColor} bg-opacity-75">${farm.compliance_status || 'Under Review'}</span></div>
                                <div class="text-muted small mt-1"><i class="bi bi-calendar me-1"></i>Created: ${farm.created_at ? new Date(farm.created_at).toLocaleDateString() : '-'}</div>
                            </div>
                            <div class="d-flex gap-1 flex-wrap mt-auto">
                                <button class="btn btn-outline-primary btn-sm flex-fill" style="min-width:70px"
                                    onclick="app.viewFarmDetails('${farm.id}')">
                                    <i class="bi bi-eye-fill me-1"></i>View
                                </button>
                                <button class="btn btn-${hasPolygon ? 'outline-warning' : 'outline-success'} btn-sm flex-fill" style="min-width:70px"
                                    data-capture-farm-id="${farm.id}" data-is-recapture="${hasPolygon}">
                                    <i class="bi bi-${hasPolygon ? 'arrow-repeat' : 'geo-alt-fill'} me-1"></i>${hasPolygon ? 'Recapture' : 'Capture'}
                                </button>
                                <button class="btn btn-outline-info btn-sm flex-fill" style="min-width:70px"
                                    onclick="app.requestSatelliteAnalysis('${farm.id}')"
                                    ${!hasPolygon ? 'disabled title="Capture farm polygon first"' : ''}>
                                    <i class="bi bi-satellite-fill me-1"></i>Analyse
                                </button>
                            </div>
                        </div>
                    </div>
                </div>`;
                }).join('') + `</div>`;

            // Attach event listeners for capture buttons (in case inline onclick fails)
            farmsList.querySelectorAll('[data-capture-farm-id]').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const farmId = btn.getAttribute('data-capture-farm-id');
                    const isRecapture = btn.getAttribute('data-is-recapture') === 'true';
                    this.openFarmCapture(farmId, isRecapture);
                });
            });
            }
            // Populate analysis farm selector with mapped farms only
            const mappedFarms = farms?.filter(f => f.parcels?.length > 0 && f.parcels[0].boundary_geojson) || [];
            const selector = document.getElementById('analysisFarmSelector');
            if (selector) {
                const previouslySelected = selector.value;
                selector.innerHTML = '<option value="">— select a mapped farm —</option>' +
                    mappedFarms.map(f => `<option value="${f.id}">${f.farm_name || 'Unnamed Farm'}</option>`).join('');
                // Restore previously selected farm; only default to first farm on initial load
                const targetId = previouslySelected && mappedFarms.find(f => f.id === previouslySelected)
                    ? previouslySelected
                    : (mappedFarms.length > 0 ? mappedFarms[0].id : '');
                if (targetId) {
                    selector.value = targetId;
                    this.loadHistoricalAnalysis(targetId);
                    this.loadTreeManagement(targetId);
                    this.loadCropAnalysis(targetId);
                }
            }
        } catch (error) {
            console.error('Error loading farms:', error);
            const farmsList = document.getElementById('farmCalculations');
            if (farmsList) {
                farmsList.innerHTML = `
                <div class="col-12 text-center py-5 text-danger">
                    <i class="bi bi-exclamation-triangle fs-1"></i>
                    <p class="mt-2">Error loading farms</p>
                    <small>${error.message}</small>
                </div>`;
            }
        }
    }

    switchAnalysisFarm(farmId) {
        if (!farmId) return;
        const setLoading = (id, msg) => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = `<div class="text-center py-3"><div class="spinner-border spinner-border-sm" role="status"></div><span class="ms-2">${msg}</span></div>`;
        };
        setLoading('historicalAnalysis', 'Loading historical data...');
        setLoading('satelliteImagePanel', 'Loading satellite image...');
        setLoading('treeManagement', 'Loading agroforestry data...');
        setLoading('cropAnalysis', 'Loading crop analysis...');
        this.loadHistoricalAnalysis(farmId);
        this.loadSatelliteImage(farmId);
        this.loadTreeManagement(farmId);
        this.loadCropAnalysis(farmId);
    }

    async loadSatelliteImage(farmId) {
        const panel = document.getElementById('satelliteImagePanel');
        if (!panel) return;
        try {
            const data = await api.request(`/farmer/farm/${farmId}/satellite-image`, { optional: true });
            if (!data || !data.image_base64) {
                panel.innerHTML = '<div class="text-muted text-center py-3 small">No satellite image available</div>';
                return;
            }
            panel.innerHTML = `
                <div class="position-relative">
                    <img src="data:image/png;base64,${data.image_base64}"
                         alt="Sentinel-2 true-colour image"
                         class="img-fluid rounded w-100"
                         style="max-height:340px;object-fit:cover;border:1px solid #dee2e6;">
                    <div class="position-absolute bottom-0 start-0 end-0 p-2 text-white small"
                         style="background:linear-gradient(transparent,rgba(0,0,0,.65));border-radius:0 0 6px 6px;">
                        <i class="bi bi-satellite me-1"></i>Sentinel-2 L2A &nbsp;·&nbsp;
                        ${data.from_date} – ${data.to_date} &nbsp;·&nbsp;
                        True colour (B4/B3/B2) &nbsp;·&nbsp; Copernicus Data Space
                    </div>
                </div>`;
        } catch (e) {
            panel.innerHTML = `<div class="text-muted text-center py-3 small"><i class="bi bi-exclamation-circle me-1"></i>${e.message || 'Image unavailable'}</div>`;
        }
    }

    async viewFarmDetails(farmId) {
        const modalEl = document.getElementById('viewFarmModal');
        const content = document.getElementById('farmDetailsContent');
        const titleEl = document.getElementById('viewFarmModalTitle');
        if (!modalEl) return;

        content.innerHTML = `<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>`;
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();

        try {
            const farm = await api.getFarmById(farmId);
            if (!farm) { this.showToast('Farm not found', 'error'); modal.hide(); return; }
            if (titleEl) titleEl.textContent = farm.farm_name || 'Farm Details';

            const parcels = farm.parcels || [];
            const hasPolygon = parcels.length > 0 && parcels[0].boundary_geojson;
            const parcel = parcels[0] || {};
            const statusColor = { draft:'secondary', pending:'warning', verified:'success', rejected:'danger' }[farm.verification_status] || 'secondary';
            const cvStr = Array.isArray(farm.coffee_varieties) ? farm.coffee_varieties.join(', ') : (farm.coffee_varieties || '');

            const fv = (v) => v != null && v !== '' ? v : '';

            content.innerHTML = `
            <form id="editFarmForm" data-farm-id="${farm.id}" class="p-3 p-md-4">

              <!-- Status banner -->
              <div class="alert alert-${statusColor} d-flex align-items-center gap-2 py-2 mb-3">
                <i class="bi bi-info-circle-fill"></i>
                <span>Status: <strong class="text-capitalize">${farm.verification_status || 'draft'}</strong>
                  ${farm.verification_status === 'draft' ? ' — Boundary not yet captured.' :
                    farm.verification_status === 'pending' ? ' — Awaiting admin review.' :
                    farm.verification_status === 'verified' ? ' — Verified &amp; compliant.' :
                    farm.verification_status === 'rejected' ? ` — Rejected. ${farm.notes ? farm.notes : ''}` : ''}
                </span>
              </div>

              <!-- Farm ID — share with field agent for mobile app access -->
              <div class="card border-0 mb-4" style="background:linear-gradient(135deg,#2c1a0e,#6f4e37);color:#fff;border-radius:10px;">
                <div class="card-body py-3 px-4 d-flex align-items-center justify-content-between flex-wrap gap-3">
                  <div>
                    <div class="small text-white-50 mb-1"><i class="bi bi-hash me-1"></i>Farm ID — for field agent mobile app</div>
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                      <span class="badge bg-white text-dark fs-5 px-3 py-2 font-monospace fw-bold">${farm.id}</span>
                      ${farm.farm_code ? `<span class="badge border border-white text-white px-3 py-2 font-monospace">${farm.farm_code}</span>` : ''}
                    </div>
                  </div>
                  <button type="button" class="btn btn-sm btn-outline-light"
                    onclick="navigator.clipboard.writeText('${farm.id}').then(()=>this.innerHTML='<i class=\\'bi bi-check-lg me-1\\'></i>Copied!').catch(()=>{})">
                    <i class="bi bi-clipboard me-1"></i>Copy ID
                  </button>
                </div>
              </div>

              <!-- Map -->
              ${hasPolygon ? `
              <div class="card border-0 shadow-sm mb-4">
                <div class="card-header d-flex justify-content-between align-items-center py-2" style="background:linear-gradient(135deg,#2c1a0e,#6f4e37);color:#fff;">
                  <span><i class="bi bi-map me-2"></i>Farm Boundary</span>
                  <button type="button" class="btn btn-sm btn-outline-light" onclick="app.openFarmCapture('${farm.id}', true)">
                    <i class="bi bi-arrow-repeat me-1"></i>Recapture
                  </button>
                </div>
                <div id="viewFarmMap" style="height:260px;"></div>
              </div>` : `
              <div class="card border-0 shadow-sm mb-4 text-center py-4 text-muted">
                <i class="bi bi-geo-alt fs-1 d-block mb-2"></i>
                <p class="mb-3">No boundary captured yet.</p>
                <button type="button" class="btn btn-success btn-sm" onclick="bootstrap.Modal.getInstance(document.getElementById('viewFarmModal')).hide();setTimeout(()=>app.openFarmCapture('${farm.id}',false),400);">
                  <i class="bi bi-geo-alt-fill me-1"></i>Capture Boundary
                </button>
              </div>`}

              <!-- ── SECTION 1: Farmer Identity ── -->
              <h6 class="fw-bold border-bottom pb-1 mb-3" style="color:#6f4e37;"><i class="bi bi-person-fill me-2"></i>Farmer Identity</h6>
              <div class="row g-3 mb-4">
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Full Name</label>
                  <input class="form-control form-control-sm" value="${fv(farm.farmer_name)}" placeholder="—" readonly style="background:#f8f3ee;">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Phone</label>
                  <input class="form-control form-control-sm" value="${fv(farm.farmer_phone)}" placeholder="—" readonly style="background:#f8f3ee;">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">National ID</label>
                  <input class="form-control form-control-sm" value="${fv(farm.farmer_national_id)}" placeholder="—" readonly style="background:#f8f3ee;">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Gender</label>
                  <input class="form-control form-control-sm" value="${fv(farm.farmer_gender)}" placeholder="—" readonly style="background:#f8f3ee;">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Coop Member No.</label>
                  <input class="form-control form-control-sm" value="${fv(farm.coop_member_no)}" placeholder="—" readonly style="background:#f8f3ee;">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Registered</label>
                  <input class="form-control form-control-sm" value="${farm.created_at ? new Date(farm.created_at).toLocaleDateString() : '—'}" readonly style="background:#f8f3ee;">
                </div>
              </div>

              <!-- ── SECTION 2: Farm Basics ── -->
              <h6 class="fw-bold border-bottom pb-1 mb-3" style="color:#6f4e37;"><i class="bi bi-house-fill me-2"></i>Farm Basics</h6>
              <div class="row g-3 mb-4">
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Farm Name <span class="text-danger">*</span></label>
                  <input class="form-control form-control-sm" name="farm_name" value="${fv(farm.farm_name)}" placeholder="Enter farm name">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Location / Subcounty</label>
                  <input class="form-control form-control-sm" value="${fv(farm.farmer_location)}" placeholder="—" readonly style="background:#f8f3ee;">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Total Area (ha)</label>
                  <input type="number" class="form-control form-control-sm" name="total_area_hectares" value="${fv(farm.total_area_hectares)}" step="0.01" min="0" placeholder="0.00">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Coffee Area (ha)</label>
                  <input type="number" class="form-control form-control-sm" name="coffee_area_hectares" value="${fv(farm.coffee_area_hectares)}" step="0.01" min="0" placeholder="0.00">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Land Ownership</label>
                  <input class="form-control form-control-sm" value="${fv(({'owned':'Title Deed (Owned)','leased':'Lease Agreement','inherited':'Family Plot / Inherited','customary':'Customary Tenure','community':'Community Land','tenant':'Tenant'}[parcel.ownership_type] || (parcel.ownership_type||'').replace(/_/g,' ')))" placeholder="—" readonly style="background:#f8f3ee;">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Land Use Type</label>
                  <select class="form-select form-select-sm" name="land_use_type">
                    ${[['agroforestry','Agroforestry'],['monocrop','Monocrop'],['mixed_cropping','Mixed Cropping'],['forest_reserve','Forest Reserve'],['buffer_zone','Buffer Zone'],['other','Other']].map(([v,l]) =>
                      `<option value="${v}" ${(farm.land_use_type||'') === v ? 'selected' : ''}>${l}</option>`
                    ).join('')}
                  </select>
                </div>
              </div>

              <!-- ── SECTION 3: Coffee Production ── -->
              <h6 class="fw-bold border-bottom pb-1 mb-3" style="color:#6f4e37;"><i class="bi bi-cup-hot-fill me-2"></i>Coffee Production</h6>
              <div class="row g-3 mb-4">
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Coffee Variety / Varieties</label>
                  <input class="form-control form-control-sm" name="coffee_varieties" value="${cvStr}" placeholder="e.g. Arabica, SL28">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Farming Method</label>
                  <select class="form-select form-select-sm" name="farming_method">
                    <option value="">— Not specified —</option>
                    ${['Organic','Conventional','Agroforestry','Shade-grown','Mixed'].map(o =>
                      `<option value="${o}" ${(farm.farming_method||'') === o ? 'selected' : ''}>${o}</option>`
                    ).join('')}
                  </select>
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Years Farming</label>
                  <input type="number" class="form-control form-control-sm" name="years_farming" value="${fv(farm.years_farming)}" min="0" placeholder="0">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Est. Annual Yield (kg)</label>
                  <input type="number" class="form-control form-control-sm" name="average_annual_production_kg" value="${fv(farm.average_annual_production_kg)}" step="0.1" min="0" placeholder="0">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Shade Trees Present</label>
                  <select class="form-select form-select-sm" name="shade_trees">
                    <option value="yes" ${farm.shade_trees_present === true || farm.shade_trees_present === 1 ? 'selected' : ''}>Yes</option>
                    <option value="no" ${farm.shade_trees_present !== true && farm.shade_trees_present !== 1 ? 'selected' : ''}>No</option>
                  </select>
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Shade Canopy (%)</label>
                  <input type="number" class="form-control form-control-sm" name="shade_tree_canopy_percent" value="${farm.shade_tree_canopy_percent != null ? farm.shade_tree_canopy_percent : ''}" min="0" max="100" placeholder="—">
                </div>
              </div>

              <!-- ── SECTION 4: Parcel Details ── -->
              ${parcels.length > 0 ? `
              <h6 class="fw-bold border-bottom pb-1 mb-3" style="color:#6f4e37;"><i class="bi bi-layers-fill me-2"></i>Parcel Details (${parcels.length})</h6>
              <div class="row g-3 mb-4">
                ${parcels.map((p,i) => `
                <div class="col-12">
                  <div class="card border-0" style="background:#fdf6ef;">
                    <div class="card-body p-3">
                      <div class="d-flex justify-content-between mb-2">
                        <strong class="small">${p.parcel_name || p.parcel_number || 'Parcel '+(i+1)}</strong>
                        <span class="badge bg-${p.verification_status==='pending'?'warning':p.verification_status==='verified'?'success':'secondary'}">${p.verification_status||'draft'}</span>
                      </div>
                      <div class="row g-2 small">
                        <div class="col-md-3 col-6"><span class="text-muted">Area:</span> <strong>${p.area_hectares||'—'} ha</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Land use:</span> <strong>${p.land_use_type||'—'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Soil:</span> <strong>${p.soil_type||'—'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Ownership:</span> <strong>${p.ownership_type||'—'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Coffee plants:</span> <strong>${p.estimated_coffee_plants||'—'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Coffee area:</span> <strong>${p.coffee_area_hectares||'—'} ha</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Irrigation:</span> <strong>${p.irrigation_type||'—'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Planting method:</span> <strong>${p.planting_method||'—'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">GPS accuracy:</span> <strong>${p.gps_accuracy_meters?p.gps_accuracy_meters+' m':'—'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Mapped:</span> <strong>${p.mapping_date?new Date(p.mapping_date).toLocaleDateString():'—'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Slope:</span> <strong>${p.slope_degrees!=null?p.slope_degrees+'°':'—'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Altitude:</span> <strong>${p.altitude_meters!=null?p.altitude_meters+' m':'—'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Canopy cover:</span> <strong>${p.canopy_cover||'—'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">NDVI baseline:</span> <strong>${p.ndvi_baseline!=null?p.ndvi_baseline.toFixed(3):'—'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Mixed farming:</span> <strong>${p.practice_mixed_farming?'Yes':'No'}</strong></div>
                        <div class="col-md-3 col-6"><span class="text-muted">Other crops:</span> <strong>${p.other_crops||'—'}</strong></div>
                      </div>
                    </div>
                  </div>
                </div>`).join('')}
              </div>` : ''}

              <!-- ── SECTION 5: Advanced ── -->
              <h6 class="fw-bold border-bottom pb-1 mb-3" style="color:#6f4e37;"><i class="bi bi-sliders me-2"></i>Advanced Information</h6>
              <div class="row g-3 mb-4">
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Agroforestry Start Year</label>
                  <input class="form-control form-control-sm" value="${fv(parcel.agroforestry_start_year)}" placeholder="—" readonly style="background:#f8f3ee;">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Previous Land Use</label>
                  <input class="form-control form-control-sm" value="${fv(parcel.previous_land_use)}" placeholder="—" readonly style="background:#f8f3ee;">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Estimated Coffee Trees</label>
                  <input class="form-control form-control-sm" value="${fv(parcel.estimated_coffee_plants)}" placeholder="—" readonly style="background:#f8f3ee;">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">NGO / Programme Support</label>
                  <input class="form-control form-control-sm" value="${fv(parcel.programme_support ? (parcel.programme_support.name || JSON.stringify(parcel.programme_support)) : '')}" placeholder="—" readonly style="background:#f8f3ee;">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Compliance Status</label>
                  <input class="form-control form-control-sm" value="${farm.compliance_status||'—'}" readonly style="background:#f8f3ee;">
                </div>
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Verification Status</label>
                  <input class="form-control form-control-sm text-capitalize" value="${farm.verification_status||'draft'}" readonly style="background:#f8f3ee;">
                </div>
                ${farm.certified_date ? `
                <div class="col-md-6 col-lg-4">
                  <label class="form-label small fw-semibold">Certified Date</label>
                  <input class="form-control form-control-sm" value="${new Date(farm.certified_date).toLocaleDateString()}" readonly style="background:#f8f3ee;">
                </div>` : ''}
              </div>

            </form>`;

            // Farmer identity is now served directly from the API response (farmer_* fields)

            // Add Save button to modal footer
            const footer = modalEl.querySelector('.modal-footer');
            if (footer) {
                const existing = footer.querySelector('#saveFarmEditBtn');
                if (!existing) {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.id = 'saveFarmEditBtn';
                    btn.className = 'btn btn-primary';
                    btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Save Changes';
                    btn.onclick = () => this.saveFarmEdits(farm.id);
                    footer.insertBefore(btn, footer.querySelector('.btn-secondary'));
                } else {
                    existing.onclick = () => this.saveFarmEdits(farm.id);
                }
            }

            // Render map
            if (hasPolygon && parcel.boundary_geojson) {
                setTimeout(() => {
                    const mapEl = document.getElementById('viewFarmMap');
                    if (!mapEl || mapEl._leaflet_id) return;
                    try {
                        const coords = parcel.boundary_geojson.coordinates[0];
                        const latlngs = coords.map(c => [c[1], c[0]]);
                        const m = L.map('viewFarmMap', { zoomControl: true, scrollWheelZoom: false });
                        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap' }).addTo(m);
                        const poly = L.polygon(latlngs, { color: '#6f4e37', fillColor: '#c8956c', fillOpacity: 0.35, weight: 2 }).addTo(m);
                        m.fitBounds(poly.getBounds(), { padding: [20, 20] });
                    } catch(e) { console.warn('Map render error', e); }
                }, 300);
            }

        } catch (error) {
            console.error('Error loading farm details:', error);
            content.innerHTML = `<div class="text-center py-5 text-danger"><i class="bi bi-exclamation-triangle fs-1"></i><p class="mt-2">${error.message}</p></div>`;
        }
    }

    async saveFarmEdits(farmId) {
        const form = document.getElementById('editFarmForm');
        if (!form) return;
        const btn = document.getElementById('saveFarmEditBtn');
        if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving...'; }

        try {
            const data = {};
            form.querySelectorAll('input[name]:not([readonly]), select[name]').forEach(el => {
                const v = el.value.trim();
                if (v !== '') data[el.name] = el.type === 'number' ? parseFloat(v) || null : v;
            });
            // Coffee varieties → array
            if (data.coffee_varieties) data.coffee_varieties = data.coffee_varieties.split(',').map(s => s.trim()).filter(Boolean);
            // shade_trees select → boolean integer
            if ('shade_trees' in data) { data.shade_trees_present = data.shade_trees === 'yes' ? 1 : 0; delete data.shade_trees; }

            await api.updateFarm(farmId, data);
            this.showToast('Farm saved successfully', 'success');
            this.loadFarmerFarms(); // refresh cards
        } catch(e) {
            this.showToast(e.message || 'Save failed', 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Save Changes'; }
        }
    }

    async openFarmCapture(farmId, isRecapture = false) {
        const modalEl = document.getElementById('farmCaptureModal');
        if (!modalEl) return;
        document.getElementById('captureFarmId').value = farmId;
        const titleEl = document.getElementById('farmCaptureModalLabel');
        if (titleEl) titleEl.innerHTML = `<i class="bi bi-geo-alt-fill me-2"></i>${isRecapture ? 'Recapture Farm Boundary' : 'Capture Farm Boundary'}`;

        // Reset state
        this._capturePoints = [];
        this._captureCapturing = false;

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

        const onShown = () => {
            this._initCaptureMap(farmId, isRecapture);
            modalEl.removeEventListener('shown.bs.modal', onShown);
        };
        const cleanupOnHide = () => {
            this._cleanupCaptureMap();
            modalEl.removeEventListener('hidden.bs.modal', cleanupOnHide);
        };
        modalEl.addEventListener('shown.bs.modal', onShown);
        modalEl.addEventListener('hidden.bs.modal', cleanupOnHide);

        modal.show();

        document.getElementById('captureStartBtn').onclick      = () => this._startCapture();
        document.getElementById('captureAddPointBtn').onclick   = () => this._addCapturePoint();
        document.getElementById('captureFinishBtn').onclick     = () => this._finishCapture();
        document.getElementById('captureClearBtn').onclick      = () => this._clearCapture();
        document.getElementById('captureNewPolygonBtn').onclick = () => this._newPolygon();
        document.getElementById('saveCaptureBtn').onclick       = () => this._saveCapturedPolygon(farmId);

        // Show "New Polygon" button only in recapture mode
        const newPolyBtn = document.getElementById('captureNewPolygonBtn');
        if (newPolyBtn) newPolyBtn.style.display = isRecapture ? '' : 'none';
    }

    async _initCaptureMap(farmId, isRecapture = false) {
        const mapEl = document.getElementById('captureMap');
        if (!mapEl) return;

        // Full cleanup of any previous session
        this._cleanupCaptureMap();

        this._captureMap = L.map('captureMap', { zoomControl: true });

        // Tile layer (OSM)
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors', maxZoom: 19
        }).addTo(this._captureMap);

        // --- Mode toggle (Walk / Click) ---
        const walkRadio  = document.getElementById('modeWalkBtn');
        const clickRadio = document.getElementById('modeClickBtn');
        // Read current radio state (persists across opens)
        this._captureInputMode = (clickRadio && clickRadio.checked) ? 'click' : 'walk';
        if (walkRadio)  walkRadio.onchange  = () => { if (walkRadio.checked)  this._captureInputMode = 'walk'; };
        if (clickRadio) clickRadio.onchange = () => { if (clickRadio.checked) this._captureInputMode = 'click'; };

        // Dashed polyline connecting points (same as add-farm)
        this._capturePolyline = L.polyline([], { color: '#6f4e37', weight: 3, dashArray: '6,4' }).addTo(this._captureMap);

        // Filled polygon (drawn once ≥3 points)
        this._capturePolygon = L.polygon([], { color: '#40916c', fillColor: '#52b788', fillOpacity: 0.3, weight: 2 }).addTo(this._captureMap);

        // Numbered point markers
        this._captureMarkers = L.layerGroup().addTo(this._captureMap);

        // Live GPS location marker
        this._captureLiveMarker = L.marker([0, 0], {
            icon: L.divIcon({
                className: '',
                html: '<div style="background:#2563eb;color:#fff;padding:0;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.4);width:34px;height:34px;display:flex;align-items:center;justify-content:center;font-size:16px;line-height:1;">📍</div>',
                iconSize: [34, 34], iconAnchor: [17, 17]
            })
        });

        // GPS accuracy circle
        this._captureAccuracyCircle = L.circle([0, 0], { radius: 0, color: '#10b981', fillColor: '#d1fae5', fillOpacity: 0.3 });

        this._existingPolygonLayer = null;

        // Load existing boundary for recapture
        if (isRecapture && farmId) {
            try {
                const farm = await api.getFarmById(farmId);
                if (farm?.parcels?.length > 0) {
                    const parcel = farm.parcels[0];
                    if (parcel.boundary_geojson?.coordinates) {
                        const coords = parcel.boundary_geojson.coordinates[0];
                        const latlngs = coords.map(c => [c[1], c[0]]);
                        this._existingPolygonLayer = L.polygon(latlngs, {
                            color: '#dc3545', fillColor: '#dc3545', fillOpacity: 0.1,
                            weight: 2, dashArray: '6, 6', interactive: false
                        }).addTo(this._captureMap);
                        this._captureMap.fitBounds(this._existingPolygonLayer.getBounds().pad(0.1));
                    }
                }
            } catch (e) {
                console.error('Failed to load existing polygon:', e);
            }
        }

        // Click-to-add-point — only active in Click mode
        this._captureMap.on('click', (e) => {
            if (!this._captureCapturing) return;
            if (this._captureInputMode !== 'click') return;
            this._addPointToCapture(e.latlng.lat, e.latlng.lng);
        });

        // For new farm or recapture without existing polygon, center map on GPS.
        // For recapture with existing polygon, fitBounds already positioned the map.
        const centerOnGPS = !this._existingPolygonLayer;

        // Set a sensible fallback view (Kenya) while waiting for GPS fix
        if (!this._existingPolygonLayer) {
            this._captureMap.setView([-0.0236, 37.9062], 13);
        }

        // Two-stage centering: fast coarse fix first (WiFi/cell, <1 s), then precise GPS
        if (centerOnGPS && navigator.geolocation) {
            const centerMap = (lat, lng) => {
                if (this._captureMap) this._captureMap.setView([lat, lng], 16);
            };
            // Stage 1: coarse but instant (allow cached/network position)
            navigator.geolocation.getCurrentPosition(
                pos => centerMap(pos.coords.latitude, pos.coords.longitude),
                () => {},
                { enableHighAccuracy: false, timeout: 5000, maximumAge: 300000 }
            );
            // Stage 2: precise GPS — refines position when hardware lock arrives
            navigator.geolocation.getCurrentPosition(
                pos => centerMap(pos.coords.latitude, pos.coords.longitude),
                () => {},
                { enableHighAccuracy: true, timeout: 30000, maximumAge: 0 }
            );
        }

        // Start continuous GPS watch — centers on first fix for new farm
        this._startCaptureGPSWatch(centerOnGPS);

        this._captureMap.invalidateSize();

        const statusEl = document.getElementById('captureStatusMsg');
        if (statusEl) statusEl.textContent = 'Press Start Capture, then tap the map or use Add Point at your GPS location.';
    }

    _startCaptureGPSWatch(centerOnFix = false) {
        const statusEl = document.getElementById('captureStatusMsg');
        if (!navigator.geolocation || !window.isSecureContext) {
            if (statusEl) {
                statusEl.style.color = '#dc3545';
                statusEl.dataset.gpsError = '1';
                statusEl.innerHTML = '⚠️ GPS requires a secure (HTTPS) connection. Switched to <strong>Click Mode</strong> — tap the map to place boundary points.';
            }
            const clickRadio = document.getElementById('captureInputClick');
            if (clickRadio) { clickRadio.checked = true; this._captureInputMode = 'click'; }
            return;
        }
        if (this._captureWatchId) return; // already watching

        this._captureWatchId = navigator.geolocation.watchPosition(pos => {
            const { latitude: lat, longitude: lng, accuracy } = pos.coords;
            this._currentCapturePos = pos.coords;

            // Update accuracy readout
            const accEl = document.getElementById('captureAccuracy');
            if (accEl) accEl.textContent = accuracy ? accuracy.toFixed(1) : '--';

            // Move live marker
            this._captureLiveMarker.setLatLng([lat, lng]);
            if (this._captureMap && !this._captureMap.hasLayer(this._captureLiveMarker)) {
                this._captureLiveMarker.addTo(this._captureMap);
            }

            // Update accuracy circle
            if (this._captureAccuracyCircle) {
                this._captureAccuracyCircle.setLatLng([lat, lng]);
                this._captureAccuracyCircle.setRadius(accuracy || 0);
                if (this._captureMap && !this._captureMap.hasLayer(this._captureAccuracyCircle)) {
                    this._captureAccuracyCircle.addTo(this._captureMap);
                }
            }

            // Clear any GPS error message and restore normal status
            const statusEl = document.getElementById('captureStatusMsg');
            if (statusEl && statusEl.dataset.gpsError) {
                delete statusEl.dataset.gpsError;
                if (!this._captureCapturing) {
                    statusEl.textContent = 'GPS locked. Press Start Capture to begin.';
                    statusEl.style.color = '';
                }
            }

            // Centre map on first GPS fix (only when no existing polygon loaded)
            if (centerOnFix && this._capturePoints.length === 0 && this._captureMap) {
                const z = this._captureMap.getZoom();
                this._captureMap.setView([lat, lng], z < 14 ? 16 : z);
                centerOnFix = false; // only centre once
            }

            // Auto-place Point 1 when Start Capture was pressed before GPS arrived
            if (this._autoAddPoint1 && this._captureCapturing) {
                this._autoAddPoint1 = false;
                this._addPointToCapture(lat, lng);
            } else if (this._captureCapturing && this._captureInputMode === 'walk' && this._capturePoints.length > 0) {
                // Walk mode: auto-add a point every 5 m of movement
                const last = this._capturePoints[this._capturePoints.length - 1];
                if (this._haversineDistance(last.lat, last.lon, lat, lng) >= 5) {
                    this._addPointToCapture(lat, lng);
                }
            }

            // Walk mode: keep map centred on user's position while capturing
            if (this._captureCapturing && this._captureInputMode === 'walk' && this._captureMap) {
                this._captureMap.panTo([lat, lng], { animate: true, duration: 0.3 });
            }
        }, err => {
            console.warn('Capture GPS error:', err.code, err.message);
            const statusEl = document.getElementById('captureStatusMsg');
            if (!statusEl) return;
            statusEl.dataset.gpsError = '1';
            statusEl.style.color = '#dc3545';
            if (err.code === 1) {
                // PERMISSION_DENIED
                statusEl.innerHTML = '⚠️ Location access denied. Please allow location in your browser settings, then reload. Or switch to <strong>Click Mode</strong> to tap the map instead.';
                // Auto-switch to click mode so the user can still proceed
                const clickRadio = document.getElementById('captureInputClick');
                if (clickRadio && !clickRadio.checked) {
                    clickRadio.checked = true;
                    this._captureInputMode = 'click';
                }
            } else if (err.code === 2) {
                // POSITION_UNAVAILABLE
                statusEl.innerHTML = '⚠️ GPS unavailable on this device. Switched to <strong>Click Mode</strong> — tap the map to place boundary points.';
                const clickRadio = document.getElementById('captureInputClick');
                if (clickRadio && !clickRadio.checked) {
                    clickRadio.checked = true;
                    this._captureInputMode = 'click';
                }
            } else {
                // TIMEOUT or other
                statusEl.innerHTML = '⚠️ GPS signal timeout. Move to open ground or switch to <strong>Click Mode</strong> to tap the map.';
            }
        }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 30000 });
    }

    _addPointToCapture(lat, lng) {
        this._capturePoints.push({ lat, lon: lng });
        const count = this._capturePoints.length;

        // Numbered circle marker (same style as add-farm)
        const icon = L.divIcon({
            className: '',
            html: `<div style="background:#40916c;color:#fff;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.5);">${count}</div>`,
            iconSize: [26, 26], iconAnchor: [13, 13]
        });
        L.marker([lat, lng], { icon }).addTo(this._captureMarkers);

        // Redraw dashed polyline
        const coords = this._capturePoints.map(p => [p.lat, p.lon]);
        if (this._capturePolyline) this._capturePolyline.setLatLngs(coords);

        // Fill polygon once ≥3 points
        if (count >= 3) {
            if (this._capturePolygon) this._capturePolygon.setLatLngs(coords);
            const area = this._calcArea(coords);
            const dispEl = document.getElementById('captureAreaDisplay');
            const inpEl  = document.getElementById('captureAreaInput');
            if (dispEl) dispEl.textContent = area.toFixed(2);
            if (inpEl && !inpEl.value) inpEl.value = area.toFixed(2);
        }

        const countEl  = document.getElementById('capturePointCount');
        const statusEl = document.getElementById('captureStatusMsg');
        const finishBtn = document.getElementById('captureFinishBtn');
        if (countEl)  countEl.textContent  = count;
        if (statusEl) statusEl.textContent = `${count} point(s) added. ${count >= 3 ? 'Tap Finish or keep adding.' : 'Add more points (min 3).'}`;
        if (finishBtn) finishBtn.disabled  = count < 3;
    }

    _newPolygon() {
        // Remove the existing boundary overlay
        if (this._existingPolygonLayer && this._captureMap) {
            try { this._captureMap.removeLayer(this._existingPolygonLayer); } catch(e) {}
            this._existingPolygonLayer = null;
        }
        // Reset all drawn points
        this._clearCapture();

        // Pan to current GPS location
        const goToPos = (lat, lng) => {
            if (this._captureMap) this._captureMap.setView([lat, lng], 17);
        };

        if (this._currentCapturePos) {
            goToPos(this._currentCapturePos.latitude, this._currentCapturePos.longitude);
        } else if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                pos => goToPos(pos.coords.latitude, pos.coords.longitude),
                ()  => {}
            );
        }

        const statusEl = document.getElementById('captureStatusMsg');
        if (statusEl) statusEl.textContent = 'Existing boundary removed. Press Start Capture to draw your new boundary.';
    }

    _startCapture() {
        this._captureCapturing = true;
        document.getElementById('captureStartBtn').disabled = true;
        document.getElementById('captureAddPointBtn').disabled = false;
        document.getElementById('captureFinishBtn').disabled = this._capturePoints.length < 3;

        const mode = this._captureInputMode || 'walk';
        const statusEl = document.getElementById('captureStatusMsg');

        // GPS watch already running; start if not yet (e.g. permission denied earlier)
        this._startCaptureGPSWatch(true);

        // Always auto-place Point 1 at current GPS location (both walk and click mode)
        if (this._currentCapturePos) {
            this._addPointToCapture(this._currentCapturePos.latitude, this._currentCapturePos.longitude);
            if (statusEl) statusEl.textContent = mode === 'walk'
                ? 'Point 1 placed. Walking… points auto-add every 5 m. Press Add Point at key corners.'
                : 'Point 1 placed at your location. Tap the map to add boundary corners.';
        } else {
            this._autoAddPoint1 = true;
            if (statusEl) statusEl.textContent = 'Waiting for GPS fix… Point 1 will be placed when location is found.';
        }
    }

    _addCapturePoint() {
        if (!this._currentCapturePos) { this.showToast('Waiting for GPS fix…', 'warning'); return; }
        if (!this._captureCapturing) { this.showToast('Press Start Capture first', 'warning'); return; }
        this._addPointToCapture(this._currentCapturePos.latitude, this._currentCapturePos.longitude);
    }

    _finishCapture() {
        if (this._capturePoints.length < 3) { this.showToast('Need at least 3 points', 'warning'); return; }
        this._captureCapturing = false;
        document.getElementById('captureAddPointBtn').disabled = true;
        document.getElementById('captureStatusMsg').textContent = 'Capture complete. Adjust area if needed, then Save.';
    }

    _clearCapture() {
        this._capturePoints = [];
        this._captureCapturing = false;
        this._autoAddPoint1 = false;
        this._captureInputMode = this._captureInputMode || 'walk';
        if (this._capturePolygon)  this._capturePolygon.setLatLngs([]);
        if (this._capturePolyline) this._capturePolyline.setLatLngs([]);
        if (this._captureMarkers)  this._captureMarkers.clearLayers();
        const countEl   = document.getElementById('capturePointCount');
        const dispEl    = document.getElementById('captureAreaDisplay');
        const inpEl     = document.getElementById('captureAreaInput');
        const startBtn  = document.getElementById('captureStartBtn');
        const addBtn    = document.getElementById('captureAddPointBtn');
        const finishBtn = document.getElementById('captureFinishBtn');
        const statusEl  = document.getElementById('captureStatusMsg');
        if (countEl)   countEl.textContent   = '0';
        if (dispEl)    dispEl.textContent    = '--';
        if (inpEl)     inpEl.value           = '';
        if (startBtn)  startBtn.disabled     = false;
        if (addBtn)    addBtn.disabled       = true;
        if (finishBtn) finishBtn.disabled    = true;
        if (statusEl)  statusEl.textContent  = 'Cleared. Press Start Capture to begin again.';
    }

    _cleanupCaptureMap() {
        if (this._captureWatchId) {
            navigator.geolocation.clearWatch(this._captureWatchId);
            this._captureWatchId = null;
        }
        if (this._captureMap) {
            try { this._captureMap.remove(); } catch(e) {}
            this._captureMap = null;
        }
        this._capturePolygon        = null;
        this._capturePolyline       = null;
        this._captureMarkers        = null;
        this._captureLiveMarker     = null;
        this._captureAccuracyCircle = null;
        this._existingPolygonLayer  = null;
        this._currentCapturePos     = null;
        this._capturePoints         = [];
        this._captureCapturing      = false;
        this._autoAddPoint1         = false;
    }

    async _saveCapturedPolygon(farmId) {
        if (this._capturePoints.length < 3) { this.showToast('Need at least 3 points to save', 'warning'); return; }
        const area = parseFloat(document.getElementById('captureAreaInput').value) || null;
        try {
            document.getElementById('saveCaptureBtn').disabled = true;
            await api.updateFarmPolygon(farmId, { gps_points: this._capturePoints, area_hectares: area });
            this.showToast('Farm boundary saved successfully', 'success');
            this._cleanupCaptureMap();
            const modal = bootstrap.Modal.getInstance(document.getElementById('farmCaptureModal'));
            if (modal) modal.hide();
            setTimeout(() => {
                document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
                this.loadFarmerFarms();
            }, 300);
        } catch (e) {
            this.showToast(e.message || 'Failed to save boundary', 'error');
        } finally {
            document.getElementById('saveCaptureBtn').disabled = false;
        }
    }

    _haversineDistance(lat1, lng1, lat2, lng2) {
        const R = 6371000;
        const φ1 = lat1 * Math.PI / 180, φ2 = lat2 * Math.PI / 180;
        const Δφ = (lat2 - lat1) * Math.PI / 180;
        const Δλ = (lng2 - lng1) * Math.PI / 180;
        const a = Math.sin(Δφ/2)**2 + Math.cos(φ1)*Math.cos(φ2)*Math.sin(Δλ/2)**2;
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    _calcArea(latlngs) {
        let area = 0;
        const n = latlngs.length;
        const R = 6371000;
        for (let i = 0; i < n; i++) {
            const [lat1, lon1] = latlngs[i];
            const [lat2, lon2] = latlngs[(i + 1) % n];
            area += (lon2 - lon1) * Math.PI / 180 * (2 + Math.sin(lat1 * Math.PI / 180) + Math.sin(lat2 * Math.PI / 180));
        }
        return Math.abs(area * R * R / 2) / 10000;
    }

    async loadCropAnalysis(farmId) {
        const categoryColors = { coffee: '#8B4513', shade_tree: '#228B22', trees: '#228B22', fruit_tree: '#32CD32', timber: '#5C4033', vegetable: '#9ACD32', legume: '#DAA520', cereal: '#F4A460', other: '#A9A9A9' };
        const categoryIcons = { coffee: 'bi-cup-hot-fill', shade_tree: 'bi-tree-fill', trees: 'bi-tree-fill', fruit_tree: 'bi-apple', timber: 'bi-tree', vegetable: 'bi-leaf', legume: 'bi-flower1', cereal: 'bi-flower2', other: 'bi-question-circle' };

        try {
            const container = document.getElementById('cropAnalysis');
            if (!container) return;

            const data = await api.request(`/farmer/farm/${farmId}/crop-analysis`, { optional: true });

            if (!data || !data.has_analysis) {
                container.innerHTML = `
                    <div class="text-center py-4">
                        <i class="bi bi-seedling fs-1 text-muted"></i>
                        <p class="text-muted mt-2">No analysis data yet</p>
                        <small class="text-muted">Click <strong>Analyse</strong> on the farm card to run satellite analysis</small>
                    </div>`;
                return;
            }

            const cropDiff = data.crop_differentiation || {};
            const dominantCrops = data.dominant_crops || [];
            const agroScore = data.agroforestry_score || 0;
            const parcels = data.parcels || [];

            let html = '';

            // ── Summary row ──
            html += `<div class="row g-3 mb-3">`;
            html += `<div class="col-12"><div class="d-flex align-items-center gap-3 flex-wrap">
                <span class="badge bg-success fs-6 px-3 py-2"><i class="bi bi-graph-up me-1"></i>Agroforestry Score: ${agroScore.toFixed(1)}/10</span>
                ${dominantCrops.length ? `<span class="small text-muted"><i class="bi bi-award me-1"></i>Dominant: <strong>${dominantCrops.join(', ')}</strong></span>` : ''}
                <span class="small text-muted"><i class="bi bi-calendar me-1"></i>Last analysis: ${data.last_analysis_date ? new Date(data.last_analysis_date).toLocaleDateString() : '—'}</span>
            </div></div>`;

            // ── Crop differentiation cards ──
            if (Object.keys(cropDiff).length > 0) {
                Object.entries(cropDiff).forEach(([name, d]) => {
                    const color = categoryColors[name] || '#6f4e37';
                    const icon = categoryIcons[name] || 'bi-seedling';
                    const health = d.health_score || 5.0;
                    const healthColor = health >= 7 ? 'success' : health >= 5 ? 'warning' : 'danger';
                    html += `
                        <div class="col-md-4">
                            <div class="card border-0 shadow-sm h-100" style="border-left:4px solid ${color};">
                                <div class="card-header py-2" style="background:${color};color:#fff;">
                                    <h6 class="mb-0"><i class="bi ${icon} me-2"></i>${name.replace(/_/g,' ').toUpperCase()}</h6>
                                </div>
                                <div class="card-body p-3">
                                    <div class="row text-center mb-2">
                                        <div class="col-6">
                                            <div class="fw-bold text-${healthColor}">${health.toFixed(1)}/10</div>
                                            <small class="text-muted">Health Score</small>
                                        </div>
                                        <div class="col-6">
                                            <div class="fw-bold">${d.estimated_area_percentage || 0}%</div>
                                            <small class="text-muted">Area Share</small>
                                        </div>
                                    </div>
                                    <div class="progress mb-2" style="height:5px;">
                                        <div class="progress-bar" style="width:${(health/10)*100}%;background:${color};"></div>
                                    </div>
                                    ${d.ndvi_range ? `<small class="text-muted">NDVI: ${d.ndvi_range[0]} – ${d.ndvi_range[1]}</small>` : ''}
                                </div>
                            </div>
                        </div>`;
                });
            }
            html += '</div>';

            // ── Per-parcel satellite metrics ──
            const withSat = parcels.filter(p => p.satellite);
            if (withSat.length > 0) {
                html += `<div class="mt-4"><h6 class="border-bottom pb-1"><i class="bi bi-satellite me-2"></i>Parcel Satellite Metrics</h6>
                <div class="table-responsive"><table class="table table-sm align-middle">
                <thead class="table-light"><tr>
                    <th>Parcel</th><th>Area (ha)</th><th>NDVI</th><th>Canopy %</th><th>Biomass t/ha</th><th>Land Cover</th><th>Source</th>
                </tr></thead><tbody>`;
                withSat.forEach(p => {
                    const s = p.satellite;
                    html += `<tr>
                        <td><strong>${p.parcel_name || p.parcel_number}</strong></td>
                        <td>${(p.area_hectares || 0).toFixed(2)}</td>
                        <td><span class="badge bg-success">${(s.ndvi_mean || 0).toFixed(3)}</span></td>
                        <td>${(s.canopy_cover_percentage || 0).toFixed(1)}%</td>
                        <td>${(s.biomass_tons_hectare || 0).toFixed(2)}</td>
                        <td><span class="badge bg-secondary">${s.land_cover_type || '—'}</span></td>
                        <td><small class="text-muted">${(s.satellite_source || 'SENTINEL_2').replace('SENTINEL_2','Sentinel-2').replace('LANDSAT_8','Landsat-8').replace('LANDSAT_9','Landsat-9')}</small></td>
                    </tr>`;
                });
                html += '</tbody></table></div></div>';
            }

            // ── Manual crops table if any exist ──
            const allManual = parcels.flatMap(p => p.manual_crops.map(c => ({ ...c, parcel_name: p.parcel_name || p.parcel_number })));
            if (allManual.length > 0) {
                html += `<div class="mt-4"><h6 class="border-bottom pb-1"><i class="bi bi-pencil-square me-2"></i>Manually Mapped Crops</h6>
                <div class="table-responsive"><table class="table table-sm">
                <thead class="table-light"><tr><th>Crop</th><th>Parcel</th><th>Area (ha)</th><th>Growth Stage</th><th>Certifications</th></tr></thead><tbody>`;
                allManual.forEach(c => {
                    const certs = [c.organic_certified && '<span class="badge bg-success">Organic</span>', c.fair_trade_certified && '<span class="badge bg-info">Fair Trade</span>'].filter(Boolean).join(' ');
                    html += `<tr><td><strong>${c.crop_type}</strong></td><td>${c.parcel_name}</td><td>${c.area_hectares?.toFixed(2) || '—'}</td><td>${c.growth_stage || '—'}</td><td>${certs || '<small class="text-muted">None</small>'}</td></tr>`;
                });
                html += '</tbody></table></div></div>';
            }

            container.innerHTML = html;

        } catch (error) {
            console.error('Error loading crop analysis:', error);
            const container = document.getElementById('cropAnalysis');
            if (container) container.innerHTML = '<div class="text-danger text-center py-3">Error loading crop analysis data</div>';
        }
    }

    async loadHistoricalAnalysis(farmId) {
        try {
            const historicalData = await api.request(`/farmer/farm/${farmId}/historical-analysis`, { optional: true }) || {};

            const container = document.getElementById('historicalAnalysis');
            if (!container) return;

            if (!historicalData.historical_data || Object.keys(historicalData.historical_data).length === 0) {
                container.innerHTML = '<div class="text-muted text-center py-3">No historical analysis data available</div>';
                return;
            }

            // Flatten all records across all years, newest first
            const allRecords = [];
            Object.keys(historicalData.historical_data).sort().reverse().forEach(year => {
                historicalData.historical_data[year].forEach(r => allRecords.push({ ...r, year }));
            });

            // Compute aggregate summary across ALL records
            const totalAnalyses = allRecords.length;
            const ndviVals = allRecords.filter(r => r.ndvi_mean).map(r => r.ndvi_mean);
            const avgNdvi = ndviVals.length ? ndviVals.reduce((s, v) => s + v, 0) / ndviVals.length : 0;
            const deforestationEvents = allRecords.filter(r => r.deforestation_detected).length;
            const treeVals = allRecords.filter(r => r.tree_cover_percentage).map(r => r.tree_cover_percentage);
            const avgTreeCover = treeVals.length ? treeVals.reduce((s, v) => s + v, 0) / treeVals.length : 0;
            const biomassVals = allRecords.filter(r => r.biomass_tons_hectare).map(r => r.biomass_tons_hectare);
            const avgBiomass = biomassVals.length ? biomassVals.reduce((s, v) => s + v, 0) / biomassVals.length : 0;
            const years = Object.keys(historicalData.historical_data).sort().reverse();

            let html = `
                <div class="card border-0 shadow-sm mb-4" style="background:linear-gradient(135deg,#2c1a0e,#6f4e37);color:#fff;">
                    <div class="card-body py-3">
                        <div class="row text-center g-2">
                            <div class="col">
                                <div class="h4 mb-0 fw-bold">${totalAnalyses}</div>
                                <small class="opacity-75">Total Analyses</small>
                            </div>
                            <div class="col">
                                <div class="h4 mb-0 fw-bold text-success">${avgNdvi.toFixed(3)}</div>
                                <small class="opacity-75">Avg NDVI</small>
                            </div>
                            <div class="col">
                                <div class="h4 mb-0 fw-bold ${deforestationEvents > 0 ? 'text-danger' : 'text-success'}">${deforestationEvents}</div>
                                <small class="opacity-75">Deforestation Events</small>
                            </div>
                            <div class="col">
                                <div class="h4 mb-0 fw-bold">${avgTreeCover.toFixed(1)}%</div>
                                <small class="opacity-75">Avg Tree Cover</small>
                            </div>
                            <div class="col">
                                <div class="h4 mb-0 fw-bold text-info">${avgBiomass.toFixed(2)} t/ha</div>
                                <small class="opacity-75">Avg Biomass</small>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Year sections — each year shows every individual run
            years.forEach(year => {
                const yearRecords = historicalData.historical_data[year];
                const yearNdvi = yearRecords.filter(r => r.ndvi_mean).reduce((s, r) => s + r.ndvi_mean, 0) / (yearRecords.filter(r => r.ndvi_mean).length || 1);
                const yearDefo = yearRecords.filter(r => r.deforestation_detected).length;

                html += `
                    <div class="mb-4">
                        <div class="d-flex align-items-center justify-content-between mb-2">
                            <h6 class="mb-0 fw-bold"><i class="bi bi-calendar3 me-2" style="color:#6f4e37;"></i>${year}</h6>
                            <span class="text-muted small">${yearRecords.length} analyses &nbsp;·&nbsp; Avg NDVI ${yearNdvi.toFixed(3)} &nbsp;·&nbsp; ${yearDefo === 0 ? '<span class="text-success">No deforestation</span>' : '<span class="text-danger">' + yearDefo + ' deforestation event(s)</span>'}</span>
                        </div>
                        <div class="row g-2">
                `;

                yearRecords.forEach((rec, idx) => {
                    const riskLevel = rec.risk_level || 'low';
                    const riskColor = riskLevel === 'high' ? 'danger' : riskLevel === 'medium' ? 'warning' : 'success';
                    const eudrOk = rec.analysis_metadata?.eudr_compliant !== false;
                    const agroScore = rec.analysis_metadata?.agroforestry_score || 0;
                    const runDate = new Date(rec.analysis_date);
                    const runLabel = runDate.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

                    html += `
                        <div class="col-md-6 col-lg-4">
                            <div class="card border-0 shadow-sm h-100">
                                <div class="card-header d-flex justify-content-between align-items-center py-2" style="background:#f8f4f0;">
                                    <span class="small fw-bold text-dark"><i class="bi bi-satellite me-1" style="color:#6f4e37;"></i>Run #${idx + 1} &mdash; ${runLabel}</span>
                                    <div class="d-flex gap-1">
                                        <span class="badge bg-${riskColor} py-1">${riskLevel}</span>
                                        <span class="badge bg-${eudrOk ? 'success' : 'danger'} py-1">${eudrOk ? 'EUDR ✓' : 'EUDR ✗'}</span>
                                    </div>
                                </div>
                                <div class="card-body p-3">
                                    <div class="row text-center g-1 mb-3">
                                        <div class="col-4">
                                            <div class="fw-bold text-success">${(rec.ndvi_mean || 0).toFixed(3)}</div>
                                            <small class="text-muted" style="font-size:0.7rem;">NDVI</small>
                                        </div>
                                        <div class="col-4">
                                            <div class="fw-bold" style="color:#6f4e37;">${(rec.canopy_cover_percentage || 0).toFixed(1)}%</div>
                                            <small class="text-muted" style="font-size:0.7rem;">Canopy</small>
                                        </div>
                                        <div class="col-4">
                                            <div class="fw-bold text-info">${(rec.biomass_tons_hectare || 0).toFixed(2)}</div>
                                            <small class="text-muted" style="font-size:0.7rem;">t/ha</small>
                                        </div>
                                    </div>
                                    <div class="small">
                                        <div class="d-flex justify-content-between py-1 border-bottom">
                                            <span class="text-muted"><i class="bi bi-tree me-1"></i>Tree Cover</span>
                                            <strong>${(rec.tree_cover_percentage || 0).toFixed(1)}%</strong>
                                        </div>
                                        <div class="d-flex justify-content-between py-1 border-bottom">
                                            <span class="text-muted"><i class="bi bi-seedling me-1"></i>Crop Cover</span>
                                            <strong>${(rec.crop_cover_percentage || 0).toFixed(1)}%</strong>
                                        </div>
                                        <div class="d-flex justify-content-between py-1 border-bottom">
                                            <span class="text-muted"><i class="bi bi-bar-chart me-1"></i>NDVI Range</span>
                                            <strong>${(rec.ndvi_min || 0).toFixed(3)} – ${(rec.ndvi_max || 0).toFixed(3)}</strong>
                                        </div>
                                        <div class="d-flex justify-content-between py-1 border-bottom">
                                            <span class="text-muted"><i class="bi bi-cloud me-1"></i>Carbon Stored</span>
                                            <strong>${(rec.carbon_stored_tons || 0).toFixed(2)} t</strong>
                                        </div>
                                        <div class="d-flex justify-content-between py-1 border-bottom">
                                            <span class="text-muted"><i class="bi bi-arrow-repeat me-1"></i>Carbon/yr</span>
                                            <strong>${(rec.carbon_sequestered_kg_year || 0).toFixed(0)} kg</strong>
                                        </div>
                                        <div class="d-flex justify-content-between py-1 border-bottom">
                                            <span class="text-muted"><i class="bi bi-heart-pulse me-1"></i>Tree Health</span>
                                            <strong>${(rec.tree_health_score || 0).toFixed(1)}/10</strong>
                                        </div>
                                        <div class="d-flex justify-content-between py-1 border-bottom">
                                            <span class="text-muted"><i class="bi bi-heart-pulse me-1"></i>Crop Health</span>
                                            <strong>${(rec.crop_health_score || 0).toFixed(1)}/10</strong>
                                        </div>
                                        <div class="d-flex justify-content-between py-1 border-bottom">
                                            <span class="text-muted"><i class="bi bi-cloud-sun me-1"></i>Cloud Cover</span>
                                            <strong>${(rec.cloud_cover_percentage || 0).toFixed(1)}%</strong>
                                        </div>
                                        <div class="d-flex justify-content-between py-1 border-bottom">
                                            <span class="text-muted"><i class="bi bi-graph-up me-1"></i>Agroforestry</span>
                                            <strong>${agroScore.toFixed(1)}/10</strong>
                                        </div>
                                        <div class="d-flex justify-content-between py-1">
                                            <span class="text-muted"><i class="bi bi-exclamation-triangle me-1"></i>Deforestation</span>
                                            <strong class="${rec.deforestation_detected ? 'text-danger' : 'text-success'}">${rec.deforestation_detected ? 'Detected' : 'None'}</strong>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                });

                html += '</div></div>';
            });

            container.innerHTML = html;

        } catch (error) {
            console.error('Error loading historical analysis:', error);
            const container = document.getElementById('historicalAnalysis');
            if (container) {
                container.innerHTML = '<div class="text-danger text-center py-3">Error loading historical data</div>';
            }
        }
    }

    exportAnalysisReport() {
        const selector = document.getElementById('analysisFarmSelector');
        const farmName = selector?.options[selector.selectedIndex]?.text || 'Farm';
        const container = document.getElementById('historicalAnalysis');
        if (!container || container.innerText.includes('No historical')) {
            this.showToast('Run a satellite analysis first before exporting.', 'warning');
            return;
        }

        const now = new Date();
        const dateStr = now.toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });
        const timeStr = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });

        const win = window.open('', '_blank');
        win.document.write(`<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Satellite Analysis Report — ${farmName}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        body { font-family: Arial, sans-serif; padding: 30px; color: #222; }
        @media print { .no-print { display: none !important; } body { padding: 10px; } }
        .report-header { border-bottom: 3px solid #6f4e37; padding-bottom: 16px; margin-bottom: 24px; }
        .watermark { color: #6f4e37; font-weight: bold; }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
        .bg-success { background:#198754!important; color:#fff; }
        .bg-danger  { background:#dc3545!important; color:#fff; }
        .bg-warning { background:#ffc107!important; color:#000; }
        .bg-info    { background:#0dcaf0!important; color:#000; }
        .card { border: 1px solid #dee2e6; border-radius: 8px; margin-bottom: 16px; }
        .card-header { background: #f8f4f0; padding: 8px 16px; font-weight: bold; border-bottom: 1px solid #dee2e6; border-radius: 8px 8px 0 0; }
        .card-body { padding: 16px; }
        table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        th, td { border: 1px solid #dee2e6; padding: 6px 10px; font-size: 13px; }
        th { background: #f8f9fa; font-weight: bold; }
        .text-muted { color: #6c757d; }
        .proof-box { border: 2px dashed #6f4e37; border-radius: 8px; padding: 12px 20px; background: #fdf8f4; margin-top: 24px; }
    </style>
</head>
<body>
    <div class="report-header d-flex justify-content-between align-items-start">
        <div>
            <h3 class="watermark">Plotra Platform</h3>
            <h5>Satellite Analysis Report</h5>
            <div class="text-muted">Farm: <strong>${farmName}</strong></div>
        </div>
        <div class="text-end">
            <div class="text-muted" style="font-size:13px;">Generated: ${dateStr} at ${timeStr}</div>
            <div class="text-muted" style="font-size:13px;">Data source: Copernicus Sentinel-2 L2A</div>
            <div class="text-muted" style="font-size:13px;">Provider: Copernicus Data Space Ecosystem</div>
        </div>
    </div>

    <div class="no-print mb-3">
        <button onclick="window.print()" style="background:#6f4e37;color:#fff;border:none;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:14px;">
            &#128438; Save as PDF / Print
        </button>
        <span style="margin-left:12px;color:#888;font-size:13px;">Use your browser's "Save as PDF" option in the print dialog</span>
    </div>

    ${container.innerHTML}

    <div class="proof-box">
        <strong style="color:#6f4e37;">Proof of Analysis</strong><br>
        <span style="font-size:13px;">
            This report was generated by Plotra Platform on <strong>${dateStr} at ${timeStr}</strong>.
            All vegetation indices (NDVI, EVI, SAVI, NDMI, NDWI) are derived from real Sentinel-2 L2A
            satellite imagery processed via the Copernicus Data Space Ecosystem (CDSE) Statistics API.
            No simulated or synthetic data has been used.
        </span>
    </div>
</body>
</html>`);
        win.document.close();
        win.focus();
    }

    async loadTreeManagement(farmId) {
        try {
            // Load all parcels for this farm
            const parcels = await api.getParcels(farmId);

            const container = document.getElementById('treeManagement');
            if (!container) return;

            if (!parcels || parcels.length === 0) {
                container.innerHTML = '<div class="text-muted text-center py-3">No parcels found</div>';
                return;
            }

            let totalTrees = 0;
            let totalCropAreas = 0;
            let agroforestryScore = 0;

            let html = '<div class="row g-3">';

            for (const parcel of parcels) {
                try {
                    // Load trees
                    const trees = await api.request(`/farmer/farm/${farmId}/parcel/${parcel.id}/trees`, { optional: true, default: [] });
                    totalTrees += (trees || []).length;

                    // Load crops
                    const crops = await api.getParcelCrops(farmId, parcel.id);
                    totalCropAreas += crops.length;

                    // Calculate parcel agroforestry score
                    const treeCount = trees.length;
                    const cropCount = crops.length;
                    const parcelAgroforestryScore = treeCount > 0 && cropCount > 0 ?
                        Math.min(10, 5 + ((treeCount / (treeCount + cropCount)) * 3)) : (treeCount > 0 ? 7 : 3);

                    agroforestryScore = Math.max(agroforestryScore, parcelAgroforestryScore);

                    html += `
                        <div class="col-md-6 col-lg-4">
                            <div class="card border-0 shadow-sm h-100">
                                <div class="card-header" style="background: linear-gradient(135deg, #6f4e37 0%, #8b4513 100%); color: white;">
                                    <h6 class="mb-0">Parcel ${parcel.parcel_number}</h6>
                                    <small>${parcel.parcel_name || 'Unnamed'}</small>
                                </div>
                                <div class="card-body d-flex flex-column">
                                    <div class="row text-center mb-3">
                                        <div class="col-4">
                                            <div class="h4 mb-0 text-success">${trees.length}</div>
                                            <small class="text-muted">Trees</small>
                                        </div>
                                        <div class="col-4">
                                            <div class="h4 mb-0" style="color: #daa520;">${crops.length}</div>
                                            <small class="text-muted">Crops</small>
                                        </div>
                                        <div class="col-4">
                                            <div class="h4 mb-0 text-info">${parcel.area_hectares || 0}</div>
                                            <small class="text-muted">Area (ha)</small>
                                        </div>
                                    </div>

                                    <div class="mb-2">
                                        <small class="text-muted">Agroforestry Score:</small>
                                        <div class="progress" style="height: 6px;">
                                            <div class="progress-bar" role="progressbar" style="width: ${parcelAgroforestryScore * 10}%; background-color: #228b22;"></div>
                                        </div>
                                        <small class="text-muted">${parcelAgroforestryScore.toFixed(1)}/10</small>
                                    </div>

                                    <div class="mt-auto d-grid gap-2">
                                        <button class="btn btn-sm" style="background-color: #228b22; color: white;" onclick="app.openTreeMapping()">
                                            <i class="bi bi-tree me-1"></i>Add Trees/Crops
                                        </button>
                                        <button class="btn btn-sm btn-outline-primary" onclick="app.viewParcelDetails(${parcel.id})">
                                            <i class="bi bi-eye me-1"></i>View Details
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                } catch (error) {
                    console.error(`Error loading data for parcel ${parcel.id}:`, error);
                }
            }

            html += '</div>';

            // Add comprehensive summary with coffee theming
            const summaryHtml = `
                <div class="row g-3 mb-4">
                    <div class="col-md-3">
                        <div class="card border-0 shadow-sm text-center" style="border-left: 4px solid #6f4e37;">
                            <div class="card-body">
                                <i class="bi bi-tree-fill fs-1 text-success"></i>
                                <h4 class="mt-2">${totalTrees}</h4>
                                <small class="text-muted">Total Trees</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card border-0 shadow-sm text-center" style="border-left: 4px solid #daa520;">
                            <div class="card-body">
                                <i class="bi bi-seedling fs-1" style="color: #daa520;"></i>
                                <h4 class="mt-2">${totalCropAreas}</h4>
                                <small class="text-muted">Crop Areas</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card border-0 shadow-sm text-center" style="border-left: 4px solid #228b22;">
                            <div class="card-body">
                                <i class="bi bi-graph-up fs-1 text-success"></i>
                                <h4 class="mt-2">${agroforestryScore.toFixed(1)}</h4>
                                <small class="text-muted">Agroforestry Score</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card border-0 shadow-sm text-center" style="border-left: 4px solid #8b4513;">
                            <div class="card-body">
                                <i class="bi bi-cup-hot-fill fs-1" style="color: #6f4e37;"></i>
                                <h4 class="mt-2">${parcels.length}</h4>
                                <small class="text-muted">Parcels</small>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="alert" style="background: linear-gradient(135deg, #f5f5dc 0%, #f0e68c 100%); border: 1px solid #daa520; color: #3d2515;">
                    <h6><i class="bi bi-info-circle me-2"></i>Agroforestry Assessment</h6>
                    <p class="mb-1">Your farm has an agroforestry score of <strong>${agroforestryScore.toFixed(1)}/10</strong>.</p>
                    <p class="mb-0">${agroforestryScore >= 7 ? 'Excellent agroforestry practices!' :
                        agroforestryScore >= 5 ? 'Good balance of trees and crops.' :
                        agroforestryScore >= 3 ? 'Consider adding more trees for better sustainability.' :
                        'Focus on integrating trees with your crops for improved environmental benefits.'}</p>
                </div>
            `;

            container.innerHTML = summaryHtml + html;

        } catch (error) {
            console.error('Error loading tree management data:', error);
            const container = document.getElementById('treeManagement');
            if (container) {
                container.innerHTML = '<div class="text-danger text-center py-3">Error loading tree and crop data</div>';
            }
        }
    }

    // ==================== CROP DIFFERENTIATION SYSTEM ====================

    async initCropManagement(farmId, parcelId) {
        this.currentFarmId = farmId;
        this.currentParcelId = parcelId;
        this.cropCaptureMode = false;
        this.cropAreas = [];
        this.cropPolygons = [];

        // Load available crop types
        await this.loadCropTypes();

        // Add crop management controls to the map
        this.addCropManagementControls();

        // Load existing crop areas
        this.loadExistingCropAreas();
    }

    addCropManagementControls() {
        if (!this.farmMap) return;

        // Create crop management control panel
        const cropControl = L.control({ position: 'topright' });
        cropControl.onAdd = (map) => {
            const div = L.DomUtil.create('div', 'crop-management-control');
            div.innerHTML = `
                <div class="card border-0 shadow-sm">
                    <div class="card-header bg-success text-white py-2">
                        <h6 class="mb-0"><i class="bi bi-seedling me-2"></i>Crop Management</h6>
                    </div>
                    <div class="card-body p-2">
                        <div class="d-grid gap-2">
                            <select class="form-select form-select-sm" id="cropTypeSelect">
                                <option value="">Select Crop Type</option>
                            </select>
                            <button class="btn btn-sm btn-success" id="startCropCaptureBtn">
                                <i class="bi bi-plus-circle me-1"></i>Add Crop Area
                            </button>
                            <button class="btn btn-sm btn-info" id="viewCropsBtn">
                                <i class="bi bi-eye me-1"></i>View Crops
                            </button>
                            <button class="btn btn-sm btn-primary" id="analyzeCropsBtn">
                                <i class="bi bi-graph-up me-1"></i>Analyze Crops
                            </button>
                        </div>
                        <div class="mt-2 text-xs">
                            <span id="cropAreaCount">0 crop areas mapped</span>
                        </div>
                    </div>
                </div>
            `;
            return div;
        };
        cropControl.addTo(this.farmMap);

        // Populate crop type select
        this.populateCropTypeSelect();

        // Add event listeners
        setTimeout(() => {
            document.getElementById('startCropCaptureBtn').addEventListener('click', () => this.startCropCapture());
            document.getElementById('viewCropsBtn').addEventListener('click', () => this.toggleCropVisibility());
            document.getElementById('analyzeCropsBtn').addEventListener('click', () => this.analyzeCropHealth());
        }, 100);
    }

    async loadCropTypes() {
        try {
            this.availableCropTypes = await api.getCropTypes();
        } catch (error) {
            console.error('Error loading crop types:', error);
            // Fallback crop types
            this.availableCropTypes = [
                { id: 'coffee_sl28', name: 'SL28 Coffee', category: 'coffee', display_color: '#8B4513' },
                { id: 'coffee_sl34', name: 'SL34 Coffee', category: 'coffee', display_color: '#A0522D' },
                { id: 'grevillea', name: 'Grevillea', category: 'shade_tree', display_color: '#228B22' },
                { id: 'macadamia', name: 'Macadamia', category: 'fruit_tree', display_color: '#32CD32' }
            ];
        }
    }

    populateCropTypeSelect() {
        const select = document.getElementById('cropTypeSelect');
        if (!select) return;

        select.innerHTML = '<option value="">Select Crop Type</option>';

        this.availableCropTypes.forEach(cropType => {
            const option = document.createElement('option');
            option.value = cropType.id;
            option.textContent = cropType.name;
            option.setAttribute('data-category', cropType.category);
            option.setAttribute('data-color', cropType.display_color);
            select.appendChild(option);
        });
    }

    startCropCapture() {
        const selectedCropType = document.getElementById('cropTypeSelect').value;
        if (!selectedCropType) {
            this.showToast('Please select a crop type first', 'warning');
            return;
        }

        this.cropCaptureMode = true;
        document.getElementById('startCropCaptureBtn').innerHTML = '<i class="bi bi-stop-circle me-1"></i>Stop Capture';
        document.getElementById('startCropCaptureBtn').classList.remove('btn-success');
        document.getElementById('startCropCaptureBtn').classList.add('btn-danger');

        this.showToast('Crop area capture mode activated. Draw polygons around crop areas.', 'info');

        // Enable drawing mode for polygons
        if (this.farmMap && this.drawnItems) {
            // Clear existing drawings
            this.drawnItems.clearLayers();

            // Add draw control for polygons
            const drawControl = new L.Control.Draw({
                draw: {
                    polygon: {
                        allowIntersection: false,
                        showArea: true,
                        shapeOptions: {
                            color: '#6f4e37',
                            weight: 2,
                            opacity: 0.8,
                            fillOpacity: 0.2
                        }
                    },
                    rectangle: false,
                    circle: false,
                    marker: false,
                    polyline: false,
                    circlemarker: false
                },
                edit: {
                    featureGroup: this.drawnItems
                }
            });

            this.farmMap.addControl(drawControl);

            // Handle draw events
            this.farmMap.on(L.Draw.Event.CREATED, (event) => {
                if (!this.cropCaptureMode) return;

                const layer = event.layer;
                this.drawnItems.addLayer(layer);

                const geojson = layer.toGeoJSON();
                this.showCropDetailsModal(geojson, selectedCropType);
            });
        }
    }

    showCropDetailsModal(geojson, cropTypeId) {
        const cropType = this.availableCropTypes.find(ct => ct.id === cropTypeId);
        if (!cropType) return;

        // Calculate area
        const area = this.calculateGeoJSONArea(geojson);

        // Create modal for crop details
        const modalHtml = `
            <div class="modal fade" id="cropDetailsModal" tabindex="-1" data-bs-backdrop="static" data-bs-keyboard="false">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header" style="background-color: ${cropType.display_color}; color: white;">
                            <h5 class="modal-title">
                                <i class="bi bi-seedling me-2"></i>Add ${cropType.name}
                            </h5>
                            <button type="button" class="btn-modal-close" data-bs-dismiss="modal"><i class="bi bi-x-lg"></i>Close</button>
                        </div>
                        <form id="cropDetailsForm">
                            <div class="modal-body">
                                <div class="alert alert-info">
                                    <strong>Detected Area:</strong> ${area.toFixed(2)} hectares
                                </div>
                                <div class="row g-3">
                                    <div class="col-md-6">
                                        <label class="form-label">Area (hectares) *</label>
                                        <input type="number" class="form-control" id="cropArea" step="0.01"
                                               value="${area.toFixed(2)}" required>
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Growth Stage</label>
                                        <select class="form-select" id="cropGrowthStage">
                                            <option value="seedling">Seedling</option>
                                            <option value="vegetative" selected>Vegetative</option>
                                            <option value="flowering">Flowering</option>
                                            <option value="fruiting">Fruiting</option>
                                            <option value="harvesting">Harvesting</option>
                                        </select>
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Health Status</label>
                                        <select class="form-select" id="cropHealthStatus">
                                            <option value="healthy" selected>Healthy</option>
                                            <option value="stressed">Stressed</option>
                                            <option value="diseased">Diseased</option>
                                            <option value="pest_infested">Pest Infested</option>
                                            <option value="water_stressed">Water Stressed</option>
                                        </select>
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Expected Yield (kg/ha)</label>
                                        <input type="number" class="form-control" id="cropExpectedYield" min="0">
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Planted Date</label>
                                        <input type="date" class="form-control" id="cropPlantedDate">
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Expected Harvest Date</label>
                                        <input type="date" class="form-control" id="cropHarvestDate">
                                    </div>
                                    <div class="col-12">
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="cropOrganic">
                                            <label class="form-check-label">Organic Certified</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="cropFairTrade">
                                            <label class="form-check-label">Fair Trade Certified</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="cropRainforest">
                                            <label class="form-check-label">Rainforest Alliance Certified</label>
                                        </div>
                                    </div>
                                    <div class="col-12">
                                        <label class="form-label">Notes</label>
                                        <textarea class="form-control" id="cropNotes" rows="2"></textarea>
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="submit" class="btn btn-success">Save Crop Area</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if present
        const existingModal = document.getElementById('cropDetailsModal');
        if (existingModal) existingModal.remove();

        document.body.insertAdjacentHTML('beforeend', modalHtml);

        const modal = new bootstrap.Modal(document.getElementById('cropDetailsModal'));
        modal.show();

        // Set default values based on crop type
        if (cropType.category === 'coffee') {
            document.getElementById('cropExpectedYield').value = '1500';
        }

        // Handle form submission
        document.getElementById('cropDetailsForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.saveCropArea(geojson, cropTypeId);
            modal.hide();
        });
    }

    async saveCropArea(geojson, cropTypeId) {
        const cropData = {
            crop_type_id: cropTypeId,
            area_hectares: parseFloat(document.getElementById('cropArea').value),
            boundary_geojson: geojson.geometry,
            growth_stage: document.getElementById('cropGrowthStage').value,
            health_status: document.getElementById('cropHealthStatus').value,
            expected_yield_kg_ha: document.getElementById('cropExpectedYield').value ?
                parseFloat(document.getElementById('cropExpectedYield').value) : null,
            planted_date: document.getElementById('cropPlantedDate').value || null,
            expected_harvest_date: document.getElementById('cropHarvestDate').value || null,
            organic_certified: document.getElementById('cropOrganic').checked ? 1 : 0,
            fair_trade_certified: document.getElementById('cropFairTrade').checked ? 1 : 0,
            rain_forest_alliance_certified: document.getElementById('cropRainforest').checked ? 1 : 0,
            notes: document.getElementById('cropNotes').value
        };

        try {
            const result = await api.addCropArea(this.currentFarmId, this.currentParcelId, cropData);

            // Add crop area to map
            this.addCropAreaToMap(geojson, cropData, result.id);

            this.updateCropAreaCount();
            this.showToast('Crop area added successfully!', 'success');

            // Stop capture mode
            this.stopCropCapture();

        } catch (error) {
            this.showToast(`Error saving crop area: ${error.message}`, 'error');
        }
    }

    addCropAreaToMap(geojson, cropData, cropId) {
        const cropType = this.availableCropTypes.find(ct => ct.id === cropData.crop_type_id);

        const polygon = L.geoJSON(geojson, {
            style: {
                color: cropType ? cropType.display_color : '#6f4e37',
                weight: 2,
                opacity: 0.8,
                fillColor: cropType ? cropType.display_color : '#6f4e37',
                fillOpacity: 0.3
            }
        }).addTo(this.farmMap);

        polygon.bindPopup(`
            <div class="crop-popup">
                <h6 style="color: ${cropType ? cropType.display_color : '#6f4e37'}">
                    ${cropType ? cropType.name : 'Unknown Crop'}
                </h6>
                <p class="mb-1"><strong>Area:</strong> ${cropData.area_hectares} ha</p>
                <p class="mb-1"><strong>Stage:</strong> ${cropData.growth_stage}</p>
                <p class="mb-1"><strong>Health:</strong> ${cropData.health_status}</p>
                ${cropData.expected_yield_kg_ha ?
                    `<p class="mb-1"><strong>Expected Yield:</strong> ${cropData.expected_yield_kg_ha} kg/ha</p>` : ''}
            </div>
        `);

        // Store polygon reference
        this.cropPolygons.push({
            id: cropId,
            polygon: polygon,
            data: cropData
        });
    }

    async loadExistingCropAreas() {
        if (!this.currentFarmId || !this.currentParcelId) return;

        try {
            const crops = await api.getParcelCrops(this.currentFarmId, this.currentParcelId);

            crops.forEach(crop => {
                // Create GeoJSON from boundary
                const geojson = {
                    type: 'Feature',
                    geometry: crop.boundary_geojson,
                    properties: {}
                };

                this.addCropAreaToMap(geojson, crop, crop.id);
            });

            this.updateCropAreaCount();

        } catch (error) {
            console.error('Error loading crop areas:', error);
        }
    }

    updateCropAreaCount() {
        const count = this.cropPolygons.length;
        const countElement = document.getElementById('cropAreaCount');
        if (countElement) {
            countElement.textContent = `${count} crop area${count !== 1 ? 's' : ''} mapped`;
        }
    }

    stopCropCapture() {
        this.cropCaptureMode = false;
        document.getElementById('startCropCaptureBtn').innerHTML = '<i class="bi bi-plus-circle me-1"></i>Add Crop Area';
        document.getElementById('startCropCaptureBtn').classList.remove('btn-danger');
        document.getElementById('startCropCaptureBtn').classList.add('btn-success');

        // Remove draw controls
        if (this.farmMap) {
            this.farmMap.off(L.Draw.Event.CREATED);
        }
    }

    toggleCropVisibility() {
        const allVisible = this.cropPolygons.every(cp => this.farmMap.hasLayer(cp.polygon));

        this.cropPolygons.forEach(cp => {
            if (allVisible) {
                this.farmMap.removeLayer(cp.polygon);
            } else {
                cp.polygon.addTo(this.farmMap);
            }
        });

        const btn = document.getElementById('viewCropsBtn');
        if (btn) {
            btn.innerHTML = allVisible ?
                '<i class="bi bi-eye-slash me-1"></i>Hide Crops' :
                '<i class="bi bi-eye me-1"></i>View Crops';
        }
    }

    async analyzeCropHealth() {
        if (this.cropPolygons.length === 0) {
            this.showToast('No crop areas to analyze', 'warning');
            return;
        }

        this.showToast('Analyzing crop health...', 'info');

        // Analyze each crop area
        const results = [];
        for (const cropPolygon of this.cropPolygons) {
            try {
                const analysis = await api.analyzeCropHealth(
                    this.currentFarmId,
                    this.currentParcelId,
                    cropPolygon.id
                );
                results.push(analysis);
            } catch (error) {
                console.error(`Error analyzing crop ${cropPolygon.id}:`, error);
            }
        }

        if (results.length > 0) {
            this.showCropAnalysisResults(results);
            this.showToast(`Analyzed ${results.length} crop areas`, 'success');
        } else {
            this.showToast('No crop analyses completed', 'warning');
        }
    }

    showCropAnalysisResults(results) {
        // Create results modal
        const resultsHtml = results.map(result => {
            const cropInsights = result.crop_specific_insights || {};
            return `
                <div class="card mb-3 border-0 shadow-sm">
                    <div class="card-header" style="background-color: ${cropInsights.expected_ndvi_range ? '#f8f9fa' : '#fff'}">
                        <h6 class="mb-0">${cropInsights.crop_type || 'Unknown Crop'}</h6>
                    </div>
                    <div class="card-body">
                        <div class="row text-center">
                            <div class="col-4">
                                <div class="h5 mb-0">${result.ndvi_mean?.toFixed(3) || 'N/A'}</div>
                                <small class="text-muted">NDVI</small>
                            </div>
                            <div class="col-4">
                                <div class="h5 mb-0 ${cropInsights.health_assessment === 'healthy' ? 'text-success' : 'text-warning'}">
                                    ${cropInsights.health_score || 'N/A'}
                                </div>
                                <small class="text-muted">Health Score</small>
                            </div>
                            <div class="col-4">
                                <div class="h5 mb-0">${cropInsights.yield_potential || 'N/A'}</div>
                                <small class="text-muted">Yield (kg/ha)</small>
                            </div>
                        </div>
                        <hr>
                        <p class="mb-1"><strong>Health Assessment:</strong> ${cropInsights.health_assessment || 'Unknown'}</p>
                        <p class="mb-0"><strong>Growth Stage:</strong> ${cropInsights.growth_stage_alignment || 'Unknown'}</p>
                    </div>
                </div>
            `;
        }).join('');

        const modalHtml = `
            <div class="modal fade" id="cropAnalysisModal" tabindex="-1" data-bs-backdrop="static" data-bs-keyboard="false">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-graph-up me-2"></i>Crop Health Analysis Results</h5>
                            <button type="button" class="btn-modal-close" data-bs-dismiss="modal"><i class="bi bi-x-lg"></i>Close</button>
                        </div>
                        <div class="modal-body">
                            ${resultsHtml}
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-primary" onclick="app.exportCropAnalysis()">
                                <i class="bi bi-download me-1"></i>Export Results
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const existingModal = document.getElementById('cropAnalysisModal');
        if (existingModal) existingModal.remove();

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        new bootstrap.Modal(document.getElementById('cropAnalysisModal')).show();
    }

    exportCropAnalysis() {
        // Export functionality would download CSV/PDF of results
        this.showToast('Export functionality coming soon', 'info');
    }

    openTreeMapping() {
        // Open tree mapping interface
        this.showToast('Opening tree mapping interface...', 'info');

        // For now, show a modal with instructions
        const modalHtml = `
            <div class="modal fade" id="treeMappingModal" tabindex="-1" data-bs-backdrop="static" data-bs-keyboard="false">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-tree me-2"></i>Tree Mapping</h5>
                            <button type="button" class="btn-modal-close" data-bs-dismiss="modal"><i class="bi bi-x-lg"></i>Close</button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <h6>How to Map Trees:</h6>
                                <ol>
                                    <li>Go to the farm mapping section</li>
                                    <li>Click "Map Trees" in the tree control panel</li>
                                    <li>Click on the map where trees are located</li>
                                    <li>Fill in tree details (type, height, health, etc.)</li>
                                    <li>Trees will be saved and analyzed in satellite imagery</li>
                                </ol>
                                <h6>How to Map Crops:</h6>
                                <ol>
                                    <li>Select a crop type from the dropdown</li>
                                    <li>Click "Add Crop Area" to start drawing</li>
                                    <li>Draw polygons around different crop areas</li>
                                    <li>Fill in crop details and save</li>
                                    <li>Use "Analyze Crops" to get health insights</li>
                                </ol>
                            </div>
                            <div class="text-center">
                                <button class="btn btn-primary" onclick="app.navigateToFarms()">
                                    <i class="bi bi-geo-alt me-1"></i>Go to Farm Mapping
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const existingModal = document.getElementById('treeMappingModal');
        if (existingModal) existingModal.remove();

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        new bootstrap.Modal(document.getElementById('treeMappingModal')).show();
    }

    navigateToFarms() {
        // Close modal and navigate to farms page
        const modal = bootstrap.Modal.getInstance(document.getElementById('treeMappingModal'));
        if (modal) modal.hide();

        this.loadPage('farms');
    }

    viewParcelTrees(parcelId) {
        // Show detailed tree view for a parcel
        this.showToast(`Viewing trees for parcel ${parcelId}`, 'info');
        // Implementation would show detailed tree list/grid
    }

    showToast(message, type = 'info', duration = 4000) {
        const container = document.querySelector('.toast-container');
        if (!container) return;
        const colorMap = { error: 'danger', success: 'success', warning: 'warning text-dark', info: 'primary' };
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${colorMap[type] || 'primary'} border-0 show`;
        toast.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), duration);
    }
}

// Initialize app
const app = new PlotraDashboard();
window.app = app;
window.showRegisterModal = function() { app.showRegisterModal(); };
window.showLoginModal = function() { app.showLoginModal(); };
window.subscribeNewsletter = function() { app.subscribeNewsletter(); };
