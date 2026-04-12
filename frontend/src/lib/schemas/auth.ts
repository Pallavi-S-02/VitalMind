import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email({ message: "Invalid email address" }),
  password: z.string().min(8, { message: "Password must be at least 8 characters" }),
});

export type LoginFormValues = z.infer<typeof loginSchema>;

export const registerSchema = z.object({
  email: z.string().email({ message: "Invalid email address" }),
  password: z.string().min(8, { message: "Password must be at least 8 characters" }),
  firstName: z.string().min(2, { message: "First name must be at least 2 characters" }),
  lastName: z.string().min(2, { message: "Last name must be at least 2 characters" }),
  role: z.enum(["patient", "doctor"]),
});

export type RegisterFormValues = z.infer<typeof registerSchema>;

export const userSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  firstName: z.string(),
  lastName: z.string(),
  role: z.enum(["patient", "doctor", "nurse", "admin"]),
  isActive: z.boolean(),
});

export type User = z.infer<typeof userSchema>;

export const authResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  user: userSchema,
});

export type AuthResponse = z.infer<typeof authResponseSchema>;
