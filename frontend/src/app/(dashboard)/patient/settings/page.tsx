"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { 
  User, 
  Shield, 
  Bell, 
  Lock, 
  Save, 
  Loader2, 
  CheckCircle2, 
  AlertCircle,
  Phone,
  Mail,
  MapPin,
  Heart,
  Calendar,
  Baby,
  X,
  Plus,
  Activity,
  Stethoscope,
  AlertTriangle
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

type Tab = "account" | "health" | "emergency";

// --- Tag Input Component ---
interface TagInputProps {
  label: string;
  placeholder: string;
  tags: string[];
  setTags: (tags: string[]) => void;
  icon: React.ElementType;
}

function TagInput({ label, placeholder, tags, setTags, icon: Icon }: TagInputProps) {
  const [inputValue, setInputValue] = useState("");

  const addTag = () => {
    if (inputValue.trim() && !tags.includes(inputValue.trim())) {
      setTags([...tags, inputValue.trim()]);
      setInputValue("");
    }
  };

  const removeTag = (tagToRemove: string) => {
    setTags(tags.filter((t) => t !== tagToRemove));
  };

  return (
    <div className="space-y-3">
      <Label className="text-gray-200 font-semibold text-sm">/ {label}</Label>
      <div className="flex flex-wrap gap-2 mb-2 min-h-[32px]">
        {tags.map((tag) => (
          <Badge key={tag} variant="secondary" className="px-3 py-1 gap-2 bg-violet-500/10 text-violet-400 border-violet-500/20">
            {tag}
            <button type="button" onClick={() => removeTag(tag)} className="hover:text-violet-200">
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
        {tags.length === 0 && <span className="text-xs text-gray-600 italic">No items added yet.</span>}
      </div>
      <div className="relative">
        <Icon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
        <Input
          placeholder={placeholder}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onBlur={addTag}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addTag();
            }
          }}
          className="pl-10 pr-12 bg-gray-950/50 border-white/20 text-gray-200 placeholder:text-gray-600"
        />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={addTag}
          className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8 p-0"
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}


export default function PatientSettingsPage() {
  const { data: session, update: updateSession } = useSession();
  const [activeTab, setActiveTab] = useState<Tab>("account");
  const [isLoading, setIsLoading] = useState(false);
  const [isPageLoading, setIsPageLoading] = useState(true);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Form states
  const [accountData, setAccountData] = useState({
    firstName: "",
    lastName: "",
    email: "",
    phone: "",
  });

  const [healthData, setHealthData] = useState({
    dob: "",
    gender: "",
    bloodType: "",
    address: "",
    height: "",
    weight: "",
    conditions: [] as string[],
    allergies: [] as string[],
    chronicDiseases: [] as string[],
  });

  const [emergencyData, setEmergencyData] = useState({
    name: "",
    phone: "",
    relation: "",
  });

  const [patientProfileId, setPatientProfileId] = useState<string | null>(null);

  // Fetch data
  useEffect(() => {
    const fetchData = async () => {
      if (!session?.accessToken) return;

      try {
        // 1. Fetch User data
        const userRes = await fetch(`${API}/api/v1/auth/me`, {
          headers: { Authorization: `Bearer ${session.accessToken}` },
          cache: "no-store",
        });
        const userData = await userRes.json();
        
        setAccountData({
          firstName: userData.first_name || "",
          lastName: userData.last_name || "",
          email: userData.email || "",
          phone: userData.phone_number || "",
        });

        // 2. Fetch Patient Profile data
        const profileRes = await fetch(`${API}/api/v1/patients/profile`, {
          headers: { Authorization: `Bearer ${session.accessToken}` },
          cache: "no-store",
        });
        
        if (profileRes.ok) {
          const profileData = await profileRes.json();
          setPatientProfileId(profileData.id);
          setHealthData({
            dob: profileData.date_of_birth ? profileData.date_of_birth.split("T")[0] : "",
            gender: profileData.gender || "",
            bloodType: profileData.blood_type || "",
            address: profileData.address || "",
            height: profileData.height_cm ? String(profileData.height_cm) : "",
            weight: profileData.weight_kg ? String(profileData.weight_kg) : "",
            conditions: profileData.medical_history || [],
            allergies: profileData.allergies || [],
            chronicDiseases: profileData.chronic_diseases || [],
          });
          setEmergencyData({
            name: profileData.emergency_contact_name || "",
            phone: profileData.emergency_contact_phone || "",
            relation: profileData.emergency_contact_relation || "",
          });
        }
      } catch (err) {
        console.error("Failed to fetch settings:", err);
      } finally {
        setIsPageLoading(false);
      }
    };

    fetchData();
  }, [session]);

  const handleUpdateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setFeedback(null);

    try {
      const res = await fetch(`${API}/api/v1/auth/me`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify({
          first_name: accountData.firstName,
          last_name: accountData.lastName,
          phone_number: accountData.phone,
          email: accountData.email,
        }),
      });

      if (!res.ok) throw new Error("Failed to update account information");

      setFeedback({ type: "success", message: "Account information updated successfully!" });
      if (updateSession) {
        await updateSession({
          ...session,
          user: {
            ...session?.user,
            first_name: accountData.firstName,
            last_name: accountData.lastName,
          }
        });
      }
    } catch (err) {
      setFeedback({ type: "error", message: err instanceof Error ? err.message : "An error occurred" });
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateHealth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientProfileId) return;
    setIsLoading(true);
    setFeedback(null);

    try {
      const res = await fetch(`${API}/api/v1/patients/${patientProfileId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify({
          date_of_birth: healthData.dob,
          gender: healthData.gender,
          blood_type: healthData.bloodType,
          address: healthData.address,
          height_cm: healthData.height ? parseFloat(healthData.height) : null,
          weight_kg: healthData.weight ? parseFloat(healthData.weight) : null,
          medical_history: healthData.conditions,
          allergies: healthData.allergies,
          chronic_diseases: healthData.chronicDiseases,
          emergency_contact_name: emergencyData.name,
          emergency_contact_phone: emergencyData.phone,
          emergency_contact_relation: emergencyData.relation,
        }),
      });

      if (!res.ok) throw new Error("Failed to update health profile");

      setFeedback({ type: "success", message: "Health profile updated successfully!" });
    } catch (err) {
      setFeedback({ type: "error", message: err instanceof Error ? err.message : "An error occurred" });
    } finally {
      setIsLoading(false);
    }
  };

  if (isPageLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500 pb-20">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Manage your account information and medical profile.</p>
      </div>

      <div className="flex flex-col md:flex-row gap-8">
        {/* Navigation Sidebar */}
        <aside className="w-full md:w-64 flex flex-col gap-2">
          <Button
            variant={activeTab === "account" ? "default" : "ghost"}
            className={`justify-start gap-3 h-12 px-4 transition-all ${
              activeTab === "account" 
                ? "bg-white text-gray-900 shadow-xl" 
                : "text-gray-400 hover:text-white hover:bg-white/10"
            }`}
            onClick={() => setActiveTab("account")}
          >
            <User className={`h-4 w-4 ${activeTab === "account" ? "text-gray-900" : "text-gray-500"}`} />
            Account Information
          </Button>
          <Button
            variant={activeTab === "health" ? "default" : "ghost"}
            className={`justify-start gap-3 h-12 px-4 transition-all ${
              activeTab === "health" 
                ? "bg-white text-gray-900 shadow-xl" 
                : "text-gray-400 hover:text-white hover:bg-white/10"
            }`}
            onClick={() => setActiveTab("health")}
          >
            <Shield className={`h-4 w-4 ${activeTab === "health" ? "text-gray-900" : "text-gray-500"}`} />
            Health Profile
          </Button>
          <Button
            variant={activeTab === "emergency" ? "default" : "ghost"}
            className={`justify-start gap-3 h-12 px-4 transition-all ${
              activeTab === "emergency" 
                ? "bg-white text-gray-900 shadow-xl" 
                : "text-gray-400 hover:text-white hover:bg-white/10"
            }`}
            onClick={() => setActiveTab("emergency")}
          >
            <Heart className={`h-4 w-4 ${activeTab === "emergency" ? "text-gray-900" : "text-gray-500"}`} />
            Emergency Contact
          </Button>
          <Separator className="my-4" />
          <Button variant="ghost" className="justify-start gap-3 h-12 px-4 text-gray-600 cursor-not-allowed" disabled>
            <Bell className="h-4 w-4 text-gray-700" />
            Notifications (Soon)
          </Button>
          <Button variant="ghost" className="justify-start gap-3 h-12 px-4 text-gray-600 cursor-not-allowed" disabled>
            <Lock className="h-4 w-4 text-gray-700" />
            Privacy & Security (Soon)
          </Button>
        </aside>

        {/* Main Content */}
        <main className="flex-1 space-y-6">
          {feedback && (
            <div className={`p-4 rounded-lg flex items-start gap-3 animate-in slide-in-from-top-4 ${
              feedback.type === "success" ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-red-50 text-red-800 border border-red-200"
            }`}>
              {feedback.type === "success" ? <CheckCircle2 className="h-5 w-5 mt-0.5" /> : <AlertCircle className="h-5 w-5 mt-0.5" />}
              <span className="text-sm font-medium">{feedback.message}</span>
            </div>
          )}

          {activeTab === "account" && (
            <form onSubmit={handleUpdateAccount}>
              <Card className="border-white/10 bg-slate-900/80 backdrop-blur-xl shadow-2xl">
                <CardHeader>
                  <CardTitle>Account Information</CardTitle>
                  <CardDescription>Update your personal details and contact information.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="firstName" className="text-gray-300 font-medium">First Name</Label>
                      <div className="relative">
                        <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                        <Input
                          id="firstName"
                          value={accountData.firstName}
                          onChange={(e) => setAccountData({ ...accountData, firstName: e.target.value })}
                          className="pl-10 bg-gray-950/50 border-white/20 text-gray-200 placeholder:text-gray-600 focus:ring-violet-500/30"
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="lastName">Last Name</Label>
                      <Input
                        id="lastName"
                        value={accountData.lastName}
                        onChange={(e) => setAccountData({ ...accountData, lastName: e.target.value })}
                        className="bg-gray-950/50 border-white/20 text-gray-200 placeholder:text-gray-600 focus:ring-violet-500/30"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email">Email Address</Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                      <Input
                        id="email"
                        type="email"
                        value={accountData.email}
                        onChange={(e) => setAccountData({ ...accountData, email: e.target.value })}
                        className="pl-10 bg-gray-950/50 border-white/20 text-gray-200 placeholder:text-gray-600 focus:ring-violet-500/30"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone Number</Label>
                    <div className="relative">
                      <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                      <Input
                        id="phone"
                        value={accountData.phone}
                        onChange={(e) => setAccountData({ ...accountData, phone: e.target.value })}
                        className="pl-10 bg-gray-950/50 border-white/20 text-gray-200 placeholder:text-gray-600 focus:ring-violet-500/30"
                      />
                    </div>
                  </div>
                </CardContent>
                <CardFooter className="bg-white/[0.02] border-t border-white/5 rounded-b-xl px-6 py-4">
                  <Button type="submit" disabled={isLoading} className="gap-2 bg-violet-600 hover:bg-violet-500 shadow-lg shadow-violet-900/20">
                    {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Save Changes
                  </Button>
                </CardFooter>
              </Card>
            </form>
          )}

          {activeTab === "health" && (
            <form onSubmit={handleUpdateHealth} className="space-y-6">
              {/* Biometrics & Demographics */}
              <Card className="border-white/10 bg-slate-900/80 backdrop-blur-xl shadow-2xl">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="h-5 w-5 text-rose-500" />
                    Biometrics & Demographics
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="height" className="text-gray-300 font-medium">Height (cm)</Label>
                      <Input
                        id="height"
                        type="number"
                        placeholder="e.g. 175"
                        value={healthData.height}
                        onChange={(e) => setHealthData({ ...healthData, height: e.target.value })}
                        className="bg-gray-950/50 border-white/20 text-gray-200 placeholder:text-gray-600"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="weight" className="text-gray-300 font-medium">Weight (kg)</Label>
                      <Input
                        id="weight"
                        type="number"
                        placeholder="e.g. 70"
                        value={healthData.weight}
                        onChange={(e) => setHealthData({ ...healthData, weight: e.target.value })}
                        className="bg-gray-950/50 border-white/20 text-gray-200 placeholder:text-gray-600"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="dob" className="text-gray-300 font-medium">Date of Birth</Label>
                      <div className="relative">
                        <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                        <Input
                          id="dob"
                          type="date"
                          value={healthData.dob}
                          onChange={(e) => setHealthData({ ...healthData, dob: e.target.value })}
                          className="pl-10 bg-gray-950/50 border-white/20 text-gray-200 focus:ring-violet-500/30"
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="gender">Gender</Label>
                      <select
                        id="gender"
                        value={healthData.gender}
                        onChange={(e) => setHealthData({ ...healthData, gender: e.target.value })}
                        className="w-full h-10 px-3 py-2 bg-gray-950/50 border border-white/20 rounded-lg text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-violet-500/50 transition-all cursor-pointer"
                      >
                        <option value="">Select Gender</option>
                        <option value="male">Male</option>
                        <option value="female">Female</option>
                        <option value="other">Other</option>
                        <option value="prefer_not_to_say">Prefer not to say</option>
                      </select>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="bloodType" className="text-gray-300 font-medium">Blood Type</Label>
                    <Input
                      id="bloodType"
                      placeholder="e.g. A+"
                      value={healthData.bloodType}
                      onChange={(e) => setHealthData({ ...healthData, bloodType: e.target.value })}
                      className="max-w-[200px] bg-gray-950/50 border-white/20 text-gray-200 placeholder:text-gray-600"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="address" className="text-gray-300 font-medium">Residential Address</Label>
                    <div className="relative">
                      <MapPin className="absolute left-3 top-3 h-4 w-4 text-gray-500" />
                      <textarea
                        id="address"
                        rows={2}
                        value={healthData.address}
                        onChange={(e) => setHealthData({ ...healthData, address: e.target.value })}
                        className="w-full px-10 py-2.5 bg-gray-950/50 border border-white/20 rounded-lg text-sm text-gray-200 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 min-h-[80px] transition-all"
                        placeholder="Your full address..."
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Medical Background */}
              <Card className="border-white/10 bg-slate-900/80 backdrop-blur-xl shadow-2xl">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Stethoscope className="h-5 w-5 text-sky-500" />
                    Medical Background
                  </CardTitle>
                  <CardDescription className="text-gray-400">Press Enter to add items to the lists.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-8">
                  <TagInput
                    label="Medical Conditions"
                    placeholder="e.g. Hypertension, Diabetes"
                    tags={healthData.conditions}
                    setTags={(tags) => setHealthData({ ...healthData, conditions: tags })}
                    icon={Activity}
                  />
                  <Separator className="border-white/5" />
                  <TagInput
                    label="Known Allergies"
                    placeholder="e.g. Penicillin, Peanuts"
                    tags={healthData.allergies}
                    setTags={(tags) => setHealthData({ ...healthData, allergies: tags })}
                    icon={AlertTriangle}
                  />
                  <Separator className="border-white/5" />
                  <TagInput
                    label="Chronic Diseases"
                    placeholder="e.g. Asthma, Heart Disease"
                    tags={healthData.chronicDiseases}
                    setTags={(tags) => setHealthData({ ...healthData, chronicDiseases: tags })}
                    icon={Shield}
                  />
                </CardContent>
                <CardFooter className="bg-white/[0.02] border-t border-white/5 rounded-b-xl px-6 py-4">
                  <Button type="submit" disabled={isLoading} className="gap-2 bg-violet-600 hover:bg-violet-500 shadow-lg shadow-violet-900/20">
                    {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Save Health Profile
                  </Button>
                </CardFooter>
              </Card>
            </form>
          )}

          {activeTab === "emergency" && (
            <form onSubmit={handleUpdateHealth}>
              <Card className="border-white/10 bg-slate-900/80 backdrop-blur-xl shadow-2xl">
                <CardHeader>
                  <CardTitle>Emergency Contact</CardTitle>
                  <CardDescription>Primary contact person in case of a medical emergency.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="eName" className="text-gray-300 font-medium">Contact Name</Label>
                    <Input
                      id="eName"
                      placeholder="Full Name"
                      value={emergencyData.name}
                      onChange={(e) => setEmergencyData({ ...emergencyData, name: e.target.value })}
                      className="bg-gray-950/50 border-white/20 text-gray-200 placeholder:text-gray-600"
                    />
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="ePhone" className="text-gray-300 font-medium">Contact Phone</Label>
                      <div className="relative">
                        <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                        <Input
                          id="ePhone"
                          value={emergencyData.phone}
                          onChange={(e) => setEmergencyData({ ...emergencyData, phone: e.target.value })}
                          className="pl-10 bg-gray-950/50 border-white/20 text-gray-200 placeholder:text-gray-600"
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="relation" className="text-gray-300 font-medium">Relationship</Label>
                      <Input
                        id="relation"
                        placeholder="e.g. Spouse, Parent"
                        value={emergencyData.relation}
                        onChange={(e) => setEmergencyData({ ...emergencyData, relation: e.target.value })}
                        className="bg-gray-950/50 border-white/20 text-gray-200 placeholder:text-gray-600"
                      />
                    </div>
                  </div>
                </CardContent>
                <CardFooter className="bg-white/[0.02] border-t border-white/5 rounded-b-xl px-6 py-4">
                  <Button type="submit" disabled={isLoading} className="gap-2 bg-violet-600 hover:bg-violet-500 shadow-lg shadow-violet-900/20">
                    {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Update Emergency Contact
                  </Button>
                </CardFooter>
              </Card>
            </form>
          )}
        </main>
      </div>
    </div>
  );
}
