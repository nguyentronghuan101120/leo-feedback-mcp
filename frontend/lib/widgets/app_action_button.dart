import 'dart:async';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

enum AppButtonVariant { outlined, floating }

class AppActionButton extends StatefulWidget {
  final String label;
  final IconData icon;
  final VoidCallback onPressed;
  final AppButtonVariant variant;
  final Color? color;
  final Color? iconColor;

  /// If non-null, after tap the button shows [confirmLabel] + [confirmIcon]
  /// for [confirmDuration] then reverts.
  final String? confirmLabel;
  final IconData? confirmIcon;
  final Duration confirmDuration;

  const AppActionButton({
    super.key,
    required this.label,
    required this.icon,
    required this.onPressed,
    this.variant = AppButtonVariant.outlined,
    this.color,
    this.iconColor,
    this.confirmLabel,
    this.confirmIcon,
    this.confirmDuration = const Duration(seconds: 2),
  });

  @override
  State<AppActionButton> createState() => _AppActionButtonState();
}

class _AppActionButtonState extends State<AppActionButton> {
  bool _confirmed = false;
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _handleTap() {
    widget.onPressed();
    if (widget.confirmLabel != null) {
      setState(() => _confirmed = true);
      _timer?.cancel();
      _timer = Timer(widget.confirmDuration, () {
        if (mounted) setState(() => _confirmed = false);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return widget.variant == AppButtonVariant.floating
        ? _buildFloating(context)
        : _buildOutlined(context);
  }

  IconData get _effectiveIcon =>
      _confirmed ? (widget.confirmIcon ?? widget.icon) : widget.icon;

  String get _effectiveLabel =>
      _confirmed ? (widget.confirmLabel ?? widget.label) : widget.label;

  TextStyle? _baseTextStyle(BuildContext context) =>
      Theme.of(context).textTheme.labelMedium?.copyWith(
            fontWeight: FontWeight.w500,
          );

  Widget _buildOutlined(BuildContext context) {
    final effectiveColor = widget.color;
    final effectiveIconColor = widget.iconColor ?? effectiveColor;

    return OutlinedButton.icon(
      onPressed: _handleTap,
      icon: Icon(_effectiveIcon, size: 14, color: effectiveIconColor),
      label: Text(
        _effectiveLabel,
        style: _baseTextStyle(context)?.copyWith(
          color: effectiveColor,
        ),
      ),
    );
  }

  Widget _buildFloating(BuildContext context) {
    final effectiveColor = widget.color;
    final effectiveIconColor = widget.iconColor ?? effectiveColor;
    final borderColor = _confirmed
        ? AppColors.success
        : effectiveColor ?? AppColors.border;

    return Material(
      color: Colors.transparent,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        decoration: BoxDecoration(
          color: _confirmed
              ? AppColors.success.withValues(alpha: 0.9)
              : AppColors.bgTertiary.withValues(alpha: 0.9),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: borderColor),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: InkWell(
          onTap: _handleTap,
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  _effectiveIcon,
                  size: 14,
                  color: _confirmed
                      ? Colors.white
                      : effectiveIconColor ?? AppColors.textSecondary,
                ),
                const SizedBox(width: 4),
                Text(
                  _effectiveLabel,
                  style: _baseTextStyle(context)?.copyWith(
                    color: _confirmed
                        ? Colors.white
                        : effectiveColor ?? AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
