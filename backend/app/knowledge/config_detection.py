"""Configuration Type Detection (M-K2.9) — определяет тип типовой 1С.

Эвристика по «характерным объектам метаданных». Каждая типовая
конфигурация (УТ 11.5, ERP 2.5, КА 2.5, БП 3.0, БГУ, ЗУП, УСО, ...)
имеет набор объектов, которые встречаются именно в ней.

**Алгоритм (двухпроходный):**
1. Характерный score: `characteristic_score = |канал ∩ characteristic_objects| / |characteristic_objects|`.
2. Кандидаты: конфигурации с `characteristic_score >= MIN_CONFIDENCE`.
   Если кандидатов нет → `kind="custom"` (самописная / неизвестная).
3. final_score = `characteristic_score + discriminative_score`, где
   `discriminative_score = |канал ∩ discriminative_objects| / |discriminative_objects|`
   (0.0 для базовых конфигураций без discriminative_objects, например УТ).
4. Победитель — кандидат с максимальным final_score.
5. `margin = final_score(top1) - final_score(top2)` — отрыв от руннер-апа.
6. `confidence` победителя: discriminative_score (если есть disc-маркеры, КА/ERP)
   или characteristic_score (для базовых: УТ/БП/ЗУП/БГУ/УСО).

**Использование:** вызывается из `indexer.bulk_refresh_metadata_cache`
после успешной индексации. Обновляет `mcp_connections.configuration`
(добавлено миграцией v11).

**Что НЕ делает:**
- Не сравнивает версии (УТ 11.4 vs УТ 11.5) — это L1.5 в M-K3+.
- Не детектит расширения / кастомизации (МСФО патчи, ERP-расширения).
- Не обрабатывает кросс-БСП конфигурации (Розница over УТ).

**Расширяемость:** добавление новой конфигурации = добавление записи в
`KNOWN_CONFIGURATIONS`. Тесты автоматически валидируют что новый
сигнатура не пересекается > 60% с существующими (анти-конфликт).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Literal

logger = logging.getLogger(__name__)


# Минимальный score для уверенной детекции. Ниже — «самописная».
MIN_CONFIDENCE = 0.30

# Confidence-gate пороги (B.3). Стартовые значения — тюнятся на 4 demo-базах
# (Open Q2 дизайн-дока). HIGH — минимальная уверенность для авто-линка;
# DELTA — минимальный отрыв победителя от руннер-апа по final_score.
HIGH_CONFIDENCE = 0.50
MARGIN_DELTA = 0.30


@dataclass(frozen=True, slots=True)
class ConfigurationSignature:
    """Сигнатура одной типовой конфигурации.

    Attrs:
        key: machine-readable id (`ut_11_5`, `erp_2_5`, ...)
        display_name: «УТ 11.5», «ERP 2.5» — что показывается в UI
        characteristic_objects: множество object_path которые встречаются
            именно в этой конфигурации (характерные). Чем уникальнее набор,
            тем выше confidence detection.
        family: общее семейство — `trade` / `accounting` / `payroll` /
            `government` — для UI группировки.
    """

    key: str
    display_name: str
    characteristic_objects: frozenset[str]
    family: str
    discriminative_objects: frozenset[str] = frozenset()

    def score(self, channel_objects: set[str]) -> float:
        """Возвращает score = |intersection| / |signature|.

        0.0 = ни одного характерного объекта в канале.
        1.0 = все характерные объекты найдены.
        """
        if not self.characteristic_objects:
            return 0.0
        intersection = channel_objects & self.characteristic_objects
        return len(intersection) / len(self.characteristic_objects)

    def discriminative_score(self, channel_objects: set[str]) -> float:
        """Доля найденных ДИСКРИМИНАТИВНЫХ маркеров (специфичных только для
        этой конфы относительно её subset-сиблингов).

        0.0 если discriminative_objects пуст (базовая конфа семейства —
        выигрывает на characteristic score, когда сиблинг-маркеров нет).
        """
        if not self.discriminative_objects:
            return 0.0
        return len(channel_objects & self.discriminative_objects) / len(
            self.discriminative_objects
        )


@dataclass(frozen=True, slots=True)
class DetectionResult:
    """Результат `detect_configuration_type()`.

    Attrs:
        configuration_key: `ut_11_5` / `erp_2_5` / ... / `custom`
        display_name: «УТ 11.5» / ... / «Самописная»
        confidence: 0.0–1.0. Семантика ветвится по наличию discriminative_objects:
            - Конфы с disc-маркерами (КА 2.5, ERP 2.5): confidence = discriminative_score
              (доля найденных дискриминативных маркеров; 1.0 = все найдены).
            - Базовые конфы без disc-маркеров (УТ 11.5, БП 3.0, ЗУП 3.1, БГУ 2.0, УСО):
              confidence = characteristic_score (доля характерных объектов в канале).
            - custom: confidence = 0.0 (пустой канал) или best characteristic_score.
        family: семейство (trade/accounting/...) — для UI
        scores: dict[key, characteristic_score] — debug: характерные scores всех конфигураций
    """

    configuration_key: str
    display_name: str
    confidence: float
    family: str
    scores: dict[str, float]
    margin: float = 0.0
    runner_up_key: str | None = None

    @property
    def is_custom(self) -> bool:
        return self.configuration_key == "custom"


# Характерные объекты определены минимально-инвазивно: используем те,
# которые однозначно отличают одну типовую от другой. Не полный набор
# документов — только маркеры.
#
# Источники:
# - УТ 11.5: типовая ERP-line trade. `Партнеры` (а не Контрагенты) — main
#   marker, `СвободныеОстатки` — register для drop-ship.
# - ERP 2.5: всё из УТ + МСФО / производство / бюджетирование.
# - КА 2.5: подмножество ERP без МСФО + регламентного учёта зарплаты.
# - БП 3.0: бухгалтерия — план счетов + регистры бух учёта.
# - БГУ 2.0: бюджетная — БК (бюджетная классификация).
# - ЗУП 3.1: зарплата + кадры.
# - УСО 2.5: «1С:ERP Управление строительной организацией» (ERP 2.5 + стройка:
#   Смета, КС-2/КС-3, УАТ, 214-ФЗ). characteristic_objects пока пуст — нет
#   верифицированной УСО-базы; детект по ключу/override, не по объектам.
KNOWN_CONFIGURATIONS: tuple[ConfigurationSignature, ...] = (
    ConfigurationSignature(
        key="ut_11_5",
        display_name="УТ 11.5",
        family="trade",
        characteristic_objects=frozenset({
            "Документ.РеализацияТоваровУслуг",
            "Документ.ЗаказПокупателя",
            "Документ.ПоступлениеТоваровУслуг",
            "Документ.ПередачаТоваровМеждуОрганизациями",
            "Справочник.Партнеры",
            "Справочник.Контрагенты",
            "Справочник.Номенклатура",
            "Справочник.СоглашенияСКлиентами",
            "РегистрНакопления.СвободныеОстатки",
            "РегистрНакопления.ТоварыНаСкладах",
        }),
    ),
    ConfigurationSignature(
        key="erp_2_5",
        display_name="ERP 2.5",
        family="trade",
        characteristic_objects=frozenset({
            # Из УТ-наследия:
            "Документ.РеализацияТоваровУслуг",
            "Документ.ЗаказПокупателя",
            "Справочник.Партнеры",
            "РегистрНакопления.СвободныеОстатки",
            # ERP-only маркеры:
            "Документ.РасчетСебестоимостиТоваров",
            "Документ.ОтражениеЗарплатыВФинансовомУчете",
            "Документ.ПроизводственнаяОперация",
            "РегистрБухгалтерии.МеждународныйУчет",
            "РегистрНакопления.НалоговыеОбязательстваРезидентов",
            "Справочник.СтатьиАктивовПассивов",
            "Справочник.МестаВозникновенияЗатрат",
        }),
        discriminative_objects=frozenset({
            # ERP vs КА: МСФО + международный/налоговый учёт + производство
            "РегистрБухгалтерии.МеждународныйУчет",
            "РегистрНакопления.НалоговыеОбязательстваРезидентов",
            "Справочник.СтатьиАктивовПассивов",
            "Документ.ПроизводственнаяОперация",
            "Документ.ОтражениеЗарплатыВФинансовомУчете",
        }),
    ),
    ConfigurationSignature(
        key="ka_2_5",
        display_name="КА 2.5",
        family="trade",
        characteristic_objects=frozenset({
            # КА = ERP минус МСФО, плюс особая ЗУП-light:
            "Документ.РеализацияТоваровУслуг",
            "Документ.ЗаказПокупателя",
            "Документ.РасчетСебестоимостиТоваров",
            "Справочник.Партнеры",
            "РегистрНакопления.СвободныеОстатки",
            "РегистрНакопления.ЗарплатаКВыплате",  # КА имеет регламентную ЗУП внутри
            "Документ.НачислениеЗарплаты",
            "Документ.ОтражениеЗарплатыВУчете",
        }),
        discriminative_objects=frozenset({
            # КА vs УТ: себестоимость + регламентная ЗУП внутри КА
            "Документ.РасчетСебестоимостиТоваров",
            "Документ.ОтражениеЗарплатыВУчете",
            "Документ.НачислениеЗарплаты",
            "РегистрНакопления.ЗарплатаКВыплате",
        }),
    ),
    ConfigurationSignature(
        key="bp_3_0",
        display_name="БП 3.0",
        family="accounting",
        characteristic_objects=frozenset({
            "Документ.СчетНаОплату",
            "Документ.ОперацияБух",
            "Документ.КорректировкаПоступления",
            "Документ.ПоступлениеТоваровУслуг",
            "ПланСчетов.Хозрасчетный",
            "РегистрБухгалтерии.Хозрасчетный",
            "Справочник.ОсновныеСредства",
            "Справочник.НоменклатурныеГруппы",
            "Справочник.СтатьиЗатрат",
        }),
    ),
    ConfigurationSignature(
        key="bgu_2_0",
        display_name="БГУ 2.0",
        family="government",
        characteristic_objects=frozenset({
            "Справочник.БюджетнаяКлассификация",
            "Справочник.КлассификационныеПризнакиСчетов",
            "Документ.БюджетноеОбязательство",
            "Документ.КассовоеПоступление",
            "Документ.КассовоеВыбытие",
            "РегистрБухгалтерии.Бюджетный",
            "ПланСчетов.ЕПСБУ",
            "Справочник.ИсточникиФинансовогоОбеспечения",
        }),
    ),
    ConfigurationSignature(
        key="zup_3_1",
        display_name="ЗУП 3.1",
        family="payroll",
        characteristic_objects=frozenset({
            "Документ.ПриемНаРаботу",
            "Документ.КадровыйПеревод",
            "Документ.УвольнениеСотрудника",
            "Документ.НачислениеЗарплатыИВзносов",
            "Справочник.Сотрудники",
            "Справочник.ВидыНачислений",
            "Справочник.ВидыУдержаний",
            "РегистрНакопления.ВыплаченныеВзносы",
            "РегистрРасчета.НачисленияСотрудникам",
        }),
    ),
    ConfigurationSignature(
        key="uso_2_5",
        display_name="УСО 2.5",
        family="construction",
        # «1С:ERP Управление строительной организацией 2.5» (1С+Рарус): ERP 2.5 +
        # строительные подсистемы (Смета, КС-2/КС-3, УАТ, долевое 214-ФЗ).
        # characteristic_objects ПУСТ намеренно: верифицированных имён метаданных
        # строительной УСО нет (нет живой УСО-базы; БЗ даёт presentation-имена с
        # пометкой «требует проверки»). Выдумывать идентификаторы нельзя — детект
        # по точному object_path просто не сматчит мимо-имя, а в код попадёт новая
        # латентная некорректность. TODO: заполнить из get_metadata первой живой
        # УСО-базы. До тех пор УСО по объектам не детектится (identity/override/
        # buddy/typical-связка работают по ключу uso_2_5, а не по маркерам).
        characteristic_objects=frozenset(),
    ),
)


def detect_configuration_type(
    channel_objects: Iterable[str],
    *,
    known_configurations: tuple[ConfigurationSignature, ...] = KNOWN_CONFIGURATIONS,
    min_confidence: float = MIN_CONFIDENCE,
) -> DetectionResult:
    """Определяет тип типовой 1С по списку object_path канала.

    Args:
        channel_objects: iterable из object_path (e.g. «Документ.ОПП»).
            Дубликаты будут схлопнуты в set.
        known_configurations: tuple сигнатур (по умолчанию KNOWN_CONFIGURATIONS).
        min_confidence: минимум для уверенной детекции. Ниже — «custom».

    Returns:
        DetectionResult с выигравшей конфигурацией или `custom`. В любом
        случае возвращает `scores: dict[key, score]` для debug / UI hint
        («2 кандидата близки: УТ 11.5 (0.42) vs КА 2.5 (0.38) — уточните»).
    """
    channel_set = set(channel_objects)

    # scores — характерные (для debug/UI и фоллбэка), как раньше.
    scores = {sig.key: sig.score(channel_set) for sig in known_configurations}

    if not channel_set:
        return DetectionResult(
            configuration_key="custom",
            display_name="Самописная",
            confidence=0.0,
            family="unknown",
            scores=scores,
            margin=0.0,
        )

    # Кандидаты: характерный score >= min_confidence.
    candidates = [
        sig for sig in known_configurations
        if sig.score(channel_set) >= min_confidence
    ]
    if not candidates:
        best_key, best_score = max(scores.items(), key=lambda kv: kv[1])
        return DetectionResult(
            configuration_key="custom",
            display_name="Самописная",
            confidence=best_score,
            family="unknown",
            scores=scores,
            margin=0.0,
        )

    # final_score = characteristic + discriminative. Дискрим разводит
    # subset-конфликт (КА⊃УТ): на КА-базе КА имеет disc>0, УТ disc=0.
    def final_score(sig: ConfigurationSignature) -> float:
        return sig.score(channel_set) + sig.discriminative_score(channel_set)

    ranked = sorted(candidates, key=final_score, reverse=True)
    winner = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None

    margin = final_score(winner) - (final_score(runner_up) if runner_up else 0.0)

    # confidence: для специфичной конфы — доля дискрим-маркеров; для базовой
    # (disc пуст) — характерный score. Всегда в [0,1], годен для бейджа/gate.
    confidence = (
        winner.discriminative_score(channel_set)
        if winner.discriminative_objects
        else winner.score(channel_set)
    )

    return DetectionResult(
        configuration_key=winner.key,
        display_name=winner.display_name,
        confidence=confidence,
        family=winner.family,
        scores=scores,
        margin=margin,
        runner_up_key=runner_up.key if runner_up else None,
    )


async def update_channel_configuration(
    db,  # aiosqlite.Connection
    channel_id: str,
    result: DetectionResult,
    *,
    source: str | None = None,
) -> None:
    """Записывает результат детекции в mcp_connections.

    Args:
        db: aiosqlite connection
        channel_id: канал
        result: что записывать
        source: значение configuration_source (auto/ambiguous/confirmed/
            manual/custom/failed). None — пишем NULL («детект без явного источника»).
    """
    await db.execute(
        "UPDATE mcp_connections SET configuration = ?, configuration_source = ? "
        "WHERE id = ?",
        (result.display_name, source, channel_id),
    )
    await db.commit()
    logger.info(
        "Configuration detected для канала %s: %s (confidence %.2f, source=%s)",
        channel_id,
        result.display_name,
        result.confidence,
        source,
    )


def gate_decision(
    result: DetectionResult,
    *,
    high_confidence: float = HIGH_CONFIDENCE,
    margin_delta: float = MARGIN_DELTA,
) -> Literal["custom", "auto", "confirm"]:
    """Решение онбординг-гейта по результату детекции (B.3).

    Returns:
        "custom"  — самописная (нет кандидата ≥ MIN_CONFIDENCE) → типовые не
                    подключаем, предлагаем ручной override.
        "auto"    — уверенно и с отрывом → авто-линк, бейдж «(авто)».
        "confirm" — кандидат есть, но близко к руннер-апу → 1 вопрос аналитику.
    """
    if result.is_custom:
        return "custom"
    if result.confidence >= high_confidence and result.margin >= margin_delta:
        return "auto"
    return "confirm"
