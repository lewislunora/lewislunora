import { NextRequest, NextResponse } from 'next/server';

// 模拟文章数据
let articles = [
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

export async function GET() {
  return NextResponse.json(articles);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const newArticle = {
    id: articles.length + 1,
    ...body,
    date: new Date().toISOString().split('T')[0]
  };
  articles.unshift(newArticle);
  return NextResponse.json(newArticle, { status: 201 });
}
