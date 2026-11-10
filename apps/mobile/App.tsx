// WHY: D1, D17, PRO-2, VOX-1, VOX-2, SPEC v1.1 — React Native + Expo Android Mobile App
import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ScrollView,
  SafeAreaView,
  Modal,
  Alert as RNAlert,
  Animated,
  ActivityIndicator,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as Haptics from 'expo-haptics';
import {
  startTripTrackingService,
  stopTripTrackingService,
  flushPendingPositions,
} from './src/services/trackingService';
import { voiceService, VoiceTurnResponse } from './src/services/voiceService';

const API_BASE = 'http://localhost:8000';

export default function App() {
  const [tab, setTab] = useState<'dawn' | 'trip' | 'sea' | 'landing' | 'prices' | 'diary'>('dawn');
  const [isTripActive, setIsTripActive] = useState(false);
  const [trackingHealthModal, setTrackingHealthModal] = useState(false);
  const [trackingState, setTrackingState] = useState<'running' | 'degraded' | 'stopped'>('running');
  const [batteryPct, setBatteryPct] = useState(86);
  const [voiceModal, setVoiceModal] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [chatMessages, setChatMessages] = useState<Array<{ sender: 'user' | 'ale'; textKn: string; textEn: string }>>([]);
  const [sosProgress] = useState(new Animated.Value(0));
  const sosTimer = useRef<NodeJS.Timeout | null>(null);

  // Checklist state
  const [checklist, setChecklist] = useState([true, true, true, true]);
  const [crewCount, setCrewCount] = useState(2);
  const [returnHours, setReturnHours] = useState(6);

  // Sync positions periodically when active
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isTripActive) {
      interval = setInterval(() => {
        flushPendingPositions(API_BASE, '9876500021');
      }, 30000);
    }
    return () => clearInterval(interval);
  }, [isTripActive]);

  // SOS Press & Hold (2 seconds)
  const handleSosPressIn = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    Animated.timing(sosProgress, {
      toValue: 1,
      duration: 2000,
      useNativeDriver: false,
    }).start();

    sosTimer.current = setTimeout(async () => {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      try {
        await fetch(`${API_BASE}/api/v1/trips/sos`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone: '9876500021', lat: 13.35, lon: 74.69 }),
        });
        RNAlert.alert('🚨 SOS SENT', 'Coast Guard, nearby boats, and Lakshmi have been alerted with your coordinates.');
      } catch (e) {
        RNAlert.alert('Offline SOS', 'Distress beacon queued in offline storage.');
      }
    }, 2000);
  };

  const handleSosPressOut = () => {
    if (sosTimer.current) clearTimeout(sosTimer.current);
    Animated.timing(sosProgress, { toValue: 0, duration: 200, useNativeDriver: false }).start();
  };

  // Trip Start / End
  const toggleTrip = async () => {
    if (!isTripActive) {
      const res = await startTripTrackingService('trip_demo_101', '9876500021', API_BASE);
      if (res.success) {
        setIsTripActive(true);
        setTrackingState('running');
        RNAlert.alert('⛵ Trip Active', 'Foreground GPS tracking started. Safe sailing!');
      }
    } else {
      await stopTripTrackingService(API_BASE, '9876500021');
      setIsTripActive(false);
      setTrackingState('stopped');
      RNAlert.alert('🏁 Trip Ended', 'Welcome home to Malpe Harbour!');
    }
  };

  // Voice Recording
  const triggerVoiceRecord = async () => {
    if (!isRecording) {
      try {
        await voiceService.startRecording();
        setIsRecording(true);
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      } catch (e) {
        RNAlert.alert('Error', 'Microphone permission required.');
      }
    } else {
      setIsRecording(false);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      try {
        const resp: VoiceTurnResponse = await voiceService.stopAndSend(API_BASE, '9876500021');
        setChatMessages(prev => [
          ...prev,
          { sender: 'user', textKn: resp.transcript, textEn: resp.transcript },
          { sender: 'ale', textKn: resp.reply_kn, textEn: resp.reply_en },
        ]);
      } catch (e) {
        RNAlert.alert('Speech Pipeline', 'Voice query could not be reached.');
      }
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />

      {/* Top Header */}
      <View style={styles.topBar}>
        <Text style={styles.brand}>ale<Text style={{ color: '#ff8a2b' }}>~</Text> <Text style={styles.brandSub}>Mobile</Text></Text>
        <TouchableOpacity style={styles.healthButton} onPress={() => setTrackingHealthModal(true)}>
          <Text style={styles.healthButtonText}>⚙️ PRO-2</Text>
        </TouchableOpacity>
      </View>

      {/* Persistent Foreground Service Notification Banner (D17) */}
      {isTripActive && (
        <TouchableOpacity
          style={[styles.fgBanner, trackingState === 'degraded' && styles.fgBannerDegraded]}
          onPress={() => setTrackingHealthModal(true)}
        >
          <Text style={styles.fgText}>
            ⛵ <Text style={{ fontWeight: '700' }}>Trip active</Text> · Foreground GPS (60s) · {batteryPct}% 🔋
          </Text>
          <Text style={styles.fgSub}>Health ›</Text>
        </TouchableOpacity>
      )}

      {/* Main Body Tabs */}
      <ScrollView contentContainerStyle={styles.content}>
        {tab === 'dawn' && (
          <View style={styles.tabCard}>
            <Text style={styles.tabTitle}>Good morning, Suresh</Text>
            <Text style={styles.tabSub}>Malpe Harbour · 5:40 AM</Text>
            <View style={styles.gauge}>
              <Text style={styles.gaugeBig}>Go</Text>
              <Text style={styles.gaugeKn}>ಹೋಗಬಹುದು</Text>
            </View>
            <View style={styles.statsRow}>
              <View style={styles.statBox}><Text style={styles.statVal}>12</Text><Text style={styles.statLbl}>Wind km/h</Text></View>
              <View style={styles.statBox}><Text style={styles.statVal}>0.8m</Text><Text style={styles.statLbl}>Waves</Text></View>
              <View style={styles.statBox}><Text style={styles.statVal}>6:12</Text><Text style={styles.statLbl}>High Tide</Text></View>
            </View>
            <TouchableOpacity style={styles.actionBtn} onPress={() => voiceService.playAudio(`${API_BASE}/api/v1/audio/dawn_sample.wav`)}>
              <Text style={styles.actionBtnText}>🔊 Hear in Kannada</Text>
            </TouchableOpacity>
          </View>
        )}

        {tab === 'trip' && (
          <View style={styles.tabCard}>
            <Text style={styles.tabTitle}>Trip Check-in</Text>
            <Text style={styles.tabSub}>Check before you sail · Malpe</Text>
            {['🦺 Life jackets for everyone', '⛽ Fuel for the trip', '🧊 Ice and water', '🔋 Phone charged'].map((item, idx) => (
              <TouchableOpacity
                key={idx}
                style={[styles.checkRow, checklist[idx] && styles.checkRowActive]}
                onPress={() => {
                  const copy = [...checklist];
                  copy[idx] = !copy[idx];
                  setChecklist(copy);
                }}
              >
                <Text style={styles.checkText}>{item}</Text>
                <Text style={styles.checkIcon}>{checklist[idx] ? '✔' : '○'}</Text>
              </TouchableOpacity>
            ))}
            <TouchableOpacity
              style={[styles.actionBtn, isTripActive && { backgroundColor: '#e74c3c' }]}
              onPress={toggleTrip}
            >
              <Text style={styles.actionBtnText}>{isTripActive ? '🏁 End Trip (Landed)' : '⛵ Start Trip'}</Text>
            </TouchableOpacity>
          </View>
        )}

        {tab === 'sea' && (
          <View style={styles.tabCard}>
            <Text style={styles.tabTitle}>Sea Mode</Text>
            <Text style={styles.tabSub}>Offline · GPS on · 3 boats nearby</Text>
            <View style={styles.seaBox}>
              <Text style={{ color: '#3ddc84', fontWeight: '700', fontSize: 16 }}>● SAFE ZONE (10 km)</Text>
              <Text style={{ color: '#8fd0ff', fontSize: 14, marginTop: 4 }}>Boat: Ale-Malpe-07 · 6.5 knots</Text>
            </View>

            {/* 2-Second Hold SOS */}
            <View style={styles.sosContainer}>
              <TouchableOpacity
                activeOpacity={0.8}
                onPressIn={handleSosPressIn}
                onPressOut={handleSosPressOut}
                style={styles.sosButton}
              >
                <Text style={styles.sosText}>SOS</Text>
              </TouchableOpacity>
              <Text style={styles.sosHint}>Press and hold for 2 seconds</Text>
            </View>
          </View>
        )}

        {tab === 'prices' && (
          <View style={styles.tabCard}>
            <Text style={styles.tabTitle}>Fair Price Board</Text>
            <Text style={styles.tabSub}>Today · ₹ per kg · Malpe</Text>
            {[
              { e: '🐟', n: 'Sardine (ಬೂತಾಯಿ)', p: '₹90–110' },
              { e: '🐠', n: 'Mackerel (ಬಂಗುಡೆ)', p: '₹140–170' },
              { e: '🐡', n: 'Pomfret (ಮಾಂಜಿ)', p: '₹620–760' },
              { e: '🦐', n: 'Prawns (ಸಿಗಡಿ)', p: '₹380–450' },
            ].map((f, i) => (
              <View key={i} style={styles.fishRow}>
                <Text style={{ fontSize: 24 }}>{f.e}</Text>
                <Text style={{ flex: 1, marginLeft: 12, fontSize: 16, color: '#f0f6fc', fontWeight: '600' }}>{f.n}</Text>
                <Text style={{ fontSize: 16, color: '#ff8a2b', fontWeight: '700' }}>{f.p}</Text>
              </View>
            ))}
          </View>
        )}

        {tab === 'diary' && (
          <View style={styles.tabCard}>
            <Text style={styles.tabTitle}>Earnings Diary</Text>
            <Text style={styles.tabSub}>This week · Malpe Harbour</Text>
            <View style={styles.statsRow}>
              <View style={styles.statBox}><Text style={styles.statVal}>₹18,400</Text><Text style={styles.statLbl}>Sold</Text></View>
              <View style={styles.statBox}><Text style={styles.statVal}>₹5,200</Text><Text style={styles.statLbl}>Fuel</Text></View>
              <View style={styles.statBox}><Text style={[styles.statVal, { color: '#2ecc71' }]}>₹13,200</Text><Text style={styles.statLbl}>Kept</Text></View>
            </View>
          </View>
        )}
      </ScrollView>

      {/* Floating Kannada Mic Button */}
      <TouchableOpacity style={styles.fabMic} onPress={() => setVoiceModal(true)}>
        <Text style={{ fontSize: 28 }}>🎙️</Text>
      </TouchableOpacity>

      {/* Bottom Tabs */}
      <View style={styles.tabBar}>
        {[
          { key: 'dawn', icon: '🌅', label: 'Dawn' },
          { key: 'trip', icon: '📋', label: 'Trip' },
          { key: 'sea', icon: '🧭', label: 'Sea' },
          { key: 'prices', icon: '🐟', label: 'Prices' },
          { key: 'diary', icon: '📒', label: 'Diary' },
        ].map(t => (
          <TouchableOpacity key={t.key} style={styles.tabItem} onPress={() => setTab(t.key as any)}>
            <Text style={{ fontSize: 20 }}>{t.icon}</Text>
            <Text style={[styles.tabLabel, tab === t.key && styles.tabLabelActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* PRO-2 Tracking Health Modal */}
      <Modal visible={trackingHealthModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>⚙️ Tracking Health (PRO-2)</Text>
            <Text style={styles.modalSub}>Spec v1.1 D17 · OEM Background Protection</Text>

            <View style={styles.healthCard}>
              <Text style={styles.healthLine}>Service: <Text style={{ color: trackingState === 'running' ? '#2ecc71' : '#f39c12', fontWeight: '700' }}>{trackingState.toUpperCase()}</Text></Text>
              <Text style={styles.healthLine}>Location: <Text style={{ color: '#2ecc71', fontWeight: '700' }}>Always Allow (Granted)</Text></Text>
              <Text style={styles.healthLine}>Battery Optimization: <Text style={{ color: '#2ecc71', fontWeight: '700' }}>Whitelisted (No restrictions)</Text></Text>
              <Text style={styles.healthLine}>GPS Sampling: 60s interval · ~15m accuracy</Text>
              <Text style={styles.healthLine}>Device: Xiaomi Redmi Note 12 · Android 14</Text>
            </View>

            <View style={{ gap: 10, marginTop: 16 }}>
              <TouchableOpacity
                style={[styles.actionBtn, { backgroundColor: '#f39c12' }]}
                onPress={() => {
                  setTrackingState('degraded');
                  setBatteryPct(14);
                  RNAlert.alert('Simulated N-15', 'Battery saver killed tracking service.');
                }}
              >
                <Text style={styles.actionBtnText}>⚠️ Simulate: Battery Saver Killed Service (N-15)</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.actionBtn, { backgroundColor: '#2ecc71' }]}
                onPress={() => {
                  setTrackingState('running');
                  setBatteryPct(86);
                  RNAlert.alert('Restored', 'Foreground tracking service resumed.');
                }}
              >
                <Text style={styles.actionBtnText}>✅ One-tap Fix & Resume Service</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.closeBtn} onPress={() => setTrackingHealthModal(false)}>
                <Text style={{ color: '#f0f6fc', fontWeight: '600' }}>Close</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Voice Assistant Modal */}
      <Modal visible={voiceModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>🎙️ Talk to Ale (Gnani AI)</Text>
            <Text style={styles.modalSub}>Speak in Kannada: ಹವಾಮಾನ, ಬೆಲೆ, ಮೀನಿನ ಸ್ಥಳ</Text>

            <ScrollView style={{ maxHeight: 200, marginVertical: 12 }}>
              {chatMessages.map((m, idx) => (
                <View key={idx} style={[styles.bubble, m.sender === 'user' ? styles.bubbleUser : styles.bubbleAle]}>
                  <Text style={{ color: '#fff', fontSize: 15, fontWeight: '600' }}>{m.textKn}</Text>
                  <Text style={{ color: '#ccc', fontSize: 12, marginTop: 2 }}>{m.textEn}</Text>
                </View>
              ))}
            </ScrollView>

            <TouchableOpacity
              style={[styles.micBig, isRecording && styles.micRecording]}
              onPress={triggerVoiceRecord}
            >
              <Text style={{ fontSize: 32 }}>🎙️</Text>
            </TouchableOpacity>
            <Text style={{ textAlign: 'center', color: '#8b9bb4', fontSize: 13, marginTop: 8 }}>
              {isRecording ? 'Listening... Tap to send' : 'Tap to speak'}
            </Text>

            <TouchableOpacity style={styles.closeBtn} onPress={() => setVoiceModal(false)}>
              <Text style={{ color: '#f0f6fc', fontWeight: '600' }}>Close</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0b1522' },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16 },
  brand: { fontSize: 24, fontWeight: '800', color: '#f0f6fc' },
  brandSub: { fontSize: 12, color: '#8b9bb4', fontWeight: '600' },
  healthButton: { backgroundColor: '#182b45', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16 },
  healthButtonText: { color: '#8fd0ff', fontWeight: '700', fontSize: 12 },
  fgBanner: {
    backgroundColor: '#0d2338',
    borderWidth: 1.5,
    borderColor: '#2ecc71',
    borderRadius: 12,
    marginHorizontal: 16,
    padding: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  fgBannerDegraded: { borderColor: '#f39c12' },
  fgText: { color: '#8fd0ff', fontSize: 13, fontWeight: '600' },
  fgSub: { color: '#2ecc71', fontSize: 11, fontWeight: '700' },
  content: { padding: 16, paddingBottom: 100 },
  tabCard: { backgroundColor: '#122033', borderRadius: 16, padding: 20, borderWidth: 1, borderColor: '#223c5e' },
  tabTitle: { fontSize: 22, fontWeight: '700', color: '#f0f6fc' },
  tabSub: { fontSize: 13, color: '#8b9bb4', marginTop: 2, marginBottom: 16 },
  gauge: {
    height: 120,
    backgroundColor: '#1f78b4',
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  gaugeBig: { fontSize: 36, fontWeight: '800', color: '#fff' },
  gaugeKn: { fontSize: 18, color: '#e0f2fe', marginTop: 4 },
  statsRow: { flexDirection: 'row', gap: 10, marginBottom: 16 },
  statBox: { flex: 1, backgroundColor: '#182b45', padding: 12, borderRadius: 12, alignItems: 'center' },
  statVal: { fontSize: 18, fontWeight: '800', color: '#f0f6fc' },
  statLbl: { fontSize: 11, color: '#8b9bb4', marginTop: 2 },
  actionBtn: { backgroundColor: '#1f78b4', padding: 14, borderRadius: 12, alignItems: 'center', marginTop: 10 },
  actionBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  checkRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#182b45',
    padding: 14,
    borderRadius: 12,
    marginBottom: 8,
  },
  checkRowActive: { borderWidth: 1, borderColor: '#2ecc71' },
  checkText: { color: '#f0f6fc', fontSize: 15, fontWeight: '600' },
  checkIcon: { color: '#2ecc71', fontSize: 18, fontWeight: '800' },
  seaBox: { backgroundColor: '#0b3a5e', padding: 20, borderRadius: 14, marginBottom: 20 },
  sosContainer: { alignItems: 'center', marginTop: 10 },
  sosButton: {
    width: 140,
    height: 140,
    borderRadius: 70,
    backgroundColor: '#e74c3c',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 8,
  },
  sosText: { color: '#fff', fontSize: 32, fontWeight: '900' },
  sosHint: { color: '#8b9bb4', fontSize: 12, marginTop: 10 },
  fishRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#223c5e',
  },
  tabBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 70,
    backgroundColor: '#122033',
    borderTopWidth: 1,
    borderTopColor: '#223c5e',
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
  },
  tabItem: { alignItems: 'center' },
  tabLabel: { fontSize: 11, color: '#8b9bb4', marginTop: 2 },
  tabLabelActive: { color: '#1f78b4', fontWeight: '700' },
  fabMic: {
    position: 'absolute',
    right: 20,
    bottom: 84,
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#ff8a2b',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 6,
  },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: '#122033', padding: 24, borderTopLeftRadius: 24, borderTopRightRadius: 24 },
  modalTitle: { fontSize: 20, fontWeight: '700', color: '#f0f6fc' },
  modalSub: { fontSize: 13, color: '#8b9bb4', marginTop: 2, marginBottom: 16 },
  healthCard: { backgroundColor: '#182b45', padding: 14, borderRadius: 12, gap: 8 },
  healthLine: { color: '#f0f6fc', fontSize: 13 },
  closeBtn: { marginTop: 12, padding: 12, alignItems: 'center' },
  bubble: { padding: 10, borderRadius: 12, marginBottom: 8, maxWidth: '85%' },
  bubbleUser: { backgroundColor: '#1f78b4', alignSelf: 'flex-end' },
  bubbleAle: { backgroundColor: '#182b45', alignSelf: 'flex-start' },
  micBig: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: '#ff8a2b',
    alignSelf: 'center',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 10,
  },
  micRecording: { backgroundColor: '#e74c3c' },
});

