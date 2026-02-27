import 'package:flutter/foundation.dart';
import 'api_service.dart';

class SessionRecord {
  final String sessionId;
  final String projectDirectory;
  final String summary;
  String? feedback;
  String status;
  final int createdAt;
  int? completedAt;

  SessionRecord({
    required this.sessionId,
    required this.projectDirectory,
    required this.summary,
    this.feedback,
    this.status = 'active',
    required this.createdAt,
    this.completedAt,
  });

  factory SessionRecord.fromJson(Map<String, dynamic> json) {
    return SessionRecord(
      sessionId: json['session_id']?.toString() ?? '',
      projectDirectory: json['project_directory']?.toString() ?? '',
      summary: json['summary']?.toString() ?? '',
      feedback: json['feedback']?.toString(),
      status: json['status']?.toString() ?? 'active',
      createdAt: _parseInt(json['created_at']),
      completedAt: json['completed_at'] != null
          ? _parseInt(json['completed_at'])
          : null,
    );
  }

  static int _parseInt(dynamic value) {
    if (value is int) return value;
    if (value is double) return value.toInt();
    if (value is String) return int.tryParse(value) ?? 0;
    return 0;
  }

  Map<String, dynamic> toJson() => {
        'session_id': sessionId,
        'project_directory': projectDirectory,
        'summary': summary,
        'feedback': feedback,
        'status': status,
        'created_at': createdAt,
        'completed_at': completedAt,
      };
}

class SessionHistoryService extends ChangeNotifier {
  List<SessionRecord> _sessions = [];
  int _lastCleanup = 0;
  bool _loaded = false;

  List<SessionRecord> get sessions => List.unmodifiable(_sessions);
  bool get loaded => _loaded;

  Future<void> load() async {
    try {
      final data = await ApiService.loadSessionHistory();
      if (data != null) {
        final list = data['sessions'] as List? ?? [];
        _sessions = list
            .whereType<Map<String, dynamic>>()
            .map(SessionRecord.fromJson)
            .toList();
        _lastCleanup = data['lastCleanup'] as int? ?? 0;
      }
    } catch (e) {
      debugPrint('Failed to load session history: $e');
    }
    _loaded = true;
    notifyListeners();
  }

  void onNewSession({
    required String sessionId,
    required String projectDirectory,
    required String summary,
  }) {
    final existing = _sessions.indexWhere((s) => s.sessionId == sessionId);
    if (existing >= 0) return;

    _sessions.insert(
      0,
      SessionRecord(
        sessionId: sessionId,
        projectDirectory: projectDirectory,
        summary: summary,
        status: 'active',
        createdAt: DateTime.now().millisecondsSinceEpoch,
      ),
    );
    notifyListeners();
    _persist();
  }

  void onFeedbackSubmitted(String sessionId, String feedback) {
    final idx = _sessions.indexWhere((s) => s.sessionId == sessionId);
    if (idx < 0) return;

    _sessions[idx].feedback = feedback;
    _sessions[idx].status = 'completed';
    _sessions[idx].completedAt = DateTime.now().millisecondsSinceEpoch;
    notifyListeners();
    _persist();
  }

  Future<void> _persist() async {
    try {
      final jsonList = _sessions.map((s) => s.toJson()).toList();
      await ApiService.saveSessionHistory(jsonList, _lastCleanup);
    } catch (e) {
      debugPrint('Failed to persist session history: $e');
    }
  }

  void removeSession(String sessionId) {
    _sessions.removeWhere((s) => s.sessionId == sessionId);
    notifyListeners();
    _persist();
  }

  void clearAll() {
    _sessions.clear();
    notifyListeners();
    _persist();
  }
}
