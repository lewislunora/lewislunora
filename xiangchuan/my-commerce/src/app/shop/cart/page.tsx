"use client";

import { useRouter } from 'next/navigation';

interface CartItem {
  id: number;
  name: string;
  nameEn: string;
  nameZhCn: string;
  price: number;
  quantity: number;
}

// 模拟购物车数据
let cart: CartItem[] = [
  { id: 1, name: '智能手表', nameEn: 'Smart Watch', nameZhCn: '智能手表', price: 199, quantity: 1 },
  { id: 2, name: '无线耳机', nameEn: 'Wireless Earbuds', nameZhCn: '无线耳机', price: 149, quantity: 2 },
];

export default function CartPage() {
  const router = useRouter();

  const total = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);

  const handleRemove = (id: number) => {
    cart = cart.filter(item => item.id !== id);
    alert('已从购物车移除');
    router.refresh();
  };

  const handleCheckout = () => {
    alert('正在前往结算...');
  };

  return (
    <main className="main-container">
      <section className="card">
        <h2>🛒 购物车</h2>
        {cart.length === 0 ? (
          <p style={{ textAlign: 'center', color: '#888' }}>购物车是空的</p>
        ) : (
          <div>
            {cart.map(item => (
              <div key={item.id} style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '1rem 0',
                borderBottom: '1px solid #f0f0f0'
              }}>
                <div>
                  <div style={{ fontWeight: 600 }}>{item.name}</div>
                  <div style={{ color: '#e74c3c' }}>${item.price} × {item.quantity}</div>
                </div>
                <button 
                  style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                  onClick={() => handleRemove(item.id)}
                >
                  ✕
                </button>
              </div>
            ))}
            
            <div style={{
              marginTop: '1.5rem',
              paddingTop: '1rem',
              borderTop: '2px solid #eee',
              fontWeight: 'bold',
              fontSize: '1.2rem'
            }}>
              总计: ${total}
            </div>
            
            <button 
              style={{
                width: '100%',
                marginTop: '1rem',
                padding: '0.75rem 1.5rem',
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer'
              }}
              onClick={handleCheckout}
            >
              去结算
            </button>
          </div>
        )}
      </section>
    </main>
  );
}
