import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Network from 'expo-network';
import * as Device from 'expo-device';
import { dbService } from '../services/database';

// URS-compliant API base (v1 endpoints)
const API_BASE_URL = 'http://192.168.100.5:8000/api/v1';
const API_KEY = 'plotra-prototype-key-2026';  // Static API key per URS

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,  // URS: static API key in header
  },
});

// Get device ID (persistent)
export async function getDeviceId() {
  try {
    const stored = await AsyncStorage.getItemAsync('device_id');
    if (stored) return stored;
    const deviceId = Device.deviceId || `android-${Date.now()}`;
    await AsyncStorage.setItemAsync('device_id', deviceId);
    return deviceId;
  } catch (e) {
    return 'unknown-device';
  }
}

// Polygon API (URS endpoints)
export const polygonAPI = {
  // URS: POST /api/v1/parcels/polygon
  submit: (data) => api.post('/parcels/polygon', data),
  
  // URS: GET /api/v1/farms/{farm_id}
  getFarm: (farmId) => api.get(`/farms/${farmId}`),
  
  // URS: POST /api/v1/sync/batch
  syncBatch: (captures) => api.post('/sync/batch', captures),
};

// Sync Service
export class SyncService {
  constructor() {
    this.isOnline = true;
    this.isSyncing = false;
  }

  async checkConnectivity() {
    try {
      const networkState = await Network.getNetworkStateAsync();
      this.isOnline = networkState.isConnected;
      return this.isOnline;
    } catch (e) {
      this.isOnline = false;
      return false;
    }
  }

  async startAutoSync() {
    // Check every 30 seconds
    setInterval(async () => {
      const online = await this.checkConnectivity();
      if (online && !this.isSyncing) {
        await this.syncPending();
      }
    }, 30000);
  }

  async syncPending() {
    if (this.isSyncing) return;
    this.isSyncing = true;

    try {
      const pending = await dbService.getQueue(null, 'pending');
      if (pending.length === 0) return;

      // Batch sync: send all pending in one call
      try {
        const response = await polygonAPI.syncBatch(pending);
        if (response.data?.synced > 0) {
          // Mark all as synced
          for (const c of pending) {
            await dbService.updateSyncStatus(c.id, 'synced');
          }
        }
      } catch (error) {
        // Mark all as failed
        for (const c of pending) {
          await dbService.updateSyncStatus(c.id, 'failed', error.message);
        }
      }
    } finally {
      this.isSyncing = false;
    }
  }

  getPendingCount() {
    return dbService.getPendingCount();
  }
}

export const syncService = new SyncService();

export default api;
