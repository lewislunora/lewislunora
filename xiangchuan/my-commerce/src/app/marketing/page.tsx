export default function MarketingPage() {
  return (
    <main className="main-container">
      <section className="card marketing-hero">
        <h1>🚀 智能营销解决方案</h1>
        <p>一站式营销推广，提升品牌曝光与转化率</p>
        <button className="btn btn-success" style={{ marginTop: '1rem' }}>
          免费试用
        </button>
      </section>

      <section className="card">
        <h2>📈 核心功能</h2>
        <div className="marketing-features">
          <div className="feature-card card">
            <div className="feature-icon">📊</div>
            <h3>数据分析</h3>
            <p>实时监控营销数据，优化推广策略</p>
          </div>
          <div className="feature-card card">
            <div className="feature-icon">✍️</div>
            <h3>文案生成</h3>
            <p>AI自动生成吸引人的推广文案</p>
          </div>
          <div className="feature-card card">
            <div className="feature-icon">📱</div>
            <h3>社群推广</h3>
            <p>多平台同步推广，覆盖更多用户</p>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>📈 成功案例</h2>
        <p>某文创品牌使用我们的营销方案，3个月内品牌曝光提升200%，转化率提升150%。</p>
      </section>
    </main>
  );
}
