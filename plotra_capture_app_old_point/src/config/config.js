import Constants from 'expo-constants';

const config = {
  // Override API_BASE_URL via expo config extra field
  API_BASE_URL:
    Constants.expoConfig?.extra?.API_BASE_URL ||
    (__DEV__ ? 'http://localhost:8000/api/v2' : 'https://your-backend.com/api/v2'),

  APP_VERSION: '1.0.0',

  // GPS settings (adjust as needed)
  GPS_ACCURACY_THRESHOLD: 10,  // meters
  MIN_ACCURACY_FOR_CAPTURE: 30, // meters
};

export default config;
