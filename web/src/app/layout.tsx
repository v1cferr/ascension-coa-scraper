import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

/* Inter carries the interface. JetBrains Mono carries the data, and it is not
 * decoration: this page is full of file paths, spell ids and blend modes, where a
 * fixed advance keeps columns aligned and a slashed zero keeps 0 from reading as O. */
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "latin-ext"],
  display: "swap",
});

const mono = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Conquest of Azeroth — talent and effect record",
  description:
    "Talent trees, spells, visual effects and sounds extracted from Project Ascension "
    + "before the realms close.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${mono.variable} font-sans antialiased`}>
        {children}
      </body>
    </html>
  );
}
