// WHY: D1, D17, TR-OFF-01, TR-OFF-02, TR-CLI-11 — Offline SQLite & Encrypted Keystore Storage
import * as SecureStore from 'expo-secure-store';
import * as SQLite from 'expo-sqlite';

export interface QueuedPosition {
  id?: number;
  trip_id: string;
  lat: number;
  lon: number;
  accuracy_m: number;
  speed_kn: number;
  heading: number;
  provider: string;
  battery_pct: number;
  recorded_at: string;
  client_op_id: string;
  synced: number;
}

export interface OutboxOperation {
  id?: number;
  client_op_id: string;
  op_type: string;
  payload: string;
  phone: string;
  created_at: string;
  synced: number;
}

class OfflineStorage {
  private db: SQLite.SQLiteDatabase | null = null;

  async init(): Promise<void> {
    if (this.db) return;
    this.db = await SQLite.openDatabaseAsync('ale_voice_client.db');

    await this.db.execAsync(`
      PRAGMA journal_mode = WAL;
      CREATE TABLE IF NOT EXISTS queued_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        accuracy_m REAL NOT NULL,
        speed_kn REAL NOT NULL,
        heading REAL NOT NULL,
        provider TEXT NOT NULL,
        battery_pct INTEGER NOT NULL,
        recorded_at TEXT NOT NULL,
        client_op_id TEXT UNIQUE NOT NULL,
        synced INTEGER DEFAULT 0
      );

      CREATE TABLE IF NOT EXISTS outbox_ops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_op_id TEXT UNIQUE NOT NULL,
        op_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        phone TEXT NOT NULL,
        created_at TEXT NOT NULL,
        synced INTEGER DEFAULT 0
      );
    `);
  }

  // --- Secure Keystore (Tokens & User Identity) ---
  async setSecureItem(key: string, value: string): Promise<void> {
    await SecureStore.setItemAsync(key, value);
  }

  async getSecureItem(key: string): Promise<string | null> {
    return await SecureStore.getItemAsync(key);
  }

  async removeSecureItem(key: string): Promise<void> {
    await SecureStore.deleteItemAsync(key);
  }

  // --- GPS Track Positions ---
  async enqueuePosition(pos: Omit<QueuedPosition, 'id' | 'synced'>): Promise<void> {
    await this.init();
    if (!this.db) return;

    await this.db.runAsync(
      `INSERT OR IGNORE INTO queued_positions 
       (trip_id, lat, lon, accuracy_m, speed_kn, heading, provider, battery_pct, recorded_at, client_op_id, synced)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0);`,
      [
        pos.trip_id,
        pos.lat,
        pos.lon,
        pos.accuracy_m,
        pos.speed_kn,
        pos.heading,
        pos.provider,
        pos.battery_pct,
        pos.recorded_at,
        pos.client_op_id
      ]
    );
  }

  async getPendingPositions(limit = 50): Promise<QueuedPosition[]> {
    await this.init();
    if (!this.db) return [];

    return await this.db.getAllAsync<QueuedPosition>(
      `SELECT * FROM queued_positions WHERE synced = 0 ORDER BY id ASC LIMIT ?;`,
      [limit]
    );
  }

  async markPositionsSynced(opIds: string[]): Promise<void> {
    if (!opIds.length || !this.db) return;
    const placeholders = opIds.map(() => '?').join(',');
    await this.db.runAsync(
      `UPDATE queued_positions SET synced = 1 WHERE client_op_id IN (${placeholders});`,
      opIds
    );
  }

  // --- Offline Outbox Operations ---
  async enqueueOutbox(op: Omit<OutboxOperation, 'id' | 'synced'>): Promise<void> {
    await this.init();
    if (!this.db) return;

    await this.db.runAsync(
      `INSERT OR IGNORE INTO outbox_ops (client_op_id, op_type, payload, phone, created_at, synced)
       VALUES (?, ?, ?, ?, ?, 0);`,
      [op.client_op_id, op.op_type, op.payload, op.phone, op.created_at]
    );
  }

  async getPendingOutbox(limit = 20): Promise<OutboxOperation[]> {
    await this.init();
    if (!this.db) return [];

    return await this.db.getAllAsync<OutboxOperation>(
      `SELECT * FROM outbox_ops WHERE synced = 0 ORDER BY id ASC LIMIT ?;`,
      [limit]
    );
  }

  async markOutboxSynced(opIds: string[]): Promise<void> {
    if (!opIds.length || !this.db) return;
    const placeholders = opIds.map(() => '?').join(',');
    await this.db.runAsync(
      `UPDATE outbox_ops SET synced = 1 WHERE client_op_id IN (${placeholders});`,
      opIds
    );
  }
}

export const offlineDb = new OfflineStorage();

