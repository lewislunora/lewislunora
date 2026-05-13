"use client";

import Link from 'next/link';

interface Product {
  id: number;
  name: string;
  nameEn: string;
  nameZhCn: string;
  price: number;
  icon: string;
}

export default function ProductCard({ product }: { product: Product }) {
  const handleAddToCart = () => {
    // 这里可以调用 API 添加购物车
    alert(`已添加 ${product.name} 到购物车`);
  };

  return (
    <div className="product-card">
      <div className="product-img">{product.icon}</div>
      <div className="product-info">
        <div className="product-title">{product.name}</div>
        <div className="product-price">${product.price}</div>
        <button 
          className="btn btn-primary" 
          onClick={handleAddToCart}
        >
          加入购物车
        </button>
      </div>
    </div>
  );
}
