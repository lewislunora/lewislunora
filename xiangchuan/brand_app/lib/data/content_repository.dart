import 'dart:convert';
import 'package:flutter/services.dart';
import '../models/content_item.dart';

class ContentRepository {
  static List<ContentItem>? _cache;

  static Future<List<ContentItem>> loadAll() async {
    if (_cache != null) return _cache!;
    final json = await rootBundle.loadString('assets/content.json');
    final list = jsonDecode(json) as List;
    _cache = list.map((e) => ContentItem.fromJson(e)).toList();
    return _cache!;
  }

  static List<ContentItem> filter({
    String? type,
    String? language,
    String? query,
  }) {
    var items = _cache ?? [];
    if (type != null) items = items.where((e) => e.type == type).toList();
    if (language != null) {
      items = items.where((e) => e.language == language).toList();
    }
    if (query != null && query.isNotEmpty) {
      final q = query.toLowerCase();
      items = items
          .where((e) =>
              e.title.toLowerCase().contains(q) ||
              e.body.toLowerCase().contains(q))
          .toList();
    }
    return items;
  }

  static ContentItem? findById(String id) {
    return _cache?.where((e) => e.id == id).firstOrNull;
  }
}
