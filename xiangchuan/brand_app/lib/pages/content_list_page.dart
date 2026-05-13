import 'package:flutter/material.dart';
import '../data/content_repository.dart';
import '../models/content_item.dart';
import '../widgets/content_card.dart';
import 'detail_page.dart';

class ContentListPage extends StatefulWidget {
  final String type;
  final String title;

  const ContentListPage({super.key, required this.type, required this.title});

  @override
  State<ContentListPage> createState() => _ContentListPageState();
}

class _ContentListPageState extends State<ContentListPage> {
  List<ContentItem> _items = [];
  List<ContentItem> _filtered = [];
  bool _loading = true;
  String _langFilter = 'all';
  String _searchQuery = '';
  final _searchCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    await ContentRepository.loadAll();
    _items = ContentRepository.filter(type: widget.type);
    _applyFilter();
    setState(() => _loading = false);
  }

  void _applyFilter() {
    _filtered = _items.where((e) {
      if (_langFilter != 'all' && e.language != _langFilter) return false;
      if (_searchQuery.isNotEmpty) {
        final q = _searchQuery.toLowerCase();
        return e.title.toLowerCase().contains(q) ||
            e.body.toLowerCase().contains(q);
      }
      return true;
    }).toList();
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    return Column(
      children: [
        _searchBar(),
        _langFilterBar(),
        Expanded(
          child: _filtered.isEmpty
              ? const Center(child: Text('暫無內容', style: TextStyle(color: Colors.grey)))
              : ListView.builder(
                  itemCount: _filtered.length,
                  itemBuilder: (_, i) {
                    final item = _filtered[i];
                    final sub = widget.type == 'drama'
                        ? '${item.genre} · ${item.style}'
                        : '${item.platformLabel}${item.keywords.isNotEmpty ? " · ${item.keywords}" : ""}';
                    return ContentCard(
                      title: item.title,
                      subtitle: sub,
                      typeLabel: widget.type == 'drama'
                          ? item.genre
                          : item.typeLabel,
                      langLabel: item.languageLabel,
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => DetailPage(item: item),
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _searchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: TextField(
        controller: _searchCtrl,
        onChanged: (v) {
          _searchQuery = v;
          _applyFilter();
        },
        decoration: InputDecoration(
          hintText: '搜尋內容...',
          prefixIcon: const Icon(Icons.search, size: 20),
          suffixIcon: _searchQuery.isNotEmpty
              ? IconButton(
                  icon: const Icon(Icons.clear, size: 18),
                  onPressed: () {
                    _searchCtrl.clear();
                    _searchQuery = '';
                    _applyFilter();
                  },
                )
              : null,
          filled: true,
          fillColor: Theme.of(context).brightness == Brightness.dark
              ? const Color(0xFF1A1F3A)
              : Colors.grey[100],
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide.none,
          ),
          contentPadding: const EdgeInsets.symmetric(vertical: 12),
        ),
      ),
    );
  }

  Widget _langFilterBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      child: Row(
        children: [
          _langChip('all', '全部'),
          const SizedBox(width: 8),
          _langChip('zh-tw', '繁中'),
          const SizedBox(width: 8),
          _langChip('en', 'English'),
        ],
      ),
    );
  }

  Widget _langChip(String value, String label) {
    final selected = _langFilter == value;
    return FilterChip(
      label: Text(label, style: TextStyle(fontSize: 12, color: selected ? Colors.white : null)),
      selected: selected,
      selectedColor: const Color(0xFF7B68EE),
      onSelected: (_) {
        _langFilter = value;
        _applyFilter();
      },
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      visualDensity: VisualDensity.compact,
    );
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
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
