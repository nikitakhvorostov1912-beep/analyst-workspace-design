import Link from "next/link";
import { Settings } from "lucide-react";
import { ChannelSelector } from "./ChannelSelector";
import { ModelBadge } from "./ModelBadge";

export type HeaderProps = {
  activeChannelId: string | null;
  onChannelChange: (id: string) => void;
};

type Props = HeaderProps;

export function Header({ activeChannelId, onChannelChange }: Props) {
  return (
    <header className="sticky top-0 h-14 flex items-center px-4 border-b border-[var(--border)] bg-[var(--bg)] z-10 col-span-2">
      {/* Логотип слева */}
      <div className="flex-none w-[260px] flex items-center">
        <span className="font-semibold text-[var(--fg)] text-sm tracking-tight">
          1С Аналитик
        </span>
      </div>

      {/* Центр: Channel selector */}
      <div className="flex-1 flex justify-center">
        <ChannelSelector activeId={activeChannelId} onChange={onChannelChange} />
      </div>

      {/* Справа: Model badge + настройки */}
      <div className="flex-none flex items-center gap-3">
        <ModelBadge />
        <Link
          href="/settings"
          className="text-[var(--fg-muted)] hover:text-[var(--fg)] transition-colors"
          aria-label="Настройки"
        >
          <Settings size={18} />
        </Link>
      </div>
    </header>
  );
}
