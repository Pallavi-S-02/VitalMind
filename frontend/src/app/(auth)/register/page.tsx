"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2, Stethoscope, User, Zap, Copy, Check } from "lucide-react";

import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

const DEMO_ACCOUNTS = [
  {
    label: "Doctor",
    email: "dr.sharma@vitalmind.com",
    password: "Doctor123!",
    role: "doctor" as const,
    icon: Stethoscope,
    gradient: "from-blue-600/20 to-indigo-600/20",
    border: "border-blue-500/30 hover:border-blue-400/60",
    badge: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    iconColor: "text-blue-400",
    btnGradient: "from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500",
  },
  {
    label: "Patient",
    email: "john@test.com",
    password: "Patient123!",
    role: "patient" as const,
    icon: User,
    gradient: "from-emerald-600/20 to-teal-600/20",
    border: "border-emerald-500/30 hover:border-emerald-400/60",
    badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    iconColor: "text-emerald-400",
    btnGradient: "from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500",
  },
];

const registerSchema = z.object({
  firstName: z.string().min(2, "First name must be at least 2 characters"),
  lastName: z.string().min(2, "Last name must be at least 2 characters"),
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  role: z.enum(["patient", "doctor"], {
    message: "Please select a role",
  }),
  licenseNumber: z.string().optional(),
}).superRefine((data, ctx) => {
  if (data.role === 'doctor' && (!data.licenseNumber || data.licenseNumber.length < 3)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "License number is required for doctors",
      path: ["licenseNumber"]
    });
  }
});

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(key);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const form = useForm<z.infer<typeof registerSchema>>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      firstName: "",
      lastName: "",
      email: "",
      password: "",
      role: "patient",
      licenseNumber: "",
    },
  });

  const selectedRole = form.watch("role");

  async function onSubmit(values: z.infer<typeof registerSchema>) {
    setIsLoading(true);
    setError(null);

    try {
      const payload: any = {
        first_name: values.firstName,
        last_name: values.lastName,
        email: values.email,
        password: values.password,
        role: values.role,
      };

      if (values.role === 'doctor') {
        payload.license_number = values.licenseNumber;
      }

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'}/api/v1/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.message || "Registration failed");
      } else {
        // Redirect to login on success
        router.push("/login?registered=true");
      }
    } catch (err) {
      setError("An unexpected error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 relative overflow-hidden py-12">
      {/* Background elements */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 pointer-events-none">
        <div className="absolute top-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-emerald-900/20 blur-[100px]"></div>
        <div className="absolute bottom-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-blue-900/20 blur-[100px]"></div>
      </div>

      <Link href="/" className="z-10 mb-8 text-2xl font-bold tracking-tighter bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400">
        VitalMind
      </Link>

      <Card className="w-full max-w-md z-10 border-white/10 bg-slate-900/50 backdrop-blur-xl shadow-2xl">
        <CardHeader className="space-y-1 text-center">
          <CardTitle className="text-2xl font-semibold tracking-tight text-white">Create an account</CardTitle>
          <CardDescription className="text-slate-400">
            Enter your details to join VitalMind
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              
              <FormField
                control={form.control}
                name="role"
                render={({ field }) => (
                  <FormItem className="space-y-3 mb-6">
                    <FormLabel className="text-slate-300">I am a...</FormLabel>
                    <FormControl>
                      <RadioGroup
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                        className="flex grid grid-cols-2 gap-4"
                      >
                        <FormItem className="flex items-center space-x-0 space-y-0">
                          <FormControl>
                            <RadioGroupItem value="patient" className="peer sr-only" />
                          </FormControl>
                          <FormLabel className="font-normal w-full rounded-md border-2 border-slate-800 bg-slate-950 p-4 hover:bg-slate-900 hover:text-white peer-data-[state=checked]:border-emerald-500 peer-data-[state=checked]:text-emerald-400 transition-all cursor-pointer text-center">
                            Patient
                          </FormLabel>
                        </FormItem>
                        <FormItem className="flex items-center space-x-0 space-y-0">
                          <FormControl>
                            <RadioGroupItem value="doctor" className="peer sr-only" />
                          </FormControl>
                          <FormLabel className="font-normal w-full rounded-md border-2 border-slate-800 bg-slate-950 p-4 hover:bg-slate-900 hover:text-white peer-data-[state=checked]:border-blue-500 peer-data-[state=checked]:text-blue-400 transition-all cursor-pointer text-center">
                            Doctor
                          </FormLabel>
                        </FormItem>
                      </RadioGroup>
                    </FormControl>
                    <FormMessage className="text-rose-400" />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="firstName"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-slate-300">First Name</FormLabel>
                      <FormControl>
                        <Input placeholder="John" {...field} className="bg-slate-950/50 border-white/10 text-white placeholder:text-slate-500 focus-visible:ring-emerald-500/50" />
                      </FormControl>
                      <FormMessage className="text-rose-400" />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="lastName"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-slate-300">Last Name</FormLabel>
                      <FormControl>
                        <Input placeholder="Doe" {...field} className="bg-slate-950/50 border-white/10 text-white placeholder:text-slate-500 focus-visible:ring-emerald-500/50" />
                      </FormControl>
                      <FormMessage className="text-rose-400" />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-slate-300">Email</FormLabel>
                    <FormControl>
                      <Input placeholder="m@example.com" {...field} className="bg-slate-950/50 border-white/10 text-white placeholder:text-slate-500 focus-visible:ring-emerald-500/50" />
                    </FormControl>
                    <FormMessage className="text-rose-400" />
                  </FormItem>
                )}
              />

              {selectedRole === 'doctor' && (
                <FormField
                  control={form.control}
                  name="licenseNumber"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-slate-300">Medical License Number</FormLabel>
                      <FormControl>
                        <Input placeholder="LIC-12345" {...field} className="bg-slate-950/50 border-white/10 text-white placeholder:text-slate-500 focus-visible:ring-emerald-500/50" />
                      </FormControl>
                      <FormMessage className="text-rose-400" />
                    </FormItem>
                  )}
                />
              )}

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-slate-300">Password</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="••••••••" {...field} className="bg-slate-950/50 border-white/10 text-white placeholder:text-slate-500 focus-visible:ring-emerald-500/50" />
                    </FormControl>
                    <FormMessage className="text-rose-400" />
                  </FormItem>
                )}
              />
              
              {error && (
                <div className="p-3 text-sm text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-md">
                  {error}
                </div>
              )}

              <Button 
                type="submit" 
                className={`w-full text-white border-0 ${selectedRole === 'doctor' ? 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500' : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500'}`}
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating account...
                  </>
                ) : (
                  "Create Account"
                )}
              </Button>
            </form>
          </Form>
        </CardContent>
        <CardFooter className="flex justify-center text-sm text-slate-400">
          <div>
            Already have an account?{" "}
            <Link href="/login" className="text-emerald-400 hover:underline">
              Sign in
            </Link>
          </div>
        </CardFooter>
      </Card>

      {/* ── Demo Accounts ─────────────────────────────────────────────── */}
      <div className="z-10 w-full max-w-md mt-4">
        {/* Divider */}
        <div className="flex items-center gap-2 mb-3">
          <div className="h-px flex-1 bg-white/10" />
          <span className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-widest">
            <Zap className="w-3 h-3 text-yellow-400" />
            Demo Accounts
          </span>
          <div className="h-px flex-1 bg-white/10" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          {DEMO_ACCOUNTS.map((account) => {
            const Icon = account.icon;
            return (
              <div
                key={account.label}
                className={`rounded-xl border bg-gradient-to-br ${account.gradient} ${account.border} p-3.5 transition-all duration-200`}
              >
                {/* Badge */}
                <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase tracking-wider mb-2.5 ${account.badge}`}>
                  <Icon className="w-3 h-3" />
                  {account.label}
                </div>

                {/* Email */}
                <div className="flex items-center gap-1 mb-1">
                  <span className="text-[10px] text-slate-400 font-mono flex-1 truncate">{account.email}</span>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(account.email, `${account.label}-email`)}
                    className="shrink-0 p-0.5 rounded text-slate-500 hover:text-white transition-colors"
                    title="Copy email"
                  >
                    {copiedField === `${account.label}-email`
                      ? <Check className="w-3 h-3 text-emerald-400" />
                      : <Copy className="w-3 h-3" />}
                  </button>
                </div>

                {/* Password */}
                <div className="flex items-center gap-1 mb-3">
                  <span className="text-[10px] text-slate-400 font-mono flex-1">{account.password}</span>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(account.password, `${account.label}-pass`)}
                    className="shrink-0 p-0.5 rounded text-slate-500 hover:text-white transition-colors"
                    title="Copy password"
                  >
                    {copiedField === `${account.label}-pass`
                      ? <Check className="w-3 h-3 text-emerald-400" />
                      : <Copy className="w-3 h-3" />}
                  </button>
                </div>

                {/* Sign in button */}
                <Link
                  href={`/login?email=${encodeURIComponent(account.email)}&hint=${encodeURIComponent(account.password)}`}
                  className={`flex w-full items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r ${account.btnGradient} py-1.5 text-[11px] font-semibold text-white transition-all`}
                >
                  <Zap className="w-3 h-3" />
                  Sign in as {account.label}
                </Link>
              </div>
            );
          })}
        </div>

        <p className="text-center text-[10px] text-slate-600 mt-3">
          Pre-seeded test accounts — click "Sign in" to go directly to the login page.
        </p>
      </div>
    </div>
  );
}
