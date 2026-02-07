# Исследование: Подкаст-пайплайн для Юки

> **Цель:** Юки получает вводные (тема, ключевые тезисы) → генерирует подкаст → публикует на Яндекс.Музыку и ВК Подкасты.
> **TTS:** ElevenLabs Creator ($22/мес, ~3.3 часа аудио = ~20 эпизодов по 10 мин).
> **Формат:** Одноголосый (bulletin), русский язык.
> **Принцип:** Прямые API, без платных оркестраторов. $0 дополнительных расходов.

---

## 1. Яндекс.Музыка Подкасты

### Есть ли API для загрузки? — НЕТ

У Яндекс.Музыки **нет публичного API** для загрузки подкастов. Никаких REST/gRPC эндпоинтов для публикации эпизодов не существует.

Существует неофициальная Python-библиотека [MarshalX/yandex-music-api](https://github.com/MarshalX/yandex-music-api), но она только для **чтения** (поиск, получение эпизодов, скачивание). Загрузка через неё невозможна.

### Как попасть на Яндекс.Музыку

**Единственный путь — RSS-фид:**

1. Хостишь подкаст на любом хостинге с RSS (mave.digital, Buzzsprout, Transistor, свой сервер)
2. Заполняешь форму на [yandex.ru/support/music/ru/podcast-authors/audio-placement.html](https://yandex.ru/support/music/ru/podcast-authors/audio-placement.html)
3. Указываешь: RSS-ссылку, название подкаста, автора, описание (до 60 символов), Яндекс-почту
4. Модерация: **от нескольких дней** до нескольких недель
5. После одобрения — **всё автоматически**: Яндекс парсит RSS каждые ~5 минут, 95% эпизодов появляются в течение 30 минут, максимум 2-4 часа

### Требования к аудио

| Параметр | Требование |
|----------|-----------|
| Форматы | MP3, MP4, M4A, AAC, FLAC |
| Битрейт | Минимум 40 Kbps, **рекомендуется 192+ Kbps** |
| Кодирование | Mono или Stereo |
| Контент | Только разговорный (без DJ-сетов/миксов) |

### Аналитика

Яндекс DataLens имеет **нативную интеграцию** с Яндекс.Музыкой:
- Статистика прослушиваний, подписчиков
- Дашборды с гранулярным доступом по эпизодам
- Документация: [yandex.cloud/en/docs/tutorials/datalens/data-from-podcasts](https://yandex.cloud/en/docs/tutorials/datalens/data-from-podcasts)

### Вывод по Яндекс.Музыке

Прямая API-интеграция **невозможна**. Единственная стратегия автоматизации:

```
Юки генерирует аудио
    ↓
Загружает на хостинг (свой сервер или mave.digital API)
    ↓
Обновляет RSS-фид
    ↓
Яндекс.Музыка автоматически подтягивает новый эпизод (2-4 часа)
```

Начальная подача RSS — **ручная, одноразовая**.

---

## 2. ВК Подкасты

### Есть ли API для загрузки? — НЕТ

VK API имеет только **read-only** методы для подкастов:

| Метод | Описание |
|-------|----------|
| `podcasts.searchPodcast` | Поиск подкастов (единственный документированный) |
| `podcasts.getCatalog` | Каталог (недокументирован, есть в SDK) |
| `podcasts.getEpisodes` | Эпизоды подкаста (недокументирован) |
| `podcasts.getCategories` | Категории (недокументирован) |
| `podcasts.subscribe` / `unsubscribe` | Подписка (недокументирован) |

**Методов `podcasts.upload` или `podcasts.createEpisode` НЕ существует.**

### Можно ли через audio.save?

Теоретический путь `audio.getUploadServer` → upload → `audio.save` создаёт **обычный аудиотрек**, а не подкаст-эпизод. VK Подкасты — отдельный тип контента, управляемый через внутреннюю платформу.

### Как попасть в VK Подкасты

**Вариант A — Бот @vk.com/podcasters:**
1. Написать боту [vk.com/podcasters](https://vk.com/podcasters)
2. Указать название подкаста, детали
3. Нужно: VK-сообщество, минимум 1 записанный эпизод
4. Модерация: **до 2 недель** (некоторые получают за 2 дня)

**Вариант B — RSS-импорт (рекомендуется):**
1. После одобрения подкаста → Настройки сообщества → Разделы → Подкасты → RSS-импорт
2. Вставить RSS-ссылку
3. Включить "Загрузить старые эпизоды"
4. Новые эпизоды **автоматически синхронизируются**
5. Можно включить **автопубликацию на стену** сообщества

**Вариант C — Мини-приложение VK Music:**
- `https://vk.com/app51488920` — импорт через RSS

### Требования к аудио

| Параметр | Требование |
|----------|-----------|
| Формат | MP3 |
| Частота дискретизации | Минимум 32 kHz |
| Размер файла | Максимум **200 MB** |
| Качество | Чистая речь, минимум шума |
| Оригинальность | Только оригинальный контент |

### Ограничения

- Только **один подкаст на сообщество**, но неограниченное количество эпизодов
- VK копирует аудио на свои сервера — аналитика прослушиваний доступна только внутри VK
- Rate limits: User token — 3 req/s, Community token — 20 req/s

### Вывод по ВК

Прямая API-загрузка подкастов **невозможна**. Стратегия аналогична Яндексу:

```
Юки генерирует аудио
    ↓
Загружает на хостинг / обновляет RSS
    ↓
VK автоматически синхронизирует через RSS-импорт
```

**Дополнительно** можно через VK API:
- `wall.post` — промо-пост о новом эпизоде на стене сообщества
- `podcasts.searchPodcast` — проверка, что эпизод появился

---

## 3. Единая стратегия публикации: RSS как хаб

Поскольку **обе платформы** работают через RSS, оптимальная архитектура:

```
Юки генерирует MP3
    ↓
Загружает на хостинг (свой S3/сервер ИЛИ mave.digital API ИЛИ Transistor API)
    ↓
Обновляет RSS-фид (python-feedgen)
    ↓
┌─────────────────────────────────┐
│ RSS-фид автоматически читается: │
│ • Яндекс.Музыка (2-4 часа)     │
│ • VK Подкасты (RSS-импорт)      │
│ • Apple Podcasts (если нужно)   │
│ • Spotify (если нужно)          │
│ • YouTube Podcasts (если нужно) │
└─────────────────────────────────┘
```

### Варианты хостинга аудио

| Хостинг | API | Цена | Плюсы |
|---------|-----|------|-------|
| **Свой сервер / S3** | Полный контроль | ~$5/мес | Максимальная гибкость, python-feedgen для RSS |
| **mave.digital** | Есть | Бесплатно (базовый) | Русский рынок, нативная интеграция с Яндекс и VK |
| **Transistor** | Полный REST API | $19-99/мес | Лучший API: pre-signed upload → episode create → publish |
| **Buzzsprout** | REST API | $12-24/мес | Простой API, `audio_url` или file upload |

**Рекомендация:** Свой S3 + python-feedgen = $0 за хостинг. Если хочется "из коробки" — mave.digital (бесплатный, русский, интеграции с Яндекс/VK).

---

## 4. Пайплайн генерации подкаста (Best Practices)

### 4.1. Форматы

| Формат | Описание | Сложность | Вовлечение |
|--------|----------|-----------|-----------|
| **Bulletin (монолог)** | Один ведущий | Простой | Среднее |
| **Conversation (диалог)** | Два ведущих, обсуждение | Средний | **Высокое** |
| **Interview** | Ведущий + "эксперт" | Средний | Высокое |

**Рекомендация:** Формат **conversation** (два голоса) — именно его популяризировал Google NotebookLM. Драматически более вовлекающий, чем монолог.

### 4.2. Оптимальная длительность

- **Короткий (AI-нативный):** 3-7 минут — дефолт ElevenLabs GenFM
- **Средний (рекомендуется для старта):** 7-15 минут — достаточная глубина без утомления от синтетических голосов
- **Стандартный:** 20-45 минут — для зрелого подкаста

**Для первой версии: 7-12 минут.**

### 4.3. Структура скрипта

```
[ХУК] — 20-40 секунд
  Провокационный вопрос, удивительная статистика, bold claim.
  НИКОГДА не начинать с "Привет, вы слушаете подкаст..."
  Сначала хук, ПОТОМ представление.

[ИНТРО] — 30-60 секунд
  Название шоу, ведущие.
  Тема эпизода и что узнает слушатель.

[СЕГМЕНТ 1: КОНТЕКСТ] — 1-2 минуты
  Почему эта тема актуальна сейчас.

[СЕГМЕНТЫ 2-4: ОСНОВНОЙ КОНТЕНТ] — 2-4 минуты каждый
  Конкретные данные, примеры, кейсы.
  Каждый сегмент имеет свой мини-хук и переход.

[ПЕРЕХОДЫ между сегментами]
  Вопросы-мосты: "Но что происходит, когда..."

[ВЫВОДЫ] — 30-60 секунд
  Ключевые тейкэвеи.

[CTA + АУТРО] — 10-30 секунд
  Один конкретный призыв к действию.
  Тизер следующего эпизода.
```

### 4.4. Как избежать "AI-помойки" в скриптах

1. **Многоагентный пайплайн** — отдельные агенты для исследования, написания, ревью
2. **Писать для уха, не для глаз** — сокращения, разговорные обороты
3. **Филлеры для естественности** — "ну вот", "знаете что", "серьёзно?", "окей, но..."
4. **Паттерны прерывания** в формате двух ведущих — Host B начинает до завершения мысли Host A
5. **Конкретные данные** — цифры, даты, имена — предотвращают абстрактность
6. **Анти-фабрикация** — явный запрет на выдумывание статистики и цитат

### 4.5. Примеры хуков

- "93% бизнесов, внедривших AI в 2025, увидели рост прибыли. Остальные 7% — банкроты."
- "На прошлой неделе компания потеряла 2 миллиона за 24 часа из-за одного решения..."
- "Все говорят, что нужно [X]. Они ошибаются, и вот почему."

### 4.6. CTA для подкастов

- **Один CTA на эпизод** — не перегружай
- **Ценность вперёд** — "Мы собрали гайд по этой теме, ссылка в описании"
- **Клиффхэнгер** — тизер следующего эпизода для удержания подписчиков

---

## 5. ElevenLabs для генерации подкастов

### 5.1. Create Podcast API (требует allowlist)

ElevenLabs имеет специальный эндпоинт `/v1/studio/podcasts`, но он **требует allowlist** для workspace. Возможно, недоступен на Creator плане.

### 5.2. Рабочий вариант: TTS API (bulletin, 1 голос)

Генерируем скрипт сами (Llama 3.3 free), озвучиваем через стандартный TTS API:

```python
from elevenlabs import ElevenLabs

client = ElevenLabs(api_key="your-key")

# Генерация по чанкам (макс 5000 символов на запрос)
audio = client.text_to_speech.convert(
    text="Текст сегмента подкаста...",
    voice_id="chosen_russian_voice_id",
    model_id="eleven_multilingual_v2",
    output_format="mp3_44100_192"
)
```

Скрипт разбивается на чанки по 3000-5000 символов, каждый озвучивается отдельно, потом склеивается через pydub.

### 5.3. Управление паузами и эмоциями

**Multilingual v2:** SSML break tags — `<break time="1.5s" />`
**Eleven v3 (alpha):** Аудио-теги — `[pause]`, `[excited]`, `[whispers]`, `[laughs]`, `[sighs]`

### 5.4. Стоимость (план Creator $22/мес)

100K кредитов = ~3.3 часа аудио = **~20 эпизодов по 10 минут**.
Overage rate: ~$0.15/мин на Creator плане.

---

## 6. Аудио постобработка

### 6.1. Нормализация LUFS

| Платформа | Целевой LUFS | True Peak |
|-----------|-------------|-----------|
| Apple Podcasts | -16 LUFS | -1 dBFS |
| Spotify | -14 LUFS | -2 dBTP |
| YouTube | -14 LUFS | -1 dBTP |
| **Стандарт подкастов** | **-16 LUFS** | **-1 dBFS** |

```bash
pip install ffmpeg-normalize

# Нормализация подкаста
ffmpeg-normalize input.mp3 -o output.mp3 --preset podcast
```

### 6.2. Сборка эпизода (Python)

```python
from pydub import AudioSegment

# Загрузка компонентов
intro_music = AudioSegment.from_mp3("intro_jingle.mp3")
main_content = AudioSegment.from_mp3("podcast_body.mp3")
outro_music = AudioSegment.from_mp3("outro_jingle.mp3")

# Сборка с кроссфейдами
intro = intro_music.fade_in(2000)
episode = intro.append(main_content, crossfade=1500)
episode = episode.append(outro_music.fade_out(3000), crossfade=2000)

# Экспорт
episode.export("final_episode.mp3", format="mp3", bitrate="192k")
```

### 6.3. ID3 теги

```python
import eyed3

audiofile = eyed3.load("final_episode.mp3")
audiofile.tag.title = "Название эпизода"
audiofile.tag.artist = "Zinin Corporation Podcast"
audiofile.tag.album = "AI Corporation Insights"
audiofile.tag.genre = "Podcast"

# Обложка
with open("cover.jpg", "rb") as cover:
    audiofile.tag.images.set(
        eyed3.id3.frames.ImageFrame.FRONT_COVER,
        cover.read(), "image/jpeg"
    )
audiofile.tag.save()
```

### 6.4. RSS-фид (python-feedgen)

```python
from feedgen.feed import FeedGenerator

fg = FeedGenerator()
fg.load_extension('podcast')

fg.title('AI Corporation Insights')
fg.link(href='https://domain.com/podcast')
fg.description('AI-инсайты от Zinin Corporation')
fg.language('ru')
fg.podcast.itunes_category('Technology')
fg.podcast.itunes_image('https://domain.com/podcast-cover.jpg')

fe = fg.add_entry()
fe.title('Эпизод 1: AI в бизнесе')
fe.description('Описание эпизода...')
fe.enclosure('https://domain.com/episodes/ep001.mp3', 0, 'audio/mpeg')
fe.podcast.itunes_duration('00:12:30')
fe.guid('unique-episode-guid-001')

fg.rss_file('podcast_feed.xml')
```

---

## 7. Существующие инструменты и аналоги

### Podcastfy (open-source, рекомендуется как референс)

[github.com/souzatharsis/podcastfy](https://github.com/souzatharsis/podcastfy) — Python-альтернатива NotebookLM Audio Overviews:
- 100+ LLM (OpenAI, Anthropic, Google)
- TTS: OpenAI, Google, **ElevenLabs**, Microsoft Edge
- Входные данные: URL, PDF, изображения, YouTube, текст
- `pip install podcastfy`
- Multi-speaker conversational TTS
- Требования: Python 3.11+, FFmpeg

### Google NotebookLM (архитектура)

1. Загрузка документов (PDF, текст, URL)
2. Gemini 1.5 Pro генерирует скрипт двух ведущих
3. Проприетарный TTS Google конвертирует в аудио
4. Форматы: Deep Dive, Brief, Critique, Debate, Lecture

### CrewAI Podcast Pipeline (существующие реализации)

Типичная crew из 3-4 агентов:
1. **Researcher** — собирает информацию по теме
2. **Script Writer** — создаёт диалоговый скрипт
3. **Editor** — проверяет качество, факты, естественность
4. **Audio Producer** — вызывает TTS API (tool)

Результат: 15-минутный эпизод за ~8 минут (vs 6-8 часов вручную).

---

## 8. Yandex SpeechKit (альтернатива ElevenLabs для русского)

### Зачем может понадобиться

ElevenLabs отлично работает с русским, но Yandex SpeechKit — **лидер по качеству русской речи**.

### Голоса для подкастов (API v3, premium)

| Голос | Пол | Эмоции | Для подкаста |
|-------|-----|--------|-------------|
| **dasha** | Ж | neutral, good, friendly | Отлично |
| **alexander** | М | neutral, good | Отлично |
| **kirill** | М | neutral, strict, good | Хорошо |
| **masha** | Ж | good, strict, friendly | Хорошо |

**Рекомендация:** `dasha` + `alexander` с эмоцией `friendly` = естественный диалог.

### Стоимость

~40-50 рублей (~$0.50) за 30-минутный эпизод (vs ~$7.20 ElevenLabs).

### Когда использовать

- Если нужно **экономить** на TTS → Yandex SpeechKit
- Если нужно **максимальное качество русского** → Yandex SpeechKit
- Если нужен **один пайплайн на оба языка** → ElevenLabs Multilingual v2
- **У нас уже оплачен ElevenLabs** → начинаем с него, SpeechKit — запасной вариант

---

## 9. Генерация музыки

### Yandex — НЕ генерирует музыку

У Яндекса **нет** сервиса генерации музыки/джинглов. "AI-сеты My Wave" — это микширование существующих треков, не генерация.

### Альтернативы для фоновой музыки / джинглов

| Сервис | Описание | Цена |
|--------|----------|------|
| **Suno AI** | Полноценная генерация песен с вокалом | Freemium |
| **Udio** | Аналог Suno | Freemium |
| **AIVA** | Классическая/кинематографическая музыка | Freemium |
| **ElevenLabs Sound Effects** | Звуковые эффекты | Включено в план |

**Рекомендация:** Suno AI для создания джинглов intro/outro, потом использовать как static asset.

---

## 10. Предлагаемая архитектура

```
┌────────────────────────────────────────────────────┐
│                   ПОЛЬЗОВАТЕЛЬ                     │
│         (тема, тезисы, формат, длительность)       │
└─────────────────────┬──────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────┐
│          STAGE 1: ИССЛЕДОВАНИЕ                     │
│     CrewAI Agent: Researcher (Мартин CTO)          │
│     → Web search, сбор фактов, статистики          │
│     → Output: структурированный research document  │
└─────────────────────┬──────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────┐
│          STAGE 2: СКРИПТ                           │
│     CrewAI Agent: Script Writer (Юки SMM)          │
│     → Генерация диалогового скрипта                │
│     → Формат: HOST_A: ... / HOST_B: ...            │
│     → Хук, сегменты, переходы, CTA                 │
│     → Анти-фабрикация, филлеры, естественность     │
└─────────────────────┬──────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────┐
│          STAGE 3: РЕВЬЮ                            │
│     CrewAI Agent: Editor (Алексей CEO)             │
│     → Проверка фактов vs research                  │
│     → Проверка на AI-шаблоны                       │
│     → Естественность, пэйсинг, переходы           │
│     → Финальный скрипт                             │
└─────────────────────┬──────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────┐
│          STAGE 4: TTS ГЕНЕРАЦИЯ                    │
│     ElevenLabs Create Podcast API                  │
│     → model: eleven_multilingual_v2                │
│     → mode: conversation (2 голоса)                │
│     → language: ru                                 │
│     → quality: high (192kbps)                      │
│     ИЛИ ручная генерация по-сегментно              │
└─────────────────────┬──────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────┐
│          STAGE 5: ПОСТОБРАБОТКА                    │
│     Python: pydub + ffmpeg-normalize + eyed3       │
│     → Intro/outro джингл с кроссфейдами            │
│     → LUFS нормализация (-16 LUFS)                 │
│     → ID3 теги (название, автор, обложка)          │
│     → Chapter markers (mutagen)                    │
└─────────────────────┬──────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────┐
│          STAGE 6: ПУБЛИКАЦИЯ                       │
│     → Upload MP3 на хостинг (S3 / mave.digital)   │
│     → Обновить RSS-фид (python-feedgen)            │
│     → Авто-дистрибуция:                            │
│       • Яндекс.Музыка (через RSS, 2-4 часа)       │
│       • VK Подкасты (через RSS-импорт)             │
│       • Apple Podcasts (через RSS)                 │
│       • Spotify (через RSS)                        │
│     → VK wall.post — промо нового эпизода          │
│     → Telegram — уведомление подписчикам            │
└─────────────────────┬──────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────┐
│          STAGE 7: ПРОМО (существующий Юки)         │
│     → Пост в LinkedIn о новом эпизоде              │
│     → Пост в Telegram-канал                        │
│     → Аудиограмма / сниппет для соцсетей           │
└────────────────────────────────────────────────────┘
```

---

## 11. Стоимость

| Компонент | Доп. стоимость | Примечание |
|-----------|:------------:|-----------|
| ElevenLabs Creator | $0 | Уже оплачен ($22/мес). ~20 эпизодов по 10 мин |
| Хостинг MP3 | $0 | Railway (уже есть) или mave.digital (бесплатно) |
| RSS-фид | $0 | python-feedgen (open source) |
| Яндекс.Музыка | $0 | RSS-импорт бесплатный |
| VK Подкасты | $0 | RSS-импорт бесплатный |
| Скрипт генерация | $0 | Llama 3.3 70B free через OpenRouter |
| Постобработка | $0 | pydub + ffmpeg (open source) |
| **Итого доп. расходов** | **$0** | Всё уже оплачено/бесплатно |

---

## 12. Порядок реализации

### Фаза 1: MVP (1-2 недели)
1. Создать подкаст-шоу (название, обложка, описание)
2. Настроить RSS-фид (python-feedgen + S3 или mave.digital)
3. Подать RSS в Яндекс.Музыку (ждать модерацию)
4. Подать в VK Подкасты (бот @podcasters + RSS-импорт)
5. Реализовать ElevenLabs Create Podcast API tool для Юки
6. Реализовать постобработку (pydub + ffmpeg-normalize)
7. Генерация первого тестового эпизода end-to-end

### Фаза 2: CrewAI Pipeline (1-2 недели)
1. Новый task type в crew.py: `generate_podcast`
2. Researcher agent: web search по теме → research document
3. Script Writer: research → двухголосый скрипт
4. Editor: проверка скрипта → финальная версия
5. Telegram-команда `/подкаст [тема]` в Юки-боте

### Фаза 3: Автоматизация (1 неделя)
1. Автоматический upload + RSS update после генерации
2. Промо-посты в LinkedIn/Telegram после публикации
3. Транскрипция (скрипт = транскрипция)
4. Show notes генерация

### Фаза 4: Улучшения (ongoing)
1. Кастомные голоса (Voice Cloning ElevenLabs)
2. Джинглы через Suno AI
3. Chapter markers
4. Аналитика через Yandex DataLens
5. A/B тестирование форматов (bulletin vs conversation)

---

## Источники

### Яндекс.Музыка
- [Портал для подкастеров](https://yandex.ru/support/music/ru/podcast-authors.html)
- [Загрузка подкаста](https://yandex.ru/support/music/ru/podcast-authors/audio-placement.html)
- [DataLens интеграция](https://yandex.cloud/en/docs/tutorials/datalens/data-from-podcasts)
- [Yandex SpeechKit](https://yandex.cloud/en/services/speechkit)
- [SpeechKit голоса](https://cloud.yandex.com/en-ru/docs/speechkit/tts/voices)

### VK
- [VK API Schema](https://github.com/VKCOM/vk-api-schema)
- [VK Podcasters бот](https://vk.com/podcasters)
- [Mave → VK дистрибуция](https://help.mave.digital/ru/articles/22-distribuciya-v-vk)
- [SMMplanner гайд по VK подкастам](https://smmplanner.com/blog/podkasty-v-vk-eto-baza-zapisyvaiem-i-zaghruzhaiem/)

### ElevenLabs
- [Create Podcast API](https://elevenlabs.io/docs/api-reference/studio/create-podcast)
- [TTS Best Practices](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices)
- [GenFM Podcasts](https://elevenlabs.io/blog/genfm-podcasts-in-projects)
- [Модели](https://elevenlabs.io/docs/overview/models)

### Podcast Pipeline
- [Podcastfy (open-source)](https://github.com/souzatharsis/podcastfy)
- [NotebookLM архитектура](https://vrungta.substack.com/p/decoding-the-architecture-of-notebooklm)
- [CrewAI Podcast Pipeline](https://www.datacamp.com/code-along/creating-a-podcast-generation-ai-multi-agent-with-crew-ai)
- [ffmpeg-normalize](https://github.com/slhck/ffmpeg-normalize)
- [python-feedgen](https://feedgen.kiesow.be/ext/api.ext.podcast.html)
