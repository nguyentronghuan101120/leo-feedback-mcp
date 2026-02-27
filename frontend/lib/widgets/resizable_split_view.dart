import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../theme/app_theme.dart';

class ResizableSplitView extends StatefulWidget {
  final Widget left;
  final Widget right;
  final double initialRatio;
  final double minPanelSize;

  const ResizableSplitView({
    super.key,
    required this.left,
    required this.right,
    this.initialRatio = 0.5,
    this.minPanelSize = 200,
  });

  @override
  State<ResizableSplitView> createState() => _ResizableSplitViewState();
}

class _ResizableSplitViewState extends State<ResizableSplitView> {
  late double _ratio;
  bool _isDragging = false;
  static const _storageKey = 'mcp-resize-ratio';

  @override
  void initState() {
    super.initState();
    _ratio = widget.initialRatio;
    _loadSavedRatio();
  }

  Future<void> _loadSavedRatio() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    final saved = prefs.getDouble(_storageKey);
    if (saved != null && saved > 0.1 && saved < 0.9) {
      setState(() => _ratio = saved);
    }
  }

  Future<void> _saveRatio() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_storageKey, _ratio);
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final totalWidth = constraints.maxWidth;
        const handleWidth = 6.0;
        final availableWidth = totalWidth - handleWidth;
        final maxLeft = (availableWidth - widget.minPanelSize).clamp(0.0, availableWidth);
        final minLeft = widget.minPanelSize.clamp(0.0, maxLeft);
        final leftWidth = (availableWidth * _ratio).clamp(minLeft, maxLeft);
        final rightWidth = availableWidth - leftWidth;

        return Row(
          children: [
            SizedBox(
              width: leftWidth,
              child: widget.left,
            ),
            MouseRegion(
              cursor: SystemMouseCursors.resizeColumn,
              child: GestureDetector(
                onHorizontalDragStart: (_) {
                  setState(() => _isDragging = true);
                },
                onHorizontalDragUpdate: (details) {
                  setState(() {
                    final newLeft = leftWidth + details.delta.dx;
                    _ratio = (newLeft / availableWidth).clamp(
                      widget.minPanelSize / availableWidth,
                      1 - widget.minPanelSize / availableWidth,
                    );
                  });
                },
                onHorizontalDragEnd: (_) {
                  setState(() => _isDragging = false);
                  _saveRatio();
                },
                child: Container(
                  width: handleWidth,
                  color: _isDragging
                      ? AppColors.accent
                      : AppColors.border,
                  child: Center(
                    child: Container(
                      width: 2,
                      height: 40,
                      decoration: BoxDecoration(
                        color: _isDragging
                            ? Colors.white.withValues(alpha: 0.8)
                            : AppColors.textSecondary.withValues(alpha: 0.5),
                        borderRadius: BorderRadius.circular(1),
                      ),
                    ),
                  ),
                ),
              ),
            ),
            SizedBox(
              width: rightWidth,
              child: widget.right,
            ),
          ],
        );
      },
    );
  }
}
