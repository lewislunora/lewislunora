import 'package:flutter/material.dart';
import '../models/content_item.dart';

class DetailPage extends StatelessWidget {
  final ContentItem item;

  const DetailPage({super.key, required this.item});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          item.typeLabel,
          style: const TextStyle(fontSize: 14),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _tags(),
            const SizedBox(height: 16),
            Text(
              item.title,
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Icon(Icons.access_time, size: 14, color: Colors.grey[400]),
                const SizedBox(width: 4),
                Text(
                  'AI 自動生成',
                  style: TextStyle(fontSize: 13, color: Colors.grey[400]),
                ),
              ],
            ),
            const Divider(height: 32),
            Text(
              item.body,
              style: TextStyle(
                fontSize: 16,
                height: 1.8,
                color: isDark ? Colors.grey[200] : Colors.grey[800],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _tags() {
    return Wrap(
      spacing: 8,
      runSpacing: 4,
      children: [
        _chip(item.typeLabel, const Color(0xFF7B68EE)),
        if (item.platform.isNotEmpty) _chip(item.platformLabel, const Color(0xFF00D4FF)),
        _chip(item.languageLabel, Colors.orange),
        if (item.genre.isNotEmpty) _chip(item.genre, Colors.pink),
      ],
    );
  }

  Widget _chip(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        text,
        style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w500),
      ),
    );
  }
}

extension on ContentItem {
  String get platformLabel {
    switch (platform) {
      case 'blog': return '部落格';
      case 'facebook': return 'Facebook';
      case 'threads': return 'Threads';
      case 'linkedin': return 'LinkedIn';
      case 'email': return '電子報';
      default: return platform;
    }
  }
}
