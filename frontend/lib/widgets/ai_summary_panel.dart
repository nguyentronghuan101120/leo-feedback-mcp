import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/app_theme.dart';
import 'app_action_button.dart';
import 'markdown_content.dart';

class AiSummaryPanel extends StatelessWidget {
  final String? summary;

  const AiSummaryPanel({super.key, this.summary});

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    if (summary == null || summary!.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.check_circle_outline,
              size: 32,
              color: AppColors.textSecondary,
            ),
            const SizedBox(height: 8),
            Text(
              'Waiting for AI response...',
              style: tt.bodyMedium?.copyWith(color: AppColors.textSecondary),
            ),
          ],
        ),
      );
    }

    return Stack(
      children: [
        Positioned.fill(
          child: Scrollbar(
            child: SingleChildScrollView(
              padding: const EdgeInsets.only(top: 4, right: 48),
              child: MarkdownContent(data: summary!),
            ),
          ),
        ),
        Positioned(
          top: 8,
          right: 8,
          child: AppActionButton(
            label: 'Copy Summary',
            icon: Icons.content_copy,
            confirmLabel: 'Copied',
            confirmIcon: Icons.check,
            variant: AppButtonVariant.floating,
            onPressed: () {
              Clipboard.setData(ClipboardData(text: summary!));
            },
          ),
        ),
      ],
    );
  }
}
