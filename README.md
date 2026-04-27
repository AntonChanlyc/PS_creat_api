# Вариант 1

## Цель работы

Написать веб-сервис на базе Flask, который собирает данные о деятельности
пользователя на GitHub и GitLab, формирует аналитическую сводку с
метаданными и отдаёт её через REST API.

Используйте наработки из первого задания: вся логика обращения к GitHub и
GitLab, правила расчёта полей и обработки ошибок переносятся без изменений.

<details>
<summary>Развернуть README первого задания</summary>

### Цель

Написать скрипт, который собирает данные о пользователе с GitHub и GitLab
и формирует аналитическую сводку в файле `result.json`.

### Какие данные нужно получить

#### GitHub

| Эндпоинт      | Метод | Описание                      |
|---------------|-------|-------------------------------|
| `/user`       | GET   | Профиль текущего пользователя |
| `/user/repos` | GET   | Список репозиториев           |

Для каждого репозитория из `/user/repos` в ответе есть поле
`languages_url` — готовая ссылка на список языков. GET-запрос по этой
ссылке отдаёт объект вида `{"Python": 15000, "JavaScript": 3000}` —
нужны только ключи.

Цепочка запросов:

1. `GET /user/repos` → список репозиториев.
2. Для каждого репозитория берёте `languages_url`.
3. `GET {languages_url}` → языки этого репозитория.

Для `N` репозиториев — `1 + N` запросов.

Заголовки всех запросов к GitHub:

```
Authorization: Bearer <GITHUB_TOKEN>
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
```

Из `/user` нужны: `login`, `name`, `bio`, `email`.
Из `/user/repos` для каждого репозитория: `name`, `stargazers_count`,
`forks_count`, `updated_at`.

Документация:

- https://docs.github.com/en/rest/users/users#get-the-authenticated-user
- https://docs.github.com/en/rest/repos/repos#list-repositories-for-the-authenticated-user
- https://docs.github.com/en/rest/repos/repos#list-repository-languages

#### GitLab

| Эндпоинт | Метод | Описание                      |
|----------|-------|-------------------------------|
| `/user`  | GET   | Профиль текущего пользователя |

Заголовок:

```
PRIVATE-TOKEN: <GITLAB_TOKEN>
```

Из `/user` нужны: `username`, `state`, `location`, `public_email`.

Документация:
https://docs.gitlab.com/ee/api/users.html#for-normal-users-1

### Что должно быть в `result.json`

В итоговый файл записывается **только сводка** — сырые данные из API
сохранять не нужно.

```json
{
  "github_username": "octocat_pro",
  "gitlab_username": "alex_gitlab_99",
  "total_repos": 5,
  "total_stars": 1335,
  "total_forks": 352,
  "most_popular_repo": "awesome-project-v1",
  "languages": ["Go", "JavaScript", "Python"],
  "github_profile_filled": 4,
  "gitlab_profile_filled": 3,
  "errors": []
}
```

| Поле                    | Тип           | Описание                                                                          |
|-------------------------|---------------|-----------------------------------------------------------------------------------|
| `github_username`       | `str \| null` | `login` из GitHub. `null`, если не удалось получить                               |
| `gitlab_username`       | `str \| null` | `username` из GitLab. `null`, если не удалось получить                            |
| `total_repos`           | `int`         | Количество репозиториев из GitHub                                                 |
| `total_stars`           | `int`         | Сумма `stargazers_count` по всем репозиториям                                     |
| `total_forks`           | `int`         | Сумма `forks_count` по всем репозиториям                                          |
| `most_popular_repo`     | `str \| null` | `name` репозитория с наибольшим `stargazers_count`. `null`, если репозиториев нет |
| `languages`             | `list`        | Уникальные языки со всех репозиториев, по алфавиту. `[]`, если данных нет         |
| `github_profile_filled` | `int`         | Сколько из 4 полей GitHub-профиля заполнены (не `null` и не `""`)                 |
| `gitlab_profile_filled` | `int`         | Сколько из 4 полей GitLab-профиля заполнены (не `null` и не `""`)                 |
| `errors`                | `list`        | Строки с описанием ошибок                                                         |

#### Подсчёт заполненности профиля

- **GitHub** — 4 поля: `login`, `name`, `bio`, `email`.
- **GitLab** — 4 поля: `username`, `state`, `location`, `public_email`.

Поле считается заполненным, если API вернул для него непустое значение
(не `null` и не `""`).

Пример: API GitHub `/user` вернул
`{"login": "octocat", "name": "Octo", "bio": null, "email": null}`.
Тогда `github_profile_filled = 2`.

### Обработка ошибок

Каждый запрос обрабатывается **независимо**. Если один упал — остальные
должны выполниться.

Если запрос завершился ошибкой (код 4xx/5xx, таймаут, сетевая ошибка),
добавьте строку в массив `"errors"` в формате:
`"<платформа> <эндпоинт>: <описание>"`.

Если ошибок нет — `"errors": []`.

Если не удалось загрузить репозитории, счётчики равны `0`,
`most_popular_repo` — `null`, `languages` — `[]`.

> Если запрос `/user/repos` упал, запросы за языками отдельных
> репозиториев делать не нужно.
> Если `/user/repos` успешен, но запрос языков для конкретного
> репозитория упал — добавьте ошибку в `"errors"`, но остальные
> репозитории обработайте.

</details>

## Настройка окружения

Токены, базовые URL API и параметры запуска сервера читаются из `.env`:

```
GITHUB_TOKEN = "<ваш-токен>"
GITLAB_TOKEN = "<ваш-токен>"

GITHUB_API_URL = "https://api.github.com"
GITLAB_API_URL = "https://git.miem.hse.ru/api/v4"

HOST = "0.0.0.0"
PORT = "8080"
```

> `GITHUB_API_URL` и `GITLAB_API_URL` — базовые адреса API **без
> завершающего слеша**. К ним добавляется путь эндпоинта:
> `{GITHUB_API_URL}/user`.
>
> `HOST` и `PORT` задают адрес и порт, на котором поднимается сервер.
> Если переменные не заданы, используются значения по умолчанию:
> `HOST=0.0.0.0`, `PORT=8080`.

## Требования к API

Сервер должен предоставлять два эндпоинта:

| Эндпоинт             | Метод | Описание                                                                   |
|----------------------|-------|----------------------------------------------------------------------------|
| `/api/resume`        | GET   | Возвращает текущую сводку в формате JSON.                                  |
| `/api/resume/update` | POST  | Запускает принудительное обновление данных и возвращает актуальную сводку. |

Дополнительные требования:

- Адрес и порт берутся из переменных окружения `HOST` и `PORT`.
- При старте сервер выполняет **первичный сбор данных** до того, как
  начинает обрабатывать запросы.
- Ответы обоих эндпоинтов имеют `Content-Type: application/json` и
  HTTP-код `200` при успехе.
- Логика полей, формат ошибок и обработка падений отдельных запросов
  совпадают с первым заданием.

## Структура ответа

При успешном сборе API возвращает JSON такого вида:

```json
{
  "metadata": {
    "last_updated": "2026-04-04T12:00:00Z"
  },
  "github_username": "dev_hero_99",
  "gitlab_username": "gitlab_warrior",
  "total_repos": 12,
  "total_stars": 850,
  "total_forks": 124,
  "most_popular_repo": "awesome-flask-api",
  "languages": [
    "CSS",
    "Dockerfile",
    "HTML",
    "JavaScript",
    "Python",
    "TypeScript"
  ],
  "github_profile_filled": 3,
  "gitlab_profile_filled": 4,
  "errors": []
}
```

**Важно: список `languages` сортируется по алфавиту.**

Объект `metadata` содержит одно поле — `last_updated`: время последнего
обновления сводки в UTC, в формате ISO 8601 `YYYY-MM-DDTHH:MM:SSZ`
(например, `2026-04-04T12:00:00Z`). Без миллисекунд, без смещений,
с обязательным суффиксом `Z`.

Остальные поля соответствуют шаблону из первого задания.

При наличии ошибок ответ выглядит так:

```json
{
  "metadata": {
    "last_updated": "2026-04-04T12:05:30Z"
  },
  "github_username": null,
  "gitlab_username": null,
  "total_repos": 0,
  "total_stars": 0,
  "total_forks": 0,
  "most_popular_repo": null,
  "languages": [],
  "github_profile_filled": 0,
  "gitlab_profile_filled": 0,
  "errors": [
    "github /user: не удалось загрузить профиль",
    "github /user/repos: не удалось загрузить репозитории",
    "github /repos/languages: не удалось получить языки проекта",
    "gitlab /user: не удалось загрузить профиль"
  ]
}
```
**Важно: ошибка `"github /repos/languages: не удалось получить языки проекта"` должна также выводить в том случае, если не удалось получить ответ от роута `/user/repos`**


## Требования к коду

Требования к стилю и `flake8` — как в первом задании. `flake8 main.py`
должен отрабатывать без замечаний.

Прочее:

1. Все зависимости перечислены в `requirements.txt`.
2. Точка входа — `python main.py`: выполняется первичный сбор данных
   и поднимается HTTP-сервер.

## Как сдать работу

В репозитории должны быть два файла:

1. `main.py` — код решения
2. `requirements.txt` — зависимости

Сделайте коммит и запушьте в репозиторий — проверка запустится
автоматически.

## Чек-лист перед отправкой

- [ ] `flake8 main.py` — без ошибок
- [ ] `.env` добавлен в `.gitignore`
- [ ] Сервер стартует на `HOST:PORT` из переменных окружения
- [ ] При старте выполняется первичный сбор до обработки запросов
- [ ] `GET /api/resume` возвращает актуальную сводку в JSON
- [ ] `POST /api/resume/update` обновляет сводку и возвращает её
- [ ] `metadata.last_updated` — строка `YYYY-MM-DDTHH:MM:SSZ` в UTC
- [ ] Ошибки API не ломают сервис, а попадают в поле `errors`
- [ ] В репозитории есть `main.py` и `requirements.txt`

## Что делать, если проверка не проходит

Если ошибка на стороне грейдера — напишите преподавателям,
приложив скриншоты с контекстом.
