import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/websocket_service.dart';
import '../services/auto_submit_service.dart';
import '../theme/app_theme.dart';

class HeaderBar extends StatelessWidget {
  const HeaderBar({super.key});

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    return Consumer2<WebSocketService, AutoSubmitService>(
      builder: (context, ws, autoSubmit, _) {
        final version = ws.serverVersion ?? '';
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          decoration: const BoxDecoration(
            color: AppColors.bgTertiary,
            border: Border(
              bottom: BorderSide(color: AppColors.border, width: 1),
            ),
          ),
          child: Row(
            children: [
              Text('Leo Feedback MCP', style: tt.titleLarge),
              if (version.isNotEmpty) ...[
                const SizedBox(width: 6),
                Text(
                  'v$version',
                  style: tt.labelSmall?.copyWith(color: AppColors.textSecondary),
                ),
              ],
              const Spacer(),
              if (autoSubmit.isCountingDown || autoSubmit.isPaused) ...[
                _AutoSubmitCountdown(service: autoSubmit),
                const SizedBox(width: 12),
              ],
              _ConnectionStatus(state: ws.connectionState),
            ],
          ),
        );
      },
    );
  }
}

class _AutoSubmitCountdown extends StatelessWidget {
  final AutoSubmitService service;

  const _AutoSubmitCountdown({required this.service});

  @override
  Widget build(BuildContext context) {
    final color = service.isPaused ? AppColors.warning : AppColors.accent;
    final label = service.isPaused
        ? 'Paused ${service.formattedRemaining}'
        : 'Auto-submit ${service.formattedRemaining}';

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          service.isPaused ? Icons.pause_circle_outline : Icons.timer,
          size: 14,
          color: color,
        ),
        const SizedBox(width: 4),
        Text(
          label,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: color,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(width: 4),
        InkWell(
          onTap: service.cancel,
          child: const Icon(
            Icons.close,
            size: 12,
            color: AppColors.textSecondary,
          ),
        ),
      ],
    );
  }
}

class _ConnectionStatus extends StatelessWidget {
  final WsConnectionState state;

  const _ConnectionStatus({required this.state});

  @override
  Widget build(BuildContext context) {
    final (color, label) = switch (state) {
      WsConnectionState.connected => (AppColors.success, 'Connected'),
      WsConnectionState.connecting => (AppColors.warning, 'Connecting...'),
      WsConnectionState.disconnected => (AppColors.error, 'Disconnected'),
    };

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 7,
          height: 7,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: color),
        ),
      ],
    );
  }
}
