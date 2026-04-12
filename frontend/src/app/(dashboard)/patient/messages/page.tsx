"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  MessageSquare, 
  Search, 
  Plus, 
  User, 
  Clock, 
  ShieldCheck, 
  Sparkles, 
  ChevronRight,
  Filter,
  MoreVertical,
  Mail,
  Send,
  Loader2,
  ArrowLeft
} from "lucide-react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import DoctorSelectionModal from "@/components/messaging/DoctorSelectionModal";
import { format } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Conversation {
  id: string;
  doctor_id: string;
  doctor_name: string;
  last_message: string | null;
  last_message_at: string;
  updated_at: string;
}

interface Message {
  id: string;
  sender_id: string;
  sender_name: string;
  content: string;
  created_at: string;
}

export default function PatientMessagesPage() {
  const { data: session } = useSession();
  const router = useRouter();
  
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newMessage, setNewMessage] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load conversations
  const fetchConversations = async () => {
    if (!session?.accessToken) return;
    try {
      const res = await fetch(`${API}/api/v1/messages/conversations`, {
        headers: { Authorization: `Bearer ${session.accessToken}` },
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

  useEffect(() => {
    fetchConversations();
  }, [session]);

  // Load message history
  const fetchMessages = async (convId: string) => {
    if (!session?.accessToken) return;
    setMessagesLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/messages/conversations/${convId}/history`, {
        headers: { Authorization: `Bearer ${session.accessToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      }
    } catch (err) {
      console.error("Failed to fetch messages:", err);
    } finally {
      setMessagesLoading(false);
    }
  };

  useEffect(() => {
    if (activeConversation) {
      fetchMessages(activeConversation.id);
    } else {
      setMessages([]);
    }
  }, [activeConversation]);

  // Start new conversation
  const handleSelectDoctor = async (doctorId: string) => {
    if (!session?.accessToken) return;
    try {
      const res = await fetch(`${API}/api/v1/messages/conversations/new`, {
        method: "POST",
        headers: { 
          Authorization: `Bearer ${session.accessToken}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ doctor_id: doctorId }),
      });
      
      if (res.ok) {
        const newConv = await res.json();
        setIsModalOpen(false);
        setActiveConversation(newConv);
        await fetchConversations(); // Refresh list to include new one
      } else {
        const errData = await res.json();
        console.error("Server error starting conversation:", errData);
        // Reset modal loading state via props or state if needed
        setIsModalOpen(false); // Close to reset for now, or keep open and alert
        alert(`Failed to start conversation: ${errData.message || "Unknown error"}`);
      }
    } catch (err) {
      console.error("Failed to start conversation:", err);
      setIsModalOpen(false);
      alert("Network error. Please try again later.");
    }
  };

  // Send message
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMessage.trim() || !activeConversation || !session?.accessToken) return;

    const content = newMessage.trim();
    setNewMessage("");

    try {
      const res = await fetch(`${API}/api/v1/messages/send`, {
        method: "POST",
        headers: { 
          Authorization: `Bearer ${session.accessToken}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ 
          conversation_id: activeConversation.id,
          content 
        }),
      });
      if (res.ok) {
        const sentMsg = await res.json();
        setMessages(prev => [...prev, sentMsg]);
      }
    } catch (err) {
      console.error("Failed to send message:", err);
    }
  };

  const filteredConversations = conversations.filter(c => 
    c.doctor_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-gray-950 via-slate-900 to-gray-950 overflow-hidden" style={{ fontFamily: "'Inter', sans-serif" }}>
      
      {/* Header */}
      <div className="px-6 py-4 flex-shrink-0">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600/20 border border-blue-500/30 rounded-xl">
              <MessageSquare className="h-5 w-5 text-blue-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight">Secure Messaging</h1>
              <p className="text-xs text-gray-500">HIPAA Compliant • End-to-End Encrypted</p>
            </div>
          </div>
          <button 
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-semibold text-sm transition-all shadow-lg shadow-blue-900/40"
          >
            <Plus className="h-4 w-4" />
            New Chat
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 max-w-7xl mx-auto w-full px-6 pb-6 overflow-hidden">
        <div className="h-full bg-gray-900/50 border border-white/10 rounded-3xl overflow-hidden backdrop-blur-md flex flex-col md:flex-row">
          
          {/* Sidebar: Conversation List */}
          <div className={`w-full md:w-80 flex-shrink-0 border-r border-white/5 flex flex-col ${activeConversation ? 'hidden md:flex' : 'flex'}`}>
            <div className="p-4 border-b border-white/5 bg-white/5">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                <input
                  type="text"
                  placeholder="Search chats..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-gray-950/50 border border-white/10 rounded-xl pl-10 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30 transition-all"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
              {loading ? (
                <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-blue-500" /></div>
              ) : filteredConversations.length === 0 ? (
                <div className="py-12 text-center px-4">
                  <Mail className="h-10 w-10 text-gray-700 mx-auto mb-3" />
                  <p className="text-sm text-gray-500">No conversations found</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {filteredConversations.map((conv) => (
                    <button
                      key={conv.id}
                      onClick={() => setActiveConversation(conv)}
                      className={`w-full flex items-center gap-3 p-3 rounded-2xl transition-all text-left group ${
                        activeConversation?.id === conv.id 
                          ? "bg-blue-600/10 border border-blue-500/20" 
                          : "hover:bg-white/5 border border-transparent"
                      }`}
                    >
                      <div className="h-10 w-10 rounded-full bg-gray-800 border border-white/5 flex items-center justify-center flex-shrink-0">
                        <User className={`h-5 w-5 ${activeConversation?.id === conv.id ? 'text-blue-400' : 'text-gray-500'}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <div className={`font-bold text-sm truncate ${activeConversation?.id === conv.id ? 'text-white' : 'text-gray-300'}`}>
                            {conv.doctor_name}
                          </div>
                          <div className="text-[10px] text-gray-600 flex-shrink-0">
                            {format(new Date(conv.last_message_at), 'HH:mm')}
                          </div>
                        </div>
                        <div className="text-xs text-gray-500 truncate mt-0.5">
                          {conv.last_message || "No messages yet"}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Chat Container */}
          <div className={`flex-1 flex flex-col bg-gray-900/20 ${!activeConversation ? 'hidden md:flex' : 'flex'}`}>
            {activeConversation ? (
              <>
                {/* Chat Header */}
                <div className="px-6 py-3 border-b border-white/5 flex items-center justify-between bg-white/5">
                  <div className="flex items-center gap-4">
                    <button 
                      onClick={() => setActiveConversation(null)}
                      className="md:hidden p-2 -ml-2 text-gray-400 hover:text-white"
                    >
                      <ArrowLeft className="h-5 w-5" />
                    </button>
                    <div className="h-10 w-10 rounded-full bg-blue-600/10 border border-blue-500/20 flex items-center justify-center">
                      <User className="h-5 w-5 text-blue-400" />
                    </div>
                    <div>
                      <div className="font-bold text-white">{activeConversation.doctor_name}</div>
                      <div className="flex items-center gap-1.5 text-[10px] text-emerald-500 font-semibold uppercase tracking-wider">
                        <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        Online
                      </div>
                    </div>
                  </div>
                  <button className="p-2 text-gray-500 hover:text-white transition-colors">
                    <MoreVertical className="h-5 w-5" />
                  </button>
                </div>

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                  {messagesLoading ? (
                    <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-blue-500" /></div>
                  ) : messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
                      <div className="h-16 w-16 bg-blue-600/5 rounded-full flex items-center justify-center">
                        <MessageSquare className="h-8 w-8 text-blue-400/30" />
                      </div>
                      <div>
                        <p className="text-gray-400 font-medium">New conversation with {activeConversation.doctor_name}</p>
                        <p className="text-gray-600 text-xs mt-1">Send a message to start the consultation.</p>
                      </div>
                    </div>
                  ) : (
                    messages.map((msg) => {
                      const isMe = msg.sender_id === session?.user?.id;
                      return (
                        <div key={msg.id} className={`flex ${isMe ? 'justify-end' : 'justify-start'} animate-in slide-in-from-bottom-2 duration-300`}>
                          <div className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm ${
                            isMe 
                              ? "bg-blue-600 text-white rounded-tr-none" 
                              : "bg-white/10 text-gray-200 border border-white/5 rounded-tl-none"
                          }`}>
                            {msg.content}
                            <div className={`text-[10px] mt-1.5 ${isMe ? 'text-blue-100/50' : 'text-gray-500'}`}>
                              {format(new Date(msg.created_at), 'HH:mm')}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Message Input */}
                <form onSubmit={handleSendMessage} className="p-4 border-t border-white/5 bg-white/5">
                  <div className="flex items-center gap-3">
                    <input
                      type="text"
                      placeholder="Type your message..."
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      className="flex-1 bg-gray-950/50 border border-white/10 rounded-2xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30 transition-all"
                    />
                    <button 
                      type="submit"
                      disabled={!newMessage.trim()}
                      className="p-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:hover:bg-blue-600 text-white rounded-2xl transition-all shadow-lg shadow-blue-900/40"
                    >
                      <Send className="h-5 w-5" />
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                <div className="max-w-md animate-in fade-in zoom-in duration-700">
                  <div className="h-24 w-24 bg-blue-600/10 border border-blue-500/20 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-[0_0_20px_rgba(37,99,235,0.1)]">
                    <Mail className="h-12 w-12 text-blue-400" />
                  </div>
                  <h2 className="text-2xl font-bold text-white mb-3">No Active Chat Selected</h2>
                  <p className="text-gray-400 mb-8 leading-relaxed">
                    Select a conversation from the sidebar or start a new medical consultation with our specialists.
                  </p>
                  <button 
                    onClick={() => setIsModalOpen(true)}
                    className="px-8 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold transition-all shadow-lg shadow-blue-900/40"
                  >
                    Start New Conversation
                  </button>
                </div>
              </div>
            )}

            {/* AI CTA - Only show when no chat is active to save space */}
            {!activeConversation && (
              <div className="p-6 border-t border-white/5">
                 <div className="bg-gradient-to-r from-indigo-900/40 to-violet-900/40 border border-indigo-700/30 rounded-3xl p-5 flex flex-col md:flex-row items-center justify-between gap-4">
                  <div className="flex items-center gap-4 text-left">
                    <div className="h-10 w-10 bg-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-900/50">
                      <Sparkles className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <h3 className="text-white font-bold text-sm">Need immediate help?</h3>
                      <p className="text-indigo-200/70 text-[10px]">Talk to our AI Medical Assistant 24/7.</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => router.push("/patient/chat")}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold text-xs transition-all shadow-lg shadow-indigo-900/40"
                  >
                    Ask AI
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Doctor Selection Modal */}
      <DoctorSelectionModal 
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSelect={handleSelectDoctor}
      />
    </div>
  );
}
