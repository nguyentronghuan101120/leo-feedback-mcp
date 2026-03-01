import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:web/web.dart' as web;
import '../theme/app_theme.dart';

class MarkdownContent extends StatelessWidget {
  final String data;
  final bool selectable;
  final EdgeInsets padding;

  const MarkdownContent({
    super.key,
    required this.data,
    this.selectable = true,
    this.padding = const EdgeInsets.all(14),
  });

  @override
  Widget build(BuildContext context) {
    final body = MarkdownBody(
      data: data,
      selectable: false,
      styleSheet: _buildStyleSheet(context),
      onTapLink: (text, href, title) {
        if (href != null && href.isNotEmpty) {
          web.window.open(href, '_blank');
        }
      },
    );

    if (!selectable) {
      return Padding(padding: padding, child: body);
    }

    return Theme(
      data: Theme.of(context).copyWith(
        textSelectionTheme: TextSelectionThemeData(
          selectionColor: AppColors.accent.withValues(alpha: 0.5),
        ),
      ),
      child: SelectionArea(
        child: Padding(padding: padding, child: body),
      ),
    );
  }

  static MarkdownStyleSheet _buildStyleSheet(BuildContext context) {
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
      tableCellsPadding:
          const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
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
