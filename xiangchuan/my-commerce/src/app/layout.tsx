import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AI 智能电商平台 - 整合营销解决方案',
  description: '一站式电商、营销推广、内容管理与客户支持平台',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW">
      <body>
        <header className="header">
          <nav className="nav">
            <a href="/" className="logo">AI 智能平台</a>
            <a href="/shop" className="nav-item">🛒 电商商城</a>
            <a href="/marketing" className="nav-item">📢 营销推广</a>
            <a href="/cms" className="nav-item">📝 内容管理</a>
            <a href="/support" className="nav-item">🎧 客户支持</a>
            
            <div className="lang-switcher">
              <button className="lang-btn">
                繁體中文 ▼
              </button>
            </div>
          </nav>
        </header>
        
        <main className="main-container">
          {children}
        </main>
      </body>
    </html>
  );
}
