import 'package:flutter/foundation.dart';

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
}

class SessionHistoryService extends ChangeNotifier {
  static const _maxSessions = 50;

  final List<SessionRecord> _sessions = [];

  List<SessionRecord> get sessions => List.unmodifiable(_sessions);
  bool get loaded => true;

  String? _latestEntryId;
  String? get latestEntryId => _latestEntryId;

  void onNewSession({
    required String sessionId,
    required String projectDirectory,
    required String summary,
  }) {
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
    notifyListeners();
  }

  void _trimSessions() {
    if (_sessions.length > _maxSessions) {
      _sessions.removeRange(_maxSessions, _sessions.length);
    }
  }

  void removeSession(String entryId) {
    _sessions.removeWhere((s) => s.entryId == entryId);
    notifyListeners();
  }

  void clearAll() {
    _sessions.clear();
    notifyListeners();
  }
}
