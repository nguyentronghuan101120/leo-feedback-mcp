import 'package:flutter/foundation.dart';
import 'dart:js_interop';
import 'package:web/web.dart' as web;

/// Always-on notification service.
/// Plays a beep and shows a browser notification when a new AI response arrives.
class NotificationService {
  bool _permissionRequested = false;

  void onNewSession() {
    _ensureNotifPermission();
    _playBeep();
    _showNotification();
  }

  void _ensureNotifPermission() {
    if (_permissionRequested) return;
    _permissionRequested = true;
    try {
      if (web.Notification.permission == 'default') {
        web.Notification.requestPermission().toDart.then((_) {}).catchError((e) {
          debugPrint('Notification permission error: $e');
        });
      }
    } catch (_) {}
  }

  void _playBeep() {
    try {
      // Create a fresh AudioContext each time to avoid suspended state issues
      final ctx = web.AudioContext();

      void doPlay() {
        final osc = ctx.createOscillator();
        final gain = ctx.createGain();

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.type = 'square';

        final now = ctx.currentTime;
        gain.gain.setValueAtTime(0.8, now);

        osc.frequency.setValueAtTime(880, now);
        osc.frequency.setValueAtTime(660, now + 0.2);
        gain.gain.setValueAtTime(0.8, now + 0.2);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.5);

        osc.start(now);
        osc.stop(now + 0.5);
      }

      if (ctx.state == 'suspended') {
        ctx.resume().toDart.then((_) => doPlay()).catchError((e) {
          debugPrint('AudioContext resume error: $e');
        });
      } else {
        doPlay();
      }
    } catch (e) {
      debugPrint('Audio beep error: $e');
    }
  }

  void _showNotification() {
    try {
      if (web.Notification.permission != 'granted') return;

      web.Notification(
        'Leo Feedback MCP',
        web.NotificationOptions(body: 'New AI response is ready for your feedback.'),
      );
    } catch (e) {
      debugPrint('Browser notification error: $e');
    }
  }
}
