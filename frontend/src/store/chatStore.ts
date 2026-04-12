import { create } from 'zustand';
import { io, Socket } from 'socket.io-client';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  intent?: string;
}

interface ChatState {
  messages: ChatMessage[];
  sessionId: string | null;
  isConnected: boolean;
  isTyping: boolean;
  error: string | null;
  socket: Socket | null;
  streamingContent: string;
  
  // Actions
  connect: (token: string) => void;
  disconnect: () => void;
  sendMessage: (content: string) => void;
  setSessionId: (id: string) => void;
  clearHistory: () => void;
  loadHistory: (token: string, sessionId: string) => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  sessionId: null,
  isConnected: false,
  isTyping: false,
  error: null,
  socket: null,
  streamingContent: "",

  connect: (token: string) => {
    const { socket: existingSocket } = get();
    if (existingSocket) {
      existingSocket.disconnect();
    }

    const socketUrl = process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:5000';
    
    // Connect to websocket server
    const socket = io(socketUrl, {
      auth: { token },
      transports: ['websocket', 'polling'], // Fallback to polling if wss fails
    });

    socket.on('connect', () => {
      set({ isConnected: true, error: null });
    });

    socket.on('disconnect', () => {
      set({ isConnected: false });
    });

    socket.on('error', (err: any) => {
      console.error('Socket error:', err);
      set({ error: err.detail || 'Connection error', isTyping: false });
    });

    socket.on('chat_chunk', (data: { content: string }) => {
      set((state) => ({
        isTyping: false,
        streamingContent: state.streamingContent + data.content
      }));
    });

    socket.on('chat_complete', (data: any) => {
      // Create new message from accumulated content or the explicit final response
      const finalContent = data.response;
      
      set((state) => ({
        messages: [
          ...state.messages,
          {
            id: Date.now().toString(),
            role: 'assistant',
            content: finalContent,
            timestamp: new Date(),
            intent: data.intent
          }
        ],
        streamingContent: "",
        sessionId: data.session_id,
        isTyping: false
      }));
    });

    set({ socket });
  },

  disconnect: () => {
    const { socket } = get();
    if (socket) {
      socket.disconnect();
    }
    set({ socket: null, isConnected: false });
  },

  sendMessage: (content: string) => {
    const { socket, sessionId, messages } = get();
    
    // Add user message to UI immediately
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date()
    };

    set({ 
      messages: [...messages, userMsg],
      isTyping: true,
      error: null,
      streamingContent: "" 
    });

    // Send over socket
    if (socket && socket.connected) {
      socket.emit('chat_message', {
        message: content,
        session_id: sessionId
      });
    } else {
      // Fallback if not connected
      set({ 
        error: "Unable to connect to the AI Assistant. Please try again.",
        isTyping: false 
      });
    }
  },

  setSessionId: (id: string) => set({ sessionId: id }),
  
  clearHistory: () => set({ messages: [], sessionId: null, error: null }),

  loadHistory: async (token: string, sessionId: string) => {
    try {
      const socketUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';
      const res = await fetch(`${socketUrl}/api/v1/chat/session/${sessionId}/history`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (!res.ok) throw new Error('Failed to load history');
      
      const data = await res.json();
      
      const loadedMessages = data.messages.map((m: any, i: number) => ({
        id: `hist-${i}`,
        role: m.role,
        content: m.content,
        timestamp: new Date() // Ideally from backend, but standard format lacks it
      }));

      set({ messages: loadedMessages, sessionId });
    } catch (err: any) {
      set({ error: "Could not load past conversation" });
    }
  }
}));
