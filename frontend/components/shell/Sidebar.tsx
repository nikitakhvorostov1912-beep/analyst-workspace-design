import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

const GROUPS = [
  { label: "Сегодня" },
  { label: "Вчера" },
  { label: "Ранее" },
];

export function Sidebar() {
  return (
    <aside className="flex flex-col h-full border-r border-[var(--border)] bg-[var(--bg)]">
      {/* Кнопка нового чата */}
      <div className="p-3 border-b border-[var(--border)]">
        <Button variant="secondary" className="w-full justify-start gap-2 text-sm">
          <Plus size={16} />
          Новый чат
        </Button>
      </div>

      {/* Группы истории */}
      <div className="flex-1 overflow-y-auto p-2">
        {GROUPS.map((group) => (
          <div key={group.label} className="mb-4">
            <div className="px-2 py-1 text-xs font-medium text-[var(--fg-muted)] uppercase tracking-wide">
              {group.label}
            </div>
            <div className="px-2 py-2 text-xs text-[var(--fg-muted)] italic">
              Истории пока нет
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
