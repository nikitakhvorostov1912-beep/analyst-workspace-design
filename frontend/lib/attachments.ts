/**
 * Хелперы для прикрепления файлов к сообщению.
 * Backend (app/orchestrator/attachments.py) поддерживает те же типы — синхронно держать.
 */
import type { ChatAttachment } from "./types";

/** Поддерживаемые MIME типы (синхронно с backend _EXTRACTORS + _IMAGE_MIMES). */
export const ACCEPTED_MIME = [
  // Документы — текст извлекается на backend
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/msword",
  "text/plain",
  "text/csv",
  "application/json",
  "application/xml",
  "text/xml",
  "text/markdown",
  // Картинки — передаются в multimodal LLM (mimo-v2-omni) как image_url
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
] as const;

/** Расширения файлов (для accept attribute и fuzzy detection). */
export const ACCEPTED_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".xlsx",
  ".doc",
  ".txt",
  ".csv",
  ".json",
  ".xml",
  ".md",
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".gif",
];

/** Image MIME types — рендерить thumbnail в чипе. */
const IMAGE_MIMES = new Set([
  "image/png",
  "image/jpeg",
  "image/jpg",
  "image/webp",
  "image/gif",
]);

export function isImageMime(mime: string): boolean {
  return IMAGE_MIMES.has((mime || "").toLowerCase());
}

export function isImageExtension(name: string): boolean {
  const ext = name.toLowerCase().split(".").pop() ?? "";
  return ["png", "jpg", "jpeg", "webp", "gif"].includes(ext);
}

/** Соглашение по UI и backend: 25 MB на файл, 5 файлов на сообщение. */
export const MAX_FILE_BYTES = 25 * 1024 * 1024;
export const MAX_FILES_PER_MESSAGE = 5;

/** Accept-строка для input[type=file]. */
export const FILE_ACCEPT_ATTR = [...ACCEPTED_MIME, ...ACCEPTED_EXTENSIONS].join(",");


/**
 * Читает File как base64 (без data:URI префикса).
 * Используем FileReader для совместимости + работает с большими файлами.
 */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("read error"));
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("FileReader: ожидалась строка"));
        return;
      }
      // result = "data:<mime>;base64,<payload>"
      const idx = result.indexOf(",");
      resolve(idx >= 0 ? result.slice(idx + 1) : result);
    };
    reader.readAsDataURL(file);
  });
}


/**
 * Принимает массив File, валидирует и конвертит в ChatAttachment[].
 * Возвращает { attachments, errors } — частичный успех допустим.
 */
export async function filesToAttachments(
  files: File[],
): Promise<{ attachments: ChatAttachment[]; errors: string[] }> {
  const attachments: ChatAttachment[] = [];
  const errors: string[] = [];

  const slice = files.slice(0, MAX_FILES_PER_MESSAGE);
  for (const file of slice) {
    if (file.size > MAX_FILE_BYTES) {
      errors.push(
        `«${file.name}» — ${(file.size / 1024 / 1024).toFixed(1)} МБ, лимит 25 МБ.`,
      );
      continue;
    }
    if (file.size === 0) {
      errors.push(`«${file.name}» — пустой файл, пропустили.`);
      continue;
    }
    try {
      const content_base64 = await fileToBase64(file);
      attachments.push({
        name: file.name,
        mime: file.type || "",
        content_base64,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "ошибка чтения";
      errors.push(`«${file.name}» — ${msg}`);
    }
  }

  if (files.length > MAX_FILES_PER_MESSAGE) {
    errors.push(
      `Можно не больше ${MAX_FILES_PER_MESSAGE} файлов за раз. Лишние не прикреплены.`,
    );
  }

  return { attachments, errors };
}


/** Иконка для UI по типу файла (lucide-react имена). */
export function fileIconName(name: string, mime?: string): string {
  const ext = name.toLowerCase().split(".").pop() ?? "";
  if (mime?.includes("pdf") || ext === "pdf") return "FileText";
  if (mime?.includes("word") || ext === "docx" || ext === "doc") return "FileText";
  if (mime?.includes("sheet") || ext === "xlsx" || ext === "csv") return "Sheet";
  if (ext === "json" || ext === "xml") return "FileCode";
  return "File";
}


/** Форматирует размер base64-payload в человекочитаемый вид (приблизительно — base64 ≈ 1.33x). */
export function approximateSize(content_base64: string): string {
  const bytes = Math.floor(content_base64.length * 0.75);
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}
