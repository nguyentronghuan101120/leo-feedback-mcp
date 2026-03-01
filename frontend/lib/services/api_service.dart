import 'dart:convert';
import 'dart:async';
// ignore: avoid_web_libraries_in_flutter
import 'dart:js_interop';
import 'package:flutter/foundation.dart';
import 'package:web/web.dart' as web;

class ApiService {
  static String get _baseUrl {
    final uri = Uri.base;
    return '${uri.scheme}://${uri.host}:${uri.port}';
  }

  /// Extract session ID from the current URL path.
  // ignore: unintended_html_in_doc_comment
  /// Expected format: /session/<session_id>
  static String? extractSessionIdFromUrl() {
    final path = Uri.base.path;
    final segments = path.split('/').where((s) => s.isNotEmpty).toList();
    if (segments.length >= 2 && segments[0] == 'session') {
      return segments[1];
    }
    return null;
  }

  static Future<Map<String, dynamic>?> getInitialData(String sessionId) async {
    return _get('/api/session/$sessionId/initial-data');
  }

  static Future<Map<String, dynamic>?> _get(String path) async {
    try {
      final completer = Completer<Map<String, dynamic>?>();
      bool completed = false;
      final request = web.XMLHttpRequest();
      request.open('GET', '$_baseUrl$path');
      request.setRequestHeader('Content-Type', 'application/json');
      request.onLoad.listen((_) {
        if (completed) return;
        completed = true;
        if (request.status == 200) {
          try {
            final text = request.responseText;
            if (text.trimLeft().startsWith('<')) {
              completer.complete(null);
              return;
            }
            final data = jsonDecode(text);
            completer.complete(data as Map<String, dynamic>?);
          } catch (e) {
            debugPrint('API parse error ($path): $e');
            completer.complete(null);
          }
        } else {
          debugPrint('API error ($path): status ${request.status}');
          completer.complete(null);
        }
      });
      request.onError.listen((_) {
        if (completed) return;
        completed = true;
        debugPrint('API network error ($path)');
        completer.complete(null);
      });
      request.send();
      return completer.future.timeout(
        const Duration(seconds: 15),
        onTimeout: () {
          if (!completed) {
            completed = true;
            request.abort();
            debugPrint('API timeout ($path)');
          }
          return null;
        },
      );
    } catch (e) {
      debugPrint('API request failed ($path): $e');
      return null;
    }
  }

  static Future<List<Map<String, dynamic>>> getActiveSessions() async {
    final data = await _get('/api/sessions/active');
    if (data == null) return [];
    final list = data['sessions'] as List? ?? [];
    return list.whereType<Map<String, dynamic>>().toList();
  }

  static Future<Map<String, dynamic>?> loadSessionHistory() async {
    return _get('/api/load-session-history');
  }

  static Future<bool> saveSessionHistory(
    List<Map<String, dynamic>> sessions,
    int lastCleanup,
  ) async {
    try {
      final request = web.XMLHttpRequest();
      final completer = Completer<bool>();
      bool completed = false;
      request.open('POST', '$_baseUrl/api/save-session-history');
      request.setRequestHeader('Content-Type', 'application/json');
      request.onLoad.listen((_) {
        if (completed) return;
        completed = true;
        completer.complete(request.status == 200);
      });
      request.onError.listen((_) {
        if (completed) return;
        completed = true;
        debugPrint('API network error (save-session-history)');
        completer.complete(false);
      });
      request.send(
        jsonEncode({'sessions': sessions, 'lastCleanup': lastCleanup}).toJS,
      );
      return completer.future.timeout(
        const Duration(seconds: 15),
        onTimeout: () {
          if (!completed) {
            completed = true;
            request.abort();
            debugPrint('API timeout (save-session-history)');
          }
          return false;
        },
      );
    } catch (e) {
      debugPrint('API request failed (save-session-history): $e');
      return false;
    }
  }
}
