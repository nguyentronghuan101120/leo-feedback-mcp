import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/auto_submit_service.dart';
import '../theme/app_theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _autoSubmitEnabled = false;
  int _autoSubmitTimeout = AutoSubmitService.defaultTimeout;
  String? _autoSubmitPrompt;

  List<String> _prompts = [];
  final _promptController = TextEditingController();
  final _timeoutController = TextEditingController();
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _promptController.dispose();
    _timeoutController.dispose();
    super.dispose();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    setState(() {
      _autoSubmitEnabled = prefs.getBool('auto_submit_enabled') ?? false;
      _autoSubmitTimeout =
          prefs.getInt('auto_submit_timeout') ??
          AutoSubmitService.defaultTimeout;
      _autoSubmitPrompt = prefs.getString('auto_submit_prompt');
      _prompts = prefs.getStringList('prompts') ?? [];
      _timeoutController.text = _autoSubmitTimeout.toString();
    });
  }

  Future<void> _saveSettings() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('auto_submit_enabled', _autoSubmitEnabled);
    await prefs.setInt('auto_submit_timeout', _autoSubmitTimeout);
    if (_autoSubmitPrompt != null) {
      await prefs.setString('auto_submit_prompt', _autoSubmitPrompt!);
    } else {
      await prefs.remove('auto_submit_prompt');
    }
    await prefs.setStringList('prompts', _prompts);

    if (mounted) {
      context.read<AutoSubmitService>().reload();
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildAutoSubmitSection(context),
          const SizedBox(height: 16),
          _buildPromptSection(context),
        ],
      ),
    );
  }

  // ─── Auto Submit ───

  Widget _buildAutoSubmitSection(BuildContext context) {
    return _SettingsCard(
      icon: Icons.timer,
      title: 'Auto Submit',
      children: [
        _buildToggle(
          context,
          'Enable Auto Submit',
          'Automatically submit selected prompt after countdown',
          _autoSubmitEnabled,
          (v) {
            setState(() => _autoSubmitEnabled = v);
            _saveSettings();
          },
        ),
        if (_autoSubmitEnabled) ...[
          const SizedBox(height: 12),
          _buildNumberInput(
            context,
            'Countdown (seconds)',
            _timeoutController,
            min: 1,
            max: 86400,
            onChanged: (v) {
              setState(() => _autoSubmitTimeout = v);
              _saveSettings();
            },
          ),
          const SizedBox(height: 12),
          _buildPromptDropdown(context),
        ],
      ],
    );
  }

  Widget _buildPromptDropdown(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Auto Submit Prompt', style: tt.bodySmall),
        const SizedBox(height: 6),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            color: AppColors.bgPrimary,
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: AppColors.border),
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: _autoSubmitPrompt,
              isExpanded: true,
              dropdownColor: AppColors.bgSecondary,
              hint: Text('Select a prompt', style: tt.bodySmall),
              items: [
                DropdownMenuItem(
                  value: null,
                  child: Text('None', style: tt.bodySmall),
                ),
                ..._prompts.map(
                  (p) => DropdownMenuItem(
                    value: p,
                    child: Text(
                      p.length > 50 ? '${p.substring(0, 50)}...' : p,
                      style: tt.bodyMedium,
                    ),
                  ),
                ),
              ],
              onChanged: (v) {
                setState(() => _autoSubmitPrompt = v);
                _saveSettings();
              },
            ),
          ),
        ),
      ],
    );
  }

  // ─── Prompt Management ───

  Widget _buildPromptSection(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    return _SettingsCard(
      icon: Icons.text_snippet_outlined,
      title: 'Prompt Management',
      children: [
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _promptController,
                style: tt.bodyMedium,
                decoration: const InputDecoration(
                  hintText: 'Enter a new prompt...',
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 8),
            ElevatedButton.icon(
              onPressed: _addPrompt,
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Add'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.accent,
                padding: const EdgeInsets.symmetric(horizontal: 12),
              ),
            ),
          ],
        ),
        if (_prompts.isNotEmpty) ...[
          const SizedBox(height: 12),
          ..._prompts.asMap().entries.map((entry) {
            return _buildPromptItem(context, entry.key, entry.value);
          }),
        ] else ...[
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Text('No prompts added yet', style: tt.bodySmall),
          ),
        ],
      ],
    );
  }

  void _addPrompt() {
    final text = _promptController.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _prompts.add(text);
      _promptController.clear();
    });
    _saveSettings();
  }

  Widget _buildPromptItem(BuildContext context, int index, String prompt) {
    final tt = Theme.of(context).textTheme;
    final isAutoSubmit = _autoSubmitPrompt == prompt;

    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: isAutoSubmit
            ? AppColors.accent.withValues(alpha: 0.1)
            : AppColors.bgTertiary,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: isAutoSubmit ? AppColors.accent : AppColors.border,
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              prompt,
              style: tt.bodySmall?.copyWith(color: AppColors.textPrimary),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (isAutoSubmit)
            Container(
              margin: const EdgeInsets.only(left: 6),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: AppColors.accent.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(3),
              ),
              child: Text(
                'Auto',
                style: tt.labelSmall?.copyWith(color: AppColors.accent),
              ),
            ),
          const SizedBox(width: 4),
          IconButton(
            onPressed: () {
              setState(() {
                _autoSubmitPrompt = _autoSubmitPrompt == prompt ? null : prompt;
              });
              _saveSettings();
            },
            icon: Icon(
              isAutoSubmit ? Icons.timer_off : Icons.timer,
              size: 16,
              color: isAutoSubmit ? AppColors.accent : AppColors.textSecondary,
            ),
            tooltip: isAutoSubmit ? 'Remove auto-submit' : 'Set as auto-submit',
            constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
            padding: EdgeInsets.zero,
          ),
          IconButton(
            onPressed: () {
              setState(() {
                if (_autoSubmitPrompt == prompt) _autoSubmitPrompt = null;
                _prompts.removeAt(index);
              });
              _saveSettings();
            },
            icon: const Icon(
              Icons.delete_outline,
              size: 16,
              color: AppColors.error,
            ),
            tooltip: 'Delete',
            constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
            padding: EdgeInsets.zero,
          ),
        ],
      ),
    );
  }

  // ─── Shared Widgets ───

  Widget _buildToggle(
    BuildContext context,
    String title,
    String subtitle,
    bool value,
    ValueChanged<bool> onChanged,
  ) {
    final tt = Theme.of(context).textTheme;

    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: tt.bodyMedium),
              const SizedBox(height: 2),
              Text(subtitle, style: tt.labelSmall),
            ],
          ),
        ),
        Switch(value: value, onChanged: onChanged),
      ],
    );
  }

  Widget _buildNumberInput(
    BuildContext context,
    String label,
    TextEditingController controller, {
    required int min,
    required int max,
    required ValueChanged<int> onChanged,
  }) {
    final tt = Theme.of(context).textTheme;

    return Row(
      children: [
        Text(label, style: tt.bodySmall),
        const Spacer(),
        SizedBox(
          width: 80,
          child: TextField(
            controller: controller,
            keyboardType: TextInputType.number,
            textAlign: TextAlign.center,
            style: tt.bodyMedium,
            decoration: const InputDecoration(isDense: true),
            onChanged: (text) {
              _debounce?.cancel();
              final n = int.tryParse(text);
              if (n == null || n < min || n > max) return;
              _debounce = Timer(const Duration(milliseconds: 500), () {
                onChanged(n);
              });
            },
          ),
        ),
        const SizedBox(width: 4),
        Text('s', style: tt.bodySmall),
      ],
    );
  }
}

class _SettingsCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final List<Widget> children;

  const _SettingsCard({
    required this.icon,
    required this.title,
    required this.children,
  });

  @override
  Widget build(BuildContext context) {
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
              Icon(icon, color: AppColors.textPrimary),
              const SizedBox(width: 8),
              Text(title, style: tt.titleSmall),
            ],
          ),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }
}
