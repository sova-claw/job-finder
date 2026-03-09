import type { Metadata } from "next";

import "./globals.css";
import { Providers } from "@/app/providers";

export const metadata: Metadata = {
  title: "Career Intelligence System",
  description: "AI-driven job intelligence dashboard for Python and ML roles."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
