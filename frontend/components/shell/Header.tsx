import Link from "next/link";
import { Settings, HelpCircle, Activity } from "lucide-react";
import { ChannelSelector } from "./ChannelSelector";
import { ModelBadge } from "./ModelBadge";
import { AnonymizationToggle } from "./AnonymizationToggle";

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

      {/* Справа: Anonymization toggle + Model badge + статус + помощь + настройки */}
      <div className="flex-none flex items-center gap-3">
        <AnonymizationToggle />
        <ModelBadge />
        <Link
          href="/status"
          className="text-[var(--fg-muted)] hover:text-[var(--fg)] transition-colors"
          aria-label="Диагностика"
          title="Диагностика — проверить что всё работает"
        >
          <Activity size={18} />
        </Link>
        <Link
          href="/about"
          className="text-[var(--fg-muted)] hover:text-[var(--fg)] transition-colors"
          aria-label="О приложении"
          title="О приложении — что это и как пользоваться"
        >
          <HelpCircle size={18} />
        </Link>
        <Link
          href="/settings"
          className="text-[var(--fg-muted)] hover:text-[var(--fg)] transition-colors"
          aria-label="Настройки"
          title="Настройки — MCP подключения и LLM"
        >
          <Settings size={18} />
        </Link>
      </div>
    </header>
  );
}
