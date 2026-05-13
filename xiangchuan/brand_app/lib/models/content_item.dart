class ContentItem {
  final String id;
  final String type;
  final String title;
  final String platform;
  final String language;
  final String genre;
  final String style;
  final String keywords;
  final String body;

  ContentItem({
    required this.id,
    required this.type,
    required this.title,
    this.platform = '',
    this.language = 'zh-tw',
    this.genre = '',
    this.style = '',
    this.keywords = '',
    required this.body,
  });

  factory ContentItem.fromJson(Map<String, dynamic> json) {
    return ContentItem(
      id: json['id'] ?? '',
      type: json['type'] ?? '',
      title: json['title'] ?? '',
      platform: json['platform'] ?? '',
      language: json['language'] ?? 'zh-tw',
      genre: json['genre'] ?? '',
      style: json['style'] ?? '',
      keywords: json['keywords'] ?? '',
      body: json['body'] ?? '',
    );
  }

  String get typeLabel {
    switch (type) {
      case 'article': return '品牌行銷';
      case 'guide': return '攻略教學';
      case 'drama': return 'AI短劇';
      default: return type;
    }
  }

  String get languageLabel {
    switch (language) {
      case 'zh-tw': return '繁中';
      case 'en': return 'EN';
      case 'zh-cn': return '简中';
      default: return language;
    }
  }
}
