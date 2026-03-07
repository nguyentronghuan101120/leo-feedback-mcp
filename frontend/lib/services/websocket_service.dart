import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'api_service.dart';

enum WsConnectionState { disconnected, connecting, connected }

class WebSocketService extends ChangeNotifier {
  WebSocketChannel? _channel;
  StreamSubscription? _streamSubscription;
  WsConnectionState _connectionState = WsConnectionState.disconnected;
  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;
  int _reconnectAttempts = 0;
  bool _disposed = false;
  static const _maxReconnectAttempts = 10;

  String? _summary;
  String? _projectDirectory;
  String? _sessionId;
  String? _serverVersion;
  bool _feedbackSubmitted = false;
  int _sessionVersion = 0;

  WsConnectionState get connectionState => _connectionState;
  String? get summary => _summary;
  String? get projectDirectory => _projectDirectory;
  String? get sessionId => _sessionId;
  String? get serverVersion => _serverVersion;
  bool get feedbackSubmitted => _feedbackSubmitted;
  int get sessionVersion => _sessionVersion;

  bool get hasSession => _summary != null;

  VoidCallback? onSessionUpdated;

  final _commandOutputController = StreamController<String>.broadcast();
  Stream<String> get commandOutput => _commandOutputController.stream;

  final _commandCompleteController = StreamController<int>.broadcast();
  Stream<int> get commandComplete => _commandCompleteController.stream;

  final _notificationController =
      StreamController<Map<String, dynamic>>.broadcast();
  Stream<Map<String, dynamic>> get notifications =>
      _notificationController.stream;

  void connect(String url) {
    if (_disposed) return;
    if (_connectionState == WsConnectionState.connected) return;

    _streamSubscription?.cancel();
    _channel?.sink.close();

    _connectionState = WsConnectionState.connecting;
    notifyListeners();

    try {
      _channel = WebSocketChannel.connect(Uri.parse(url));
      _streamSubscription = _channel!.stream.listen(
        _onMessage,
        onError: _onError,
        onDone: _onDone,
      );
      _connectionState = WsConnectionState.connected;
      _reconnectAttempts = 0;
      _reconnectTimer?.cancel();
      _startHeartbeat();
      notifyListeners();
    } catch (e) {
      debugPrint('WebSocket connect error: $e');
      _connectionState = WsConnectionState.disconnected;
      notifyListeners();
      _scheduleReconnect();
    }
  }

  void _onMessage(dynamic data) {
    if (_disposed) return;
    if (data is! String) return;

    try {
      final message = jsonDecode(data) as Map<String, dynamic>;
      final type = message['type'] as String?;

      switch (type) {
        case 'connection_established':
          _sendMessage({'type': 'get_status'});
          break;

        case 'session_updated':
          final sessionInfo = message['session_info'] as Map<String, dynamic>?;
          if (sessionInfo != null) {
            _summary = sessionInfo['summary'] as String? ?? _summary;
            _projectDirectory =
                sessionInfo['project_directory'] as String? ??
                    _projectDirectory;
            _sessionId = sessionInfo['session_id'] as String? ?? _sessionId;
            _feedbackSubmitted = false;
            _sessionVersion++;
            notifyListeners();
            onSessionUpdated?.call();
          }
          break;

        case 'status_update':
          final statusInfo = message['status_info'] as Map<String, dynamic>?;
          if (statusInfo != null) {
            _summary = statusInfo['summary'] as String? ?? _summary;
            _projectDirectory =
                statusInfo['project_directory'] as String? ??
                _projectDirectory;
            _sessionId = statusInfo['session_id'] as String? ?? _sessionId;
            _feedbackSubmitted =
                statusInfo['feedback_completed'] as bool? ?? false;
            notifyListeners();
          }
          break;

        case 'ping':
          _sendMessage({
            'type': 'pong',
            'timestamp': DateTime.now().millisecondsSinceEpoch,
          });
          break;

        case 'heartbeat_response':
          break;

        case 'notification':
          _notificationController.add(message);
          final code = message['code'] as String?;
          if (code == 'session.feedbackSubmitted') {
            _feedbackSubmitted = true;
            notifyListeners();
          }
          break;

        case 'command_output':
          _commandOutputController.add(message['output'] as String? ?? '');
          break;

        case 'command_complete':
          _commandCompleteController.add(message['exit_code'] as int? ?? -1);
          break;

        case 'command_error':
          _commandOutputController.add(
            'Error: ${message['error'] ?? 'Unknown error'}',
          );
          break;
      }
    } catch (e) {
      debugPrint('WebSocket message parse error: $e');
    }
  }

  void _onError(dynamic error) {
    debugPrint('WebSocket error: $error');
    _connectionState = WsConnectionState.disconnected;
    if (!_disposed) notifyListeners();
    _scheduleReconnect();
  }

  void _onDone() {
    debugPrint('WebSocket closed');
    _connectionState = WsConnectionState.disconnected;
    _heartbeatTimer?.cancel();
    if (!_disposed) notifyListeners();
    _scheduleReconnect();
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      _sendMessage({
        'type': 'heartbeat',
        'timestamp': DateTime.now().millisecondsSinceEpoch,
      });
    });
  }

  void _scheduleReconnect() {
    if (_disposed) return;
    if (_reconnectAttempts >= _maxReconnectAttempts) return;
    _reconnectTimer?.cancel();
    final delay = Duration(seconds: (_reconnectAttempts + 1) * 2);
    _reconnectTimer = Timer(delay, () async {
      if (_disposed) return;
      _reconnectAttempts++;
      await _fetchInitialData();
      final wsUrl = _buildWsUrl();
      connect(wsUrl);
    });
  }

  String _buildWsUrl() {
    final uri = Uri.base;
    final port = ApiService.debugBackendPort ?? uri.port;
    final wsScheme = uri.scheme == 'https' ? 'wss' : 'ws';
    return '$wsScheme://${uri.host}:$port/ws';
  }

  void _sendMessage(Map<String, dynamic> message) {
    if (_channel != null && _connectionState == WsConnectionState.connected) {
      _channel!.sink.add(jsonEncode(message));
    }
  }

  bool submitFeedback({
    required String feedback,
    List<Map<String, dynamic>>? images,
  }) {
    if (_channel == null || _connectionState != WsConnectionState.connected) {
      debugPrint('Cannot submit feedback: WebSocket not connected');
      return false;
    }
    _sendMessage({
      'type': 'submit_feedback',
      'feedback': feedback,
      'images': images ?? [],
      'settings': {},
    });
    return true;
  }

  void runCommand(String command) {
    _sendMessage({'type': 'run_command', 'command': command});
  }

  Future<void> connectToCurrentServer() async {
    await _fetchInitialData();
    final wsUrl = _buildWsUrl();
    connect(wsUrl);
  }

  Future<void> _fetchInitialData() async {
    try {
      final data = await ApiService.getInitialData();
      if (data != null && !_disposed) {
        _summary = data['summary'] as String?;
        _projectDirectory = data['project_directory'] as String?;
        _sessionId = data['session_id'] as String?;
        _serverVersion = data['version'] as String?;
        notifyListeners();
      }
    } catch (e) {
      debugPrint('Failed to fetch initial data: $e');
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _heartbeatTimer?.cancel();
    _reconnectTimer?.cancel();
    _streamSubscription?.cancel();
    _channel?.sink.close();
    _commandOutputController.close();
    _commandCompleteController.close();
    _notificationController.close();
    super.dispose();
  }
}
