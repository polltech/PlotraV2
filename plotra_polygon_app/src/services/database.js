import * as SQLite from 'expo-sqlite';
import { catchAsync } from '../utils/helpers';

const DB_NAME = 'plotra_capture.db';
const DB_VERSION = 1;

class DatabaseService {
  db = null;

  async init() {
    try {
      this.db = await SQLite.openDatabaseAsync(DB_NAME);
      await this.createTables();
      console.log('Database initialized');
    } catch (e) {
      console.error('DB init error:', e);
    }
  }

  async createTables() {
    const createPolygonTable = `
      CREATE TABLE IF NOT EXISTS polygon_captures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farm_id TEXT NOT NULL,
        parcel_name TEXT,
        polygon_coordinates TEXT NOT NULL,  -- JSON array of {lat, lng}
        area_ha REAL NOT NULL,
        perimeter_meters REAL,
        points_count INTEGER NOT NULL,
        captured_at TEXT NOT NULL,
        uploaded_at TEXT NOT NULL,
        sync_status TEXT DEFAULT 'pending',
        sync_attempts INTEGER DEFAULT 0,
        last_sync_error TEXT,
        device_id TEXT NOT NULL,
        accuracy_m REAL,
        agent_id TEXT,
        notes TEXT,
        topology_validated BOOLEAN DEFAULT 0,
        validation_warnings TEXT,  -- JSON array
        device_info TEXT,  -- JSON object
        created_at TEXT DEFAULT (datetime('now'))
      );
    `;

    const createQueueIndex = `
      CREATE INDEX IF NOT EXISTS idx_polygon_status ON polygon_captures(sync_status);
      CREATE INDEX IF NOT EXISTS idx_polygon_farm ON polygon_captures(farm_id);
    `;

    await this.db.execAsync(createPolygonTable);
    await this.db.execAsync(createQueueIndex);
  }

  async savePolygonCapture(capture) {
    const {
      farmId,
      parcelName,
      polygonCoords,  // array of {latitude, longitude}
      areaHectares,
      perimeterMeters,
      pointsCount,
      capturedAt,
      deviceInfo,
      notes,
      topologyValidated,
      validationWarnings,
    } = capture;

    // URS format: polygon_coordinates as array of {lat, lng} objects
    const polygonCoordinates = polygonCoords.map(p => ({
      lat: p.latitude,
      lng: p.longitude
    }));

    // Get device ID (persisted)
    const deviceId = deviceInfo?.device_id || `android-${Date.now()}`;

    const result = await this.db.runAsync(
      `INSERT INTO polygon_captures
       (farm_id, parcel_name, polygon_coordinates, area_ha, perimeter_meters,
        points_count, captured_at, uploaded_at, sync_status,
        device_id, accuracy_m, agent_id, notes, topology_validated, validation_warnings, device_info)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, NULL, ?, ?, ?, ?)`,
      [
        farmId,
        parcelName || null,
        JSON.stringify(polygonCoordinates),  // Store as URS format
        areaHectares,
        perimeterMeters || null,
        pointsCount,
        capturedAt || new Date().toISOString(),
        new Date().toISOString(),
        deviceId,
        null,  // accuracy_m — set later if available
        null,  // agent_id — optional
        notes || null,
        topologyValidated ? 1 : 0,
        JSON.stringify(validationWarnings || []),
        JSON.stringify(deviceInfo || {}),
      ]
    );

    return result.lastInsertRowId;
  }

  @catchAsync
  async getQueue(farmId = null, status = null) {
    let query = 'SELECT * FROM polygon_captures';
    const params = [];

    if (farmId || status) {
      query += ' WHERE';
      const conditions = [];
      if (farmId) {
        conditions.push('farm_id = ?');
        params.push(farmId);
      }
      if (status) {
        conditions.push('sync_status = ?');
        params.push(status);
      }
      query += ' ' + conditions.join(' AND ');
    }
    query += ' ORDER BY created_at DESC';

     const rows = await this.db.getAllAsync(query, params);
     return rows.map(row => ({
       ...row,
       polygon_coordinates: JSON.parse(row.polygon_coordinates),
       device_info: row.device_info ? JSON.parse(row.device_info) : {},
       validation_warnings: row.validation_warnings ? JSON.parse(row.validation_warnings) : [],
     }));
  }

   @catchAsync
   async getCapture(id) {
     const row = await this.db.getFirstAsync(
       'SELECT * FROM polygon_captures WHERE id = ?',
       [id]
     );
     if (row) {
       return {
         ...row,
         polygon_coordinates: JSON.parse(row.polygon_coordinates),
         device_info: row.device_info ? JSON.parse(row.device_info) : {},
         validation_warnings: row.validation_warnings ? JSON.parse(row.validation_warnings) : [],
       };
     }
     return null;
   }

  @catchAsync
  async updateSyncStatus(id, status, error = null) {
    const fields = ['sync_status = ?', 'sync_attempts = sync_attempts + 1'];
    const params = [status, id];

    if (status === 'synced') {
      fields.push('synced_at = datetime("now")');
    }
    if (error) {
      fields.push('last_sync_error = ?');
      params.push(error);
    }

    await this.db.runAsync(
      `UPDATE polygon_captures SET ${fields.join(', ')} WHERE id = ?`,
      params
    );
  }

  @catchAsync
  async deleteCapture(id) {
    await this.db.runAsync('DELETE FROM polygon_captures WHERE id = ?', [id]);
  }

  getPendingCount() {
    return this.db.getFirstAsync(
      "SELECT COUNT(*) as count FROM polygon_captures WHERE sync_status = 'pending'"
    );
  }
}

export const dbService = new DatabaseService();
