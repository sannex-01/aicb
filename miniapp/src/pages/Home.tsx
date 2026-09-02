export default function Home() {
  const user = (window as any).Telegram?.WebApp?.initDataUnsafe?.user;

  return (
    <div className="page-header">
      <h1 className="page-title gradient-text">
        Welcome, {user?.first_name || 'Guest'}!
      </h1>
      <p className="page-subtitle">Your personal AI shopping assistant.</p>
      
      <div className="glass-panel" style={{ marginTop: '24px', padding: '20px' }}>
        <h2 style={{ fontSize: '18px', marginBottom: '12px' }}>Featured Items</h2>
        <p style={{ color: 'var(--tg-theme-hint-color)', fontSize: '14px' }}>
          Discover the latest products curated just for you by our AI.
        </p>
        <button className="btn-primary" style={{ marginTop: '16px' }} onClick={() => window.location.href = '/catalog'}>
          Browse Catalog
        </button>
      </div>
    </div>
  );
}
