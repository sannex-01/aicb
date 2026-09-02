import { useState, useEffect } from 'react';

export default function Catalog() {
  const [search, setSearch] = useState('');
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/v1/miniapp/catalog')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setProducts(data);
        } else {
          console.error("API did not return an array:", data);
          setProducts([]);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Error fetching catalog", err);
        setLoading(false);
      });
  }, []);

  const filtered = products.filter(p => p.title?.toLowerCase().includes(search.toLowerCase()));

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Catalog</h1>
        <p className="page-subtitle">Browse all products</p>
        
        <input 
          type="text" 
          placeholder="Search products..." 
          className="chat-input" 
          style={{ width: '100%', marginTop: '16px', marginBottom: '24px' }}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="product-grid">
        {loading ? (
          <p>Loading products...</p>
        ) : filtered.length === 0 ? (
          <p>No products found.</p>
        ) : (
          filtered.map(product => (
            <div key={product.id} className="product-card glass-panel">
              <img src={product.image || 'https://via.placeholder.com/150'} alt={product.title} className="product-image" />
              <div className="product-info">
                <span className="product-title">{product.title}</span>
                <span className="product-price">{product.currency} {product.price}</span>
              </div>
              <button className="btn-primary" style={{ padding: '8px', fontSize: '14px', marginTop: 'auto' }}>
                Add to Cart
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
