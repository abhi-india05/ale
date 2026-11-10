// WHY: D4, D5, TR-VOX-05, TR-VOX-06, TR-CLI-10 — 16 kHz Mono WAV Voice Pipeline & Audio Playback
import { Audio } from 'expo-av';

export interface VoiceTurnResponse {
  transcript: string;
  intent: string;
  decision: string;
  reply_kn: string;
  reply_en: string;
  tts_audio_url?: string;
  confidence: number;
  repair_options?: string[];
}

class VoiceManager {
  private recording: Audio.Recording | null = null;
  private sound: Audio.Sound | null = null;

  async requestPermissions(): Promise<boolean> {
    const { status } = await Audio.requestPermissionsAsync();
    return status === 'granted';
  }

  async startRecording(): Promise<void> {
    await this.requestPermissions();
    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true,
      staysActiveInBackground: false,
      shouldDuckAndroid: true,
      playThroughEarpieceAndroid: false, // Force loudspeaker
    });

    // 16 kHz mono 16-bit PCM WAV preset for Gnani Prisma STT
    const recordingOptions: Audio.RecordingOptions = {
      isMeteringEnabled: true,
      android: {
        extension: '.wav',
        outputFormat: Audio.AndroidOutputFormat.DEFAULT,
        audioEncoder: Audio.AndroidAudioEncoder.DEFAULT,
        sampleRate: 16000,
        numberOfChannels: 1,
        bitRate: 256000,
      },
      ios: {
        extension: '.wav',
        outputFormat: Audio.IOSOutputFormat.LINEARPCM,
        sampleRate: 16000,
        numberOfChannels: 1,
        bitRate: 256000,
        linearPCMBitDepth: 16,
        linearPCMIsBigEndian: false,
        linearPCMIsFloat: false,
      },
      web: {
        mimeType: 'audio/wav',
        bitsPerSecond: 256000,
      },
    };

    const { recording } = await Audio.Recording.createAsync(recordingOptions);
    this.recording = recording;
  }

  async stopAndSend(
    apiBase = 'http://localhost:8000',
    phone = '9876500021',
    noise = false
  ): Promise<VoiceTurnResponse> {
    if (!this.recording) {
      throw new Error('No active recording.');
    }

    await this.recording.stopAndUnloadAsync();
    const uri = this.recording.getURI();
    this.recording = null;

    if (!uri) {
      throw new Error('Recording URI is null.');
    }

    const formData = new FormData();
    formData.append('audio', {
      uri,
      name: 'voice.wav',
      type: 'audio/wav',
    } as any);
    formData.append('phone', phone);
    formData.append('noise', noise ? '1' : '0');

    const response = await fetch(`${apiBase}/api/v1/voice/turn`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Voice API error: ${response.statusText}`);
    }

    const data: VoiceTurnResponse = await response.json();

    // If TTS audio is returned, play it automatically over loudspeaker
    if (data.tts_audio_url) {
      const fullAudioUrl = data.tts_audio_url.startsWith('http')
        ? data.tts_audio_url
        : `${apiBase}${data.tts_audio_url}`;
      await this.playAudio(fullAudioUrl);
    }

    return data;
  }

  async playAudio(audioUrl: string): Promise<void> {
    try {
      if (this.sound) {
        await this.sound.unloadAsync();
      }
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        playsInSilentModeIOS: true,
        playThroughEarpieceAndroid: false, // Loudspeaker
      });
      const { sound } = await Audio.Sound.createAsync({ uri: audioUrl });
      this.sound = sound;
      await sound.playAsync();
    } catch (e) {
      console.warn('[Audio Playback Fallback]:', e);
    }
  }
}

export const voiceService = new VoiceManager();

