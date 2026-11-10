// WHY: D17, FR-SEA-02, FR-SEA-07, TR-CLI-11, TR-CLI-12 — Foreground Trip Tracking Service
import * as Location from 'expo-location';
import * as TaskManager from 'expo-task-manager';
import * as Battery from 'expo-battery';
import { offlineDb } from './offlineDb';

export const ALE_BACKGROUND_LOCATION_TASK = 'ALE_BACKGROUND_LOCATION_TASK';

interface TrackingConfig {
  tripId: string;
  phone: string;
  apiBase: string;
}

let currentConfig: TrackingConfig | null = null;

// --- TaskManager Background Task Definition ---
TaskManager.defineTask(ALE_BACKGROUND_LOCATION_TASK, async ({ data, error }) => {
  if (error) {
    console.error('[ALE Background Location Error]:', error.message);
    if (currentConfig) {
      await reportHealth(currentConfig.apiBase, currentConfig.phone, 'degraded', error.message);
    }
    return;
  }

  if (data) {
    const { locations } = data as { locations: Location.LocationObject[] };
    if (!locations || !locations.length) return;

    let batteryPct = 86;
    try {
      const level = await Battery.getBatteryLevelAsync();
      if (level >= 0) batteryPct = Math.round(level * 100);
    } catch (e) {}

    for (const loc of locations) {
      const clientOpId = `pos_${loc.timestamp}_${Math.random().toString(36).substring(2, 7)}`;
      const tripId = currentConfig?.tripId || 'active_trip';

      await offlineDb.enqueuePosition({
        trip_id: tripId,
        lat: loc.coords.latitude,
        lon: loc.coords.longitude,
        accuracy_m: loc.coords.accuracy || 10.0,
        speed_kn: loc.coords.speed ? loc.coords.speed * 1.94384 : 6.5,
        heading: loc.coords.heading || 240.0,
        provider: 'gps',
        battery_pct: batteryPct,
        recorded_at: new Date(loc.timestamp).toISOString(),
        client_op_id: clientOpId,
      });
    }

    // Attempt opportunistic flush
    if (currentConfig?.apiBase) {
      await flushPendingPositions(currentConfig.apiBase, currentConfig.phone);
    }
  }
});

// --- Service Lifecycle ---
export async function startTripTrackingService(
  tripId: string,
  phone = '9876500021',
  apiBase = 'http://localhost:8000'
): Promise<{ success: boolean; message: string }> {
  currentConfig = { tripId, phone, apiBase };

  // 1. Request Foreground Permissions
  const { status: fgStatus } = await Location.requestForegroundPermissionsAsync();
  if (fgStatus !== 'granted') {
    await reportHealth(apiBase, phone, 'stopped', 'Foreground location permission denied.');
    return { success: false, message: 'Location permission denied by user.' };
  }

  // 2. Request Background Permissions (Always allow)
  const { status: bgStatus } = await Location.requestBackgroundPermissionsAsync();
  if (bgStatus !== 'granted') {
    await reportHealth(apiBase, phone, 'degraded', 'Background location permission not granted ("Always" required).');
  }

  // 3. Start Location Updates with Android Ongoing Foreground Notification
  const isStarted = await Location.hasStartedLocationUpdatesAsync(ALE_BACKGROUND_LOCATION_TASK);
  if (!isStarted) {
    await Location.startLocationUpdatesAsync(ALE_BACKGROUND_LOCATION_TASK, {
      accuracy: Location.Accuracy.High,
      timeInterval: 60000, // 60 seconds interval per Spec v1.1
      distanceInterval: 10, // 10 meters minimum movement
      showsBackgroundLocationIndicator: true,
      foregroundService: {
        notificationTitle: '⛵ Trip active · Ale Voice',
        notificationBody: 'Foreground GPS tracking (60s interval) · Safety service active',
        notificationColor: '#1f78b4',
      },
    });
  }

  await reportHealth(apiBase, phone, 'running', 'Foreground service started successfully.');
  return { success: true, message: 'Trip tracking service running.' };
}

export async function stopTripTrackingService(apiBase = 'http://localhost:8000', phone = '9876500021'): Promise<void> {
  const isStarted = await Location.hasStartedLocationUpdatesAsync(ALE_BACKGROUND_LOCATION_TASK);
  if (isStarted) {
    await Location.stopLocationUpdatesAsync(ALE_BACKGROUND_LOCATION_TASK);
  }
  await reportHealth(apiBase, phone, 'stopped', 'Trip ended by fisher.');
  currentConfig = null;
}

// --- Outbox Flush ---
export async function flushPendingPositions(apiBase: string, phone: string): Promise<number> {
  const pending = await offlineDb.getPendingPositions(50);
  if (!pending.length) return 0;

  try {
    const payload = {
      phone,
      trip_id: pending[0].trip_id,
      positions: pending.map(p => ({
        trip_id: p.trip_id,
        lat: p.lat,
        lon: p.lon,
        accuracy_m: p.accuracy_m,
        speed_kn: p.speed_kn,
        heading: p.heading,
        provider: p.provider,
        battery_pct: p.battery_pct,
        recorded_at: p.recorded_at,
        client_op_id: p.client_op_id,
      })),
    };

    const res = await fetch(`${apiBase}/api/v1/trips/positions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const data = await res.json();
      await offlineDb.markPositionsSynced(pending.map(p => p.client_op_id));
      return data.saved || pending.length;
    }
  } catch (e) {
    // Retain in SQLite for next retry
  }
  return 0;
}

// --- Health Heartbeat ---
async function reportHealth(apiBase: string, phone: string, state: string, reason?: string): Promise<void> {
  try {
    await fetch(`${apiBase}/api/v1/devices/health`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone,
        tracking_state: state,
        location_permission: 'always',
        notifications_enabled: true,
        battery_optimised: false,
        gps_enabled: true,
        battery_pct: 86,
        network: 'good',
        reason,
      }),
    });
  } catch (e) {}
}

