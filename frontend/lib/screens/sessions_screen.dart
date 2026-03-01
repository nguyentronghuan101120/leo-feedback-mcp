import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../services/session_history_service.dart';
import '../theme/app_theme.dart';
import '../widgets/app_action_button.dart';
import '../widgets/markdown_content.dart';

class SessionsScreen extends StatefulWidget {
  const SessionsScreen({super.key});

  @override
  State<SessionsScreen> createState() => _SessionsScreenState();
}

class _SessionsScreenState extends State<SessionsScreen> {
  String? _expandedEntryId;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _buildHeader(context),
        Expanded(child: _buildContent(context)),
      ],
    );
  }

  Widget _buildHeader(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final history = context.watch<SessionHistoryService>();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: const BoxDecoration(
        color: AppColors.bgTertiary,
        border: Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Row(
        children: [
          const Icon(Icons.history, color: AppColors.textPrimary),
          const SizedBox(width: 6),
          Text('Session History', style: tt.titleSmall),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: AppColors.accent.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              '${history.sessions.length}',
              style: tt.labelSmall?.copyWith(color: AppColors.accent),
            ),
          ),
          const Spacer(),
          if (history.sessions.isNotEmpty)
            IconButton(
              onPressed: () => _confirmClearAll(context),
              icon: const Icon(
                Icons.delete_sweep,
                color: AppColors.textSecondary,
              ),
              tooltip: 'Clear all history',
              constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
              padding: EdgeInsets.zero,
            ),
          IconButton(
            onPressed: () => context.read<SessionHistoryService>().load(),
            icon: const Icon(Icons.refresh, color: AppColors.textSecondary),
            tooltip: 'Refresh',
            constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
            padding: EdgeInsets.zero,
          ),
        ],
      ),
    );
  }

  Widget _buildContent(BuildContext context) {
    final history = context.watch<SessionHistoryService>();
    final tt = Theme.of(context).textTheme;

    if (!history.loaded) {
      return const Center(child: CircularProgressIndicator(strokeWidth: 2));
    }

    if (history.sessions.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.history, size: 48, color: AppColors.textSecondary),
            const SizedBox(height: 12),
            Text('No session history yet', style: tt.bodyMedium),
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
      padding: const EdgeInsets.all(12),
      itemCount: history.sessions.length,
      itemBuilder: (context, index) {
        final session = history.sessions[index];
        final isCurrent = session.entryId == history.latestEntryId;
        final isExpanded = _expandedEntryId == session.entryId;
        return _buildSessionCard(context, session, isCurrent, isExpanded);
      },
    );
  }

  Widget _buildSessionCard(
    BuildContext context,
    SessionRecord session,
    bool isCurrent,
    bool isExpanded,
  ) {
    final tt = Theme.of(context).textTheme;
    final timeStr = session.createdAt > 0
        ? _formatTime(DateTime.fromMillisecondsSinceEpoch(session.createdAt))
        : 'Unknown';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppColors.bgSecondary,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isCurrent ? AppColors.accent : AppColors.border,
          width: isCurrent ? 1.5 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: () {
              setState(() {
                _expandedEntryId = isExpanded ? null : session.entryId;
              });
            },
            borderRadius: const BorderRadius.vertical(top: Radius.circular(8)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            if (isCurrent) ...[
                              Container(
                                width: 8,
                                height: 8,
                                decoration: const BoxDecoration(
                                  color: AppColors.accent,
                                  shape: BoxShape.circle,
                                ),
                              ),
                              const SizedBox(width: 6),
                            ],
                            Flexible(
                              child: Text(
                                _extractTitle(session.summary),
                                style: tt.bodyMedium?.copyWith(
                                  color: AppColors.textPrimary,
                                  fontWeight: isCurrent
                                      ? FontWeight.w600
                                      : FontWeight.w500,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Text(timeStr, style: tt.labelSmall),
                            const SizedBox(width: 8),
                            _buildStatusBadge(
                              context,
                              session.status,
                              isCurrent,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  Icon(
                    isExpanded ? Icons.expand_less : Icons.expand_more,
                    color: AppColors.textSecondary,
                  ),
                ],
              ),
            ),
          ),
          if (isExpanded) _buildExpandedContent(context, session, isCurrent),
        ],
      ),
    );
  }

  Widget _buildStatusBadge(
    BuildContext context,
    String status,
    bool isCurrent,
  ) {
    final tt = Theme.of(context).textTheme;

    Color bgColor;
    Color textColor;
    String label;

    if (isCurrent) {
      bgColor = AppColors.accent.withValues(alpha: 0.2);
      textColor = AppColors.accent;
      label = 'Current';
    } else {
      switch (status) {
        case 'completed':
        case 'feedback_submitted':
          bgColor = AppColors.success.withValues(alpha: 0.2);
          textColor = AppColors.success;
          label = status == 'completed' ? 'Completed' : 'Submitted';
          break;
        case 'active':
        case 'waiting':
          bgColor = AppColors.warning.withValues(alpha: 0.2);
          textColor = AppColors.warning;
          label = status == 'active' ? 'Active' : 'Waiting';
          break;
        case 'error':
          bgColor = AppColors.error.withValues(alpha: 0.2);
          textColor = AppColors.error;
          label = 'Error';
          break;
        case 'timeout':
        case 'expired':
          bgColor = AppColors.textSecondary.withValues(alpha: 0.2);
          textColor = AppColors.textSecondary;
          label = status == 'timeout' ? 'Timeout' : 'Expired';
          break;
        default:
          bgColor = AppColors.surface;
          textColor = AppColors.textSecondary;
          label = status;
      }
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(3),
      ),
      child: Text(
        label,
        style: tt.labelSmall?.copyWith(
          color: textColor,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  Widget _buildExpandedContent(
    BuildContext context,
    SessionRecord session,
    bool isCurrent,
  ) {
    final tt = Theme.of(context).textTheme;

    return Container(
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: AppColors.border)),
      ),
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            decoration: BoxDecoration(
              color: AppColors.bgTertiary,
              borderRadius: BorderRadius.circular(6),
              border: Border.all(color: AppColors.border),
            ),
            child: MarkdownContent(
              data: session.summary.isNotEmpty
                  ? session.summary
                  : '_No summary_',
              padding: const EdgeInsets.all(10),
            ),
          ),
          if (session.feedback != null && session.feedback!.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text('Your Feedback', style: tt.titleSmall),
            const SizedBox(height: 6),
            Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: AppColors.success.withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(
                  color: AppColors.success.withValues(alpha: 0.3),
                ),
              ),
              child: MarkdownContent(
                data: session.feedback!,
                padding: const EdgeInsets.all(10),
              ),
            ),
          ],
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              AppActionButton(
                label: 'Copy Summary',
                icon: Icons.content_copy,
                confirmLabel: 'Copied',
                confirmIcon: Icons.check,
                onPressed: () => _copyToClipboard(session.summary),
              ),
              if (!isCurrent)
                AppActionButton(
                  label: 'Remove',
                  icon: Icons.delete_outline,
                  color: AppColors.error,
                  iconColor: AppColors.error,
                  onPressed: () {
                    context.read<SessionHistoryService>().removeSession(
                      session.entryId,
                    );
                    if (mounted && _expandedEntryId == session.entryId) {
                      setState(() => _expandedEntryId = null);
                    }
                  },
                ),
            ],
          ),
        ],
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
    if (diff.inDays < 7) return '${diff.inDays}d ago';

    return '${time.month}/${time.day} ${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
  }

  void _copyToClipboard(String text) {
    if (text.isEmpty) return;
    Clipboard.setData(ClipboardData(text: text));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Copied to clipboard'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  void _confirmClearAll(BuildContext context) {
    final historyService = context.read<SessionHistoryService>();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.bgSecondary,
        title: const Text('Clear all history?'),
        content: const Text('This action cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              historyService.clearAll();
              Navigator.pop(ctx);
            },
            child: const Text(
              'Clear',
              style: TextStyle(color: AppColors.error),
            ),
          ),
        ],
      ),
    );
  }
}
