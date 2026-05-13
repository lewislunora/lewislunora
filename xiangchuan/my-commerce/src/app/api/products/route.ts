import { NextRequest, NextResponse } from 'next/server';

// 模拟产品数据
const products = [
  { id: 1, name: '智能手表', nameEn: 'Smart Watch', nameZhCn: '智能手表', price: 199, icon: '⌚' },
  { id: 2, name: '无线耳机', nameEn: 'Wireless Earbuds', nameZhCn: '无线耳机', price: 149, icon: '🎧' },
  { id: 3, name: '便携充电宝', nameEn: 'Power Bank', nameZhCn: '便携充电宝', price: 59, icon: '🔋' },
  { id: 4, name: '智能音箱', nameEn: 'Smart Speaker', nameZhCn: '智能音箱', price: 129, icon: '🔊' },
];

export async function GET() {
  return NextResponse.json(products);
}
