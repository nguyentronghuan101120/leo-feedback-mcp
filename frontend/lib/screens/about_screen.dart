import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/websocket_service.dart';
import '../theme/app_theme.dart';

class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildHeader(context),
          const SizedBox(height: 16),
          _buildInfoSection(context),
          const SizedBox(height: 16),
          _buildTechStack(context),
          const SizedBox(height: 16),
          _buildLinks(context),
          const SizedBox(height: 16),
          _buildAcknowledgments(context),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final version = context.watch<WebSocketService>().serverVersion ?? '';

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.bgSecondary,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: [
          const Icon(Icons.feedback, size: 48, color: AppColors.accent),
          const SizedBox(height: 12),
          Text('Leo Feedback MCP', style: tt.titleLarge),
          if (version.isNotEmpty) ...[
            const SizedBox(height: 4),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: AppColors.accent.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                'v$version',
                style: tt.labelSmall?.copyWith(color: AppColors.accent),
              ),
            ),
          ],
          const SizedBox(height: 8),
          Text(
            'Interactive Feedback Tool for AI Assistants',
            style: tt.bodySmall,
          ),
          const SizedBox(height: 4),
          Text(
            'by Leo Nguyen',
            style: tt.bodySmall?.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 8),
          Text(
            'Powered by Flutter Web',
            style: tt.bodySmall?.copyWith(color: AppColors.accent),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoSection(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.bgSecondary,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.info_outline, color: AppColors.textPrimary),
              const SizedBox(width: 6),
              Text('About', style: tt.titleSmall),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            'Leo Feedback MCP is a Model Context Protocol (MCP) server that enables '
            'interactive feedback between AI assistants and users through a Flutter Web UI. '
            'It establishes a feedback-oriented development workflow, guiding AI to confirm '
            'with users rather than making speculative operations.',
            style: tt.bodyMedium?.copyWith(height: 1.5),
          ),
          const SizedBox(height: 12),
          Text(
            'Features:',
            style: tt.bodySmall?.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 4),
          Text(
            '• Real-time AI summary with Markdown rendering\n'
            '• Text and image feedback (PNG, JPG, GIF, WebP, BMP)\n'
            '• Drag & drop files from IDE and file system\n'
            '• Clipboard image paste (Ctrl+V / Cmd+V)\n'
            '• Session management and history\n'
            '• Auto-submit with configurable countdown & prompts\n'
            '• Audio & browser notifications on new sessions\n'
            '• Keyboard shortcuts (Ctrl+Enter / Cmd+Enter)\n'
            '• Resizable split-panel layout\n'
            '• WSL / SSH remote environment support\n'
            '• Smart browser tab reuse\n'
            '• Dark theme optimized for development',
            style: tt.bodySmall?.copyWith(height: 1.6),
          ),
        ],
      ),
    );
  }

  Widget _buildTechStack(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.bgSecondary,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.build, color: AppColors.textPrimary),
              const SizedBox(width: 6),
              Text('Tech Stack', style: tt.titleSmall),
            ],
          ),
          const SizedBox(height: 12),
          _buildTechItem(context, 'Frontend', 'Flutter Web (Dart)'),
          _buildTechItem(context, 'State Mgmt', 'Provider'),
          _buildTechItem(context, 'Backend', 'FastAPI + uvicorn (Python)'),
          _buildTechItem(context, 'MCP Server', 'FastMCP'),
          _buildTechItem(context, 'Protocol', 'Model Context Protocol (MCP)'),
          _buildTechItem(context, 'Communication', 'WebSocket + REST API'),
          _buildTechItem(context, 'Markdown', 'flutter_markdown'),
          _buildTechItem(context, 'Python', '>=3.11'),
        ],
      ),
    );
  }

  Widget _buildTechItem(BuildContext context, String label, String value) {
    final tt = Theme.of(context).textTheme;

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          SizedBox(
            width: 120,
            child: Text(label, style: tt.bodySmall),
          ),
          Flexible(
            child: Text(
              value,
              style: tt.bodySmall?.copyWith(color: AppColors.textPrimary),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLinks(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.bgSecondary,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.link, color: AppColors.textPrimary),
              const SizedBox(width: 6),
              Text('Links', style: tt.titleSmall),
            ],
          ),
          const SizedBox(height: 12),
          _buildLinkItem(context, 'PyPI', 'pip install leo-feedback-mcp'),
          _buildLinkItem(context, 'Install', 'uvx leo-feedback-mcp'),
          _buildLinkItem(context, 'License', 'MIT License'),
        ],
      ),
    );
  }

  Widget _buildLinkItem(BuildContext context, String label, String value) {
    final tt = Theme.of(context).textTheme;

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          SizedBox(
            width: 80,
            child: Text(
              label,
              style: tt.bodySmall?.copyWith(color: AppColors.accent),
            ),
          ),
          Flexible(
            child: Text(
              value,
              style: tt.bodySmall?.copyWith(
                color: AppColors.textPrimary,
                fontFamily: 'monospace',
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAcknowledgments(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.bgSecondary,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.favorite_outline, color: AppColors.textPrimary),
              const SizedBox(width: 6),
              Text('Acknowledgments', style: tt.titleSmall),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            'Inspired by and built upon:',
            style: tt.bodySmall?.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 8),
          Text(
            '• mcp-feedback-enhanced by Minidoracat\n'
            '• interactive-feedback-mcp by Fábio Ferreira (noopstudios)',
            style: tt.bodySmall?.copyWith(height: 1.6),
          ),
        ],
      ),
    );
  }
}
