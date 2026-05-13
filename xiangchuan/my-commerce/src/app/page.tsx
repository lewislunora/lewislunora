import Link from 'next/link';
import ProductCard from '@/app/components/product-card';

// 模拟产品数据
const products = [
  { id: 1, name: '智能手表', nameEn: 'Smart Watch', nameZhCn: '智能手表', price: 199, icon: '⌚' },
  { id: 2, name: '无线耳机', nameEn: 'Wireless Earbuds', nameZhCn: '无线耳机', price: 149, icon: '🎧' },
  { id: 3, name: '便携充电宝', nameEn: 'Power Bank', nameZhCn: '便携充电宝', price: 59, icon: '🔋' },
  { id: 4, name: '智能音箱', nameEn: 'Smart Speaker', nameZhCn: '智能音箱', price: 129, icon: '🔊' },
];

export default function Home() {
  return (
    <main className="main-container">
      <section className="card">
        <h2>🛒 电商微商城</h2>
        <p>精选优质商品，快速下单，便捷购物体验。</p>
        
        <div className="products-grid">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      </section>

      <section className="card">
        <h2>🛒 购物车</h2>
        <Link href="/shop/cart">
          <button className="btn btn-primary">查看购物车</button>
        </Link>
      </section>
    </main>
  );
}
