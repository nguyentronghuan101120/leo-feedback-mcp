import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:web/web.dart' as web;
import '../theme/app_theme.dart';

class AiSummaryPanel extends StatelessWidget {
  final String? summary;

  const AiSummaryPanel({super.key, this.summary});

  @override
  Widget build(BuildContext context) {
    return _buildContent(context);
  }

  Widget _buildContent(BuildContext context) {
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

    return Align(
      alignment: Alignment.topLeft,
      child: Theme(
        data: Theme.of(context).copyWith(
          textSelectionTheme: TextSelectionThemeData(
            selectionColor: AppColors.accent.withValues(alpha: 0.5),
          ),
        ),
        child: SelectionArea(
          child: Scrollbar(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(14),
              child: MarkdownBody(
                data: summary!,
                selectable: false,
                styleSheet: _markdownStyleSheet(context),
                onTapLink: (text, href, title) {
                  if (href != null && href.isNotEmpty) {
                    web.window.open(href, '_blank');
                  }
                },
              ),
            ),
          ),
        ),
      ),
    );
  }

  MarkdownStyleSheet _markdownStyleSheet(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    return MarkdownStyleSheet(
      p: tt.bodyMedium?.copyWith(height: 1.5),
      h1: tt.headlineLarge,
      h2: tt.headlineMedium,
      h3: tt.headlineSmall,
      h4: tt.titleMedium,
      code: tt.bodyMedium?.copyWith(
        backgroundColor: AppColors.surface.withValues(alpha: 0.1),
        fontFamily: 'monospace',
        color: const Color(0xFFCE9178),
      ),
      codeblockDecoration: BoxDecoration(
        color: AppColors.bgPrimary,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppColors.border),
      ),
      codeblockPadding: const EdgeInsets.all(12),
      blockquoteDecoration: const BoxDecoration(
        border: Border(left: BorderSide(color: AppColors.accent, width: 3)),
        color: AppColors.bgTertiary,
      ),
      blockquotePadding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      listBullet: tt.bodyMedium,
      tableHead: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
      tableBody: tt.bodyMedium,
      tableBorder: TableBorder.all(color: AppColors.border, width: 1),
      tableCellsPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      horizontalRuleDecoration: const BoxDecoration(
        border: Border(top: BorderSide(color: AppColors.border, width: 1)),
      ),
      a: const TextStyle(
        color: AppColors.accent,
        decoration: TextDecoration.underline,
        decorationColor: AppColors.accent,
      ),
      strong: tt.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
      em: tt.bodyMedium?.copyWith(fontStyle: FontStyle.italic),
      del: tt.bodySmall?.copyWith(decoration: TextDecoration.lineThrough),
    );
  }
}
