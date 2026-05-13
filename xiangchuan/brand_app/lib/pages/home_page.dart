import 'package:flutter/material.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          const SizedBox(height: 40),
          _logo(),
          const SizedBox(height: 16),
          _tagline(),
          const SizedBox(height: 40),
          _features(context),
          const SizedBox(height: 40),
          _stats(context),
        ],
      ),
    );
  }

  Widget _logo() {
    return ShaderMask(
      shaderCallback: (bounds) => const LinearGradient(
        colors: [Color(0xFF00D4FF), Color(0xFF7B68EE)],
      ).createShader(bounds),
      child: const Text(
        '翔川 Neo｜曜科技 |Ai_bot',
        style: TextStyle(
          fontSize: 40,
          fontWeight: FontWeight.w700,
          color: Colors.white,
        ),
      ),
    );
  }

  Widget _tagline() {
    return const Text(
      'AI 智能助手 · 自動化行銷 · 品牌經營',
      style: TextStyle(fontSize: 16, color: Colors.white70),
    );
  }

  Widget _features(BuildContext context) {
    final features = [
      ('🤖', 'AI 智能客服', '24 小時自動回覆，串接 LLM 智能對話'),
      ('📝', '內容自動生成', '一鍵產出部落格、社群貼文、行銷文案'),
      ('📊', '多平台分發', 'Telegram、Web、App 全通路覆蓋'),
      ('🎬', 'AI 短劇創作', '從劇本到分鏡，AI 輔助完整製作'),
    ];
    return Column(
      children: [
        const Text('核心功能', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        ...features.map((f) => _featureCard(f.$1, f.$2, f.$3)),
      ],
    );
  }

  Widget _featureCard(String icon, String title, String desc) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      color: const Color(0xFF1A1F3A),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        leading: Text(icon, style: const TextStyle(fontSize: 28)),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(desc, style: const TextStyle(color: Colors.grey)),
      ),
    );
  }

  Widget _stats(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [Color(0xFF00D4FF), Color(0xFF7B68EE)]),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          const Text('目前已產生', style: TextStyle(fontSize: 14, color: Colors.white70)),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _statItem('133', '品牌文章'),
              _statItem('5', '攻略教學'),
              _statItem('2', 'AI 劇本'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _statItem(String count, String label) {
    return Column(
      children: [
        Text(count, style: const TextStyle(fontSize: 32, fontWeight: FontWeight.w700)),
        Text(label, style: const TextStyle(fontSize: 12, color: Colors.white70)),
      ],
    );
  }
}
