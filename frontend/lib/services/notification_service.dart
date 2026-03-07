import 'package:flutter/foundation.dart';
import 'dart:js_interop';
import 'package:web/web.dart' as web;

/// Always-on notification service.
/// Plays a beep and shows a browser notification when a new AI response arrives.
///
/// Uses a persistent AudioContext that is "unlocked" on the first user
/// interaction so that subsequent beeps work even when the tab is in
/// the background.
class NotificationService {
  bool _permissionRequested = false;
  web.AudioContext? _audioCtx;
  bool _audioUnlocked = false;

  void onNewSession() {
    _ensureNotifPermission();
    _playBeep();
    _showNotification();
  }

  /// Call once on any user gesture (click, keypress) to unlock audio
  /// for background playback.
  void unlockAudio() {
    if (_audioUnlocked) return;
    _audioUnlocked = true;

    try {
      _audioCtx ??= web.AudioContext();
      final ctx = _audioCtx!;

      if (ctx.state == 'suspended') {
        ctx.resume().toDart.then((_) {
          _playSilent(ctx);
          debugPrint('Audio unlocked via resume');
        }).catchError((e) {
          debugPrint('Audio unlock resume error: $e');
        });
      } else {
        _playSilent(ctx);
        debugPrint('Audio unlocked');
      }
    } catch (e) {
      debugPrint('Audio unlock error: $e');
    }
  }

  /// Play a near-silent tone to establish audio permission for the tab.
  void _playSilent(web.AudioContext ctx) {
    final osc = ctx.createOscillator();
    final gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    gain.gain.setValueAtTime(0.001, ctx.currentTime);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.05);
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
      _audioCtx ??= web.AudioContext();
      final ctx = _audioCtx!;

      void doPlay() {
        final osc = ctx.createOscillator();
        final gain = ctx.createGain();

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.type = 'sine';

        final now = ctx.currentTime;
        gain.gain.setValueAtTime(0.5, now);

        osc.frequency.setValueAtTime(660, now);
        osc.frequency.setValueAtTime(440, now + 0.15);
        gain.gain.setValueAtTime(0.5, now + 0.15);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.4);

        osc.start(now);
        osc.stop(now + 0.4);
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

      final notif = web.Notification(
        'Leo Feedback MCP',
        web.NotificationOptions(body: 'New AI response is ready for your feedback.'),
      );
      notif.addEventListener(
        'click',
        ((web.Event e) {
          web.window.focus();
          notif.close();
        }).toJS,
      );
    } catch (e) {
      debugPrint('Browser notification error: $e');
    }
  }
}
