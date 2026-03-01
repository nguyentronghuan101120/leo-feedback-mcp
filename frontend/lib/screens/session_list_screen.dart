import 'dart:async';
import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;
import '../services/api_service.dart';
import '../theme/app_theme.dart';

class SessionListScreen extends StatefulWidget {
  const SessionListScreen({super.key});

  @override
  State<SessionListScreen> createState() => _SessionListScreenState();
}

class _SessionListScreenState extends State<SessionListScreen> {
  List<Map<String, dynamic>> _sessions = [];
  bool _loading = true;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _loadSessions();
    _refreshTimer = Timer.periodic(
      const Duration(seconds: 5),
      (_) => _loadSessions(),
    );
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadSessions() async {
    final sessions = await ApiService.getActiveSessions();
    if (!mounted) return;
    setState(() {
      _sessions = sessions;
      _loading = false;
    });
  }

  void _openSession(String sessionId) {
    final uri = Uri.base;
    final url = '${uri.scheme}://${uri.host}:${uri.port}/session/$sessionId';
    web.window.open(url, '_blank');
  }

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    return Scaffold(
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
            decoration: const BoxDecoration(
              color: AppColors.bgSecondary,
              border: Border(bottom: BorderSide(color: AppColors.border)),
            ),
            child: Row(
              children: [
                const Icon(Icons.dashboard, color: AppColors.accent, size: 20),
                const SizedBox(width: 8),
                Text('Leo Feedback MCP', style: tt.titleMedium),
                const Spacer(),
                IconButton(
                  onPressed: _loadSessions,
                  icon: const Icon(Icons.refresh, color: AppColors.textSecondary),
                  tooltip: 'Refresh',
                ),
              ],
            ),
          ),
          Expanded(child: _buildContent(context)),
        ],
      ),
    );
  }

  Widget _buildContent(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    if (_loading) {
      return const Center(child: CircularProgressIndicator(strokeWidth: 2));
    }

    if (_sessions.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.hourglass_empty, size: 48, color: AppColors.textSecondary),
            const SizedBox(height: 12),
            Text('No active sessions', style: tt.titleSmall),
            const SizedBox(height: 4),
            Text(
              'Sessions will appear here when AI calls the feedback tool',
              style: tt.bodySmall,
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _sessions.length,
      itemBuilder: (context, index) {
        final session = _sessions[index];
        return _buildSessionCard(context, session);
      },
    );
  }

  Widget _buildSessionCard(BuildContext context, Map<String, dynamic> session) {
    final tt = Theme.of(context).textTheme;
    final sessionId = session['session_id'] as String? ?? '';
    final summary = session['summary'] as String? ?? 'No summary';
    final projectDir = session['project_directory'] as String? ?? '';
    final createdAt = session['created_at'] as int? ?? 0;
    final timeStr = createdAt > 0
        ? _formatTime(DateTime.fromMillisecondsSinceEpoch(createdAt))
        : '';

    final title = _extractTitle(summary);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: AppColors.bgSecondary,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          onTap: () => _openSession(sessionId),
          borderRadius: BorderRadius.circular(8),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: AppColors.accent,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          if (projectDir.isNotEmpty) ...[
                            Icon(Icons.folder_outlined,
                                size: 12, color: AppColors.textSecondary),
                            const SizedBox(width: 4),
                            Flexible(
                              child: Text(
                                projectDir,
                                style: tt.labelSmall,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            const SizedBox(width: 8),
                          ],
                          if (timeStr.isNotEmpty)
                            Text(timeStr, style: tt.labelSmall),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.warning.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    'Waiting',
                    style: tt.labelSmall?.copyWith(
                      color: AppColors.warning,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                const Icon(Icons.open_in_new, size: 16, color: AppColors.textSecondary),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _extractTitle(String summary) {
    if (summary.isEmpty) return 'No summary';
    final firstLine = summary.split('\n').first.trim();
    final cleaned = firstLine.replaceAll(RegExp(r'^#+\s*'), '');
    if (cleaned.length > 80) return '${cleaned.substring(0, 80)}...';
    return cleaned.isNotEmpty ? cleaned : 'No summary';
  }

  String _formatTime(DateTime time) {
    final now = DateTime.now();
    final diff = now.difference(time);
    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}
