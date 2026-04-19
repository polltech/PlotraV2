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
    }
    
    checkResetPasswordToken() {
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        
        if (token) {
            this.resetToken = token;
            console.log('Reset password token detected:', token.substring(0, 8) + '...');
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
        const email = document.getElementById('forgotEmail').value;
        if (!email || !email.includes('@')) {
            this.showToast('Please enter a valid email', 'error');
            return;
        }
        
        try {
            await api.forgotPassword(email);
            this.showToast('Reset link sent! Redirecting to reset page...', 'success');
            
            // Simulate receiving the email and clicking the link after 2 seconds
            setTimeout(() => {
                document.querySelectorAll('#loginModal .step-content').forEach(s => s.classList.remove('active'));
                document.getElementById('loginStepReset').classList.add('active');
            }, 2000);
        } catch (error) {
            this.showToast(error.message, 'error');
        }
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
            this.showToast('Password reset successful! Please sign in.', 'success');
            // Clear the URL token parameter
            window.history.replaceState({}, document.title, window.location.pathname);
            this.resetToken = null;
            this.showLoginModal();
        } catch (error) {
            this.showToast(error.message, 'error');
        }
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

        this.loadCurrentUser().then(() => {
            this.updateSidebarNavigation();
            this.loadPage('dashboard');
        }).catch(err => {
            console.error('Failed to show app:', err);
            this.showToast('Failed to load user data', 'error');
        });
    }
    
    async loadCurrentUser() {
        try {
            this.currentUser = await api.getCurrentUser();
            localStorage.setItem('plotra_user', JSON.stringify(this.currentUser));
            console.log('Current user loaded:', this.currentUser);
            console.log('User role:', this.currentUser?.role);

            // Validate user data exists
            if (!this.currentUser || !this.currentUser.id) {
                throw new Error('Invalid user data');
            }
            
            const roleBadge = document.getElementById('userRole');
            const userRoleDisplay = document.getElementById('userRoleDisplay');
            const userProfile = document.getElementById('userProfile');
            const userName = document.getElementById('userName');
            const userAvatar = document.getElementById('userAvatar');
            
            if (roleBadge) roleBadge.textContent = this.formatRole(this.currentUser.role);
            if (userRoleDisplay) userRoleDisplay.textContent = this.formatRole(this.currentUser.role);
            
            // Show user profile in sidebar
            if (userProfile) {
                userProfile.style.display = 'flex';
                if (userName) userName.textContent = `${this.currentUser.first_name || ''} ${this.currentUser.last_name || ''}`.trim() || this.currentUser.email;
                if (userAvatar) userAvatar.textContent = (this.currentUser.first_name || this.currentUser.email || 'U').charAt(0).toUpperCase();
            }
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
            { id: 'parcels', icon: 'bi-boundary', label: 'My Parcels' },
            { id: 'deliveries', icon: 'bi-box-seam', label: 'Deliveries' },
            { id: 'documents', icon: 'bi-file-earmark-text', label: 'KYC Documents' },
            { id: 'compliance', icon: 'bi-file-earmark-check', label: 'EUDR Compliance' }
        ];
        
        const coopAdminNav = [
            { id: 'dashboard', icon: 'bi-speedometer2', label: 'Dashboard' },
            { id: 'farms', icon: 'bi-geo-alt', label: 'Farms' },
            { id: 'parcels', icon: 'bi-boundary', label: 'Parcels' },
            { id: 'deliveries', icon: 'bi-box-seam', label: 'Deliveries' },
            { id: 'batches', icon: 'bi-layers', label: 'Batches' },
            { id: 'verification', icon: 'bi-check-circle', label: 'Verification' },
            { id: 'satellite', icon: 'bi-satellite', label: 'Satellite' },
            { id: 'compliance', icon: 'bi-file-earmark-check', label: 'EUDR' },
            { id: 'users', icon: 'bi-people', label: 'Users' }
        ];
        
        const coopOfficerNav = [
            { id: 'dashboard', icon: 'bi-speedometer2', label: 'Dashboard' },
            { id: 'farms', icon: 'bi-geo-alt', label: 'Farms' },
            { id: 'parcels', icon: 'bi-boundary', label: 'Parcels' },
            { id: 'deliveries', icon: 'bi-box-seam', label: 'Deliveries' },
            { id: 'verification', icon: 'bi-check-circle', label: 'Verification' },
            { id: 'compliance', icon: 'bi-file-earmark-check', label: 'EUDR' }
        ];
        
        const eudrReviewerNav = [
            { id: 'dashboard', icon: 'bi-speedometer2', label: 'Dashboard' },
            { id: 'verification', icon: 'bi-check-circle', label: 'Verification' },
            { id: 'compliance', icon: 'bi-file-earmark-check', label: 'EUDR Review' }
        ];
        
        const adminNav = [
            { id: 'dashboard', icon: 'bi-speedometer2', label: 'Dashboard' },
            { id: 'cooperatives', icon: 'bi-building', label: 'Cooperatives' },
            { id: 'farmers', icon: 'bi-people', label: 'Farmers' },
            { id: 'farms', icon: 'bi-geo-alt', label: 'Farms' },
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
        const navItems = this.getRoleNavigation(role);
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
            }
        });

        // Safe helper to add listener
        const safeAddListener = (id, event, callback) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener(event, callback);
        };

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
            const emailInput = document.getElementById('loginEmail');
            const email = emailInput ? emailInput.value : '';
            if (email && email.includes('@')) {
                const displayEmail = document.getElementById('displayLoginEmail');
                if (displayEmail) displayEmail.textContent = email;
                const step1 = document.getElementById('loginStep1');
                const step2 = document.getElementById('loginStep2');
                if (step1) step1.classList.remove('active');
                if (step2) step2.classList.add('active');
            } else {
                this.showToast('Please enter a valid email', 'error');
            }
        });

        safeAddListener('btnBackLogin', 'click', () => {
            const step1 = document.getElementById('loginStep1');
            const step2 = document.getElementById('loginStep2');
            if (step1) step1.classList.add('active');
            if (step2) step2.classList.remove('active');
        });

        // Registration form navigation
        safeAddListener('btnNextReg1', 'click', () => {
            const email = document.getElementById('regEmail').value;
            const firstName = document.getElementById('regFirstName').value;
            const lastName = document.getElementById('regLastName').value;
            
            if (email && email.includes('@') && firstName && lastName) {
                document.getElementById('regStep1').classList.remove('active');
                document.getElementById('regStep2').classList.add('active');
            } else {
                this.showToast('Please fill in all personal details', 'error');
            }
        });

        document.querySelectorAll('.btnBackReg1').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('regStep1').classList.add('active');
                document.getElementById('regStep2').classList.remove('active');
            });
        });

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
                const response = await fetch(`http://localhost:8000/api/v2/coop/cooperatives/validate-code?code=` + encodeURIComponent(cooperativeCode), {
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
                        const response = await fetch(`http://localhost:8000/api/v2/coop/cooperatives/search?code=` + encodeURIComponent(searchTerm), {
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
    
    async handleLogin() {
        const email = document.getElementById('loginEmail').value;
        const pass = document.getElementById('loginPassword').value;
        
        try {
            this.showToast('Logging in...', 'info');
            await api.login(email, pass);
            
            // Close login modal
            const loginEl = document.getElementById('loginModal');
            const loginModal = bootstrap.Modal.getInstance(loginEl);
            if (loginModal) loginModal.hide();
            
            this.showApp();
            this.showToast('Login successful!', 'success');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }
    
    async handleRegister() {
        const email = document.getElementById('regEmail').value;
        const password = document.getElementById('regPassword').value;
        const confirmPassword = document.getElementById('regConfirmPassword').value;
        const firstName = document.getElementById('regFirstName').value;
        const lastName = document.getElementById('regLastName').value;
        const role = document.getElementById('regRole').value;
        const county = document.getElementById('regCounty')?.value;
        const subcounty = document.getElementById('regSubcounty')?.value;
        
        // New additional fields
        const gender = document.getElementById('regGender')?.value;
        const idType = document.getElementById('regIdType')?.value;
        const idNumber = document.getElementById('regIdNumber')?.value;
        const phoneNumber = document.getElementById('regPhone')?.value;
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
        
        if (!email || !firstName || !lastName || !role) {
            this.showToast('Please fill in all required fields', 'error');
            return;
        }
        
        try {
            // Get cooperative code field
            const cooperativeCode = document.getElementById('regCooperativeCode')?.value || '';
            
            console.log('Attempting registration for:', email, 'with role:', role);
            await api.register({
                email: email,
                password: password,
                first_name: firstName,
                last_name: lastName,
                role: role,
                county: county || undefined,
                subcounty: subcounty || undefined,
                // New fields
                gender: gender || undefined,
                id_type: idType || undefined,
                id_number: idNumber || undefined,
                phone_number: phoneNumber || undefined,
                payout_method: payoutMethod || 'mpesa',
                payout_recipient_id: payoutRecipientId || undefined,
                payout_bank_name: payoutBankName || undefined,
                payout_account_number: payoutAccountNumber || undefined,
                // Cooperative membership (required)
                cooperative_code: cooperativeCode
            });
            
            console.log('Registration request sent successfully');
            this.showToast('Registration successful! Logging you in...', 'success');
            
            // Close register modal
            const registerEl = document.getElementById('registerModal');
            const registerModal = bootstrap.Modal.getInstance(registerEl);
            if (registerModal) registerModal.hide();
            
            // Clear form
            document.getElementById('registerForm').reset();
            
            // Auto-login after registration
            await api.login(email, password);
            this.showApp();
            this.showToast('Welcome! Please complete your profile information.', 'success');
            
            // Redirect to profile page after registration to complete profile
            setTimeout(() => {
                this.loadPage('profile');
            }, 1000);
        } catch (error) {
            console.error('Registration/Login Error:', error);
            this.showToast(error.message || 'Registration failed', 'error');
        }
    }
    
    logout() {
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
        
        return true; // Default allow
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
                case 'farms':
                    if (title) title.textContent = 'Farms Management';
                    await this.loadFarms(content);
                    break;
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
        } else if (role === 'COOP_OFFICER' || role === 'FACTOR') {
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
            
            content.innerHTML = `
                <div class="row">
                    <div class="col-md-12 col-lg-12">
                        <div class="row row-cols-1">
                            <div class="overflow-hidden d-slider1 ">
                                <ul class="p-0 m-0 mb-2 swiper-wrapper list-inline">
                                    <li class="swiper-slide card card-slide" data-aos="fade-up" data-aos-delay="700">
                                        <div class="card-body">
                                            <div class="progress-widget">
                                                <div id="circle-progress-01" class="text-center circle-progress-01 circle-progress circle-progress-primary" data-min-value="0" data-max-value="100" data-value="80" data-type="percent">
                                                    <svg class="card-slie-arrow icon-24" width="24" viewBox="0 0 24 24">
                                                        <path fill="currentColor" d="M5,17.59L15.59,7H9V5H19V15H17V8.41L6.41,19L5,17.59Z" />
                                                    </svg>
                                                </div>
                                                <div class="progress-detail">
                                                    <p class="mb-2 text-muted small">Cooperatives</p>
                                                    <h4 class="counter">${stats.total_cooperatives || 0}</h4>
                                                </div>
                                            </div>
                                        </div>
                                    </li>
                                    <li class="swiper-slide card card-slide" data-aos="fade-up" data-aos-delay="800">
                                        <div class="card-body">
                                            <div class="progress-widget">
                                                <div id="circle-progress-02" class="text-center circle-progress-01 circle-progress circle-progress-info" data-min-value="0" data-max-value="100" data-value="70" data-type="percent">
                                                    <svg class="card-slie-arrow icon-24" width="24" viewBox="0 0 24 24">
                                                        <path fill="currentColor" d="M19,6.41L17.59,5L7,15.59V9H5V19H15V17H8.41L19,6.41Z" />
                                                    </svg>
                                                </div>
                                                <div class="progress-detail">
                                                    <p class="mb-2 text-muted small">Total Farms</p>
                                                    <h4 class="counter">${stats.total_farms || 0}</h4>
                                                </div>
                                            </div>
                                        </div>
                                    </li>
                                    <li class="swiper-slide card card-slide" data-aos="fade-up" data-aos-delay="900">
                                        <div class="card-body">
                                            <div class="progress-widget">
                                                <div id="circle-progress-03" class="text-center circle-progress-01 circle-progress circle-progress-primary" data-min-value="0" data-max-value="100" data-value="60" data-type="percent">
                                                    <svg class="card-slie-arrow icon-24" width="24" viewBox="0 0 24 24">
                                                        <path fill="currentColor" d="M5,17.59L15.59,7H9V5H19V15H17V8.41L6.41,19L5,17.59Z" />
                                                    </svg>
                                                </div>
                                                <div class="progress-detail">
                                                    <p class="mb-2 text-muted small">Farmers</p>
                                                    <h4 class="counter">${stats.total_farmers || 0}</h4>
                                                </div>
                                            </div>
                                        </div>
                                    </li>
                                    <li class="swiper-slide card card-slide" data-aos="fade-up" data-aos-delay="1000">
                                        <div class="card-body">
                                            <div class="progress-widget">
                                                <div id="circle-progress-04" class="text-center circle-progress-01 circle-progress circle-progress-info" data-min-value="0" data-max-value="100" data-value="40" data-type="percent">
                                                    <svg class="card-slie-arrow icon-24" width="24" viewBox="0 0 24 24">
                                                        <path fill="currentColor" d="M19,6.41L17.59,5L7,15.59V9H5V19H15V17H8.41L19,6.41Z" />
                                                    </svg>
                                                </div>
                                                <div class="progress-detail">
                                                    <p class="mb-2 text-muted small">Compliance</p>
                                                    <h4 class="counter">${stats.compliance_rate || 0}%</h4>
                                                </div>
                                            </div>
                                        </div>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row g-4">
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
                                                <th class="small">FARMS</th>
                                                <th class="small">COMPLIANCE</th>
                                                <th class="small">PROGRESS</th>
                                                <th class="text-end small">ACTION</th>
                                            </tr>
                                        </thead>
                                        <tbody id="coop-performance-list">
                                            <tr><td colspan="5" class="text-center py-4 text-muted">No data available</td></tr>
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
                                    <hr>
                                    <button class="btn btn-soft-danger w-100" onclick="app.confirmClearAllData()">
                                        <i class="bi bi-trash me-2"></i> Reset Platform Data
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
                this.initAdminDashboardCharts(overview);
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

    initAdminDashboardCharts(overview) {
        const chartContainer = document.querySelector("#compliance-chart");
        if (!chartContainer) {
            console.log('Chart container not found');
            return;
        }
        console.log('Chart container found, checking ApexCharts...');
        console.log('ApexCharts defined:', typeof ApexCharts);
        
        const options = {
            series: [{
                name: 'Compliant',
                data: overview?.compliant_trend || [30, 40, 35, 50, 49, 60, 70, 91, 125]
            }, {
                name: 'Pending',
                data: overview?.pending_trend || [20, 30, 25, 30, 29, 40, 40, 50, 60]
            }],
            chart: {
                height: 245,
                type: 'area',
                toolbar: { show: false },
                sparkline: { enabled: false }
            },
            dataLabels: { enabled: false },
            stroke: { curve: 'smooth', width: 3 },
            colors: ["#6f4e37", "#a67b5b"],
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
                categories: overview?.categories || ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"],
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
            legend: { show: false },
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
            const verifications = await api.getPendingVerifications({ limit: 5 });
            if (verifications && verifications.length > 0) {
                list.innerHTML = verifications.map(v => `
                    <tr>
                        <td class="small">
                            <div class="fw-bold">${v.farmer_name || 'N/A'}</div>
                            <div class="text-muted x-small-text">${v.cooperative_name || v.cooperative_code || 'N/A'}</div>
                        </td>
                        <td>
                            <span class="badge bg-warning-subtle text-warning" style="font-size: 0.6rem;">Pending</span>
                        </td>
                        <td class="text-end small text-muted">
                            ${new Date(v.created_at).toLocaleDateString()}
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
                    const rate = coop.compliance_rate || Math.floor(Math.random() * 40) + 60;
                    const color = rate > 90 ? 'success' : (rate > 70 ? 'info' : 'warning');
                    return `
                        <tr>
                            <td>
                                <div class="d-flex align-items-center">
                                    <div class="bg-soft-primary rounded-circle p-2 me-3" style="width: 40px; height: 40px; display: flex; align-items: center; justify-content: center;">
                                        <i class="bi bi-building text-primary"></i>
                                    </div>
                                    <div class="fw-bold">${coop.name}</div>
                                </div>
                            </td>
                            <td>${coop.total_farms || 0}</td>
                            <td><span class="text-${color}">${rate}%</span></td>
                            <td style="width: 200px;">
                                <div class="progress" style="height: 6px;">
                                    <div class="progress-bar bg-${color}" role="progressbar" style="width: ${rate}%"></div>
                                </div>
                            </td>
                            <td class="text-end">
                                <button class="btn btn-sm btn-outline-primary" onclick="app.viewCooperative('${coop.id}')">
                                    <i class="bi bi-arrow-right"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                }).join('');
            } else {
                list.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted">No cooperatives found</td></tr>';
            }
        } catch (error) {
            console.error('Failed to load coop performance:', error);
            list.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-danger">Error loading data</td></tr>';
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

    async confirmClearAllData() {
        if (!confirm('CRITICAL: This will permanently delete ALL data from the platform. Proceed?')) return;
        try {
            this.showToast('Clearing platform data...', 'warning');
            await api.clearAllData();
            this.showToast('All data cleared successfully. Reloading...', 'success');
            setTimeout(() => window.location.reload(), 2000);
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async renderCoopDashboard(content) {
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

            const farms = farmsResponse.farms || [];
            const farmList = Array.isArray(farms) ? farms : (farms ? [farms] : []);
            const deliveryList = Array.isArray(deliveries) ? deliveries : [];
            const totalWeight = deliveryList.reduce((sum, d) => sum + (d.net_weight_kg || 0), 0);
            
            content.innerHTML = `
                <div class="row g-4 mb-4">
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body">
                                <div class="d-flex align-items-center mb-3">
                                    <div class="avatar-sm bg-soft-primary text-primary rounded-circle me-3">
                                        <i class="bi bi-tree fs-4"></i>
                                    </div>
                                    <h6 class="card-title mb-0">Total Farms</h6>
                                </div>
                                <h2 class="mb-0">${farmList.length}</h2>
                                <p class="text-muted small mt-2 mb-0">Active farm registrations</p>
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
                    <div class="col-lg-6">
                        <div class="card h-100">
                            <div class="card-header d-flex justify-content-between align-items-center bg-transparent">
                                <h4 class="card-title mb-0">My Farms</h4>
                                <button class="btn btn-sm btn-primary" onclick="app.navigateTo('farms')">Manage</button>
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    <table class="table table-hover mb-0">
                                        <thead class="table-light">
                                            <tr>
                                                <th>Farm Name</th>
                                                <th>Size (Ha)</th>
                                                <th>Status</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${farmList.length > 0 ? farmList.map(f => `
                                                <tr>
                                                    <td>${f.farm_name || 'Unnamed Farm'}</td>
                                                    <td>${f.total_area_hectares || '0.00'}</td>
                                                    <td><span class="badge bg-soft-success text-success">${f.compliance_status || 'Compliant'}</span></td>
                                                </tr>
                                            `).join('') : '<tr><td colspan="3" class="text-center py-4">No farms registered yet</td></tr>'}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card h-100">
                            <div class="card-header d-flex justify-content-between align-items-center bg-transparent">
                                <h4 class="card-title mb-0">Recent Deliveries</h4>
                                <button class="btn btn-sm btn-primary" onclick="app.navigateTo('deliveries')">View All</button>
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    <table class="table table-hover mb-0">
                                        <thead class="table-light">
                                            <tr>
                                                <th>ID</th>
                                                <th>Weight</th>
                                                <th>Quality</th>
                                                <th>Date</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${deliveryList.length > 0 ? deliveryList.slice(0, 5).map(d => `
                                                <tr>
                                                    <td><span class="small text-muted">#${d.delivery_number || d.id}</span></td>
                                                    <td>${d.net_weight_kg || 0} kg</td>
                                                    <td><span class="badge bg-soft-info text-info">${d.quality_grade || 'PB'}</span></td>
                                                    <td>${new Date(d.created_at).toLocaleDateString()}</td>
                                                </tr>
                                            `).join('') : '<tr><td colspan="4" class="text-center py-4">No recent deliveries</td></tr>'}
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
            const verifications = await api.getPendingVerifications({ limit: 5 });
            
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
                                <h6 class="text-uppercase small mb-2">Compliant Farms</h6>
                                <h2 class="mb-0">${stats.compliant_farms || 0}</h2>
                                <p class="text-muted small mt-2 mb-0">Verified for EUDR</p>
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
                document.getElementById('total-farmers-count').textContent = users.length;
                document.getElementById('verified-farmers-count').textContent = users.filter(u => u.verification_status === 'verified').length;
                document.getElementById('pending-farmers-count').textContent = users.filter(u => u.verification_status !== 'verified').length;

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

                // Render Gender Chart
                if (typeof ApexCharts !== 'undefined') {
                    const males = users.filter(u => u.gender?.toLowerCase() === 'male').length;
                    const females = users.filter(u => u.gender?.toLowerCase() === 'female').length;
                    const others = users.length - males - females;

                    new ApexCharts(document.querySelector("#farmer-gender-chart"), {
                        series: [males, females, others],
                        chart: { type: 'donut', height: 250 },
                        labels: ['Male', 'Female', 'Other'],
                        colors: ['#6f4e37', '#a67b5b', '#c4a77d'],
                        legend: { position: 'bottom' }
                    }).render();
                }
            } else {
                list.innerHTML = '<tr><td colspan="5" class="text-center py-4">No farmers found</td></tr>';
            }
        } catch (e) {
            console.error(e);
            this.showToast('Error loading farmers', 'error');
        }
    }

    async loadFarms(content) {
        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-3">
                    <div class="card bg-soft-primary text-primary h-100">
                        <div class="card-body text-center">
                            <h6 class="text-uppercase small mb-2">Total Area</h6>
                            <h3 class="mb-0" id="total-area-count">... Ha</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card bg-soft-info text-info h-100">
                        <div class="card-body text-center">
                            <h6 class="text-uppercase small mb-2">Mapped Farms</h6>
                            <h3 class="mb-0" id="mapped-farms-count">...</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card bg-soft-success text-success h-100">
                        <div class="card-body text-center">
                            <h6 class="text-uppercase small mb-2">EUDR Compliant</h6>
                            <h3 class="mb-0" id="compliant-farms-count">...</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card bg-soft-danger text-danger h-100">
                        <div class="card-body text-center">
                            <h6 class="text-uppercase small mb-2">High Risk</h6>
                            <h3 class="mb-0" id="high-risk-count">...</h3>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-lg-12">
                    <div class="card">
                        <div class="card-header">
                            <h4 class="card-title">Farm Distribution & Risk Analysis</h4>
                        </div>
                        <div class="card-body">
                            <div id="farm-risk-chart" style="min-height: 300px;"></div>
                        </div>
                    </div>
                </div>
                <div class="col-lg-12">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h4 class="card-title mb-0">All Registered Farms</h4>
                            <button class="btn btn-primary btn-sm" onclick="app.showAddFarmModal()">
                                <i class="bi bi-plus-lg me-1"></i> Add Farm
                            </button>
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>Farm Name</th>
                                            <th>Owner</th>
                                            <th>Location</th>
                                            <th>Area (Ha)</th>
                                            <th>Compliance</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody id="farms-admin-list">
                                        <tr><td colspan="6" class="text-center py-4">Loading farms...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        try {
            const response = await api.getFarms();
            const farms = response.farms || [];
            const list = document.getElementById('farms-admin-list');
            
            if (farms && farms.length > 0) {
                const totalArea = farms.reduce((sum, f) => sum + (f.total_area || f.total_area_hectares || 0), 0);
                document.getElementById('total-area-count').textContent = totalArea.toFixed(2) + ' Ha';
                document.getElementById('mapped-farms-count').textContent = farms.length;
                document.getElementById('compliant-farms-count').textContent = farms.filter(f => f.compliance_status === 'compliant').length;
                document.getElementById('high-risk-count').textContent = farms.filter(f => f.compliance_status === 'non_compliant').length;

                list.innerHTML = farms.map(f => `
                    <tr>
                        <td><div class="fw-bold">${f.name || f.farm_name}</div><div class="text-muted x-small-text">${f.code || ''}</div></td>
                        <td>${f.owner_name || 'N/A'}</td>
                        <td>${f.county || 'N/A'}</td>
                        <td>${f.total_area || f.total_area_hectares || 0} Ha</td>
                        <td>
                            <span class="badge ${f.compliance_status === 'compliant' ? 'bg-soft-success text-success' : (f.compliance_status === 'non_compliant' ? 'bg-soft-danger text-danger' : 'bg-soft-warning text-warning')}">
                                ${f.compliance_status || 'pending'}
                            </span>
                        </td>
                        <td>
                            <button class="btn btn-sm btn-outline-primary" onclick="app.showAddParcelModal('${f.id}')">
                                <i class="bi bi-plus-lg"></i> Parcel
                            </button>
                            <button class="btn btn-sm btn-outline-info" onclick="app.loadMonitoring('${f.id}', 'farm')">
                                <i class="bi bi-satellite"></i> Monitor
                            </button>
                        </td>
                    </tr>
                `).join('');

                if (typeof ApexCharts !== 'undefined') {
                    const compliant = farms.filter(f => f.compliance_status === 'compliant').length;
                    const pending = farms.filter(f => f.compliance_status === 'pending' || !f.compliance_status).length;
                    const risk = farms.filter(f => f.compliance_status === 'non_compliant').length;

                    new ApexCharts(document.querySelector("#farm-risk-chart"), {
                        series: [{
                            name: 'Farms',
                            data: [compliant, pending, risk]
                        }],
                        chart: { type: 'bar', height: 300 },
                        plotOptions: { bar: { borderRadius: 4, horizontal: true } },
                        dataLabels: { enabled: false },
                        xaxis: { categories: ['Compliant', 'Pending', 'High Risk'] },
                        colors: ['#1aa053', '#f86441', '#c03221']
                    }).render();
                }
            } else {
                list.innerHTML = '<tr><td colspan="6" class="text-center py-4">No farms found</td></tr>';
            }
        } catch (e) {
            console.error(e);
            this.showToast('Error loading farms', 'error');
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

        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h4 class="card-title">Coffee Deliveries</h4>
                            ${(isCoop || isAdmin) ? `
                                <button class="btn btn-primary btn-sm" onclick="app.showRecordDeliveryModal()">
                                    <i class="bi bi-plus-lg me-1"></i> Record Delivery
                                </button>
                            ` : ''}
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>ID</th>
                                            <th>Farm</th>
                                            <th>Net Weight</th>
                                            <th>Grade</th>
                                            <th>Status</th>
                                            <th>Date</th>
                                        </tr>
                                    </thead>
                                    <tbody id="deliveries-list">
                                        <tr><td colspan="6" class="text-center py-4">Loading deliveries...</td></tr>
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
            
            if (deliveries && deliveries.length > 0) {
                list.innerHTML = deliveries.map(d => `
                    <tr>
                        <td><span class="fw-bold">${d.delivery_number || 'D-'+d.id}</span></td>
                        <td>${d.farm_name || 'Farm #'+d.farm_id}</td>
                        <td class="fw-bold">${d.net_weight_kg || 0} kg</td>
                        <td><span class="badge bg-soft-primary text-primary">${d.quality_grade || 'N/A'}</span></td>
                        <td><span class="badge ${this.getDeliveryStatusClass(d.status)}">${d.status}</span></td>
                        <td>${new Date(d.created_at).toLocaleDateString()}</td>
                    </tr>
                `).join('');
            } else {
                list.innerHTML = '<tr><td colspan="6" class="text-center py-4">No deliveries found.</td></tr>';
            }
        } catch (error) {
            console.error(error);
            list.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-danger">Error: ${error.message}</td></tr>`;
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
            const response = await api.getFarms();
            const farms = response.farms || [];
            const farmSelect = document.getElementById('deliveryFarm');
            if (farmSelect) {
                farmSelect.innerHTML = '<option value="">Select Farm</option>' + 
                    farms.map(f => `<option value="${f.id}">${f.farm_name || 'Farm #'+f.id}</option>`).join('');
            }
            const modalEl = document.getElementById('addDeliveryModal');
            if (modalEl) {
                const modal = new bootstrap.Modal(modalEl);
                modal.show();
            }
        } catch (error) {
            this.showToast('Failed to load farms: ' + error.message, 'error');
        }
    }

    async handleRecordDelivery() {
        try {
            const data = {
                farm_id: document.getElementById('deliveryFarm').value,
                quality_grade: document.getElementById('deliveryGrade').value,
                net_weight_kg: parseFloat(document.getElementById('deliveryWeight').value),
                moisture_content: parseFloat(document.getElementById('deliveryMoisture').value)
            };

            await api.recordDelivery(data);
            this.showToast('Delivery recorded successfully', 'success');
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

    async showGenerateDDSModal() {
        // Populate farm dropdown
        const farmSelect = document.getElementById('ddsFarmIds');
        try {
            const farms = await api.getFarms();
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
        const canVerify = ['COOPERATIVE_OFFICER', 'FACTOR', 'COOP_ADMIN', 'PLATFORM_ADMIN', 'SUPER_ADMIN', 'ADMIN', 'PLOTRA_ADMIN', 'EUDR_REVIEWER'].includes(role);

        content.innerHTML = `
            <div class="row g-4 mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h4 class="card-title">Pending Verifications</h4>
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>Farmer Name</th>
                                            <th>Cooperative</th>
                                            <th>Date Submitted</th>
                                            <th>Status</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody id="verifications-list">
                                        <tr><td colspan="6" class="text-center py-4">Loading pending verifications...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        if (!canVerify) {
            document.getElementById('verifications-list').innerHTML = '<tr><td colspan="6" class="text-center py-4 text-warning">You do not have permission to view this page.</td></tr>';
            return;
        }

        try {
            const verifications = await api.getPendingVerifications();
            const list = document.getElementById('verifications-list');
            
            if (verifications && verifications.length > 0) {
                list.innerHTML = verifications.map(v => `
                    <tr>
                        <td>
                            <div class="fw-bold">${v.farmer_name || 'N/A'}</div>
                            <div class="text-muted small">${v.farmer_email || ''}</div>
                        </td>
                        <td>${v.cooperative_name || v.cooperative_code || 'N/A'}</td>
                        <td>${new Date(v.created_at).toLocaleDateString()}</td>
                        <td><span class="badge bg-soft-warning text-warning">${v.status || 'Pending'}</span></td>
                        <td>
                            <div class="btn-group">
                                <button class="btn btn-sm btn-outline-success" onclick="app.approveVerification('${v.id}')">
                                    <i class="bi bi-check-lg"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-danger" onclick="app.rejectVerification('${v.id}')">
                                    <i class="bi bi-x-lg"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `).join('');
            } else {
                list.innerHTML = '<tr><td colspan="5" class="text-center py-4">No pending verifications found.</td></tr>';
            }
        } catch (error) {
            console.error(error);
            list.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-danger">Error: ${error.message}</td></tr>`;
        }
    }

    async approveVerification(id) {
        if (!confirm('Are you sure you want to approve this verification?')) return;
        try {
            await api.approveVerification(id, { comments: 'Approved via dashboard' });
            this.showToast('Verification approved successfully', 'success');
            this.loadPage('verification');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async rejectVerification(id) {
        const reason = prompt('Please enter the reason for rejection:');
        if (reason === null) return;
        try {
            await api.rejectVerification(id, reason || 'Rejected via dashboard');
            this.showToast('Verification rejected', 'warning');
            this.loadPage('verification');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
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
            const ddsList = await api.getDDSList();
            const list = document.getElementById('dds-list');
            
            if (ddsList.length > 0) {
                list.innerHTML = ddsList.map(dds => `
                    <tr>
                        <td><a href="#" onclick="app.viewDDS('${dds.dds_number}')">${dds.dds_number}</a></td>
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
            const farms = farmsResponse?.farms || [];
            const farmArray = Array.isArray(farms) ? farms : (farms ? [farms] : []);
            
            const parcelsData = [];
            for (const farm of farmArray) {
                const parcelsResp = await api.getParcels(farm.id);
                const parcels = parcelsResp?.parcels || parcelsResp || [];
                parcelsData.push({ farm, parcels: Array.isArray(parcels) ? parcels : [parcels] });
            }
            
            const status = this.getProfileCompletionStatus(user, farmArray);
            
            content.innerHTML = `
                ${!status.isComplete ? `
                <div class="alert alert-warning d-flex align-items-center mb-4" role="alert">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    <div>
                        <strong>Please complete your profile!</strong>
                        <p class="mb-0 small">
                            ${status.missingUserFields.length > 0 ? `Missing personal details: ${status.missingUserFields.join(', ')}` : ''}
                            ${status.farmComplete === 0 && status.totalFarms > 0 ? ' Please complete your farm details.' : ''}
                            ${status.totalFarms === 0 ? ' Please register your farm first.' : ''}
                        </p>
                    </div>
                </div>
                ` : `
                <div class="alert alert-success d-flex align-items-center mb-4" role="alert">
                    <i class="bi bi-check-circle-fill me-2"></i>
                    <div>
                        <strong>Profile Complete!</strong>
                        <p class="mb-0 small">Your profile is fully configured.</p>
                    </div>
                </div>
                `}
                
                <!-- Farm Details Section (Outer Container) -->
                <div class="row g-4 mb-4">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center bg-transparent">
                                <h4 class="card-title mb-0">
                                    <i class="bi bi-tree-fill me-2"></i>
                                    Farm Details
                                </h4>
                                <button class="btn btn-primary btn-sm" onclick="app.navigateTo('farms')">
                                    <i class="bi bi-plus-circle me-1"></i> Add Farm
                                </button>
                            </div>
                            <div class="card-body">
                                ${farmArray.length > 0 ? `
                                <div class="table-responsive mb-4">
                                    <table class="table table-hover">
                                        <thead>
                                            <tr>
                                                <th>Farm Name</th>
                                                <th>Area (Ha)</th>
                                                <th>Coffee Area</th>
                                                <th>Ownership</th>
                                                <th>Varieties</th>
                                                <th>Status</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${farmArray.map(f => `
                                            <tr>
                                                <td class="fw-bold">${f.farm_name || 'Unnamed Farm'}</td>
                                                <td>${f.total_area_hectares || '0'} ha</td>
                                                <td>${f.coffee_area_hectares || '0'} ha</td>
                                                <td><span class="badge bg-soft-info text-info">${f.ownership_type || 'Not set'}</span></td>
                                                <td>${(f.coffee_varieties || []).join(', ') || 'Not set'}</td>
                                                <td>
                                                    <span class="badge ${f.verification_status === 'certified' ? 'bg-soft-success text-success' : 'bg-soft-warning text-warning'}">
                                                        ${f.verification_status || 'Draft'}
                                                    </span>
                                                </td>
                                                <td>
                                                    <button class="btn btn-sm btn-outline-primary" onclick="app.editFarm('${f.id}')">
                                                        <i class="bi bi-pencil"></i>
                                                    </button>
                                                </td>
                                            </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                                ` : `
                                <div class="text-center py-4">
                                    <i class="bi bi-tree fs-1 text-muted"></i>
                                    <p class="text-muted mt-2">No farms registered yet.</p>
                                    <button class="btn btn-primary" onclick="app.navigateTo('farms')">
                                        <i class="bi bi-plus-circle me-1"></i> Register Your First Farm
                                    </button>
                                </div>
                                `}
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Section 1: Farmer Profile Details -->
                <div class="row g-4 mb-4">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header bg-transparent">
                                <h4 class="card-title mb-0">
                                    <i class="bi bi-person-badge me-2"></i>
                                    Farmer Details
                                </h4>
                            </div>
                            <div class="card-body">
                                <form id="farmerProfileForm">
                                    <div class="row g-3">
                                        <div class="col-md-6">
                                            <label class="form-label">Full Name</label>
                                            <input type="text" class="form-control" id="profileFullName" 
                                                value="${user?.full_name || user?.name || ''}" readonly>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Email</label>
                                            <input type="email" class="form-control" 
                                                value="${user?.email || ''}" readonly>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Phone Number <span class="text-danger">*</span></label>
                                            <input type="tel" class="form-control" id="profilePhone" 
                                                value="${user?.phone || ''}" placeholder="+254..." required>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">ID Number <span class="text-danger">*</span></label>
                                            <input type="text" class="form-control" id="profileIdNumber" 
                                                value="${user?.id_number || ''}" placeholder="National ID number" required>
                                        </div>
                                        <div class="col-md-4">
                                            <label class="form-label">Date of Birth</label>
                                            <input type="date" class="form-control" id="profileDob" 
                                                value="${user?.date_of_birth || ''}">
                                        </div>
                                        <div class="col-md-4">
                                            <label class="form-label">Gender</label>
                                            <select class="form-select" id="profileGender">
                                                <option value="">Select...</option>
                                                <option value="male" ${user?.gender === 'male' ? 'selected' : ''}>Male</option>
                                                <option value="female" ${user?.gender === 'female' ? 'selected' : ''}>Female</option>
                                            </select>
                                        </div>
                                        <div class="col-md-4">
                                            <label class="form-label">County</label>
                                            <input type="text" class="form-control" id="profileCounty" 
                                                value="${user?.county || ''}" placeholder="County">
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Sub-County</label>
                                            <input type="text" class="form-control" id="profileSubCounty" 
                                                value="${user?.subcounty || ''}">
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Ward</label>
                                            <input type="text" class="form-control" id="profileWard" 
                                                value="${user?.ward || ''}">
                                        </div>
                                        <div class="col-12">
                                            <label class="form-label">Physical Address</label>
                                            <textarea class="form-control" id="profileAddress" rows="2">${user?.address || ''}</textarea>
                                        </div>
                                        <div class="col-12 mt-4">
                                            <button type="submit" class="btn btn-primary">
                                                <i class="bi bi-save me-2"></i> Save Farmer Details
                                            </button>
                                        </div>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- EUDR Compliance Sections -->
                ${parcelsData.map(pd => pd.parcels.map((parcel, idx) => `
                <div class="row g-4 mb-4">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header bg-transparent">
                                <h4 class="card-title mb-0">
                                    <i class="bi bi-geo-alt me-2"></i>
                                    ${pd.farm?.farm_name || 'Farm'} - Parcel: ${parcel.parcel_name || parcel.parcel_number || 'Parcel ' + (idx + 1)}
                                </h4>
                            </div>
                            <div class="card-body">
                                <form id="parcelForm_${parcel.id}" class="parcel-eudr-form" data-parcel-id="${parcel.id}" data-farm-id="${pd.farm.id}">
                                    <!-- Section 1: Land & Parcel Information -->
                                    <h6 class="text-primary fw-bold mb-3 border-bottom pb-2">
                                        <i class="bi bi-map me-2"></i>1. Land & Parcel Information
                                    </h6>
                                    <div class="row g-3 mb-4">
                                        <div class="col-md-6">
                                            <label class="form-label">Parcel Name / ID</label>
                                            <input type="text" class="form-control" id="parcelName_${parcel.id}" 
                                                value="${parcel.parcel_name || ''}" placeholder="Farmer-assigned label for the plot">
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Total Parcel Area (ha)</label>
                                            <input type="number" class="form-control" id="parcelArea_${parcel.id}" 
                                                value="${parcel.area_hectares || ''}" step="0.01" placeholder="Auto-calculated from polygon">
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Land Ownership Type</label>
                                            <select class="form-select" id="ownershipType_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="owned" ${parcel.ownership_type === 'owned' ? 'selected' : ''}>Owned</option>
                                                <option value="leased" ${parcel.ownership_type === 'leased' ? 'selected' : ''}>Leased</option>
                                                <option value="customary" ${parcel.ownership_type === 'customary' ? 'selected' : ''}>Customary</option>
                                                <option value="inherited" ${parcel.ownership_type === 'inherited' ? 'selected' : ''}>Inherited</option>
                                                <option value="community" ${parcel.ownership_type === 'community' ? 'selected' : ''}>Community</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Land Registration Number</label>
                                            <input type="text" class="form-control" id="landRegNumber_${parcel.id}" 
                                                value="${parcel.land_registration_number || ''}" placeholder="Title deed or government-issued ID">
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Altitude (m above sea level)</label>
                                            <input type="number" class="form-control" id="altitude_${parcel.id}" 
                                                value="${parcel.altitude_meters || ''}" placeholder="Important for coffee quality">
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Soil Type</label>
                                            <select class="form-select" id="soilType_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="clay" ${parcel.soil_type === 'clay' ? 'selected' : ''}>Clay</option>
                                                <option value="loam" ${parcel.soil_type === 'loam' ? 'selected' : ''}>Loam</option>
                                                <option value="sandy" ${parcel.soil_type === 'sandy' ? 'selected' : ''}>Sandy</option>
                                                <option value="silt" ${parcel.soil_type === 'silt' ? 'selected' : ''}>Silt</option>
                                                <option value="unknown" ${parcel.soil_type === 'unknown' ? 'selected' : ''}>Unknown</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Terrain / Slope</label>
                                            <select class="form-select" id="terrainSlope_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="flat" ${parcel.terrain_slope === 'flat' ? 'selected' : ''}>Flat</option>
                                                <option value="gentle_slope" ${parcel.terrain_slope === 'gentle_slope' ? 'selected' : ''}>Gentle slope</option>
                                                <option value="moderate_slope" ${parcel.terrain_slope === 'moderate_slope' ? 'selected' : ''}>Moderate slope</option>
                                                <option value="steep" ${parcel.terrain_slope === 'steep' ? 'selected' : ''}>Steep</option>
                                            </select>
                                        </div>
                                    </div>
                                    
                                    <!-- Section 2: Coffee Farming Details -->
                                    <h6 class="text-primary fw-bold mb-3 border-bottom pb-2">
                                        <i class="bi bi-cup-hot me-2"></i>2. Coffee Farming Details
                                    </h6>
                                    <div class="row g-3 mb-4">
                                        <div class="col-md-6">
                                            <label class="form-label">Coffee Variety</label>
                                            <select class="form-select" id="coffeeVarieties_${parcel.id}" multiple>
                                                <option value="SL28" ${(parcel.coffee_varieties || []).includes('SL28') ? 'selected' : ''}>SL28</option>
                                                <option value="SL34" ${(parcel.coffee_varieties || []).includes('SL34') ? 'selected' : ''}>SL34</option>
                                                <option value="Ruiru_11" ${(parcel.coffee_varieties || []).includes('Ruiru_11') ? 'selected' : ''}>Ruiru 11</option>
                                                <option value="Batian" ${(parcel.coffee_varieties || []).includes('Batian') ? 'selected' : ''}>Batian</option>
                                                <option value="K7" ${(parcel.coffee_varieties || []).includes('K7') ? 'selected' : ''}>K7</option>
                                            </select>
                                            <small class="text-muted">Hold Ctrl/Cmd to select multiple</small>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Year Coffee First Planted</label>
                                            <input type="number" class="form-control" id="yearPlanted_${parcel.id}" 
                                                value="${parcel.year_coffee_first_planted || ''}" min="1900" max="2030" placeholder="Baseline for satellite validation">
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Estimated Coffee Plants</label>
                                            <input type="number" class="form-control" id="coffeePlants_${parcel.id}" 
                                                value="${parcel.estimated_coffee_plants || ''}" placeholder="Count of productive trees">
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Coffee Farm Status</label>
                                            <select class="form-select" id="farmStatus_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="active" ${parcel.farm_status === 'active' ? 'selected' : ''}>Active</option>
                                                <option value="rehabilitating" ${parcel.farm_status === 'rehabilitating' ? 'selected' : ''}>Rehabilitating</option>
                                                <option value="abandoned" ${parcel.farm_status === 'abandoned' ? 'selected' : ''}>Abandoned</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Planting Method</label>
                                            <select class="form-select" id="plantingMethod_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="monoculture" ${parcel.planting_method === 'monoculture' ? 'selected' : ''}>Monoculture</option>
                                                <option value="intercropped" ${parcel.planting_method === 'intercropped' ? 'selected' : ''}>Intercropped</option>
                                                <option value="agroforestry" ${parcel.planting_method === 'agroforestry' ? 'selected' : ''}>Agroforestry</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Irrigation Used</label>
                                            <select class="form-select" id="irrigation_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="none" ${parcel.irrigation_type === 'none' ? 'selected' : ''}>None</option>
                                                <option value="drip" ${parcel.irrigation_type === 'drip' ? 'selected' : ''}>Drip</option>
                                                <option value="furrow" ${parcel.irrigation_type === 'furrow' ? 'selected' : ''}>Furrow</option>
                                                <option value="rain_fed" ${parcel.irrigation_type === 'rain_fed' ? 'selected' : ''}>Rain-fed</option>
                                                <option value="sprinkler" ${parcel.irrigation_type === 'sprinkler' ? 'selected' : ''}>Sprinkler</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Coffee Area (ha)</label>
                                            <input type="number" class="form-control" id="coffeeArea_${parcel.id}" 
                                                value="${parcel.coffee_area_hectares || ''}" step="0.01" placeholder="Estimated Annual Yield">
                                        </div>
                                    </div>
                                    
                                    <!-- Section 3: Mixed Farming Declaration (EUDR Critical) -->
                                    <h6 class="text-danger fw-bold mb-3 border-bottom pb-2">
                                        <i class="bi bi-exclamation-triangle me-2"></i>3. Mixed Farming Declaration (EUDR Critical)
                                    </h6>
                                    <div class="row g-3 mb-4">
                                        <div class="col-md-6">
                                            <label class="form-label">Practice mixed farming on this parcel?</label>
                                            <select class="form-select" id="mixedFarming_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="1" ${parcel.practice_mixed_farming === 1 ? 'selected' : ''}>Yes</option>
                                                <option value="0" ${parcel.practice_mixed_farming === 0 ? 'selected' : ''}>No</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Other Crops Grown</label>
                                            <select class="form-select" id="otherCrops_${parcel.id}" multiple>
                                                <option value="maize" ${(parcel.other_crops || []).includes('maize') ? 'selected' : ''}>Maize</option>
                                                <option value="banana" ${(parcel.other_crops || []).includes('banana') ? 'selected' : ''}>Banana</option>
                                                <option value="beans" ${(parcel.other_crops || []).includes('beans') ? 'selected' : ''}>Beans</option>
                                                <option value="vegetables" ${(parcel.other_crops || []).includes('vegetables') ? 'selected' : ''}>Vegetables</option>
                                                <option value="other" ${(parcel.other_crops || []).includes('other') ? 'selected' : ''}>Other</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Livestock on Parcel?</label>
                                            <select class="form-select" id="livestock_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="1" ${parcel.livestock_on_parcel === 1 ? 'selected' : ''}>Yes</option>
                                                <option value="0" ${parcel.livestock_on_parcel === 0 ? 'selected' : ''}>No</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Livestock Type</label>
                                            <select class="form-select" id="livestockType_${parcel.id}" multiple>
                                                <option value="cattle" ${(parcel.livestock_type || []).includes('cattle') ? 'selected' : ''}>Cattle</option>
                                                <option value="goats" ${(parcel.livestock_type || []).includes('goats') ? 'selected' : ''}>Goats</option>
                                                <option value="poultry" ${(parcel.livestock_type || []).includes('poultry') ? 'selected' : ''}>Poultry</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">% of Parcel Under Coffee</label>
                                            <input type="number" class="form-control" id="coffeePercent_${parcel.id}" 
                                                value="${parcel.coffee_percentage || ''}" min="0" max="100" placeholder="e.g., 60%">
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Crop Rotation Practiced?</label>
                                            <select class="form-select" id="cropRotation_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="1" ${parcel.crop_rotation_practiced === 1 ? 'selected' : ''}>Yes</option>
                                                <option value="0" ${parcel.crop_rotation_practiced === 0 ? 'selected' : ''}>No</option>
                                            </select>
                                        </div>
                                    </div>
                                    
                                    <!-- Section 4: Tree Cover & Deforestation Declaration (EUDR Critical) -->
                                    <h6 class="text-danger fw-bold mb-3 border-bottom pb-2">
                                        <i class="bi bi-tree me-2"></i>4. Tree Cover & Deforestation Declaration (EUDR Critical)
                                    </h6>
                                    <div class="row g-3 mb-4">
                                        <div class="col-md-6">
                                            <label class="form-label">Trees planted in last 5 years?</label>
                                            <select class="form-select" id="treesPlanted_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="1" ${parcel.trees_planted_last_5_years === 1 ? 'selected' : ''}>Yes</option>
                                                <option value="0" ${parcel.trees_planted_last_5_years === 0 ? 'selected' : ''}>No</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Tree Species Planted</label>
                                            <select class="form-select" id="treeSpecies_${parcel.id}" multiple>
                                                <option value="grevillea" ${(parcel.tree_species_planted || []).includes('grevillea') ? 'selected' : ''}>Grevillea</option>
                                                <option value="macadamia" ${(parcel.tree_species_planted || []).includes('macadamia') ? 'selected' : ''}>Macadamia</option>
                                                <option value="eucalyptus" ${(parcel.tree_species_planted || []).includes('eucalyptus') ? 'selected' : ''}>Eucalyptus</option>
                                                <option value="indigenous" ${(parcel.tree_species_planted || []).includes('indigenous') ? 'selected' : ''}>Indigenous</option>
                                                <option value="other" ${(parcel.tree_species_planted || []).includes('other') ? 'selected' : ''}>Other</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Number of Trees Planted</label>
                                            <input type="number" class="form-control" id="treesCount_${parcel.id}" 
                                                value="${parcel.trees_planted_count || ''}" placeholder="Approximate count">
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Reason for Planting</label>
                                            <select class="form-select" id="plantingReason_${parcel.id}" multiple>
                                                <option value="shade" ${(parcel.reason_for_planting || []).includes('shade') ? 'selected' : ''}>Shade</option>
                                                <option value="windbreak" ${(parcel.reason_for_planting || []).includes('windbreak') ? 'selected' : ''}>Windbreak</option>
                                                <option value="timber" ${(parcel.reason_for_planting || []).includes('timber') ? 'selected' : ''}>Timber</option>
                                                <option value="soil_health" ${(parcel.reason_for_planting || []).includes('soil_health') ? 'selected' : ''}>Soil health</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label text-danger">Trees cleared in last 5 years?</label>
                                            <select class="form-select border-danger" id="treesCleared_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="1" ${parcel.trees_cleared_last_5_years === 1 ? 'selected' : ''}>Yes</option>
                                                <option value="0" ${parcel.trees_cleared_last_5_years === 0 ? 'selected' : ''}>No</option>
                                            </select>
                                            <small class="text-danger">HIGH EUDR risk flag — triggers review</small>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Reason for Clearing</label>
                                            <select class="form-select" id="clearingReason_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="expanding_farmland" ${(parcel.reason_for_clearing || []).includes('expanding_farmland') ? 'selected' : ''}>Expanding farmland</option>
                                                <option value="disease" ${(parcel.reason_for_clearing || []).includes('disease') ? 'selected' : ''}>Disease</option>
                                                <option value="construction" ${(parcel.reason_for_clearing || []).includes('construction') ? 'selected' : ''}>Construction</option>
                                                <option value="other" ${(parcel.reason_for_clearing || []).includes('other') ? 'selected' : ''}>Other</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Current Tree Canopy Cover</label>
                                            <select class="form-select" id="canopyCover_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="none" ${parcel.canopy_cover === 'none' ? 'selected' : ''}>None</option>
                                                <option value="very_low" ${parcel.canopy_cover === 'very_low' ? 'selected' : ''}>&lt;10%</option>
                                                <option value="low" ${parcel.canopy_cover === 'low' ? 'selected' : ''}>10–30%</option>
                                                <option value="moderate" ${parcel.canopy_cover === 'moderate' ? 'selected' : ''}>30–50%</option>
                                                <option value="high" ${parcel.canopy_cover === 'high' ? 'selected' : ''}>&gt;50%</option>
                                            </select>
                                        </div>
                                    </div>
                                    
                                    <!-- Section 5: Satellite Verification Consent -->
                                    <h6 class="text-primary fw-bold mb-3 border-bottom pb-2">
                                        <i class="bi bi-satellite me-2"></i>5. Satellite Verification Consent
                                    </h6>
                                    <div class="row g-3 mb-4">
                                        <div class="col-md-6">
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" id="consentSatellite_${parcel.id}" 
                                                    ${parcel.consent_satellite_monitoring === 1 ? 'checked' : ''}>
                                                <label class="form-check-label" for="consentSatellite_${parcel.id}">
                                                    Consent to Parcel Satellite Monitoring
                                                </label>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" id="consentHistorical_${parcel.id}" 
                                                    ${parcel.consent_historical_imagery === 1 ? 'checked' : ''}>
                                                <label class="form-check-label" for="consentHistorical_${parcel.id}">
                                                    Consent to Historical Imagery (2020–present)
                                                </label>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Preferred Monitoring Frequency</label>
                                            <select class="form-select" id="monitorFreq_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="monthly" ${parcel.monitoring_frequency === 'monthly' ? 'selected' : ''}>Monthly</option>
                                                <option value="quarterly" ${parcel.monitoring_frequency === 'quarterly' ? 'selected' : ''}>Quarterly</option>
                                                <option value="annually" ${parcel.monitoring_frequency === 'annually' ? 'selected' : ''}>Annually</option>
                                            </select>
                                        </div>
                                    </div>
                                    
                                    <!-- Section 6: Certifications & Compliance History -->
                                    <h6 class="text-primary fw-bold mb-3 border-bottom pb-2">
                                        <i class="bi bi-award me-2"></i>6. Certifications & Compliance History
                                    </h6>
                                    <div class="row g-3 mb-4">
                                        <div class="col-md-6">
                                            <label class="form-label">Existing Certifications</label>
                                            <select class="form-select" id="certifications_${parcel.id}" multiple>
                                                <option value="fairtrade" ${(parcel.certifications || []).includes('fairtrade') ? 'selected' : ''}>Fairtrade</option>
                                                <option value="rainforest_alliance" ${(parcel.certifications || []).includes('rainforest_alliance') ? 'selected' : ''}>Rainforest Alliance</option>
                                                <option value="organic" ${(parcel.certifications || []).includes('organic') ? 'selected' : ''}>Organic</option>
                                                <option value="utz" ${(parcel.certifications || []).includes('utz') ? 'selected' : ''}>UTZ</option>
                                                <option value="none" ${(parcel.certifications || []).includes('none') ? 'selected' : ''}>None</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Certificate Expiry Date</label>
                                            <input type="date" class="form-control" id="certExpiry_${parcel.id}" 
                                                value="${parcel.certificate_expiry_date ? new Date(parcel.certificate_expiry_date).toISOString().split('T')[0] : ''}">
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Previously Flagged for Violations?</label>
                                            <select class="form-select" id="previouslyFlagged_${parcel.id}">
                                                <option value="">Select...</option>
                                                <option value="1" ${parcel.previously_flagged === 1 ? 'selected' : ''}>Yes</option>
                                                <option value="0" ${parcel.previously_flagged === 0 ? 'selected' : ''}>No</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Cooperative Registration Number</label>
                                            <input type="text" class="form-control" id="coopRegNum_${parcel.id}" 
                                                value="${parcel.cooperative_registration_number || ''}">
                                        </div>
                                    </div>
                                    
                                    <div class="col-12 mt-3">
                                        <button type="button" class="btn btn-primary" onclick="app.saveParcelEUDR(${parcel.id}, ${pd.farm.id})">
                                            <i class="bi bi-save me-2"></i> Save Parcel Details
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
                `).join('')).join('')}
            `;
            
            // Handle farmer profile form submission
            document.getElementById('farmerProfileForm')?.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = {
                    phone: document.getElementById('profilePhone').value,
                    id_number: document.getElementById('profileIdNumber').value,
                    date_of_birth: document.getElementById('profileDob').value,
                    gender: document.getElementById('profileGender').value,
                    county: document.getElementById('profileCounty').value,
                    subcounty: document.getElementById('profileSubCounty').value,
                    ward: document.getElementById('profileWard').value,
                    address: document.getElementById('profileAddress').value
                };
                
                try {
                    await api.updateProfile(formData);
                    this.showToast('Farmer details saved successfully!', 'success');
                    this.loadProfile(content);
                } catch (error) {
                    this.showToast(error.message, 'error');
                }
            });
            
        } catch (error) {
            console.error(error);
            content.innerHTML = `<div class="alert alert-danger">Error loading profile: ${error.message}</div>`;
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

    showAddFarmModal() {
        const modalEl = document.getElementById('addFarmModal');
        if (modalEl) {
            const form = document.getElementById('addFarmForm');
            if (form) form.reset();
            
            // Initialize farm map and GPS capture
            this.initFarmMap();
            this.initGPSCapture();
            
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
        }
    }

    async loadSystemConfig(content) {
        try {
            const [requiredDocs, sessionTimeout] = await Promise.all([
                api.getRequiredDocuments(),
                api.getSessionTimeout()
            ]);
            
            const documents = requiredDocs || [];
            const timeoutMinutes = sessionTimeout?.timeout_minutes || 30;
            
            content.innerHTML = `
                <div class="row g-4">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header">
                                <h4 class="card-title">System Configuration</h4>
                            </div>
                            <div class="card-body">
                                <ul class="nav nav-tabs" id="systemConfigTabs" role="tablist">
                                    <li class="nav-item">
                                        <button class="nav-link active" id="docs-tab" data-bs-toggle="tab" data-bs-target="#requiredDocs" type="button">
                                            Required Documents
                                        </button>
                                    </li>
                                    <li class="nav-item">
                                        <button class="nav-link" id="session-tab" data-bs-toggle="tab" data-bs-target="#sessionSettings" type="button">
                                            Session Settings
                                        </button>
                                    </li>
                                    <li class="nav-item">
                                        <button class="nav-link" id="creds-tab" data-bs-toggle="tab" data-bs-target="#envCredentials" type="button">
                                            Environment Credentials
                                        </button>
                                    </li>
                                </ul>
                                <div class="tab-content mt-4" id="systemConfigTabsContent">
                                    <div class="tab-pane fade show active" id="requiredDocs" role="tabpanel">
                                        <div class="d-flex justify-content-between align-items-center mb-3">
                                            <h5>Required Documents</h5>
                                            <button class="btn btn-primary btn-sm" onclick="app.showAddRequiredDocModal()">
                                                <i class="bi bi-plus-lg me-1"></i> Add Document
                                            </button>
                                        </div>
                                        <p class="text-muted small mb-3">Documents that cooperatives must submit when registering.</p>
                                        <div class="table-responsive">
                                            <table class="table table-hover">
                                                <thead>
                                                    <tr>
                                                        <th>Name</th>
                                                        <th>Display Name</th>
                                                        <th>Description</th>
                                                        <th>Required</th>
                                                        <th>Actions</th>
                                                    </tr>
                                                </thead>
                                                <tbody id="requiredDocsList">
                                                    ${documents.length > 0 ? documents.map(doc => `
                                                        <tr>
                                                            <td>${doc.name || ''}</td>
                                                            <td>${doc.display_name || ''}</td>
                                                            <td>${doc.description || '-'}</td>
                                                            <td>${doc.is_required ? '<span class="badge bg-success">Yes</span>' : '<span class="badge bg-secondary">No</span>'}</td>
                                                            <td>
                                                                <button class="btn btn-sm btn-danger" onclick="app.deleteRequiredDocument('${doc.id}')">
                                                                    <i class="bi bi-trash"></i>
                                                                </button>
                                                            </td>
                                                        </tr>
                                                    `).join('') : '<tr><td colspan="5" class="text-center text-muted">No required documents configured</td></tr>'}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                    <div class="tab-pane fade" id="sessionSettings" role="tabpanel">
                                        <h5>Session Settings</h5>
                                        <div class="row mt-3">
                                            <div class="col-md-6">
                                                <label class="form-label">Session Timeout (minutes)</label>
                                                <div class="input-group">
                                                    <input type="number" class="form-control" id="sessionTimeoutInput" value="${timeoutMinutes}" min="5" max="1440">
                                                    <button class="btn btn-primary" onclick="app.updateSessionTimeout()">Save</button>
                                                </div>
                                                <small class="text-muted">Value between 5 and 1440 minutes (24 hours)</small>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="tab-pane fade" id="envCredentials" role="tabpanel">
                                        <h5>Environment Credentials</h5>
                                        <p class="text-muted small mb-3">Store API keys and credentials securely.</p>
                                        <div class="row mt-3">
                                            <div class="col-md-4">
                                                <input type="text" class="form-control" id="credKey" placeholder="Key name">
                                            </div>
                                            <div class="col-md-4">
                                                <input type="password" class="form-control" id="credValue" placeholder="Value">
                                            </div>
                                            <div class="col-md-2">
                                                <button class="btn btn-primary w-100" onclick="app.addEnvCredential()">Add</button>
                                            </div>
                                        </div>
                                        <div class="mt-3" id="credentialsList"></div>
                                    </div>
                                </div>
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

    async showAddRequiredDocModal() {
        const html = `
            <div class="modal fade" id="addRequiredDocModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Add Required Document</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
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

        // Check if map already exists
        if (this.farmMap) {
            return; // Map already initialized
        }

        try {
            // Initialize Leaflet map
            this.farmMap = L.map('farmMap').setView([-0.0236, 37.9062], 13);
            
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(this.farmMap);

            // Initialize polygon layer
            this.farmPolygon = L.polygon([], {
                color: '#2563eb',
                fillColor: '#dbeafe',
                fillOpacity: 0.5
            }).addTo(this.farmMap);

            // Initialize GPS accuracy circle
            this.accuracyCircle = L.circle([0, 0], {
                radius: 0,
                color: '#10b981',
                fillColor: '#d1fae5',
                fillOpacity: 0.3
            }).addTo(this.farmMap);

            // Initialize marker for current location
            this.currentLocationMarker = L.marker([0, 0], {
                icon: L.divIcon({
                    className: 'current-location-marker',
                    html: '<div style="background-color: #2563eb; color: white; padding: 8px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 10px rgba(0,0,0,0.3);">📍</div>',
                    iconSize: [40, 40]
                })
            }).addTo(this.farmMap);
        } catch (error) {
            console.error('Map initialization error:', error);
            // If map initialization fails, try to clean up and re-initialize
            if (this.farmMap) {
                try {
                    this.farmMap.remove();
                } catch (removeError) {
                    console.error('Map removal error:', removeError);
                }
                this.farmMap = null;
            }
            // Clear map container
            mapDiv.innerHTML = '';
            // Try again
            this.initFarmMap();
        }
    }

    initGPSCapture() {
        this.gpsPoints = [];
        this.isCapturing = false;
        this.watchId = null;

        // Add event listeners
        const startBtn = document.getElementById('startCaptureBtn');
        const addPointBtn = document.getElementById('addPointBtn');
        const finishBtn = document.getElementById('finishCaptureBtn');
        const clearBtn = document.getElementById('clearPointsBtn');

        if (startBtn) startBtn.addEventListener('click', () => this.startGPSCapture());
        if (addPointBtn) addPointBtn.addEventListener('click', () => this.addGPSPoint());
        if (finishBtn) finishBtn.addEventListener('click', () => this.finishGPSCapture());
        if (clearBtn) clearBtn.addEventListener('click', () => this.clearGPSPoints());
    }

    startGPSCapture() {
        if (!navigator.geolocation) {
            this.showToast('GPS not available on this device', 'error');
            return;
        }

        this.isCapturing = true;
        this.gpsPoints = [];
        
        // Update UI
        document.getElementById('startCaptureBtn').disabled = true;
        document.getElementById('addPointBtn').disabled = false;
        document.getElementById('finishCaptureBtn').disabled = true;
        document.getElementById('clearPointsBtn').disabled = true;
        document.getElementById('captureInstructions').textContent = 'Walking around the farm boundary... Click "Add Point" at each corner.';

        // Start watching GPS position
        this.watchId = navigator.geolocation.watchPosition(
            (position) => this.handleGPSUpdate(position),
            (error) => this.handleGPSError(error),
            {
                enableHighAccuracy: true,
                maximumAge: 1000,
                timeout: 10000
            }
        );
    }

    handleGPSUpdate(position) {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        const accuracy = position.coords.accuracy;

        // Update accuracy display
        document.getElementById('gpsAccuracy').textContent = accuracy.toFixed(1);

        // Update current location marker
        this.currentLocationMarker.setLatLng([lat, lon]);
        this.accuracyCircle.setLatLng([lat, lon]).setRadius(accuracy);

        // Center map on current location
        if (this.farmMap) {
            this.farmMap.setView([lat, lon], 16);
        }

        // Store last known position
        this.lastKnownPosition = { lat, lon, accuracy };
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
            const hectares = (area / 10000).toFixed(2);
            document.getElementById('farmArea').value = hectares;
        }
    }

    calculatePolygonArea(coordinates) {
        // Shoelace formula for polygon area calculation
        let area = 0;
        const n = coordinates.length;

        for (let i = 0; i < n; i++) {
            const j = (i + 1) % n;
            const xi = coordinates[i][0];
            const yi = coordinates[i][1];
            const xj = coordinates[j][0];
            const yj = coordinates[j][1];
            area += (xi * yj) - (xj * yi);
        }

        return Math.abs(area) * 111319.9 * 111319.9; // Convert to square meters (approximate)
    }

    finishGPSCapture() {
        this.stopGPSCapture();

        // Close polygon by adding first point at end
        if (this.gpsPoints.length > 2) {
            const firstPoint = this.gpsPoints[0];
            this.gpsPoints.push({
                ...firstPoint,
                timestamp: Date.now()
            });
            this.updateFarmPolygon();
        }

        // Update UI
        document.getElementById('startCaptureBtn').disabled = false;
        document.getElementById('addPointBtn').disabled = true;
        document.getElementById('finishCaptureBtn').disabled = true;
        document.getElementById('clearPointsBtn').disabled = false;
        document.getElementById('captureInstructions').textContent = 'Capture complete! You can clear and re-capture if needed.';
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
        
        // Reset UI
        document.getElementById('pointCount').textContent = '0';
        document.getElementById('gpsAccuracy').textContent = '--';
        document.getElementById('farmArea').value = '';
        document.getElementById('startCaptureBtn').disabled = false;
        document.getElementById('addPointBtn').disabled = true;
        document.getElementById('finishCaptureBtn').disabled = true;
        document.getElementById('clearPointsBtn').disabled = true;
        document.getElementById('captureInstructions').textContent = 'Click "Start Capture" to begin mapping your farm boundary. Walk around the perimeter and click "Add Point" at each corner.';

        // Clear map
        if (this.farmPolygon) {
            this.farmPolygon.setLatLngs([]);
        }
    }

    async handleCreateFarm() {
        try {
            const varietiesStr = document.getElementById('farmVarieties').value || '';
            
            // Validate farm boundary if GPS capture was used
            if (this.gpsPoints && this.gpsPoints.length > 3) {
                // Create GeoJSON polygon from GPS points
                const polygonCoords = this.gpsPoints.map(point => [point.lon, point.lat]);
                
                const data = {
                    farm_name: document.getElementById('farmName').value,
                    total_area_hectares: parseFloat(document.getElementById('farmArea').value),
                    coffee_varieties: varietiesStr ? varietiesStr.split(',').map(v => v.trim()) : [],
                    years_farming: parseInt(document.getElementById('farmYears').value) || null,
                    average_annual_production_kg: parseFloat(document.getElementById('farmProduction').value) || null,
                    centroid_lat: this.gpsPoints.reduce((sum, point) => sum + point.lat, 0) / this.gpsPoints.length,
                    centroid_lon: this.gpsPoints.reduce((sum, point) => sum + point.lon, 0) / this.gpsPoints.length,
                    parcels: [
                        {
                            parcel_number: 1,
                            parcel_name: 'Main Parcel',
                            boundary_geojson: {
                                type: 'Polygon',
                                coordinates: [polygonCoords]
                            },
                            area_hectares: parseFloat(document.getElementById('farmArea').value),
                            gps_accuracy_meters: Math.max(...this.gpsPoints.map(point => point.accuracy)),
                            mapping_device: 'GPS',
                            land_use_type: 'agroforestry'
                        }
                    ]
                };

                if (!data.farm_name) {
                    this.showToast('Farm name is required', 'error');
                    return;
                }

                await api.createFarm(data);
                this.showToast('Farm created successfully', 'success');
                const modal = bootstrap.Modal.getInstance(document.getElementById('addFarmModal'));
                if (modal) modal.hide();
                
                if (this.currentPage === 'farms') {
                    this.loadPage('farms');
                }
            } else {
                // Fallback to manual entry if no GPS boundary captured
                const data = {
                    farm_name: document.getElementById('farmName').value,
                    total_area_hectares: parseFloat(document.getElementById('farmArea').value),
                    coffee_varieties: varietiesStr ? varietiesStr.split(',').map(v => v.trim()) : [],
                    years_farming: parseInt(document.getElementById('farmYears').value) || null,
                    average_annual_production_kg: parseFloat(document.getElementById('farmProduction').value) || null,
                    centroid_lat: null,
                    centroid_lon: null,
                    parcels: []
                };

                if (!data.farm_name) {
                    this.showToast('Farm name is required', 'error');
                    return;
                }

                await api.createFarm(data);
                this.showToast('Farm created successfully', 'success');
                const modal = bootstrap.Modal.getInstance(document.getElementById('addFarmModal'));
                if (modal) modal.hide();
                
                if (this.currentPage === 'farms') {
                    this.loadPage('farms');
                }
            }
        } catch (error) {
            console.error('Failed to create farm:', error);
            this.showToast(error.message || 'Failed to create farm', 'error');
        }
    }

    showCreateCooperativeModal() {
        const modalEl = document.getElementById('addCooperativeModal');
        if (modalEl) {
            const form = document.getElementById('addCooperativeForm');
            if (form) form.reset();
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
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
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
        try {
            const selectedDocs = [];
            document.querySelectorAll('#coopRequiredDocsList input[type="checkbox"]:checked').forEach(cb => {
                selectedDocs.push(cb.value);
            });
            
            const data = {
                name: document.getElementById('coopName').value,
                registration_number: document.getElementById('coopRegNumber').value || null,
                cooperative_type: document.getElementById('coopType').value || null,
                email: document.getElementById('coopEmail').value || null,
                phone: document.getElementById('coopPhone').value || null,
                address: document.getElementById('coopAddress').value || null,
                county: document.getElementById('coopCounty').value || null,
                district: document.getElementById('coopDistrict').value || null,
                subcounty: document.getElementById('coopSubcounty').value || null,
                ward: document.getElementById('coopWard').value || null,
                admin_email: document.getElementById('coopAdminEmail').value,
                admin_first_name: document.getElementById('coopAdminFirstName').value || null,
                admin_last_name: document.getElementById('coopAdminLastName').value || null,
                admin_phone: document.getElementById('coopAdminPhone').value || null,
                required_documents: selectedDocs
            };

            if (!data.name || !data.admin_email) {
                this.showToast('Cooperative name and admin email are required', 'error');
                return;
            }

            const response = await api.createCooperative(data);
            if (response) {
                this.showToast('Cooperative created successfully', 'success');
                const modalEl = document.getElementById('addCooperativeModal');
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
                
                // Refresh the cooperatives list if we are on that page
                if (this.currentPage === 'cooperatives') {
                    this.loadPage('cooperatives');
                }
            }
        } catch (error) {
            console.error('Failed to create cooperative:', error);
            this.showToast(error.message || 'Failed to create cooperative', 'error');
        }
    }

    async loadCooperativeRequiredDocs() {
        const listDiv = document.getElementById('coopRequiredDocsList');
        if (!listDiv) return;
        
        try {
            const docs = await api.getRequiredDocuments();
            
            if (!docs || docs.length === 0) {
                listDiv.innerHTML = '<div class="col-12 text-muted">No required documents configured</div>';
                return;
            }
            
            listDiv.innerHTML = docs.map(doc => `
                <div class="col-md-6">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="coopDoc_${doc.id}" value="${doc.id}" ${doc.is_required ? 'checked' : ''}>
                        <label class="form-check-label" for="coopDoc_${doc.id}">
                            ${doc.display_name}
                            ${doc.is_required ? '<span class="badge bg-warning text-dark ms-1">Required</span>' : ''}
                        </label>
                    </div>
                    ${doc.description ? `<small class="text-muted d-block">${doc.description}</small>` : ''}
                </div>
            `).join('');
        } catch (error) {
            console.error('Error loading required docs:', error);
            listDiv.innerHTML = '<div class="col-12 text-muted">Error loading documents</div>';
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
        this.currentPolygon = null;
        this.gpsWatchId = null;
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

        // Form submission
        document.getElementById('addFarmForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitFarm();
        });
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

    startGPSCapture() {
        this.captureMode = true;
        this.capturedPoints = [];

        document.getElementById('startCaptureBtn').disabled = true;
        document.getElementById('addPointBtn').disabled = false;
        document.getElementById('clearPointsBtn').disabled = false;
        document.getElementById('captureInstructions').textContent =
            'Walk to the first corner of your farm and click "Add Point". Continue around the perimeter.';

        this.showToast('GPS capture started. Walk to your farm boundary and add points.', 'info');
    }

    addGPSPoint() {
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
                total_area_hectares: parseFloat(formData.get('farmArea')),
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
                    area_hectares: parseFloat(formData.get('farmArea')),
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
            this.loadFarms(); // Refresh farm list

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
            <div class="modal fade" id="treeDetailsModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-tree me-2"></i>Add Tree</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
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

    async requestSatelliteAnalysis(farmId, parcelIds = null) {
        try {
            this.showToast('Requesting satellite analysis...', 'info');

            const result = await api.request(`/farmer/farm/${farmId}/satellite-analysis`, {
                method: 'POST',
                body: JSON.stringify({
                    parcel_ids: parcelIds,
                    acquisition_date: new Date().toISOString()
                })
            });

            this.showToast('Satellite analysis completed!', 'success');

            // Store historical analysis data
            if (result.results && result.results.length > 0) {
                await this.storeHistoricalAnalysis(farmId, result.results);
            }

            // Refresh data
            this.loadSatelliteAnalysis(farmId);

        } catch (error) {
            this.showToast(`Satellite analysis failed: ${error.message}`, 'error');
        }
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
                        satellite_source: result.satellite_source || 'SIMULATION',
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
            case 'farms':
                await this.loadFarmsPage();
                break;
            case 'cooperatives':
                await this.loadCooperatives(pageContent);
                break;
            case 'farmers':
                await this.loadFarmers(pageContent);
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
                            <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addFarmModal">
                                <i class="bi bi-plus-circle me-1"></i>Add Farm
                            </button>
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

                <!-- Historical Analysis -->
                <div class="col-12">
                    <div class="card border-0 shadow-sm">
                        <div class="card-header bg-light d-flex justify-content-between align-items-center">
                            <h6 class="mb-0">Historical Analysis</h6>
                            <div class="btn-group btn-group-sm">
                                <select class="form-select form-select-sm" id="historyYearFilter" style="width: auto;">
                                    <option value="">All Years</option>
                                    <option value="2024">2024</option>
                                    <option value="2023">2023</option>
                                    <option value="2022">2022</option>
                                    <option value="2021">2021</option>
                                </select>
                            </div>
                        </div>
                        <div class="card-body">
                            <div id="historicalAnalysis">
                                <div class="text-center py-3">
                                    <div class="spinner-border spinner-border-sm" role="status"></div>
                                    <span class="ms-2">Loading historical data...</span>
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
                                    <div class="text-center py-3">
                                        <div class="spinner-border spinner-border-sm" role="status"></div>
                                        <span class="ms-2">Loading agroforestry data...</span>
                                    </div>
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
                                    <div class="text-center py-3">
                                        <div class="spinner-border spinner-border-sm" role="status"></div>
                                        <span class="ms-2">Loading crop analysis...</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Farm Details Modal -->
            <div class="modal fade" id="farmDetailsModal" tabindex="-1">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-geo-alt me-2"></i>Farm Details</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
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

        await this.loadFarms();
    }

    async loadFarms() {
        try {
            const farms = await api.getFarms();
            const farmsList = document.getElementById('farmCalculations');
            if (!farmsList) {
                console.warn('Farm calculations container not found');
                return;
            }
            if (!farms || farms.length === 0) {
                farmsList.innerHTML = '<div class="col-12 text-center py-5"><i class="bi bi-geo-alt fs-1 text-muted"></i><h5 class="text-muted mt-2">No farms found</h5><p class="text-muted">Create your first farm to get started with satellite monitoring.</p></div>';
            } else {
                farmsList.innerHTML = farms.map(farm => '<div class="col-md-6 col-lg-4"><div class="card border-0 shadow-sm h-100"><div class="card-body d-flex flex-column"><h6 class="card-title mb-0">' + (farm.farm_name || 'Unnamed Farm') + '</h6></div></div></div>').join('');
            }
        } catch (error) {
            console.error('Error loading farms:', error);
            const farmsList = document.getElementById('farmCalculations');
            if (farmsList) {
                farmsList.innerHTML = '<div class="col-12 text-center py-5 text-danger"><i class="bi bi-exclamation-triangle fs-1"></i><p class="mt-2">Error loading farms</p><small>' + error.message + '</small></div>';
            }
        }
    }

    async viewFarmDetails(farmId) {
        try {
            const farm = await api.getFarm(farmId);
            const parcels = await api.getParcels(farmId);

            const modal = new bootstrap.Modal(document.getElementById('farmDetailsModal'));
            const content = document.getElementById('farmDetailsContent');

            content.innerHTML = `
                <div class="row g-3">
                    <!-- Farm Overview -->
                    <div class="col-12">
                        <div class="card border-0 shadow-sm">
                            <div class="card-header bg-light">
                                <h6 class="mb-0">Farm Overview</h6>
                            </div>
                            <div class="card-body">
                                <div class="row g-3">
                                    <div class="col-md-6">
                                        <strong>Name:</strong> ${farm.farm_name || 'Unnamed'}
                                    </div>
                                    <div class="col-md-6">
                                        <strong>Total Area:</strong> ${farm.total_area_hectares || 0} hectares
                                    </div>
                                    <div class="col-md-6">
                                        <strong>Coffee Area:</strong> ${farm.coffee_area_hectares || 0} hectares
                                    </div>
                                    <div class="col-md-6">
                                        <strong>Compliance Status:</strong>
                                        <span class="badge bg-${farm.compliance_status === 'Compliant' ? 'success' :
                                            farm.compliance_status === 'Under Review' ? 'warning' : 'secondary'} ms-2">
                                            ${farm.compliance_status || 'Unknown'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Calculations -->
                    <div class="col-12">
                        <div id="farmCalculations">
                            <div class="text-center py-3">
                                <div class="spinner-border spinner-border-sm" role="status"></div>
                                <span class="ms-2">Loading calculations...</span>
                            </div>
                        </div>
                    </div>

                    <!-- Satellite History -->
                    <div class="col-12">
                        <div id="satelliteHistory">
                            <div class="text-center py-3">
                                <div class="spinner-border spinner-border-sm" role="status"></div>
                                <span class="ms-2">Loading satellite history...</span>
                            </div>
                        </div>
                    </div>

                    <!-- Satellite Imagery -->
                    <div class="col-12">
                        <div id="satelliteImagery">
                            <div class="text-center py-3">
                                <div class="spinner-border spinner-border-sm" role="status"></div>
                                <span class="ms-2">Loading satellite imagery controls...</span>
                            </div>
                        </div>
                    </div>

                    <!-- Parcels -->
                    <div class="col-12">
                        <div class="card border-0 shadow-sm">
                            <div class="card-header bg-light">
                                <h6 class="mb-0">Parcels (${parcels ? parcels.length : 0})</h6>
                            </div>
                            <div class="card-body">
                                ${parcels && parcels.length > 0 ? `
                                    <div class="table-responsive">
                                        <table class="table table-sm">
                                            <thead>
                                                <tr>
                                                    <th>Parcel #</th>
                                                    <th>Name</th>
                                                    <th>Area (ha)</th>
                                                    <th>Land Use</th>
                                                    <th>NDVI</th>
                                                    <th>Status</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                ${parcels.map(parcel => `
                                                    <tr>
                                                        <td>${parcel.parcel_number}</td>
                                                        <td>${parcel.parcel_name || '-'}</td>
                                                        <td>${parcel.area_hectares || 0}</td>
                                                        <td>${parcel.land_use_type || '-'}</td>
                                                        <td>${parcel.ndvi_baseline ? parcel.ndvi_baseline.toFixed(3) : '-'}</td>
                                                        <td>
                                                            <span class="badge bg-${parcel.verification_status === 'certified' ? 'success' :
                                                                parcel.verification_status === 'submitted' ? 'warning' : 'secondary'}">
                                                                ${parcel.verification_status || 'draft'}
                                                            </span>
                                                        </td>
                                                    </tr>
                                                `).join('')}
                                            </tbody>
                                        </table>
                                    </div>
                                ` : '<p class="text-muted mb-0">No parcels found</p>'}
                            </div>
                        </div>
                    </div>
                </div>
            `;

            modal.show();

            // Load satellite analysis data
            this.loadSatelliteAnalysis(farmId);

            // Load historical analysis
            this.loadHistoricalAnalysis(farmId);

            // Load tree management data
            this.loadTreeManagement(farmId);

            // Load crop analysis data
            this.loadCropAnalysis(farmId);

        } catch (error) {
            console.error('Error loading farm details:', error);
            this.showToast('Error loading farm details', 'error');
        }
    }

    async loadCropAnalysis(farmId) {
        try {
            const container = document.getElementById('cropAnalysis');
            if (!container) return;

            // Get latest satellite analysis which includes crop differentiation
            const parcels = await api.getParcels(farmId);
            let cropAnalysisData = [];

            for (const parcel of parcels) {
                try {
                    // Get parcel crops
                    const crops = await api.getParcelCrops(farmId, parcel.id);

                    for (const crop of crops) {
                        // Get individual crop analysis if available
                        try {
                            const analysis = await api.analyzeCropHealth(farmId, parcel.id, crop.id);
                            cropAnalysisData.push({
                                parcel_name: `Parcel ${parcel.parcel_number}`,
                                crop_type: crop.crop_type?.name || 'Unknown',
                                category: crop.crop_type?.category || 'other',
                                health_score: analysis.crop_specific_insights?.health_score || crop.health_score || 5.0,
                                ndvi_estimated: analysis.ndvi_mean || 0.5,
                                area_hectares: crop.area_hectares,
                                growth_stage: crop.growth_stage,
                                certifications: crop.certifications || {}
                            });
                        } catch (error) {
                            // If no specific analysis, use crop data
                            cropAnalysisData.push({
                                parcel_name: `Parcel ${parcel.parcel_number}`,
                                crop_type: crop.crop_type?.name || 'Unknown',
                                category: crop.crop_type?.category || 'other',
                                health_score: crop.health_score || 5.0,
                                ndvi_estimated: 0.5, // Default
                                area_hectares: crop.area_hectares,
                                growth_stage: crop.growth_stage,
                                certifications: {
                                    organic: crop.organic_certified,
                                    fair_trade: crop.fair_trade_certified,
                                    rain_forest_alliance: crop.rain_forest_alliance_certified
                                }
                            });
                        }
                    }
                } catch (error) {
                    console.error(`Error loading crops for parcel ${parcel.id}:`, error);
                }
            }

            if (cropAnalysisData.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-4">
                        <i class="bi bi-seedling fs-1 text-muted"></i>
                        <p class="text-muted mt-2">No crop areas analyzed yet</p>
                        <small class="text-muted">Map crops and run satellite analysis to see differentiation results</small>
                    </div>
                `;
                return;
            }

            // Group by category
            const categoryGroups = {};
            cropAnalysisData.forEach(crop => {
                const category = crop.category;
                if (!categoryGroups[category]) {
                    categoryGroups[category] = [];
                }
                categoryGroups[category].push(crop);
            });

            let html = '<div class="row g-3">';

            Object.keys(categoryGroups).forEach(category => {
                const crops = categoryGroups[category];
                const avgHealth = crops.reduce((sum, c) => sum + c.health_score, 0) / crops.length;
                const totalArea = crops.reduce((sum, c) => sum + (c.area_hectares || 0), 0);
                const certifiedCount = crops.filter(c => c.certifications.organic || c.certifications.fair_trade || c.certifications.rain_forest_alliance).length;

                const categoryColors = {
                    coffee: '#8B4513',
                    shade_tree: '#228B22',
                    fruit_tree: '#32CD32',
                    timber: '#8B4513',
                    vegetable: '#9ACD32',
                    legume: '#DAA520',
                    cereal: '#F4A460',
                    other: '#A9A9A9'
                };

                const categoryIcons = {
                    coffee: 'bi-cup-hot-fill',
                    shade_tree: 'bi-tree-fill',
                    fruit_tree: 'bi-apple',
                    timber: 'bi-tree',
                    vegetable: 'bi-leaf',
                    legume: 'bi-flower1',
                    cereal: 'bi-wheat',
                    other: 'bi-question-circle'
                };

                html += `
                    <div class="col-md-6 col-lg-4">
                        <div class="card border-0 shadow-sm h-100" style="border-left: 4px solid ${categoryColors[category] || '#6f4e37'};">
                            <div class="card-header" style="background-color: ${categoryColors[category] || '#f8f9fa'}; color: ${category === 'coffee' ? 'white' : 'black'};">
                                <h6 class="mb-0">
                                    <i class="bi ${categoryIcons[category] || 'bi-question-circle'} me-2"></i>
                                    ${category.replace('_', ' ').toUpperCase()}
                                </h6>
                            </div>
                            <div class="card-body">
                                <div class="row text-center mb-2">
                                    <div class="col-6">
                                        <div class="h5 mb-0 ${avgHealth >= 7 ? 'text-success' : avgHealth >= 5 ? 'text-warning' : 'text-danger'}">
                                            ${avgHealth.toFixed(1)}
                                        </div>
                                        <small class="text-muted">Avg Health</small>
                                    </div>
                                    <div class="col-6">
                                        <div class="h5 mb-0">${totalArea.toFixed(1)}</div>
                                        <small class="text-muted">Area (ha)</small>
                                    </div>
                                </div>
                                <div class="mb-2">
                                    <small class="text-muted">${crops.length} crop${crops.length !== 1 ? 's' : ''}</small>
                                    ${certifiedCount > 0 ? `<br><small class="text-success">${certifiedCount} certified</small>` : ''}
                                </div>
                                <div class="progress mb-2" style="height: 6px;">
                                    <div class="progress-bar" role="progressbar" style="width: ${(avgHealth/10)*100}%; background-color: ${categoryColors[category]};"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });

            html += '</div>';

            // Add detailed crop list
            html += '<div class="mt-4"><h6>Detailed Crop Analysis</h6><div class="table-responsive"><table class="table table-sm"><thead><tr><th>Crop Type</th><th>Parcel</th><th>Health Score</th><th>Area (ha)</th><th>Growth Stage</th><th>Certifications</th></tr></thead><tbody>';

            cropAnalysisData.forEach(crop => {
                const certBadges = [];
                if (crop.certifications.organic) certBadges.push('<span class="badge bg-success">Organic</span>');
                if (crop.certifications.fair_trade) certBadges.push('<span class="badge bg-info">Fair Trade</span>');
                if (crop.certifications.rain_forest_alliance) certBadges.push('<span class="badge bg-warning">RFA</span>');

                html += `
                    <tr>
                        <td><strong>${crop.crop_type}</strong></td>
                        <td>${crop.parcel_name}</td>
                        <td>
                            <span class="badge ${crop.health_score >= 7 ? 'bg-success' : crop.health_score >= 5 ? 'bg-warning' : 'bg-danger'}">
                                ${crop.health_score.toFixed(1)}
                            </span>
                        </td>
                        <td>${crop.area_hectares?.toFixed(1) || 'N/A'}</td>
                        <td>${crop.growth_stage || 'Unknown'}</td>
                        <td>${certBadges.join(' ') || '<small class="text-muted">None</small>'}</td>
                    </tr>
                `;
            });

            html += '</tbody></table></div>';

            container.innerHTML = html;

        } catch (error) {
            console.error('Error loading crop analysis:', error);
            const container = document.getElementById('cropAnalysis');
            if (container) {
                container.innerHTML = '<div class="text-danger text-center py-3">Error loading crop analysis data</div>';
            }
        }
    }

    async loadHistoricalAnalysis(farmId) {
        try {
            const historicalData = await api.request(`/farmer/farm/${farmId}/historical-analysis`);

            const container = document.getElementById('historicalAnalysis');
            if (!container) return;

            if (!historicalData.historical_data || Object.keys(historicalData.historical_data).length === 0) {
                container.innerHTML = '<div class="text-muted text-center py-3">No historical analysis data available</div>';
                return;
            }

            let html = '<div class="row g-3">';

            // Display yearly summaries
            Object.keys(historicalData.historical_data).sort().reverse().forEach(year => {
                const yearData = historicalData.historical_data[year];
                const avgNdvi = yearData.filter(d => d.ndvi_mean).reduce((sum, d) => sum + d.ndvi_mean, 0) / yearData.filter(d => d.ndvi_mean).length || 0;
                const deforestationEvents = yearData.filter(d => d.deforestation_detected).length;

                html += `
                    <div class="col-md-6 col-lg-4">
                        <div class="card border-0 shadow-sm">
                            <div class="card-header bg-primary text-white">
                                <h6 class="mb-0">${year}</h6>
                            </div>
                            <div class="card-body">
                                <div class="row text-center">
                                    <div class="col-6">
                                        <div class="h5 mb-0">${avgNdvi.toFixed(3)}</div>
                                        <small class="text-muted">Avg NDVI</small>
                                    </div>
                                    <div class="col-6">
                                        <div class="h5 mb-0 ${deforestationEvents > 0 ? 'text-danger' : 'text-success'}">${deforestationEvents}</div>
                                        <small class="text-muted">Deforestation Events</small>
                                    </div>
                                </div>
                                <hr>
                                <div class="small">
                                    <div class="d-flex justify-content-between">
                                        <span>Analyses:</span>
                                        <span>${yearData.length}</span>
                                    </div>
                                    <div class="d-flex justify-content-between">
                                        <span>Tree Cover:</span>
                                        <span>${yearData[0].tree_cover_percentage || 0}%</span>
                                    </div>
                                    <div class="d-flex justify-content-between">
                                        <span>Biomass:</span>
                                        <span>${yearData[0].biomass_tons_hectare || 0}t/ha</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });

            html += '</div>';

            // Add trends section
            if (historicalData.yearly_trends && Object.keys(historicalData.yearly_trends).length > 0) {
                html += `
                    <div class="mt-4">
                        <h6>Year-over-Year Trends</h6>
                        <div class="table-responsive">
                            <table class="table table-sm">
                                <thead>
                                    <tr>
                                        <th>Year</th>
                                        <th>NDVI Change</th>
                                        <th>Canopy Trend</th>
                                        <th>Biomass Trend</th>
                                    </tr>
                                </thead>
                                <tbody>
                `;

                Object.keys(historicalData.yearly_trends).sort().reverse().forEach(year => {
                    const trend = historicalData.yearly_trends[year];
                    html += `
                        <tr>
                            <td>${year}</td>
                            <td class="${trend.ndvi_change >= 0 ? 'text-success' : 'text-danger'}">
                                ${trend.ndvi_change >= 0 ? '+' : ''}${trend.ndvi_change}
                            </td>
                            <td class="${trend.canopy_trend === 'increasing' ? 'text-success' : 'text-warning'}">
                                ${trend.canopy_trend}
                            </td>
                            <td class="${trend.biomass_trend === 'increasing' ? 'text-success' : 'text-warning'}">
                                ${trend.biomass_trend}
                            </td>
                        </tr>
                    `;
                });

                html += '</tbody></table></div>';
            }

            container.innerHTML = html;

        } catch (error) {
            console.error('Error loading historical analysis:', error);
            const container = document.getElementById('historicalAnalysis');
            if (container) {
                container.innerHTML = '<div class="text-danger text-center py-3">Error loading historical data</div>';
            }
        }
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

            html = '<div class="row g-3">';

            for (const parcel of parcels) {
                try {
                    // Load trees
                    const trees = await api.request(`/farmer/farm/${farmId}/parcel/${parcel.id}/trees`);
                    totalTrees += trees.length;

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
            <div class="modal fade" id="cropDetailsModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header" style="background-color: ${cropType.display_color}; color: white;">
                            <h5 class="modal-title">
                                <i class="bi bi-seedling me-2"></i>Add ${cropType.name}
                            </h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
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
            <div class="modal fade" id="cropAnalysisModal" tabindex="-1">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-graph-up me-2"></i>Crop Health Analysis Results</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
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
            <div class="modal fade" id="treeMappingModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-tree me-2"></i>Tree Mapping</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
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

    showToast(message, type = 'info') {
        const container = document.querySelector('.toast-container');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : (type === 'success' ? 'success' : 'primary')} border-0 show`;
        toast.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }
}

// Initialize app
const app = new PlotraDashboard();
window.app = app;
window.showRegisterModal = function() { app.showRegisterModal(); };
window.showLoginModal = function() { app.showLoginModal(); };
window.subscribeNewsletter = function() { app.subscribeNewsletter(); };
