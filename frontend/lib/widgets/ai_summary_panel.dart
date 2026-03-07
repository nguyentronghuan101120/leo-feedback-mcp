import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/app_theme.dart';
import 'app_action_button.dart';
import 'markdown_content.dart';

class AiSummaryPanel extends StatefulWidget {
  final String? summary;

  const AiSummaryPanel({super.key, this.summary});

  @override
  State<AiSummaryPanel> createState() => _AiSummaryPanelState();
}

class _AiSummaryPanelState extends State<AiSummaryPanel> {
  bool _pinned = false;
  String? _pinnedSummary;
  bool _hovered = false;

  String? get _displaySummary =>
      _pinned ? _pinnedSummary : widget.summary;

  void _togglePin() {
    setState(() {
      if (_pinned) {
        _pinned = false;
        _pinnedSummary = null;
      } else {
        _pinned = true;
        _pinnedSummary = widget.summary;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final summary = _displaySummary;

    if (summary == null || summary.isEmpty) {
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

    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: Stack(
        children: [
          Positioned.fill(
            child: Scrollbar(
              child: SingleChildScrollView(
                padding: const EdgeInsets.only(top: 4, right: 16),
                child: MarkdownContent(data: summary),
              ),
            ),
          ),
          Positioned(
            top: 8,
            right: 8,
            child: AnimatedOpacity(
              opacity: _hovered ? 1.0 : 0.0,
              duration: const Duration(milliseconds: 150),
              child: IgnorePointer(
                ignoring: !_hovered,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    AppActionButton(
                      label: _pinned ? 'Unpin' : 'Pin',
                      icon: _pinned ? Icons.push_pin : Icons.push_pin_outlined,
                      variant: AppButtonVariant.floating,
                      color: _pinned ? AppColors.warning : null,
                      iconColor: _pinned ? AppColors.warning : null,
                      onPressed: _togglePin,
                    ),
                    const SizedBox(width: 4),
                    AppActionButton(
                      label: 'Copy',
                      icon: Icons.content_copy,
                      confirmLabel: 'Copied',
                      confirmIcon: Icons.check,
                      variant: AppButtonVariant.floating,
                      onPressed: () {
                        Clipboard.setData(ClipboardData(text: summary));
                      },
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
