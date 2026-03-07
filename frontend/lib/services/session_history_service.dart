import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web/web.dart' as web;

class SessionRecord {
  final String entryId;
  final String sessionId;
  final String projectDirectory;
  final String summary;
  String? feedback;
  String status;
  final int createdAt;
  int? completedAt;

  SessionRecord({
    required this.entryId,
    required this.sessionId,
    required this.projectDirectory,
    required this.summary,
    this.feedback,
    this.status = 'active',
    required this.createdAt,
    this.completedAt,
  });

  Map<String, dynamic> toJson() => {
        'entryId': entryId,
        'sessionId': sessionId,
        'projectDirectory': projectDirectory,
        'summary': summary,
        'feedback': feedback,
        'status': status,
        'createdAt': createdAt,
        'completedAt': completedAt,
      };

  factory SessionRecord.fromJson(Map<String, dynamic> json) => SessionRecord(
        entryId: json['entryId'] as String,
        sessionId: json['sessionId'] as String,
        projectDirectory: json['projectDirectory'] as String,
        summary: json['summary'] as String,
        feedback: json['feedback'] as String?,
        status: json['status'] as String? ?? 'active',
        createdAt: json['createdAt'] as int,
        completedAt: json['completedAt'] as int?,
      );
}

class SessionHistoryService extends ChangeNotifier {
  static const _maxSessions = 50;

  final List<SessionRecord> _sessions = [];
  bool _loaded = false;
  String? _storageKey;
  String? _currentChatSessionId;

  List<SessionRecord> get sessions => List.unmodifiable(_sessions);
  bool get loaded => _loaded;

  String? _latestEntryId;
  String? get latestEntryId => _latestEntryId;

  SessionHistoryService() {
    _initStorage();
  }

  void _initStorage() {
    try {
      final uri = Uri.base;
      _storageKey = 'session_history_${uri.port}';
      _load();
    } catch (e) {
      debugPrint('[SessionHistory] init error: $e');
      _loaded = true;
    }
  }

  void _load() {
    try {
      final raw = web.window.localStorage.getItem(_storageKey ?? '');
      if (raw != null && raw.isNotEmpty) {
        final decoded = jsonDecode(raw) as Map<String, dynamic>;
        _currentChatSessionId = decoded['chatSessionId'] as String?;
        final items = decoded['sessions'] as List<dynamic>? ?? [];
        _sessions.clear();
        for (final item in items) {
          _sessions.add(SessionRecord.fromJson(item as Map<String, dynamic>));
        }
      }
    } catch (e) {
      debugPrint('[SessionHistory] load error, clearing corrupt data: $e');
      _sessions.clear();
      _currentChatSessionId = null;
      _removeFromStorage();
    }
    _loaded = true;
    notifyListeners();
  }

  void _save() {
    if (_storageKey == null) return;
    try {
      final data = jsonEncode({
        'chatSessionId': _currentChatSessionId,
        'sessions': _sessions.map((s) => s.toJson()).toList(),
      });
      web.window.localStorage.setItem(_storageKey!, data);
    } catch (e) {
      debugPrint('[SessionHistory] save error: $e');
    }
  }

  void _removeFromStorage() {
    if (_storageKey == null) return;
    try {
      web.window.localStorage.removeItem(_storageKey!);
    } catch (e) {
      debugPrint('[SessionHistory] remove error: $e');
    }
  }

  void onNewSession({
    required String sessionId,
    required String projectDirectory,
    required String summary,
  }) {
    if (_currentChatSessionId != null &&
        _currentChatSessionId != sessionId) {
      _sessions.clear();
    }
    _currentChatSessionId = sessionId;

    final now = DateTime.now().millisecondsSinceEpoch;
    final entryId = '${sessionId}_$now';

    _latestEntryId = entryId;

    _sessions.insert(
      0,
      SessionRecord(
        entryId: entryId,
        sessionId: sessionId,
        projectDirectory: projectDirectory,
        summary: summary,
        status: 'active',
        createdAt: now,
      ),
    );
    _trimSessions();
    _save();
    notifyListeners();
  }

  void onFeedbackSubmitted(String sessionId, String feedback) {
    final idx = _sessions.indexWhere(
      (s) => s.sessionId == sessionId && s.status == 'active',
    );
    if (idx < 0) return;

    _sessions[idx].feedback = feedback;
    _sessions[idx].status = 'completed';
    _sessions[idx].completedAt = DateTime.now().millisecondsSinceEpoch;
    _save();
    notifyListeners();
  }

  void _trimSessions() {
    if (_sessions.length > _maxSessions) {
      _sessions.removeRange(_maxSessions, _sessions.length);
    }
  }

  void removeSession(String entryId) {
    _sessions.removeWhere((s) => s.entryId == entryId);
    _save();
    notifyListeners();
  }

  void clearAll() {
    _sessions.clear();
    _currentChatSessionId = null;
    _removeFromStorage();
    notifyListeners();
  }
}
