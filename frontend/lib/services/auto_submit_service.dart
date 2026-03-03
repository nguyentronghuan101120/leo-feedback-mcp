import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web/web.dart' as web;

class AutoSubmitService extends ChangeNotifier {
  static const defaultTimeout = 120;

  bool _enabled = false;
  int _timeoutSeconds = defaultTimeout;
  String? _prompt;
  int _remaining = 0;
  Timer? _timer;
  bool _paused = false;
  bool _active = false;

  DateTime? _targetTime;

  bool get enabled => _enabled;
  int get timeoutSeconds => _timeoutSeconds;
  String? get prompt => _prompt;
  int get remaining => _remaining;
  bool get isCountingDown => _active && !_paused && _remaining > 0;
  bool get isPaused => _active && _paused;

  AutoSubmitService() {
    _loadSettings();
    _setupVisibilityListener();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    _enabled = prefs.getBool('auto_submit_enabled') ?? false;
    _timeoutSeconds = prefs.getInt('auto_submit_timeout') ?? defaultTimeout;
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

  void onNewSession() {
    if (!_enabled || _prompt == null || _prompt!.isEmpty) return;
    _targetTime = DateTime.now().add(Duration(seconds: _timeoutSeconds));
    _remaining = _timeoutSeconds;
    _paused = false;
    _active = true;
    _startTimer();
    notifyListeners();
  }

  void pause() {
    if (!_active) return;
    _paused = true;
    _timer?.cancel();
    notifyListeners();
  }

  void resume() {
    if (!_active || !_paused) return;
    _paused = false;
    _targetTime = DateTime.now().add(Duration(seconds: _remaining));
    _startTimer();
    notifyListeners();
  }

  void cancel() {
    _timer?.cancel();
    _active = false;
    _paused = false;
    _remaining = 0;
    _targetTime = null;
    notifyListeners();
  }

  VoidCallback? _onAutoSubmit;

  void setAutoSubmitCallback(VoidCallback callback) {
    _onAutoSubmit = callback;
  }

  void _startTimer() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      _updateRemaining();
    });
  }

  void _updateRemaining() {
    if (_targetTime == null || !_active || _paused) return;

    final now = DateTime.now();
    final diff = _targetTime!.difference(now).inSeconds;

    if (diff <= 0) {
      _timer?.cancel();
      _remaining = 0;
      _active = false;
      _targetTime = null;
      notifyListeners();
      _onAutoSubmit?.call();
    } else {
      _remaining = diff;
      notifyListeners();
    }
  }

  void _setupVisibilityListener() {
    web.document.onVisibilityChange.listen((_) {
      if (web.document.visibilityState == 'visible') {
        _onTabVisible();
      }
    });
  }

  void _onTabVisible() {
    if (!_active || _paused || _targetTime == null) return;
    _updateRemaining();
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
