import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";

import ChatWidget from "./ChatWidget";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function Shell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  const { pathname } = useLocation();

  return (
    <div className="flex h-screen bg-anvil-surface">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Topbar title={title} subtitle={subtitle} />
        <main className="flex-1 overflow-y-auto px-8 py-6">{children}</main>
      </div>
      {pathname !== "/ask" && <ChatWidget />}
    </div>
  );
}
