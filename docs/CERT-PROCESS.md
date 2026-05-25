# Code-Signing Certificate Process

**Owner:** Никита Хворостов
**Status:** в работе (M-K0.7 → M-K5)
**Trigger:** перед v2.0.0 commerce release (M-K5)

## Зачем

Windows SmartScreen **блокирует** или показывает «неизвестный издатель» для
любого `.exe` без code-signing certificate. Аналитики из enterprise клиентов
**не нажмут «Выполнить в любом случае»** — это политика IT-департамента.

Для commerce launch v2.0 нужен подписанный installer. Сейчас (v1.4.7) — unsigned,
работает но требует ручного override от пользователя.

## Опции

| Тип | Цена/год | SmartScreen | Verification | Когда брать |
|-----|----------|-------------|--------------|-------------|
| **Self-signed** | 0 | ❌ Блокирует | — | dev/internal only (текущее) |
| **OV (Organization Validation)** | ~$200-300 | ⚠️ Warning ~30 дней «build reputation» через downloads | DUNS + corp docs (3-7 дней) | MVP commerce launch |
| **EV (Extended Validation)** | ~$400-500 | ✅ Сразу trusted (никакого warning) | DUNS + corp docs + USB HSM token (1-3 недели) | Enterprise клиенты |

## Вендоры (сравнение для РФ)

| Вендор | OV цена | EV цена | Доставка | РФ-friendly? |
|--------|---------|---------|----------|--------------|
| **Sectigo** (бывш. Comodo) | $179/год | $359/год | email | ✅ принимают РФ карты, доставка email |
| **DigiCert** | $474/год | $691/год | USB courier для EV | ⚠️ для EV нужна USB-доставка, может быть проблемой |
| **SSL.com** | $129/год | $349/год | email | ✅ дешевле всех |
| **GoGetSSL** (reseller) | $89/год | $299/год | email | ✅ бюджетный вариант |

**Рекомендация для MVP commerce (M-K5):**
- Старт с **Sectigo OV** ($179/год) — самый быстрый процесс (3-7 дней), email
  доставка, после ~30 дней «build reputation» SmartScreen перестаёт ругаться.
- При наличии 10+ enterprise клиентов с жёсткими политиками — upgrade на
  **Sectigo EV** ($359/год) который trusted сразу.

## Документы для получения

### OV (Organization Validation):
1. **Свидетельство о регистрации юр.лица** (выписка из ЕГРЮЛ)
2. **DUNS Number** — бесплатная регистрация на upik.de (Dun & Bradstreet),
   1-2 недели на получение для РФ
3. **Email на корпоративном домене** (не gmail.com)
4. **Адрес и телефон** организации (вендор позвонит подтвердить)

### EV (Extended Validation) — дополнительно:
5. **Нотариально заверенная копия** свидетельства о регистрации
6. **USB HSM token** (FIPS 140-2 Level 2+) — куплен отдельно ($30-50) или
   доставляется вендором
7. **Видео-верификация** или **личный визит** в Notary office

## Timeline

| Этап | Срок | Зависимости |
|------|------|-------------|
| 1. Регистрация DUNS Number | 1-2 недели | юр.лицо |
| 2. Заказ + оплата cert | 1 день | DUNS |
| 3. OV verification (звонок, документы) | 3-7 дней | DUNS, docs |
| 4. EV verification (доп. notary) | +1-2 недели | OV пройдено |
| 5. Доставка cert (email для OV, USB для EV) | 1-3 дня | verification done |
| 6. Установка в electron-builder | 1 день | cert |
| 7. Подписать installer + test | 1 день | electron-builder |
| 8. «Build reputation» SmartScreen (OV only) | ~30 дней органически | дистрибуция |

**Critical path для commerce launch (OV):** ~2-4 недели от старта до подписанного
installer без SmartScreen warning.

## Интеграция в electron-builder

После получения `.pfx` файла cert + password — добавить в `desktop/package.json`:

```json
{
  "build": {
    "win": {
      "certificateFile": "build/cert.pfx",
      "certificatePassword": "${env.WIN_CERT_PASSWORD}",
      "signingHashAlgorithms": ["sha256"],
      "signAndEditExecutable": true,
      "rfc3161TimeStampServer": "http://timestamp.sectigo.com"
    }
  }
}
```

`WIN_CERT_PASSWORD` в GitHub Actions Secrets, `cert.pfx` в `.gitignore` (НЕ
коммитить в репо!).

Для EV с USB HSM — другой подход (signtool через HSM driver), отдельная
инструкция от вендора.

## Action items (отслеживаемые)

- [ ] **DUNS Number** — старт регистрации (отдельная задача владельца, до M-K3)
- [ ] **Юр.лицо** — определить через какое юр.лицо (Хворостов ИП vs ООО?) — до M-K3
- [ ] **Sectigo OV order** — после получения DUNS, ~2 недели до M-K5 start
- [ ] **electron-builder integration** — после получения cert, 1 день в M-K5
- [ ] **Smoke test** на чистой Windows-VM — подписанный installer не triggers
  SmartScreen warning после ~30 дней органической дистрибуции

## Связи

- `desktop/main.js` — auto-update handler (DEVOPS-5 downgrade guard уже сделан)
- `desktop/package.json` — electron-builder config (будет обновлён при cert)
- `M6 Phase 18` (через `.planning/handoff/m6-quality-expansion/`) — Distribution v2.0
- `.planning/milestones/INTEGRATION-DECISIONS.md` §Q5 — рекомендация: MVP self-signed,
  commerce → OV

## DEVOPS-5 (выполнено)

Уже сделан в `desktop/main.js`: `semverGt()` + `downgradeUpdateVersion` +
`semverGt(downloadedUpdateVersion, currentVersion)` проверка в ipcMain
`updater:install` handler. Защищает от downgrade attack через manifest manipulation.
