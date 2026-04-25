/**
 * Plotra Dashboard - Authentication Module
 * Login, registration, OTP, password reset
 */

class AuthModule {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this._forgotPhone = null;
        this._pendingProfilePhoto = null;
    }
    
    showLoginModal() {
        document.body.classList.add('auth-active');
        const modal = new bootstrap.Modal(document.getElementById('loginModal'));
        modal.show();
    }
    
    showRegisterModal() {
        document.body.classList.add('auth-active');
        const modal = new bootstrap.Modal(document.getElementById('registerModal'));
        modal.show();
    }
    
    showForgotStep() {
        document.querySelectorAll('#loginModal .step-content').forEach(s => s.classList.remove('active'));
        document.getElementById('loginStepForgot').classList.add('active');
    }
    
    buildPhoneNumber(prefix, inputId) {
        const prefixEl = document.getElementById(prefix);
        const inputEl = document.getElementById(inputId);
        const countryCode = prefixEl?.value || '+254';
        const phone = inputEl?.value.replace(/\D/g, '') || '';
        return countryCode + phone;
    }
    
    async handleLogin() {
        const identifier = document.getElementById('loginEmail')?.value;
        const password = document.getElementById('loginPassword')?.value;
        
        if (!identifier || !password) {
            this.dashboard.showToast('Please enter credentials', 'error');
            return;
        }
        
        try {
            const data = await api.login(identifier, password);
            if (data.access_token) {
                localStorage.setItem('plotra_token', data.access_token);
                localStorage.setItem('session_expires_at', String(Date.now() + (data.expires_in || 3600) * 1000));
                this.dashboard.showApp();
            }
        } catch (error) {
            this.dashboard.showToast(error.message || 'Login failed', 'error');
        }
    }
    
    async handleRegister() {
        const firstName = document.getElementById('regFirstName')?.value;
        const lastName = document.getElementById('regLastName')?.value;
        const phone = this.buildPhoneNumber('regCountryPrefix', 'regPhone');
        const email = document.getElementById('regEmail')?.value;
        const password = document.getElementById('regPassword')?.value;
        
        if (!firstName || !lastName || !phone || !email || !password) {
            this.dashboard.showToast('Please fill all required fields', 'error');
            return;
        }
        
        if (password.length < 8) {
            this.dashboard.showToast('Password must be at least 8 characters', 'error');
            return;
        }
        
        try {
            const data = await api.register({
                first_name: firstName,
                last_name: lastName,
                phone_number: phone,
                email: email,
                password: password
            });
            
            if (data.access_token) {
                localStorage.setItem('plotra_token', data.access_token);
                localStorage.setItem('plotra_user', JSON.stringify(data.user));
                this.dashboard.showApp();
            }
        } catch (error) {
            this.dashboard.showToast(error.message || 'Registration failed', 'error');
        }
    }
    
    async handleForgot() {
        const phone = this.buildPhoneNumber('forgotPrefix', 'forgotEmail');
        
        try {
            const formData = new FormData();
            formData.append('phone', phone);
            const res = await api.request('/auth/forgot-password-otp', { method: 'POST', body: formData });
            
            this._forgotPhone = phone;
            
            if (res.dev_code) {
                const banner = document.getElementById('devForgotOtpBanner');
                const code = document.getElementById('devForgotOtpCode');
                if (banner) banner.style.display = 'block';
                if (code) code.textContent = res.dev_code;
            }
            
            const grid = document.getElementById('forgotOtpGrid');
            if (grid) this._initOTPBoxes(grid);
            
            document.querySelectorAll('#loginModal .step-content').forEach(s => s.classList.remove('active'));
            document.getElementById('loginStepForgotOTP').classList.add('active');
        } catch (error) {
            this.dashboard.showToast(error.message, 'error');
        }
    }
    
    async handleForgotOTPVerify() {
        const grid = document.getElementById('forgotOtpGrid');
        const code = Array.from(grid?.querySelectorAll('.otp-box') || []).map(i => i.value).join('');
        
        if (code.length < 6) {
            this.dashboard.showToast('Enter the 6-digit code', 'error');
            return;
        }
        
        try {
            const formData = new FormData();
            formData.append('phone', this._forgotPhone);
            formData.append('code', code);
            const res = await api.request('/auth/verify-otp', { method: 'POST', body: formData });
            
            if (res.reset_token) {
                this.dashboard.resetToken = res.reset_token;
            }
            
            document.querySelectorAll('#loginModal .step-content').forEach(s => s.classList.remove('active'));
            document.getElementById('loginStepReset').classList.add('active');
        } catch (error) {
            this.dashboard.showToast(error.message, 'error');
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
        const pass = document.getElementById('resetPassword')?.value;
        const confirm = document.getElementById('resetConfirmPassword')?.value;
        
        if (!pass || pass.length < 8) {
            this.dashboard.showToast('Password must be at least 8 characters', 'error');
            return;
        }
        if (pass !== confirm) {
            this.dashboard.showToast('Passwords do not match', 'error');
            return;
        }
        if (!this.dashboard.resetToken) {
            this.dashboard.showToast('Invalid reset token', 'error');
            return;
        }
        
        try {
            await api.resetPassword(this.dashboard.resetToken, pass);
            this.dashboard.showToast('Password set successfully!', 'success');
            this.dashboard.showLoginModal();
        } catch (error) {
            this.dashboard.showToast(error.message, 'error');
        }
    }
    
    previewPhoto(input) {
        if (!input.files || !input.files[0]) return;
        const reader = new FileReader();
        reader.onload = e => {
            const preview = document.getElementById('regPhotoPreview');
            if (preview) preview.src = e.target.result;
            this._pendingProfilePhoto = e.target.result;
        };
        reader.readAsDataURL(input.files[0]);
    }
    
    togglePassword(inputId, iconId) {
        const input = document.getElementById(inputId);
        const icon = document.getElementById(iconId);
        if (input && icon) {
            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.replace('bi-eye', 'bi-eye-slash');
            } else {
                input.type = 'password';
                icon.classList.replace('bi-eye-slash', 'bi-eye');
            }
        }
    }
}

// Export for use in main app
window.AuthModule = AuthModule;