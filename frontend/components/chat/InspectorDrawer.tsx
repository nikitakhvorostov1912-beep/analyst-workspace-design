"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X, Eye } from "lucide-react";
import type { ObjectCardPayload } from "@/lib/types";
import { ObjectCard } from "@/components/cards/ObjectCard";

/**
 * InspectorDrawer (shell v3 §7) — выезжающая справа панель для подробного
 * просмотра объекта. Radix Dialog даёт из коробки: ловушку фокуса, Esc,
 * возврат фокуса на триггер, aria-modal, клик-вне.
 *
 * Открывается событийно: ObjectCard диспатчит `open-inspector` с payload,
 * SessionPage слушает и держит состояние. Внутри — полная ObjectCard
 * (inInspector чтобы не показывать рекурсивную кнопку «Открыть в инспекторе»).
 */
export function InspectorDrawer({
  open,
  onOpenChange,
  payload,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  payload: ObjectCardPayload | null;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content
          className="fixed right-0 top-0 z-50 h-screen w-[min(460px,92vw)] overflow-y-auto bg-[var(--bg-0)] border-l border-[var(--bd-3)] shadow-2xl
                     data-[state=open]:animate-in data-[state=open]:slide-in-from-right
                     data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right
                     motion-reduce:animate-none"
        >
          <div className="sticky top-0 z-10 flex items-center gap-2.5 px-4 py-3.5 bg-[var(--bg-1)] border-b border-[var(--bd-2)]">
            <Eye className="h-4 w-4 text-[var(--accent)]" />
            <Dialog.Title
              className="text-[13px] font-semibold text-[var(--fg-1)]"
              style={{ fontFamily: "var(--font-plex-mono), ui-monospace, monospace" }}
            >
              Инспектор объекта
            </Dialog.Title>
            <span className="flex-1" />
            <Dialog.Close
              className="inline-flex items-center justify-center h-8 w-8 rounded-md text-[var(--fg-3)] hover:text-[var(--fg-1)] hover:bg-[var(--bg-2)]"
              aria-label="Закрыть (Esc)"
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>
          <div className="p-4 space-y-3.5">
            {payload && <ObjectCard payload={payload} inInspector />}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
