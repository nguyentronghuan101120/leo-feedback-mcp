import 'package:flutter/material.dart';
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
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    final tt = Theme.of(context).textTheme;

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
          const SizedBox(height: 4),
          Text('Interactive Feedback Tool for AI Assistants', style: tt.bodySmall),
          const SizedBox(height: 8),
          Text('Powered by Flutter Web', style: tt.bodySmall?.copyWith(color: AppColors.accent)),
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
            'interactive feedback between AI assistants and users through a web-based UI.',
            style: tt.bodyMedium?.copyWith(height: 1.5),
          ),
          const SizedBox(height: 8),
          Text(
            'Features:\n'
            '• Real-time AI summary with Markdown rendering\n'
            '• Text and image feedback submission\n'
            '• Session management and history\n'
            '• Auto-submit with configurable countdown\n'
            '• Resizable split-panel layout\n'
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
          _buildTechItem(context, 'Backend', 'FastAPI (Python)'),
          _buildTechItem(context, 'Protocol', 'Model Context Protocol (MCP)'),
          _buildTechItem(context, 'Communication', 'WebSocket'),
          _buildTechItem(context, 'Markdown', 'flutter_markdown'),
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
          Flexible(child: Text(value, style: tt.bodySmall?.copyWith(color: AppColors.textPrimary))),
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
          Text(
            '• GitHub: github.com/noamgat/mcp-feedback-enhanced\n'
            '• License: MIT',
            style: tt.bodySmall?.copyWith(color: AppColors.accent, height: 1.6),
          ),
        ],
      ),
    );
  }
}
