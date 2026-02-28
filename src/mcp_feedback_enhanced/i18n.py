#!/usr/bin/env python3
"""i18n: JSON translation files, nested keys, metadata, language detection."""

import json
import locale
import os
from pathlib import Path
from typing import Any


class I18nManager:
    """i18n manager."""

    def __init__(self):
        self._current_language = None
        self._translations = {}
        self._supported_languages = ["zh-CN", "zh-TW", "en"]
        self._fallback_language = "zh-TW"
        self._config_file = self._get_config_file_path()
        self._locales_dir = Path(__file__).parent / "web" / "locales"

        self._load_all_translations()
        self._current_language = self._detect_language()

    def _get_config_file_path(self) -> Path:
        """Get config file path."""
        config_dir = Path.home() / ".config" / "leo-feedback-mcp"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "language.json"

    def _load_all_translations(self) -> None:
        """Load all translation files."""
        self._translations = {}

        for lang_code in self._supported_languages:
            lang_dir = self._locales_dir / lang_code
            translation_file = lang_dir / "translation.json"

            if translation_file.exists():
                try:
                    with open(translation_file, encoding="utf-8") as f:
                        data = json.load(f)
                        self._translations[lang_code] = data
                except Exception:
                    self._translations[lang_code] = {}
            else:
                self._translations[lang_code] = {}

    def _detect_language(self) -> str:
        """Detect language."""
        saved_lang = self._load_saved_language()
        if saved_lang and saved_lang in self._supported_languages:
            return saved_lang

        env_lang = os.getenv("MCP_LANGUAGE", "").strip()
        if env_lang and env_lang in self._supported_languages:
            return env_lang

        for env_var in ["LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE"]:
            env_value = os.getenv(env_var, "").strip()
            if env_value:
                if env_value.startswith("zh_TW") or env_value.startswith("zh_Hant"):
                    return "zh-TW"
                if env_value.startswith("zh_CN") or env_value.startswith("zh_Hans"):
                    return "zh-CN"
                if env_value.startswith("en"):
                    return "en"

        if not os.getenv("MCP_TEST_MODE"):
            try:
                system_locale = locale.getdefaultlocale()[0]
                if system_locale:
                    if system_locale.startswith("zh_TW") or system_locale.startswith(
                        "zh_Hant"
                    ):
                        return "zh-TW"
                    if system_locale.startswith("zh_CN") or system_locale.startswith(
                        "zh_Hans"
                    ):
                        return "zh-CN"
                    if system_locale.startswith("en"):
                        return "en"
            except Exception:
                pass

        return self._fallback_language

    def _load_saved_language(self) -> str | None:
        """Load saved language setting."""
        try:
            if self._config_file.exists():
                with open(self._config_file, encoding="utf-8") as f:
                    config = json.load(f)
                    language = config.get("language")
                    return language if isinstance(language, str) else None
        except Exception:
            pass
        return None

    def save_language(self, language: str) -> None:
        """Save language setting."""
        try:
            config = {"language": language}
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_current_language(self) -> str:
        """Get current language."""
        return self._current_language or "zh-TW"

    def set_language(self, language: str) -> bool:
        """Set language."""
        if language in self._supported_languages:
            self._current_language = language
            self.save_language(language)
            return True
        return False

    def get_supported_languages(self) -> list[str]:
        """Get supported languages."""
        return self._supported_languages.copy()

    def get_language_info(self, language_code: str) -> dict[str, Any]:
        """Get language metadata."""
        if language_code in self._translations:
            meta = self._translations[language_code].get("meta", {})
            return meta if isinstance(meta, dict) else {}
        return {}

    def _get_nested_value(self, data: dict[str, Any], key_path: str) -> str | None:
        """Get value from nested dict by dot-separated key path."""
        keys = key_path.split(".")
        current: Any = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return str(current) if isinstance(current, str) else None

    def t(self, key: str, **kwargs) -> str:
        """Translate; supports nested and legacy key formats."""
        current_translations = self._translations.get(self._current_language, {})

        text = self._get_nested_value(current_translations, key)

        if text is None:
            text = self._get_legacy_translation(current_translations, key)

        if text is None:
            fallback_translations = self._translations.get(self._fallback_language, {})
            text = self._get_nested_value(fallback_translations, key)
            if text is None:
                text = self._get_legacy_translation(fallback_translations, key)

        if text is None:
            text = key

        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass

        return text

    def _get_legacy_translation(
        self, translations: dict[str, Any], key: str
    ) -> str | None:
        """Legacy key to new key mapping."""
        legacy_mapping = {
            "app_title": "app.title",
            "project_directory": "app.projectDirectory",
            "language": "app.language",
            "settings": "app.settings",
            "feedback_tab": "tabs.feedback",
            "command_tab": "tabs.command",
            "images_tab": "tabs.images",
            "feedback_title": "feedback.title",
            "feedback_description": "feedback.description",
            "feedback_placeholder": "feedback.placeholder",
            "command_title": "command.title",
            "command_description": "command.description",
            "command_placeholder": "command.placeholder",
            "command_output": "command.output",
            "images_title": "images.title",
            "images_select": "images.select",
            "images_paste": "images.paste",
            "images_clear": "images.clear",
            "images_status": "images.status",
            "images_status_with_size": "images.statusWithSize",
            "images_drag_hint": "images.dragHint",
            "images_delete_confirm": "images.deleteConfirm",
            "images_delete_title": "images.deleteTitle",
            "images_size_warning": "images.sizeWarning",
            "images_format_error": "images.formatError",
            "submit": "buttons.submit",
            "cancel": "buttons.cancel",
            "close": "buttons.close",
            "clear": "buttons.clear",
            "btn_submit_feedback": "buttons.submitFeedback",
            "btn_cancel": "buttons.cancel",
            "btn_select_files": "buttons.selectFiles",
            "btn_paste_clipboard": "buttons.pasteClipboard",
            "btn_clear_all": "buttons.clearAll",
            "btn_run_command": "buttons.runCommand",
            "feedback_submitted": "status.feedbackSubmitted",
            "feedback_cancelled": "status.feedbackCancelled",
            "timeout_message": "status.timeoutMessage",
            "error_occurred": "status.errorOccurred",
            "loading": "status.loading",
            "connecting": "status.connecting",
            "connected": "status.connected",
            "disconnected": "status.disconnected",
            "uploading": "status.uploading",
            "upload_success": "status.uploadSuccess",
            "upload_failed": "status.uploadFailed",
            "command_running": "status.commandRunning",
            "command_finished": "status.commandFinished",
            "paste_success": "status.pasteSuccess",
            "paste_failed": "status.pasteFailed",
            "invalid_file_type": "status.invalidFileType",
            "file_too_large": "status.fileTooLarge",
            "ai_summary": "aiSummary",
            "language_selector": "languageSelector",
            "language_zh_tw": "languageNames.zhTw",
            "language_en": "languageNames.en",
            "language_zh_cn": "languageNames.zhCn",
            "test_web_ui_summary": "test.webUiSummary",
        }

        new_key = legacy_mapping.get(key)
        if new_key:
            return self._get_nested_value(translations, new_key)

        return None

_i18n_manager = None


def get_i18n_manager() -> I18nManager:
    """Get global i18n manager instance."""
    global _i18n_manager
    if _i18n_manager is None:
        _i18n_manager = I18nManager()
    return _i18n_manager


def t(key: str, **kwargs) -> str:
    """Convenience translate function."""
    return get_i18n_manager().t(key, **kwargs)


def get_current_language() -> str:
    """Get current language."""
    return get_i18n_manager().get_current_language()
