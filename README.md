# Telegram Bot Template

Минимальный шаблон Telegram-бота на Python и aiogram 3.

## Структура

- `main.py` — точка запуска;
- `manage.py` — сборка и настройка приложения;
- `settings.py` — настройки из окружения;
- `bot/commands/` — команды `/start` и `/help`;
- `bot/handlers/` — обработчики меню, языка и поддержки;
- `bot/keyboards/` — inline-клавиатуры;
- `storage/` — пользователи, обращения и модели данных;
- `locales/` — русские и английские тексты по кодам.

При первом запуске бот создаёт `data/users.db` и `data/appeals.db`. Эти файлы не добавляются в Git.
FSM-состояния также сохраняются в `users.db`, поэтому незавершённый ввод обращения переживает перезапуск бота.

## Запуск

Создайте виртуальное окружение и установите зависимости:

```shell
python -m venv .venv
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env`, укажите токен от BotFather и запустите:

```shell
python main.py
```
