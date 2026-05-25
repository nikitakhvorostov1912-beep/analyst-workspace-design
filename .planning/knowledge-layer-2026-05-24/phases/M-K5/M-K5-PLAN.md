# M-K5 — Predictive + Distribution v2.0 + Commerce Launch

**Milestone:** M-K5
**Срок:** 6-8 недель, до **30.01.2027** (+2 нед vs исходного за счёт Q2 5 типовых)
**Parent plan:** `../../PLAN.md` v1.2
**Branch:** `feature/m-k5-predictive-launch` (создаётся при kickoff)

## Зафиксированные решения

- **Q2 5 типовых** в Reference Configurations Library (УТ/ERP/КА/БГУ/ЗУП)
- **Q5 Code-signing**: Sectigo OV $179/year для commerce launch (см. docs/CERT-PROCESS.md)
- **Q6 Dual license**: Commerce features (Reference Library, Rulebook) — proprietary
- **R-01 решение**: к этому моменту OPS-2 Telemetry даёт данные для Напарник
  build vs buy

## Цель милстоуна

Доставить **commerce-ready v2.0**:
- Reference Configurations Library (5 типовых fingerprints)
- Predictive use cases (temporal, vs типовой, 8.5-Ready Assessment)
- Distribution v2.0 (signed installer ≤ 250 MB)
- Paid features через license check (PG-4 8.5-Ready как paid service)
- SaaS readiness: per-user rate-limit, multi-tenancy (R-08)

## Definition of Done всего милстоуна

- [ ] Electron installer v2.0.0 ≤ 250 MB подписан Sectigo OV
- [ ] First-run wizard работает (включая 8.5-Ready opt-in)
- [ ] EPF/CFE installers — отдельные файлы (downloadable from in-app)
- [ ] Bundled JRE 17 через jlink (~30-40 MB)
- [ ] BSL LS jar shrunk через proguard (~50 MB)
- [ ] Reference Configurations Library: 5 fingerprints (УТ/ERP/КА/БГУ/ЗУП)
- [ ] L6-1..L6-4 use cases работают (temporal, vs типовой, reference, 8.5-Ready)
- [ ] PG-4 8.5-Ready Assessment — paid feature через license check
- [ ] Per-user rate-limit (ProxyFix middleware, R-08)
- [ ] Decision по Напарник (build vs buy) принято на основе OPS-2 данных
- [ ] README-V2 + INSTALL-V2 + UPGRADE-V1-TO-V2 docs
- [ ] Auto-update protocol работает (granular update, не full installer)
- [ ] `phases/M-K5/SUMMARY.md` написан

## Phases внутри M-K5

```
Phase 18 — Distribution v2.0 (7-10 дней)
18.1 Electron upgrade + electron-builder         [1.0d]  pending
18.2 Bundle optimization (R-05)                  [2.0d]  pending  jlink + proguard
18.3 First-run wizard                            [2.0d]  pending
18.4 EPF/CFE installer split                     [1.0d]  pending
18.5 Code-signing Sectigo OV integration         [1.0d]  pending  (DEVOPS-1 done)
18.6 Auto-update granular protocol               [2.0d]  pending  (DEVOPS-5 base)
18.7 INSTALL/UPGRADE docs + release notes        [1.0d]  pending
                                                  ───
                                                  10d

Phase L6 — Predictive Use Cases (15-20 дней)
L6-1 Temporal analysis use case                  [3.0d]  pending
L6-2 vs Типовой comparison                       [3.0d]  pending
L6-3 Reference Configurations Library (5 fp)     [5.0d]  pending  (Q2 D)
L6-4 8.5-Ready Assessment + paid gate            [4.0d]  pending  (PG-4)
                                                  ───
                                                  15d

Phase L3 — Hybrid Retrieval + Export (10 дней)
L3-5 Sessions encoder                            [2.0d]  pending
L3-6 Explain функцию                             [2.0d]  pending
X-5 Hybrid Retrieval                             [3.0d]  pending  (BM25 + vector)
UX-7 Citation Layer (financial proof)            [3.0d]  pending

OPS — Operations (8 дней)
OPS-3 Export / Import knowledge                  [2.0d]  pending
OPS-4 Per-user rate-limit (R-08)                 [2.0d]  pending  ProxyFix
OPS-5 MCP Server для own MCP                     [2.0d]  pending
OPS-6 License check для PG-4                     [2.0d]  pending

R-01 — Напарник build vs buy decision (1 день)
- Read OPS-2 metrics от M-K4
- Compare: cost Напарника vs наша latency / quality
- Decision: keep primary / switch to наш / pay Напарник
- Документ в RISKS.md как resolved

M-K5.99 SUMMARY + final launch                    [2.0d]  pending
                                                  ───
                                                  ~46d (~6-8 weeks)
```

## Distribution v2.0 (Phase 18 detail)

### Bundle composition (target ≤ 250 MB)
- Electron app: ~40 MB
- Node.js runtime: ~50 MB
- Backend PyInstaller exe: ~80 MB (current 60 + новые knowledge module)
- sqlite-vec extension: ~1 MB
- Bundled JRE 17 (jlink minimal): ~30-40 MB
- BSL LS jar (proguard): ~50 MB
- Static assets / fonts / icons: ~5 MB
- **Total: ~256-266 MB** — над targetом, нужна доп. оптимизация

Если над target:
- BGE-M3 модель скачивается при первом запуске (как сейчас) — экономия 570 MB
- BSL LS download-on-demand — экономия 50 MB → installer ~200 MB
- Тогда within target

### Signed installer
- Sectigo OV $179/year (см. docs/CERT-PROCESS.md)
- Build pipeline: GitHub Actions с WIN_CERT_PASSWORD в Secrets
- `cert.pfx` в `.gitignore`, импорт перед build step

### Auto-update granular
- Сейчас (v1.x): full installer 100+ MB на каждое обновление
- v2.x: delta updates через `electron-updater` — обновляется только changed
  asset hashes
- DEVOPS-5 downgrade guard уже implemented (M-K0)

## Decisions / Risks

### R-08 (slowapi на 127.0.0.1) — закрывается OPS-4
ProxyFix middleware + per-user key (через X-User-Id header после auth).

### R-05 (Bundle size) — Phase 18.2
Если jlink + proguard не дают ≤ 200 MB — переход на download-on-demand для
BSL LS (та же тактика что BGE-M3 в ADR-003).

### R-01 (Напарник lifecycle) — решается в M-K5
Решение на основе OPS-2 данных от M-K4. Документируется в RISKS.md как
resolved + commit с reference на decision.

### G9 (Distribution в M-K5) — закрыт этим планом
Phase 18 покрывает full Distribution v2.0.

## Paid features (PG-4)

- 8.5-Ready Assessment — paid через license check (~$50-100/мес per company)
- Reference Configurations Library — paid (или freemium с 1 fingerprint)
- License check: HMAC-signed token в localStorage + backend validation
- Trial: 14 days после first-run, потом nag screen

## SUMMARY скелет

См. `../M-K0-stabilization/SUMMARY.md` образец.

Обязательные секции:
- TL;DR (v2.0 launched, signed installer, 5 fingerprints, OPS-4 multi-tenancy)
- Bundle size до/после оптимизации (R-05)
- Решение по R-01 (Напарник) с цифрами OPS-2
- Commerce metrics: первые paid users? license activations?
- Open items для M-K6 (если будет)
