import axios from 'axios';
import * as SecureStore from 'expo-secure-store';
import { API_BASE_URL } from '../config';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  async (config) => {
    const token = await SecureStore.getItemAsync('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - clear storage and redirect to login
      await SecureStore.deleteItemAsync('auth_token');
      await SecureStore.deleteItemAsync('user_data');
      // Navigation handled by auth context
    }
    return Promise.reject(error);
  }
);

// Auth APIs
export const authAPI = {
  login: (email, password) => api.post('/auth/token', {
    username: email,
    password,
    grant_type: 'password',
  }),
  register: (userData) => api.post('/auth/register', userData),
  getMe: () => api.get('/auth/me'),
  refreshToken: () => api.post('/auth/refresh'),
};

// Farm APIs
export const farmAPI = {
  // Get all farms for selection (for capture screen)
  getAll: () => api.get('/capture/farms'),
  // Get user's farms only (logged in user)
  getMyFarms: () => api.get('/farmer/farm'),
  // Get parcels for a specific farm
  getParcels: (farmId) => api.get(`/capture/farms/${farmId}/parcels`),
  // Get single farm with parcels
  getFarm: () => api.get('/farmer/farm'),
};

// GPS Capture APIs
export const captureAPI = {
  // Capture GPS point and get instant analysis
  capture: (captureData) => api.post('/capture/capture', captureData),
  // Get previous capture analysis
  getCapture: (captureId) => api.get(`/capture/capture/${captureId}`),
};

export default api;
