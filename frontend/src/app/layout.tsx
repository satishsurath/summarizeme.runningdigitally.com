/**
 * Root layout with navigation.
 * Replaces templates/base.html
 */

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SummarizeMe",
  description: "AI-powered YouTube video summarization",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 min-h-screen">
        {/* Navigation */}
        <nav className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
          <div className="max-w-7xl mx-auto px-4">
            <div className="flex items-center justify-between h-16">
              {/* Logo */}
              <a href="/" className="flex items-center gap-2">
                <span className="text-xl font-bold bg-gradient-to-r from-blue-500 to-purple-500 bg-clip-text text-transparent">
                  SummarizeMe
                </span>
              </a>

              {/* Nav links */}
              <div className="hidden sm:flex items-center gap-1">
                <a
                  href="/"
                  className="px-3 py-2 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-blue-500 transition-colors"
                >
                  Home
                </a>
                <a
                  href="/status"
                  className="px-3 py-2 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-blue-500 transition-colors"
                >
                  Status
                </a>
                <a
                  href="/admin"
                  className="px-3 py-2 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-blue-500 transition-colors"
                >
                  Admin
                </a>
              </div>

              {/* Mobile menu button */}
              <details className="sm:hidden relative">
                <summary className="px-3 py-2 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer">
                  Menu
                </summary>
                <div className="absolute right-0 top-full mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-2 min-w-[120px] z-50">
                  <a
                    href="/"
                    className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    Home
                  </a>
                  <a
                    href="/status"
                    className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    Status
                  </a>
                  <a
                    href="/admin"
                    className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    Admin
                  </a>
                </div>
              </details>
            </div>
          </div>
        </nav>

        {/* Main content */}
        <main className="py-6">{children}</main>
      </body>
    </html>
  );
}
