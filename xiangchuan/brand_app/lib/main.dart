import 'package:flutter/material.dart';
import 'pages/home_page.dart';
import 'pages/content_list_page.dart';

void main() {
  FlutterError.onError = (details) {
    debugPrint('🔥 ${details.exception}');
  };
  ErrorWidget.builder = (details) => Material(
    color: const Color(0xFF0A0E27),
    child: Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(
          '${details.exception}',
          style: const TextStyle(color: Colors.redAccent, fontSize: 14),
        ),
      ),
    ),
  );
  runApp(const BrandApp());
}

class BrandApp extends StatelessWidget {
  const BrandApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '翔川 Neo｜曜科技 |Ai_bot',
      debugShowCheckedModeBanner: false,
      theme: _darkTheme(),
      home: const MainScreen(),
    );
  }

  ThemeData _darkTheme() {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: const Color(0xFF0A0E27),
      primaryColor: const Color(0xFF7B68EE),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF0A0E27),
        elevation: 0,
        centerTitle: true,
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Color(0xFF0A0E27),
        selectedItemColor: Color(0xFF00D4FF),
        unselectedItemColor: Colors.grey,
      ),
    );
  }
}

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _index = 0;

  final _pages = [
    const HomePage(),
    const ContentListPage(type: 'article', title: '品牌行銷'),
    const ContentListPage(type: 'guide', title: '攻略教學'),
    const ContentListPage(type: 'drama', title: 'AI 短劇'),
  ];

  final _titles = ['翔川 Neo｜曜科技 |Ai_bot', '品牌行銷', '攻略教學', 'AI 短劇'];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_titles[_index])),
      body: _pages[_index],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home), label: '首頁'),
          BottomNavigationBarItem(icon: Icon(Icons.article), label: '文章'),
          BottomNavigationBarItem(icon: Icon(Icons.menu_book), label: '攻略'),
          BottomNavigationBarItem(icon: Icon(Icons.movie), label: '劇本'),
        ],
      ),
    );
  }
}
