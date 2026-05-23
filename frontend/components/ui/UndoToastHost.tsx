"use client";

import { useEffect, useState } from "react";
import { UndoToast, type UndoToastProps } from "./UndoToast";
import { listenUndoToast } from "@/lib/undo-toast";

/**
 * Global host для активного UndoToast.
 *
 * Sprint 02 (handoff 2026-05-23, A): подключается в `app/layout.tsx`
 * рядом с существующим ToastHost. Слушает `publishUndoToast()` от
 * любого компонента и рендерит активный toast (один за раз).
 */
export function UndoToastHost() {
  const [active, setActive] = useState<UndoToastProps | null>(null);

  useEffect(() => listenUndoToast(setActive), []);

  if (!active) return null;
  // key={active.id} гарантирует rerender (включая onMount хуки)
  // когда публикуется новый toast подряд за старым.
  return <UndoToast key={active.id} {...active} />;
}
