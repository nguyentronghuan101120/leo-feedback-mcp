import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/websocket_service.dart';
import '../services/auto_submit_service.dart';
import '../services/session_history_service.dart';
import '../widgets/ai_summary_panel.dart';
import '../widgets/feedback_panel.dart';
import '../widgets/resizable_split_view.dart';

class WorkspaceScreen extends StatefulWidget {
  const WorkspaceScreen({super.key});

  @override
  State<WorkspaceScreen> createState() => _WorkspaceScreenState();
}

class _WorkspaceScreenState extends State<WorkspaceScreen> {
  final _feedbackKey = GlobalKey<FeedbackPanelState>();
  String? _lastSessionId;
  bool _autoSubmitCallbackSet = false;

  void _doAutoSubmit() {
    if (!mounted) return;
    final autoSubmit = context.read<AutoSubmitService>();
    final ws = context.read<WebSocketService>();
    final prompt = autoSubmit.prompt;
    if (prompt == null || prompt.isEmpty) return;
    ws.submitFeedback(feedback: prompt);
    _feedbackKey.currentState?.clearFeedback();
    if (ws.sessionId != null) {
      context.read<SessionHistoryService>().onFeedbackSubmitted(
            ws.sessionId!,
            prompt,
          );
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_autoSubmitCallbackSet) {
      _autoSubmitCallbackSet = true;
      context.read<AutoSubmitService>().setAutoSubmitCallback(_doAutoSubmit);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer2<WebSocketService, AutoSubmitService>(
      builder: (context, ws, autoSubmit, _) {

        if (ws.sessionId != null && ws.sessionId != _lastSessionId) {
          _lastSessionId = ws.sessionId;
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted) return;
            _feedbackKey.currentState?.clearFeedback();
            autoSubmit.onNewSession();
            if (ws.sessionId != null) {
              context.read<SessionHistoryService>().onNewSession(
                    sessionId: ws.sessionId!,
                    projectDirectory: ws.projectDirectory ?? '',
                    summary: ws.summary ?? '',
                  );
            }
          });
        }

        return ResizableSplitView(
          left: AiSummaryPanel(summary: ws.summary),
          right: FeedbackPanel(
            key: _feedbackKey,
            feedbackSubmitted: ws.feedbackSubmitted,
            onSubmit: (data) {
              autoSubmit.cancel();
              ws.submitFeedback(
                feedback: data.text,
                images: data.images,
              );
              if (ws.sessionId != null) {
                context.read<SessionHistoryService>().onFeedbackSubmitted(
                      ws.sessionId!,
                      data.text,
                    );
              }
            },
            onTypingStart: autoSubmit.pause,
            onTypingStop: autoSubmit.resume,
          ),
        );
      },
    );
  }
}
