import { useState, useEffect } from 'react';

export default function Orders() {
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    const userId = tg?.initDataUnsafe?.user?.id?.toString() || 'guest';

    fetch(`/api/v1/miniapp/orders/${userId}`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setOrders(data);
        } else {
          console.error("API did not return an array:", data);
          setOrders([]);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Error fetching orders", err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="page-header">
      <h1 className="page-title">Orders</h1>
      <p className="page-subtitle">Your recent purchases</p>
      
      <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {loading ? (
          <p>Loading orders...</p>
        ) : orders.length === 0 ? (
          <p>You have no recent orders.</p>
        ) : (
          orders.map(order => (
            <div key={order.id} className="glass-panel" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: '600', fontSize: '15px' }}>{order.order_number || order.id}</div>
                <div style={{ fontSize: '13px', color: 'var(--tg-theme-hint-color)', marginTop: '4px' }}>
                  {new Date(order.created_at).toLocaleDateString()} • {order.status}
                </div>
              </div>
              <div style={{ fontWeight: '700', color: 'var(--tg-theme-button-color)' }}>
                {order.currency} {order.total_amount}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
