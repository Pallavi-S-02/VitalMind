"use client";

import React, { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { 
  User, 
  Mail, 
  Phone, 
  Stethoscope, 
  FileText, 
  DollarSign, 
  ShieldCheck,
  Save,
  Loader2,
  CheckCircle2,
  AlertCircle
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface ProfileData {
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string;
}

interface DoctorData {
  specialization: string;
  bio: string;
  consultation_fee: number;
}

export default function DoctorSettingsPage() {
  const { data: session } = useSession();
  const [activeTab, setActiveTab] = useState<"profile" | "clinical" | "security">("profile");
  
  const [profileData, setProfileData] = useState<ProfileData>({
    first_name: "",
    last_name: "",
    email: "",
    phone_number: ""
  });
  
  const [doctorData, setDoctorData] = useState<DoctorData>({
    specialization: "",
    bio: "",
    consultation_fee: 0
  });

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (session?.accessToken) {
      fetchData();
    }
  }, [session]);

  const fetchData = async () => {
    try {
      setIsLoading(true);
      const [authRes, doctorRes] = await Promise.all([
        fetch(`${API}/api/v1/auth/me`, {
          headers: { Authorization: `Bearer ${session?.accessToken}` }
        }),
        fetch(`${API}/api/v1/doctors/me`, {
          headers: { Authorization: `Bearer ${session?.accessToken}` }
        })
      ]);

      if (authRes.ok) {
        const authData = await authRes.json();
        setProfileData({
          first_name: authData.first_name || "",
          last_name: authData.last_name || "",
          email: authData.email || "",
          phone_number: authData.phone_number || ""
        });
      }

      if (doctorRes.ok) {
        const dData = await doctorRes.json();
        setDoctorData({
          specialization: dData.doctor.specialization || "",
          bio: dData.doctor.bio || "",
          consultation_fee: dData.doctor.consultation_fee || 0
        });
      }
    } catch (err) {
      console.error("Failed to fetch settings", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setMessage(null);
    try {
      const res = await fetch(`${API}/api/v1/auth/me`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`
        },
        body: JSON.stringify(profileData)
      });

      if (res.ok) {
        setMessage({ type: "success", text: "Account details updated successfully!" });
      } else {
        throw new Error("Failed to update profile");
      }
    } catch (err) {
      setMessage({ type: "error", text: "Error updating account details." });
    } finally {
      setIsSaving(false);
    }
  };

  const handleUpdateClinical = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setMessage(null);
    try {
      const res = await fetch(`${API}/api/v1/doctors/me`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`
        },
        body: JSON.stringify(doctorData)
      });

      if (res.ok) {
        setMessage({ type: "success", text: "Clinical profile updated successfully!" });
      } else {
        throw new Error("Failed to update clinical profile");
      }
    } catch (err) {
      setMessage({ type: "error", text: "Error updating clinical profile." });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-96">
        <Loader2 className="h-10 w-10 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">Settings</h1>
        <p className="text-gray-500 mt-1">Manage your professional profile and account security.</p>
      </div>

      {message && (
        <div className={`mb-6 p-4 rounded-xl flex items-center gap-3 ${
          message.type === "success" ? "bg-emerald-50 text-emerald-700 border border-emerald-100" : "bg-red-50 text-red-700 border border-red-100"
        }`}>
          {message.type === "success" ? <CheckCircle2 className="h-5 w-5" /> : <AlertCircle className="h-5 w-5" />}
          <p className="text-sm font-medium">{message.text}</p>
        </div>
      )}

      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        {/* Tabs */}
        <div className="flex border-b border-gray-100 bg-gray-50/50">
          {[
            { id: "profile", label: "Account Details", icon: User },
            { id: "clinical", label: "Clinical Profile", icon: Stethoscope },
            { id: "security", label: "Security", icon: ShieldCheck }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id as any);
                setMessage(null);
              }}
              className={`flex items-center gap-2 px-6 py-4 text-sm font-semibold transition-all relative ${
                activeTab === tab.id ? "text-blue-600 bg-white" : "text-gray-500 hover:text-gray-900"
              }`}
            >
              <tab.icon className={`h-4 w-4 ${activeTab === tab.id ? "text-blue-600" : "text-gray-400"}`} />
              {tab.label}
              {activeTab === tab.id && (
                <div className="absolute bottom-0 left-0 right-0 h-1 bg-blue-600 rounded-t-full" />
              )}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-8">
          {activeTab === "profile" && (
            <form onSubmit={handleUpdateProfile} className="space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-gray-700">First Name</label>
                  <div className="relative">
                    <User className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                    <input
                      type="text"
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
                      value={profileData.first_name}
                      onChange={(e) => setProfileData({ ...profileData, first_name: e.target.value })}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-gray-700">Last Name</label>
                  <div className="relative">
                    <User className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                    <input
                      type="text"
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
                      value={profileData.last_name}
                      onChange={(e) => setProfileData({ ...profileData, last_name: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold text-gray-700">Email Address</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                  <input
                    type="email"
                    readOnly
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-100 bg-gray-50 text-gray-500 cursor-not-allowed"
                    value={profileData.email}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold text-gray-700">Phone Number</label>
                <div className="relative">
                  <Phone className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="+91 XXXXX XXXXX"
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
                    value={profileData.phone_number}
                    onChange={(e) => setProfileData({ ...profileData, phone_number: e.target.value })}
                  />
                </div>
              </div>

              <div className="pt-4">
                <button
                  disabled={isSaving}
                  type="submit"
                  className="inline-flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-full font-semibold hover:bg-blue-700 transition-all disabled:opacity-50"
                >
                  {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save Changes
                </button>
              </div>
            </form>
          )}

          {activeTab === "clinical" && (
            <form onSubmit={handleUpdateClinical} className="space-y-6">
              <div className="space-y-2">
                <label className="text-sm font-semibold text-gray-700">Specialization</label>
                <div className="relative">
                  <Stethoscope className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
                    value={doctorData.specialization}
                    onChange={(e) => setDoctorData({ ...doctorData, specialization: e.target.value })}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold text-gray-700">Consultation Fee (IDR/USD)</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                  <input
                    type="number"
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
                    value={doctorData.consultation_fee}
                    onChange={(e) => setDoctorData({ ...doctorData, consultation_fee: parseFloat(e.target.value) || 0 })}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold text-gray-700">Professional Bio</label>
                <div className="relative">
                  <FileText className="absolute left-3 top-4 h-4 w-4 text-gray-400" />
                  <textarea
                    rows={4}
                    className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all resize-none"
                    placeholder="Tell us about your clinical experience..."
                    value={doctorData.bio}
                    onChange={(e) => setDoctorData({ ...doctorData, bio: e.target.value })}
                  />
                </div>
              </div>

              <div className="pt-4">
                <button
                  disabled={isSaving}
                  type="submit"
                  className="inline-flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-full font-semibold hover:bg-blue-700 transition-all disabled:opacity-50"
                >
                  {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Update Clinical Profile
                </button>
              </div>
            </form>
          )}

          {activeTab === "security" && (
            <div className="space-y-8">
              <div>
                <h3 className="text-sm font-bold text-gray-900 mb-4 uppercase tracking-wider">Change Password</h3>
                <div className="space-y-4 max-w-md">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-600">Current Password</label>
                    <input type="password" disabled className="w-full px-4 py-2 rounded-xl border border-gray-100 bg-gray-50 text-gray-400 cursor-not-allowed" placeholder="••••••••" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-600">New Password</label>
                    <input type="password" disabled className="w-full px-4 py-2 rounded-xl border border-gray-100 bg-gray-50 text-gray-400 cursor-not-allowed" placeholder="Minimum 8 characters" />
                  </div>
                  <button disabled className="px-6 py-2 bg-gray-100 text-gray-400 rounded-full font-semibold cursor-not-allowed">
                    Update Password
                  </button>
                  <p className="text-xs text-amber-600 italic">Self-service password change is temporarily disabled. Please contact your system administrator.</p>
                </div>
              </div>
              
              <div className="pt-6 border-t border-gray-50">
                <h3 className="text-sm font-bold text-gray-900 mb-2 uppercase tracking-wider text-red-600">Danger Zone</h3>
                <p className="text-sm text-gray-500 mb-4">You can request account deactivation if you are leaving the practice.</p>
                <button className="px-6 py-2 border border-red-200 text-red-600 rounded-full font-semibold hover:bg-red-50 transition-colors">
                  Request Deactivation
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
