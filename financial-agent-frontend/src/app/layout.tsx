import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinAgent — AI-Powered Financial Assistant",
  description:
    "FinAgent is an AI-powered financial assistant that helps students, employees and business owners track income and expenses, set budgets and goals, and make smarter money decisions with grounded, explainable guidance.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
