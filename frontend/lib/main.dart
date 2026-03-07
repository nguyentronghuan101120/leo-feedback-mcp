import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/websocket_service.dart';
import 'services/auto_submit_service.dart';
import 'services/notification_service.dart';
import 'services/session_history_service.dart';
import 'theme/app_theme.dart';
import 'widgets/header_bar.dart';
import 'screens/workspace_screen.dart';
import 'screens/sessions_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/about_screen.dart';

void main() {
  runApp(const FeedbackApp());
}

class FeedbackApp extends StatelessWidget {
  const FeedbackApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
          create: (_) => WebSocketService()..connectToCurrentServer(),
        ),
        ChangeNotifierProvider(create: (_) => AutoSubmitService()),
        Provider(create: (_) => NotificationService()),
        ChangeNotifierProvider(create: (_) => SessionHistoryService()),
      ],
      child: MaterialApp(
        title: 'Leo Feedback MCP',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.darkTheme,
        home: const FeedbackHome(),
      ),
    );
  }
}

class FeedbackHome extends StatefulWidget {
  const FeedbackHome({super.key});

  @override
  State<FeedbackHome> createState() => _FeedbackHomeState();
}

class _FeedbackHomeState extends State<FeedbackHome> {
  int _selectedTab = 0;
  bool _notificationWired = false;
  final _rootFocusNode = FocusNode();

  static const _tabs = [
    _TabInfo(Icons.dashboard, 'Workspace'),
    _TabInfo(Icons.history, 'Sessions'),
    _TabInfo(Icons.settings, 'Settings'),
    _TabInfo(Icons.info_outline, 'About'),
  ];

  @override
  void dispose() {
    _rootFocusNode.dispose();
    super.dispose();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_notificationWired) {
      _notificationWired = true;
      final ws = context.read<WebSocketService>();
      final notif = context.read<NotificationService>();
      final autoSubmit = context.read<AutoSubmitService>();
      ws.onSessionUpdated = () {
        notif.onNewSession();
        autoSubmit.onNewSession();
      };
    }
  }

  void _onUserInteraction() {
    context.read<NotificationService>().unlockAudio();
  }

  @override
  Widget build(BuildContext context) {
    return KeyboardListener(
      focusNode: _rootFocusNode,
      autofocus: true,
      onKeyEvent: (_) => _onUserInteraction(),
      child: GestureDetector(
        onTap: _onUserInteraction,
        behavior: HitTestBehavior.translucent,
        child: Scaffold(
          body: Column(
            children: [
              const HeaderBar(),
              _buildTabBar(context),
              Expanded(child: _buildTabContent()),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTabBar(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    return Container(
      decoration: const BoxDecoration(
        color: AppColors.bgSecondary,
        border: Border(bottom: BorderSide(color: AppColors.border, width: 1)),
      ),
      child: Row(
        children: List.generate(_tabs.length, (index) {
          final tab = _tabs[index];
          final isSelected = _selectedTab == index;
          return InkWell(
            onTap: () => setState(() => _selectedTab = index),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: isSelected ? AppColors.bgTertiary : Colors.transparent,
                border: Border(
                  bottom: BorderSide(
                    color: isSelected ? AppColors.accent : Colors.transparent,
                    width: 2,
                  ),
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    tab.icon,
                    size: 15,
                    color: isSelected ? AppColors.textPrimary : AppColors.textSecondary,
                  ),
                  const SizedBox(width: 5),
                  Text(
                    tab.label,
                    style: isSelected ? tt.labelMedium?.copyWith(color: AppColors.textPrimary, fontWeight: FontWeight.w600) : tt.labelMedium,
                  ),
                ],
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _buildTabContent() {
    return IndexedStack(
      index: _selectedTab,
      children: const [
        WorkspaceScreen(),
        SessionsScreen(),
        SettingsScreen(),
        AboutScreen(),
      ],
    );
  }
}

class _TabInfo {
  final IconData icon;
  final String label;
  const _TabInfo(this.icon, this.label);
}
