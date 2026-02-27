import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AutoSubmitService extends ChangeNotifier {
  bool _enabled = false;
  int _timeoutSeconds = 30;
  String? _prompt;
  int _remaining = 0;
  Timer? _timer;
  bool _paused = false;
  bool _active = false;

  bool get enabled => _enabled;
  int get timeoutSeconds => _timeoutSeconds;
  String? get prompt => _prompt;
  int get remaining => _remaining;
  bool get isCountingDown => _active && !_paused && _remaining > 0;
  bool get isPaused => _active && _paused;

  AutoSubmitService() {
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    _enabled = prefs.getBool('auto_submit_enabled') ?? false;
    _timeoutSeconds = prefs.getInt('auto_submit_timeout') ?? 30;
    _prompt = prefs.getString('auto_submit_prompt');
    notifyListeners();
  }

  Future<void> reload() async {
    final wasActive = _active;
    await _loadSettings();
    if (wasActive && (!_enabled || _prompt == null || _prompt!.isEmpty)) {
      cancel();
    }
  }

  /// Called when a new AI response/session arrives.
  void onNewSession() {
    if (!_enabled || _prompt == null || _prompt!.isEmpty) return;
    _remaining = _timeoutSeconds;
    _paused = false;
    _active = true;
    _startTimer();
    notifyListeners();
  }

  /// Pause countdown (e.g. user starts typing).
  void pause() {
    if (!_active) return;
    _paused = true;
    _timer?.cancel();
    notifyListeners();
  }

  /// Resume countdown (e.g. user stops typing).
  void resume() {
    if (!_active || !_paused) return;
    _paused = false;
    _startTimer();
    notifyListeners();
  }

  /// Cancel the current countdown without submitting.
  void cancel() {
    _timer?.cancel();
    _active = false;
    _paused = false;
    _remaining = 0;
    notifyListeners();
  }

  VoidCallback? _onAutoSubmit;

  void setAutoSubmitCallback(VoidCallback callback) {
    _onAutoSubmit = callback;
  }

  void _startTimer() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (_remaining <= 1) {
        _timer?.cancel();
        _remaining = 0;
        _active = false;
        notifyListeners();
        _onAutoSubmit?.call();
      } else {
        _remaining--;
        notifyListeners();
      }
    });
  }

  String get formattedRemaining {
    final m = _remaining ~/ 60;
    final s = _remaining % 60;
    if (m > 0) return '${m}m ${s.toString().padLeft(2, '0')}s';
    return '${s}s';
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}
