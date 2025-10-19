import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trilingual Translator - OpenAI First",
  description: "Simple trilingual translator using OpenAI SDK",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
