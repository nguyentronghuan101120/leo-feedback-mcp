import 'dart:convert';
import 'dart:async';
// ignore: avoid_web_libraries_in_flutter
import 'dart:js_interop';
import 'package:flutter/foundation.dart';
import 'package:web/web.dart' as web;

class ApiService {
  static String get _baseUrl {
    final uri = Uri.base;
    final host = uri.host;
    var port = uri.port;

    if (port != 8765 && (host == 'localhost' || host == '127.0.0.1')) {
      port = 8765;
    }

    return '${uri.scheme}://$host:$port';
  }

  static Future<Map<String, dynamic>?> getInitialData() async {
    return _get('/api/initial-data');
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

  static Future<Map<String, dynamic>?> loadSessionHistory() async {
    return _get('/api/load-session-history');
  }

  static Future<bool> saveSessionHistory(
      List<Map<String, dynamic>> sessions, int lastCleanup) async {
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
      request.send(jsonEncode({
        'sessions': sessions,
        'lastCleanup': lastCleanup,
      }).toJS);
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
