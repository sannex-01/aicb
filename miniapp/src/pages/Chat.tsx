import { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';

export default function Chat() {
  const [messages, setMessages] = useState([
    { id: 1, text: "Hello! I'm your AI assistant. How can I help you today?", isBot: true },
  ]);
  const [input, setInput] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    // Add user message
    const newMsg = { id: Date.now(), text: input, isBot: false };
    const botMsgId = Date.now() + 1;
    
    setMessages(prev => [
      ...prev, 
      newMsg, 
      { id: botMsgId, text: '', isBot: true }
    ]);
    setInput('');

    try {
      const tg = (window as any).Telegram?.WebApp;
      const userId = tg?.initDataUnsafe?.user?.id?.toString() || 'guest';
      const firstName = tg?.initDataUnsafe?.user?.first_name || 'Guest';

      const response = await fetch('/api/v1/miniapp/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message: newMsg.text, 
          user_id: userId,
          first_name: firstName 
        })
      });

      if (!response.body) return;
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '').trim();
            if (dataStr === '[DONE]') break;
            
            try {
              const data = JSON.parse(dataStr);
              setMessages(prev => prev.map(msg => 
                msg.id === botMsgId 
                  ? { ...msg, text: msg.text + data.content }
                  : msg
              ));
            } catch (e) {
              // Ignore parse errors on incomplete chunks
            }
          }
        }
      }
    } catch (err) {
      console.error("Chat error", err);
      setMessages(prev => prev.map(msg => 
        msg.id === botMsgId 
          ? { ...msg, text: "Sorry, I'm having trouble connecting right now." }
          : msg
      ));
    }
  };

  return (
    <div style={{ paddingBottom: '70px' }}>
      <div className="page-header" style={{ paddingBottom: '0' }}>
        <h1 className="page-title">Assistant</h1>
      </div>
      
      <div className="chat-container">
        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.isBot ? 'bot' : 'user'}`}>
            {msg.text}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div className="chat-input-area">
        <input 
          type="text" 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask me anything..." 
          className="chat-input"
        />
        <button onClick={handleSend} className="send-button">
          <Send size={20} style={{ marginLeft: '-2px' }} />
        </button>
      </div>
    </div>
  );
}
