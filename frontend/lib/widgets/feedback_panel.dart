import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
// ignore: avoid_web_libraries_in_flutter
import 'dart:js_interop';
import 'package:web/web.dart' as web;
import '../theme/app_theme.dart';

class FeedbackPanel extends StatefulWidget {
  final bool feedbackSubmitted;
  final ValueChanged<FeedbackData> onSubmit;
  final VoidCallback? onTypingStart;
  final VoidCallback? onTypingStop;

  const FeedbackPanel({
    super.key,
    required this.feedbackSubmitted,
    required this.onSubmit,
    this.onTypingStart,
    this.onTypingStop,
  });

  @override
  State<FeedbackPanel> createState() => FeedbackPanelState();
}

class FeedbackData {
  final String text;
  final List<Map<String, dynamic>> images;
  FeedbackData({required this.text, required this.images});
}

class FeedbackPanelState extends State<FeedbackPanel> {
  final _controller = TextEditingController();
  final _focusNode = FocusNode();
  bool _isSubmitting = false;
  bool _hasSubmitted = false;
  bool _hasContent = false;
  bool _isTyping = false;
  bool _isDragOver = false;
  Timer? _typingDebounce;
  Timer? _submitResetTimer;
  final List<_ImageAttachment> _images = [];

  late final JSFunction _globalDragOverHandler;
  late final JSFunction _globalDropHandler;
  late final JSFunction _globalPasteHandler;

  static const _imageTypes = {
    'image/png',
    'image/jpeg',
    'image/gif',
    'image/webp',
    'image/bmp',
  };

  static const _maxImages = 10;
  static const _maxImageBytes = 5 * 1024 * 1024; // 5MB

  @override
  void initState() {
    super.initState();
    _controller.addListener(_onTextChanged);
    _setupGlobalDropPrevention();
    _setupClipboardPaste();
  }

  void _setupGlobalDropPrevention() {
    _globalDragOverHandler = ((web.Event e) {
      e.preventDefault();
    }).toJS;
    _globalDropHandler = ((web.Event e) {
      e.preventDefault();
    }).toJS;
    web.document.addEventListener('dragover', _globalDragOverHandler);
    web.document.addEventListener('drop', _globalDropHandler);
  }

  void _setupClipboardPaste() {
    _globalPasteHandler = ((web.Event e) {
      if (_isDisabled) return;
      final clipboardEvent = e as web.ClipboardEvent;
      final clipboardData = clipboardEvent.clipboardData;
      if (clipboardData == null) return;

      final items = clipboardData.items;
      for (var i = 0; i < items.length; i++) {
        final item = items[i];
        if (item.type.startsWith('image/')) {
          e.preventDefault();
          final file = item.getAsFile();
          if (file != null) {
            _readFile(file);
          }
        }
      }
    }).toJS;
    web.document.addEventListener('paste', _globalPasteHandler);
  }

  void _onTextChanged() {
    final hasText = _controller.text.trim().isNotEmpty;
    if (hasText != _hasContent) {
      setState(() => _hasContent = hasText);
    }

    if (!_isTyping) {
      _isTyping = true;
      widget.onTypingStart?.call();
    }
    _typingDebounce?.cancel();
    _typingDebounce = Timer(const Duration(seconds: 2), () {
      _isTyping = false;
      widget.onTypingStop?.call();
    });
  }

  void clearFeedback() {
    _controller.clear();
    setState(() {
      _images.clear();
      _hasSubmitted = false;
      _isSubmitting = false;
      _hasContent = false;
    });
  }

  @override
  void didUpdateWidget(FeedbackPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!widget.feedbackSubmitted && oldWidget.feedbackSubmitted) {
      setState(() {
        _hasSubmitted = false;
        _isSubmitting = false;
      });
    }
  }

  @override
  void dispose() {
    web.document.removeEventListener('dragover', _globalDragOverHandler);
    web.document.removeEventListener('drop', _globalDropHandler);
    web.document.removeEventListener('paste', _globalPasteHandler);
    _typingDebounce?.cancel();
    _submitResetTimer?.cancel();
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _handleSubmit() {
    final text = _controller.text.trim();
    if (text.isEmpty && _images.isEmpty) return;

    setState(() {
      _isSubmitting = true;
      _hasSubmitted = true;
    });

    final imageData = _images
        .map(
          (img) => {'name': img.name, 'data': img.base64Data, 'size': img.size},
        )
        .toList();

    widget.onSubmit(FeedbackData(text: text, images: imageData));

    _controller.clear();
    setState(() {
      _images.clear();
      _hasContent = false;
    });

    _submitResetTimer?.cancel();
    _submitResetTimer = Timer(const Duration(milliseconds: 500), () {
      if (mounted) {
        setState(() => _isSubmitting = false);
      }
    });
  }

  void _copyUserContent() {
    final text = _controller.text;
    if (text.isNotEmpty) {
      Clipboard.setData(ClipboardData(text: text));
    }
  }

  void _pickImages() {
    final input = web.document.createElement('input') as web.HTMLInputElement;
    input.type = 'file';
    input.accept = 'image/png,image/jpeg,image/gif,image/webp,image/bmp';
    input.multiple = true;

    input.addEventListener(
      'change',
      (web.Event event) {
        final files = input.files;
        if (files != null) {
          for (var i = 0; i < files.length; i++) {
            final file = files.item(i);
            if (file != null) {
              _readFile(file);
            }
          }
        }
      }.toJS,
    );

    input.click();
  }

  bool _isDuplicate(String name, int size) {
    return _images.any((img) => img.name == name && img.size == size);
  }

  void _readFile(web.File file) {
    if (_images.length >= _maxImages) return;
    if (file.size > _maxImageBytes) return;

    final reader = web.FileReader();
    reader.addEventListener(
      'load',
      (web.Event event) {
        if (!mounted) return;
        final result = reader.result;
        if (result != null) {
          final dataUrl = (result as JSString).toDart;
          final base64 = dataUrl.split(',').last;
          if (_isDuplicate(file.name, file.size)) return;
          if (_images.length >= _maxImages) return;
          setState(() {
            _images.add(
              _ImageAttachment(
                name: file.name,
                base64Data: base64,
                size: file.size,
                dataUrl: dataUrl,
              ),
            );
          });
        }
      }.toJS,
    );
    reader.readAsDataURL(file);
  }

  DecorationImage? _decodeImage(String base64Data) {
    try {
      return DecorationImage(
        image: MemoryImage(base64Decode(base64Data)),
        fit: BoxFit.cover,
      );
    } catch (_) {
      return null;
    }
  }

  void _removeImage(int index) {
    setState(() => _images.removeAt(index));
  }

  bool get _isDisabled => _hasSubmitted && widget.feedbackSubmitted;

  void _handleDrop(web.DataTransfer dataTransfer) {
    if (_isDisabled) return;

    final files = dataTransfer.files;
    bool handledFiles = false;

    for (var i = 0; i < files.length; i++) {
      final file = files.item(i);
      if (file == null) continue;
      handledFiles = true;

      if (_imageTypes.contains(file.type)) {
        _readFile(file);
      } else {
        _insertTextAtCursor(file.name);
      }
    }

    if (!handledFiles) {
      final textData = dataTransfer.getData('text/plain');
      if (textData.isNotEmpty) {
        _insertTextAtCursor(textData);
      }
    }
  }

  void _insertTextAtCursor(String insert) {
    final pos = _controller.selection.baseOffset;
    final text = _controller.text;
    if (pos >= 0) {
      _controller.text =
          '${text.substring(0, pos)}$insert${text.substring(pos)}';
      _controller.selection = TextSelection.collapsed(
        offset: pos + insert.length,
      );
    } else {
      _controller.text = text.isEmpty ? insert : '$text\n$insert';
      _controller.selection = TextSelection.collapsed(
        offset: _controller.text.length,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return _DropZone(
      isDragOver: _isDragOver,
      onDragEnter: () => setState(() => _isDragOver = true),
      onDragLeave: () => setState(() => _isDragOver = false),
      onDrop: _handleDrop,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildHeader(context),
          Expanded(
            child: Scrollbar(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _buildTextInput(context),
                    const SizedBox(height: 8),
                    OutlinedButton.icon(
                      onPressed: _copyUserContent,
                      icon: const Icon(Icons.content_copy, size: 14),
                      label: const Text('Copy User Content'),
                    ),
                    const SizedBox(height: 12),
                    _buildImageUpload(context),
                    if (_images.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      _buildImagePreview(),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: const BoxDecoration(
        color: AppColors.bgTertiary,
        border: Border(bottom: BorderSide(color: AppColors.border, width: 1)),
      ),
      child: Row(
        children: [
          const Icon(Icons.chat_bubble_outline, color: AppColors.textPrimary),
          const SizedBox(width: 6),
          Text('Provide Feedback', style: tt.titleSmall),
          const Spacer(),
          _buildSubmitButton(context),
        ],
      ),
    );
  }

  Widget _buildSubmitButton(BuildContext context) {
    final isSubmitted = _isDisabled;

    return ElevatedButton.icon(
      onPressed:
          (_isSubmitting || isSubmitted || (!_hasContent && _images.isEmpty))
          ? null
          : _handleSubmit,
      icon: _isSubmitting
          ? const SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: Colors.white,
              ),
            )
          : Icon(isSubmitted ? Icons.check : Icons.check_circle, size: 14),
      label: Text(
        _isSubmitting
            ? 'Submitting...'
            : isSubmitted
            ? 'Submitted'
            : 'Submit Feedback',
      ),
      style: ElevatedButton.styleFrom(
        backgroundColor: isSubmitted || _isSubmitting
            ? AppColors.textSecondary
            : AppColors.success,
        padding: const EdgeInsets.symmetric(horizontal: 12),
      ),
    );
  }

  Widget _buildTextInput(BuildContext context) {
    final tt = Theme.of(context).textTheme;

    return CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.enter, control: true):
            _handleSubmit,
        const SingleActivator(LogicalKeyboardKey.enter, meta: true):
            _handleSubmit,
      },
      child: TextField(
        controller: _controller,
        focusNode: _focusNode,
        maxLines: 20,
        enabled: !_isDisabled,
        style: tt.bodyMedium?.copyWith(fontFamily: 'monospace'),
        decoration: const InputDecoration(
          hintText:
              'Please enter your feedback here...\n\nTips:\n• Press Ctrl+Enter / Cmd+Enter for quick submit\n• Paste images with Ctrl+V / Cmd+V',
          hintMaxLines: 6,
        ),
      ),
    );
  }

  Widget _buildImageUpload(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final atLimit = _images.length >= _maxImages;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              'Image Attachments (Optional)',
              style: tt.labelMedium?.copyWith(fontWeight: FontWeight.w500),
            ),
            if (_images.isNotEmpty) ...[
              const SizedBox(width: 8),
              Text(
                '${_images.length}/$_maxImages',
                style: tt.labelSmall?.copyWith(
                  color: atLimit ? AppColors.warning : AppColors.textSecondary,
                ),
              ),
            ],
          ],
        ),
        const SizedBox(height: 6),
        GestureDetector(
          onTap: (_isDisabled || atLimit) ? null : _pickImages,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 16),
            decoration: BoxDecoration(
              color: AppColors.bgPrimary,
              borderRadius: BorderRadius.circular(6),
              border: Border.all(
                color: atLimit ? AppColors.warning : AppColors.border,
              ),
            ),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    atLimit ? Icons.block : Icons.add_photo_alternate_outlined,
                    color: atLimit
                        ? AppColors.warning
                        : AppColors.textSecondary,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    atLimit
                        ? 'Maximum $_maxImages images reached'
                        : 'Click to select or paste images',
                    style: tt.bodySmall,
                  ),
                  if (!atLimit)
                    Text(
                      'PNG, JPG, GIF, WebP, BMP • Max 5MB • Ctrl+V to paste',
                      style: tt.labelSmall,
                    ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildImagePreview() {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: List.generate(_images.length, (index) {
        final img = _images[index];
        return Stack(
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: AppColors.border),
                image: _decodeImage(img.base64Data),
              ),
            ),
            if (!_isDisabled)
              Positioned(
                top: 2,
                right: 2,
                child: GestureDetector(
                  onTap: () => _removeImage(index),
                  child: Container(
                    width: 20,
                    height: 20,
                    decoration: const BoxDecoration(
                      color: AppColors.error,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.close,
                      size: 12,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
          ],
        );
      }),
    );
  }
}

class _ImageAttachment {
  final String name;
  final String base64Data;
  final int size;
  final String dataUrl;

  _ImageAttachment({
    required this.name,
    required this.base64Data,
    required this.size,
    required this.dataUrl,
  });
}

class _DropZone extends StatefulWidget {
  final Widget child;
  final bool isDragOver;
  final VoidCallback onDragEnter;
  final VoidCallback onDragLeave;
  final void Function(web.DataTransfer) onDrop;

  const _DropZone({
    required this.child,
    required this.isDragOver,
    required this.onDragEnter,
    required this.onDragLeave,
    required this.onDrop,
  });

  @override
  State<_DropZone> createState() => _DropZoneState();
}

class _DropZoneState extends State<_DropZone> {
  int _dragCounter = 0;
  JSFunction? _dragEnterHandler;
  JSFunction? _dragLeaveHandler;
  JSFunction? _dropHandler;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _attachListeners());
  }

  void _attachListeners() {
    final body = web.document.body;
    if (body == null) return;

    _dragEnterHandler = ((web.Event e) {
      e.preventDefault();
      _dragCounter++;
      if (_dragCounter == 1) widget.onDragEnter();
    }).toJS;

    _dragLeaveHandler = ((web.Event e) {
      _dragCounter--;
      if (_dragCounter <= 0) {
        _dragCounter = 0;
        widget.onDragLeave();
      }
    }).toJS;

    _dropHandler = ((web.Event e) {
      e.preventDefault();
      _dragCounter = 0;
      widget.onDragLeave();
      final de = e as web.DragEvent;
      final dt = de.dataTransfer;
      if (dt != null) widget.onDrop(dt);
    }).toJS;

    body.addEventListener('dragenter', _dragEnterHandler!);
    body.addEventListener('dragleave', _dragLeaveHandler!);
    body.addEventListener('drop', _dropHandler!);
  }

  @override
  void dispose() {
    final body = web.document.body;
    if (body != null) {
      if (_dragEnterHandler != null) {
        body.removeEventListener('dragenter', _dragEnterHandler!);
      }
      if (_dragLeaveHandler != null) {
        body.removeEventListener('dragleave', _dragLeaveHandler!);
      }
      if (_dropHandler != null) body.removeEventListener('drop', _dropHandler!);
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        widget.child,
        if (widget.isDragOver)
          Positioned.fill(
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.accent.withValues(alpha: 0.1),
                border: Border.all(color: AppColors.accent, width: 2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.file_download,
                      size: 48,
                      color: AppColors.accent,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Drop files here',
                      style: Theme.of(
                        context,
                      ).textTheme.titleSmall?.copyWith(color: AppColors.accent),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Images will be attached, other files will insert filename',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}
