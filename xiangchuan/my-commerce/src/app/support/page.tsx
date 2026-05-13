"use client";

import { useState } from 'react';

interface FAQ {
  id: number;
  question: string;
  questionEn: string;
  questionZhCn: string;
  answer: string;
  answerEn: string;
  answerZhCn: string;
  isOpen: boolean;
}

// 模拟 FAQ 数据
const initialFAQs: FAQ[] = [
  {
    id: 1,
    question: '如何下单购买商品？',
    questionEn: 'How to order products?',
    questionZhCn: '如何下单购买商品？',
    answer: '浏览商品列表，点击"加入购物车"，然后在购物车中点击"去结算"即可完成下单。',
    answerEn: 'Browse product list, click "Add to Cart", then click "Checkout" in cart to complete order.',
    answerZhCn: '浏览商品列表，点击"加入购物车"，然后在购物车中点击"去结算"即可完成下单。',
    isOpen: false
  },
  {
    id: 2,
    question: '支持哪些支付方式？',
    questionEn: 'What payment methods are supported?',
    questionZhCn: '支持哪些支付方式？',
    answer: '目前支持信用卡、支付宝、微信支付等主流支付方式。',
    answerEn: 'Currently supports credit cards, Alipay, WeChat Pay and other mainstream payment methods.',
    answerZhCn: '目前支持信用卡、支付宝、微信支付等主流支付方式。',
    isOpen: false
  },
  {
    id: 3,
    question: '如何查看订单状态？',
    questionEn: 'How to check order status?',
    questionZhCn: '如何查看订单状态？',
    answer: '登录后在"我的订单"页面可以查看所有订单的状态和物流信息。',
    answerEn: 'After login, you can check all order status and logistics info in "My Orders" page.',
    answerZhCn: '登录后在"我的订单"页面可以查看所有订单的状态和物流信息。',
    isOpen: false
  },
  {
    id: 4,
    question: '营销服务如何收费？',
    questionEn: 'How is marketing service charged?',
    questionZhCn: '营销服务如何收费？',
    answer: '我们提供多种套餐，您可以根据需求选择适合的方案，详情请联系客服。',
    answerEn: 'We offer various packages, you can choose the suitable one based on your needs, contact customer service for details.',
    answerZhCn: '我们提供多种套餐，您可以根据需求选择适合的方案，详情请联系客服。',
    isOpen: false
  }
];

export default function SupportPage() {
  const [faqs, setFaqs] = useState<FAQ[]>(initialFAQs);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');

  const toggleFAQ = (id: number) => {
    setFaqs(faqs.map(faq => 
      faq.id === id ? { ...faq, isOpen: !faq.isOpen } : faq
    ));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!name || !email || !message) {
      alert('请填写所有字段');
      return;
    }

    // 这里应该调用 API
    const response = await fetch('/api/contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, message })
    });

    if (response.ok) {
      alert('感谢您的留言！我们会尽快与您联系。');
      setName('');
      setEmail('');
      setMessage('');
    }
  };

  return (
    <main className="main-container">
      <section className="card">
        <h2>🎧 客户支持</h2>
        <p>我们随时为您提供帮助与支持。</p>
        
        <h3 style={{ marginTop: '1.5rem' }}>❓ 常见问题</h3>
        <div className="faq-list">
          {faqs.map(faq => (
            <div key={faq.id} className="faq-item">
              <div 
                className="faq-question" 
                onClick={() => toggleFAQ(faq.id)}
              >
                {faq.question}
                <span>{faq.isOpen ? '▲' : '▼'}</span>
              </div>
              {faq.isOpen && (
                <div className="faq-answer">
                  {faq.answer}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>📞 联系我们</h2>
        <form onSubmit={handleSubmit} className="contact-form">
          <div className="form-group">
            <label>姓名</label>
            <input 
              type="text" 
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="您的姓名"
            />
          </div>
          <div className="form-group">
            <label>邮箱</label>
            <input 
              type="email" 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
            />
          </div>
          <div className="form-group">
            <label>留言内容</label>
            <textarea 
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="请输入您的问题或建议"
            />
          </div>
          <button type="submit" className="btn btn-primary">
            提交留言
          </button>
        </form>
      </section>
    </main>
  );
}
