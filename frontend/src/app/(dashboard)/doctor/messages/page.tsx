"use client";

import { useState, useEffect, useRef } from "react";
import { useSession } from "next-auth/react";
import { 
  Search, 
  Send, 
  User, 
  MoreVertical, 
  Phone, 
  Video, 
  Info,
  Clock,
  Check,
  CheckCheck,
  MessageCircle,
  Loader2,
  Calendar,
  ChevronLeft
} from "lucide-react";
import { format } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Conversation {
  id: string;
  patient_id: string;
  doctor_id: string;
  doctor_name: string;
  patient_name: string;
  last_message: string | null;
  last_message_at: string;
  updated_at: string;
}

interface Message {
  id: string;
  sender_id: string;
  content: string;
  created_at: string;
  is_read: boolean;
}

export default function DoctorMessagesPage() {
  const { data: session } = useSession();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSidebar, setShowSidebar] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (session?.accessToken) {
      fetchConversations();
    }
  }, [session]);

  useEffect(() => {
    if (activeConversation) {
      fetchMessages(activeConversation.id);
      // Auto-mark as read
      markAsRead(activeConversation.id);
      
      // On mobile, hide sidebar when conversation is selected
      if (window.innerWidth < 768) {
        setShowSidebar(false);
      }
    }
  }, [activeConversation]);

  useEffect(scrollToBottom, [messages]);

  const fetchConversations = async () => {
    try {
      const res = await fetch(`${API}/api/v1/messages/conversations`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
      }
    } catch (err) {
      console.error("Failed to fetch conversations:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async (convId: string) => {
    try {
      const res = await fetch(`${API}/api/v1/messages/conversations/${convId}/history`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      }
    } catch (err) {
      console.error("Failed to fetch messages:", err);
    }
  };

  const markAsRead = async (convId: string) => {
    try {
      await fetch(`${API}/api/v1/messages/conversations/${convId}/read`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
    } catch (err) {
      console.error("Failed to mark as read:", err);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMessage.trim() || !activeConversation || !session?.accessToken) return;

    setSending(true);
    try {
      const res = await fetch(`${API}/api/v1/messages/send`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          conversation_id: activeConversation.id,
          content: newMessage,
        }),
      });

      if (res.ok) {
        const msg = await res.json();
        setMessages((prev) => [...prev, msg]);
        setNewMessage("");
        fetchConversations(); // Update last message in sidebar
      }
    } catch (err) {
      console.error("Failed to send message:", err);
    } finally {
      setSending(false);
    }
  };

  const filteredConversations = conversations.filter(conv => 
    conv.patient_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (conv.last_message?.toLowerCase() || "").includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-[calc(100vh-120px)] bg-white rounded-3xl overflow-hidden border border-gray-100 shadow-sm transition-all duration-500">
      {/* Sidebar */}
      <div className={`${showSidebar ? 'w-full md:w-80' : 'hidden md:flex md:w-80'} border-r flex flex-col bg-gray-50/30 transition-all duration-300`}>
        <div className="p-6 border-b bg-white">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Patient Chats</h1>
          </div>
          <div className="relative group">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
            <input
              type="text"
              placeholder="Search patients..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-gray-50 border-none rounded-2xl pl-10 pr-4 py-3 text-sm focus:ring-2 focus:ring-blue-500/20 transition-all"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 opacity-50">
              <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
              <p className="text-xs font-medium text-gray-400 uppercase tracking-widest">Loading chats</p>
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center gap-4">
              <div className="w-16 h-16 rounded-3xl bg-blue-50 flex items-center justify-center">
                <MessageCircle className="h-8 w-8 text-blue-400" />
              </div>
              <div>
                <p className="text-gray-900 font-semibold">No messages yet</p>
                <p className="text-sm text-gray-500 mt-1">Patient inquiries will appear here as soon as they message you.</p>
              </div>
            </div>
          ) : (
            <div className="p-2 space-y-1">
              {filteredConversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => setActiveConversation(conv)}
                  className={`w-full flex items-center gap-4 p-4 rounded-2xl transition-all duration-200 group ${
                    activeConversation?.id === conv.id
                      ? "bg-blue-600 shadow-lg shadow-blue-200 -translate-y-0.5"
                      : "hover:bg-white hover:shadow-md hover:-translate-y-0.5"
                  }`}
                >
                  <div className={`h-12 w-12 rounded-2xl flex items-center justify-center flex-shrink-0 transition-colors ${
                    activeConversation?.id === conv.id ? "bg-white/20" : "bg-blue-50 group-hover:bg-blue-100"
                  }`}>
                    <User className={`h-6 w-6 ${activeConversation?.id === conv.id ? "text-white" : "text-blue-500"}`} />
                  </div>
                  <div className="flex-1 text-left min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className={`font-bold truncate ${activeConversation?.id === conv.id ? "text-white" : "text-gray-900"}`}>
                        {conv.patient_name}
                      </span>
                      <span className={`text-[10px] font-medium uppercase tracking-tighter ${activeConversation?.id === conv.id ? "text-white/60" : "text-gray-400"}`}>
                        {format(new Date(conv.updated_at), "h:mm a")}
                      </span>
                    </div>
                    <p className={`text-sm truncate ${activeConversation?.id === conv.id ? "text-white/80" : "text-gray-500"}`}>
                      {conv.last_message || "No messages yet"}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className={`flex-1 flex flex-col bg-white transition-all duration-500 h-full ${!showSidebar ? 'flex' : 'hidden md:flex'}`}>
        {activeConversation ? (
          <>
            {/* Chat Header */}
            <div className="px-8 py-4 border-b flex items-center justify-between bg-white/80 backdrop-blur-md sticky top-0 z-10">
              <div className="flex items-center gap-4">
                <button 
                  onClick={() => setShowSidebar(true)}
                  className="md:hidden p-2 -ml-2 hover:bg-gray-100 rounded-xl transition-colors"
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
                <div className="h-12 w-12 rounded-2xl bg-blue-50 flex items-center justify-center ring-4 ring-blue-50/50">
                  <User className="h-6 w-6 text-blue-500" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-gray-900">{activeConversation.patient_name}</h2>
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-xs font-semibold text-gray-400 uppercase tracking-widest">Active Consultation</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button className="p-3 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-2xl transition-all">
                  <Phone className="h-5 w-5" />
                </button>
                <button className="p-3 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-2xl transition-all">
                  <Video className="h-5 w-5" />
                </button>
                <button className="p-3 text-gray-400 hover:text-gray-900 hover:bg-gray-100 rounded-2xl transition-all">
                  <MoreVertical className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6 bg-gray-50/30">
              {messages.map((msg, idx) => {
                const isMe = msg.sender_id === session?.user?.id;
                const isNewDay = idx === 0 || 
                  format(new Date(messages[idx-1].created_at), 'yyyy-MM-dd') !== format(new Date(msg.created_at), 'yyyy-MM-dd');

                return (
                  <div key={msg.id} className="space-y-4">
                    {isNewDay && (
                      <div className="flex items-center justify-center py-4">
                        <span className="px-4 py-1.5 bg-white border border-gray-100 rounded-full text-[10px] font-bold text-gray-400 uppercase tracking-widest shadow-sm">
                          {format(new Date(msg.created_at), "MMMM d, yyyy")}
                        </span>
                      </div>
                    )}
                    <div className={`flex ${isMe ? "justify-end" : "justify-start"} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
                      <div className={`max-w-[70%] group`}>
                        <div className={`p-4 rounded-3xl shadow-sm ${
                          isMe 
                            ? "bg-blue-600 text-white rounded-tr-none" 
                            : "bg-white border border-gray-100 text-gray-800 rounded-tl-none"
                        }`}>
                          <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                          <div className={`flex items-center gap-1.5 mt-2 transition-opacity ${isMe ? "justify-end" : "justify-start"}`}>
                            <span className={`text-[10px] font-medium ${isMe ? "text-white/60" : "text-gray-400"}`}>
                              {format(new Date(msg.created_at), "h:mm a")}
                            </span>
                            {isMe && (
                              msg.is_read ? (
                                <CheckCheck className="h-3 w-3 text-blue-200" />
                              ) : (
                                <Check className="h-3 w-3 text-blue-200/50" />
                              )
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>

            {/* Message Input */}
            <div className="p-8 bg-white/80 backdrop-blur-md border-t">
              <form onSubmit={handleSendMessage} className="relative flex items-end gap-4 overflow-visible">
                <div className="flex-1 relative group bg-gray-50 rounded-3xl transition-all focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:bg-white border-2 border-transparent focus-within:border-blue-500/10">
                  <textarea
                    rows={1}
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage(e);
                      }
                    }}
                    placeholder="Type your clinical response..."
                    className="w-full bg-transparent border-none focus:ring-0 text-sm py-4 px-6 max-h-32 resize-none placeholder-gray-400"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!newMessage.trim() || sending}
                  className="h-14 w-14 bg-blue-600 text-white rounded-2xl flex items-center justify-center hover:bg-blue-700 disabled:opacity-50 disabled:grayscale transition-all shadow-lg shadow-blue-200 hover:-translate-y-1 active:scale-95 group"
                >
                  {sending ? (
                    <Loader2 className="h-6 w-6 animate-spin" />
                  ) : (
                    <Send className="h-6 w-6 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                  )}
                </button>
              </form>
              <div className="flex items-center gap-6 mt-4 px-2">
                <button className="flex items-center gap-2 text-xs font-bold text-gray-400 hover:text-blue-500 transition-colors uppercase tracking-widest">
                  <div className="h-1 w-1 rounded-full bg-current" /> Attachment
                </button>
                <button className="flex items-center gap-2 text-xs font-bold text-gray-400 hover:text-blue-500 transition-colors uppercase tracking-widest">
                  <div className="h-1 w-1 rounded-full bg-current" /> Quick Response
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center bg-gray-50/20 p-12 text-center animate-in fade-in duration-1000">
            <div className="w-32 h-32 rounded-[40px] bg-white shadow-2xl shadow-blue-100 flex items-center justify-center mb-10 group relative">
              <div className="absolute inset-0 bg-blue-500/5 rounded-[40px] animate-ping" />
              <div className="absolute inset-4 border-2 border-dashed border-blue-100 rounded-[30px] animate-spin-slow" />
              <MessageCircle className="h-14 w-14 text-blue-500 relative z-10 transition-transform group-hover:scale-110" />
            </div>
            <h3 className="text-3xl font-bold text-gray-900 mb-4 tracking-tight">Select a Patient Conversation</h3>
            <p className="text-gray-500 max-w-sm text-lg leading-relaxed mb-10">
              Welcome back, Doctor. Select a chat from the sidebar to view clinical inquiries and patient messages.
            </p>
            <div className="grid grid-cols-2 gap-4 max-w-md w-full">
              <div className="p-6 bg-white rounded-3xl border border-gray-100 shadow-sm text-left">
                <Clock className="w-6 h-6 text-blue-400 mb-3" />
                <h4 className="font-bold text-gray-900 text-sm mb-1">Response Time</h4>
                <p className="text-xs text-gray-500">Average 4m reply</p>
              </div>
              <div className="p-6 bg-white rounded-3xl border border-gray-100 shadow-sm text-left">
                <Calendar className="w-6 h-6 text-green-400 mb-3" />
                <h4 className="font-bold text-gray-900 text-sm mb-1">Today's Active</h4>
                <p className="text-xs text-gray-500">{conversations.length} total chains</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
