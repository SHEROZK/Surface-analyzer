import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Surface Analyzer",
  description: "Visualize tile materials in real spaces.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
