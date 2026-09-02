import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { Store, MessageCircle, ShoppingBag, LayoutDashboard } from 'lucide-react';

// Pages (to be implemented)
import Home from './pages/Home';
import Catalog from './pages/Catalog';
import Chat from './pages/Chat';
import Orders from './pages/Orders';

function Layout() {
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    { path: '/', icon: <Store />, label: 'Home' },
    { path: '/catalog', icon: <LayoutDashboard />, label: 'Catalog' },
    { path: '/chat', icon: <MessageCircle />, label: 'Chat' },
    { path: '/orders', icon: <ShoppingBag />, label: 'Orders' },
  ];

  return (
    <div className="app-container">
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/catalog" element={<Catalog />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/orders" element={<Orders />} />
        </Routes>
      </main>

      <nav className="bottom-nav">
        {navItems.map((item) => (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
            style={{ background: 'none', border: 'none', cursor: 'pointer' }}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}

export default function App() {
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      
      // We can access user data like this:
      // const user = tg.initDataUnsafe?.user;
      // console.log("Telegram User:", user);
      
      setIsReady(true);
    } else {
      // Fallback for browser testing
      setIsReady(true);
    }
  }, []);

  if (!isReady) {
    return <div className="page-header"><h1 className="page-title">Loading...</h1></div>;
  }

  return (
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  );
}
