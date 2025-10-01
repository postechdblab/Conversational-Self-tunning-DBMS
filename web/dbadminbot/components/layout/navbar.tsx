"use client";
import { LAB_URL } from "@/lib/constants";
import useScroll from "@/lib/hooks/use-scroll";
import Link from "next/link";

export default function NavBar() {
  const scrolled = useScroll(50);

  return (
    <>
      <div
        className={`fixed top-0 w-full flex justify-center ${
          scrolled
            ? "border-b border-gray-200 bg-white/50 backdrop-blur-xl"
            : "bg-white/0"
        } z-30 transition-all`}
      >
        <div className="mx-5 flex h-16 max-w-screen-xl items-center justify-between w-full">
          <Link href="/" className="flex items-center font-display text-2xl">
            <p>DBAdminBot</p>
          </Link>
          <div>
          <Link href={LAB_URL} className="flex items-center font-display text-2xl">
            <button
              className="rounded-full border border-black bg-black p-1.5 px-4 text-sm text-white transition-all hover:bg-white hover:text-black"
            >
              About
            </button>
            </Link>
          </div>
        </div>
      </div>
    </>
  );
}
