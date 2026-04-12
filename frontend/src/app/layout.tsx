import type { Metadata } from "next";
import "./globals.css";
import { Inter } from "next/font/google";
import { cn } from "@/lib/utils";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { Providers } from "@/components/providers";
import { SessionTimeoutGuard } from "@/components/SessionTimeoutGuard";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "VitalMind Healthcare",
  description: "AI-driven healthcare platform",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} className={cn("font-sans", inter.variable)}>
      <body className="antialiased">
        <NextIntlClientProvider messages={messages}>
          <Providers>
            <SessionTimeoutGuard>
              {children}
            </SessionTimeoutGuard>
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
