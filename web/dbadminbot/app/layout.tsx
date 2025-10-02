import Footer from "@/components/layout/footer";
import Navbar from "@/components/layout/navbar";
import { Analytics } from "@vercel/analytics/react";
import cx from "classnames";
import { Viewport } from "next";
import { inter, sfPro } from "./fonts";
import "./globals.css";
import { Providers } from "./providers";

export const metadata = {
    title: "DBAdminBot",
    description:
      "DBAdminBot is a conversational database interface that allows users to query databases using natural language.",
    metadataBase: new URL("https://sqlbot.co.kr"),
  };
  
export const viewport: Viewport = {
  themeColor: "#FFF",
}


export default async function RootLayout({
    children,
  }: {
    children: React.ReactNode;
  }) {
    return (
      <html lang="en" className="light">
        <body className={cx(sfPro.variable, inter.variable)}>
          <div className="fixed h-screen w-full bg-gradient-to-br from-indigo-50 via-white to-cyan-100" />
          <Navbar />
          <Providers>
          <main className="py-6 mb-auto">
            {children}
          </main>
          </Providers>
          {/* <Footer /> */}
          <Analytics />
        </body>
      </html>
    );
  }