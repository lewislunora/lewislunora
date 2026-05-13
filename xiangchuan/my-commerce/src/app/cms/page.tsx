"use client";

import { useState } from 'react';
import Link from 'next/link';

interface Article {
  id: number;
  title: string;
  titleEn: string;
  titleZhCn: string;
  content: string;
  contentEn: string;
  contentZhCn: string;
  date: string;
}

// 模拟数据
const initialArticles: Article[] = [
  { 
    id: 1, 
    title: '欢迎来到我们的网站', 
    titleEn: 'Welcome to Our Website',
    titleZhCn: '欢迎来到我们的网站',
    content: '这是第一篇文章，介绍我们的产品和服务。', 
    contentEn: 'This is the first article, introducing our products and services.',
    contentZhCn: '这是第一篇文章，介绍我们的产品和服务。',
    date: '2026-05-05' 
  },
  { 
    id: 2, 
    title: '最新营销技巧', 
    titleEn: 'Latest Marketing Tips',
    titleZhCn: '最新营销技巧',
    content: '了解最新的数字营销趋势和技巧，提升您的推广效果。', 
    contentEn: 'Learn the latest digital marketing trends and tips to boost your promotion effectiveness.',
    contentZhCn: '了解最新的数字营销趋势和技巧，提升您的推广效果。',
    date: '2026-05-04' 
  }
];

export default function CmsPage() {
  const [articles, setArticles] = useState<Article[]>(initialArticles);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');

  const handlePublish = () => {
    if (!title || !content) {
      alert('请填写标题和内容');
      return;
    }

    const newArticle: Article = {
      id: articles.length + 1,
      title,
      titleEn: title,
      titleZhCn: title,
      content,
      contentEn: content,
      contentZhCn: content,
      date: new Date().toISOString().split('T')[0]
    };

    setArticles([newArticle, ...articles]);
    setTitle('');
    setContent('');
    alert('文章发布成功！');
  };

  return (
    <main className="main-container">
      <section className="card">
        <h2>📝 内容管理系统</h2>
        <p>轻松管理网站内容，发布最新资讯。</p>
        
        <div className="form-group">
          <label>文章标题</label>
          <input 
            type="text" 
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="输入文章标题"
          />
        </div>
        <div className="form-group">
          <label>文章内容</label>
          <textarea 
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="输入文章内容"
          />
        </div>
        <button 
          className="btn btn-primary" 
          onClick={handlePublish}
        >
          发布文章
        </button>
      </section>

      <section className="card">
        <h2>📚 文章列表</h2>
        <div className="article-list">
          {articles.map((article) => (
            <div key={article.id} className="article-item">
              <div className="article-title">{article.title}</div>
              <div className="article-meta">发布日期: {article.date}</div>
              <div>{article.content}</div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
