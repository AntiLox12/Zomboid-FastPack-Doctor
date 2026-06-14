# Zomboid FastPack Doctor

![Zomboid FastPack Doctor](assets/branding/github-social-preview.png)

[English](README.md) | [Последний релиз](https://github.com/AntiLox12/Zomboid-FastPack-Doctor/releases/latest)

FastPack Doctor - гибридный диагностический инструмент для больших сборок
Project Zomboid Build 42. Он ищет измеримые проблемы конфигурации и контента,
не обещая невозможную замену нативного загрузчика игры.

## Что входит

- **Мод из Workshop:** внутриигровой runtime-отчёт, API отложенных задач и
  лёгкое профилирование обработчиков, подключённых через FastPack.
- **Windows Companion:** проверка до запуска игры: размеры модов, дубликаты
  определений, пересечения карт, зависимости, рискованный порядок, ошибки
  консоли, устаревшая структура и кандидаты для safe mode.
- **HTML и JSON отчёты:** отчёты можно сохранять и сравнивать после обновлений
  Workshop.

## Использование версии Workshop

1. Подпишитесь на **Zomboid FastPack Doctor** и включите его в менеджере модов
   Build 42.
2. Загрузите мир.
3. Откройте меню паузы, список активных модов и нажмите
   **Отчёт FastPack**.
4. Кнопка **Скачать Companion** откроет полный сканер на GitHub.

Подписка Steam устанавливает только внутриигровой мод. Workshop не умеет
устанавливать или запускать внешнюю программу Companion.

## Windows Companion

Скачайте `FastPackDoctor-Windows-v0.1.0.zip` из
[последнего релиза](https://github.com/AntiLox12/Zomboid-FastPack-Doctor/releases/latest),
распакуйте архив и выполните:

```powershell
.\FastPackDoctor.exe scan --safe-mode
```

Steam, Workshop, активный профиль Build 42, `console.txt` и runtime-отчёт
определяются автоматически. Результаты появятся в папке
`outputs\fastpack-report\`.

Запуск из исходников:

```powershell
python .\companion\fastpack.py scan --safe-mode
python -m unittest discover -s tests -v
```

## Ограничения

- Lua-мод не патчит Java-загрузчик.
- Runtime-профилирование видит обработчики, зарегистрированные через API
  FastPack.
- Одинаковый script ID означает возможное переопределение, но не доказывает
  несовместимость.
- Safe-mode профиль создаётся только для проверки и никогда не заменяет
  рабочий профиль автоматически.

Подробности: [использование Companion](docs/USAGE.md) и
[API для мододелов](docs/MODDER_API.md).
