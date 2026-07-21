#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$SCRIPT_DIR}"
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
SERVICE="${SERVICE:-shans.service}"
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-45}"
RUN_TESTS="${RUN_TESTS:-1}"
GUNICORN_VERSION="${GUNICORN_VERSION:-26.0.0}"

BEFORE_HEAD=""
UPDATED=0
SERVICE_TOUCHED=0

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
  printf 'Ошибка: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "не найдена команда '$1'"
}

systemctl_cmd() {
  if [[ "$EUID" -eq 0 ]]; then
    systemctl "$@"
  else
    sudo systemctl "$@"
  fi
}

read_env_value() {
  local key="$1"
  local env_file="$2"
  local value=""

  if [[ -f "$env_file" ]]; then
    value="$(grep -E "^[[:space:]]*${key}=" "$env_file" | tail -n 1 || true)"
    value="${value#*=}"
    value="${value%$'\r'}"
    if [[ ${#value} -ge 2 ]]; then
      if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
        value="${value:1:${#value}-2}"
      elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
        value="${value:1:${#value}-2}"
      fi
    fi
  fi

  printf '%s' "$value"
}

backup_database() {
  local database_path="${DATABASE_NAME:-}"
  local backup_path

  if [[ -z "$database_path" ]]; then
    database_path="$(read_env_value DATABASE_NAME "$APP_DIR/.env")"
  fi
  database_path="${database_path:-app.db}"

  if [[ "$database_path" != /* ]]; then
    database_path="$APP_DIR/$database_path"
  fi

  if [[ ! -f "$database_path" ]]; then
    log "База данных пока не существует, резервная копия не требуется"
    return
  fi

  mkdir -p "$BACKUP_DIR"
  backup_path="$BACKUP_DIR/$(basename "$database_path").$(date '+%Y%m%d-%H%M%S').backup"
  cp -p -- "$database_path" "$backup_path"
  log "Резервная копия базы: $backup_path"
}

install_dependencies() {
  "$VENV_DIR/bin/python" -m pip install \
    --disable-pip-version-check \
    -r requirements.txt \
    "gunicorn==$GUNICORN_VERSION"
}

check_health() {
  "$VENV_DIR/bin/python" - "$HEALTH_URL" <<'PY'
import json
import sys
import urllib.request

url = sys.argv[1]
with urllib.request.urlopen(url, timeout=5) as response:
    payload = json.load(response)
if response.status != 200 or payload.get("status") != "ok":
    raise SystemExit(1)
PY
}

wait_for_health() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))

  while (( SECONDS < deadline )); do
    if check_health >/dev/null 2>&1; then
      log "Проверка $HEALTH_URL успешна"
      return 0
    fi
    sleep 2
  done

  return 1
}

rollback_on_error() {
  local exit_code="$1"
  local line_number="$2"

  trap - ERR
  set +e
  printf 'Ошибка деплоя в строке %s. Выполняется откат.\n' "$line_number" >&2

  if [[ "$UPDATED" -eq 1 && -n "$BEFORE_HEAD" ]]; then
    git reset --hard "$BEFORE_HEAD"
    if [[ -x "$VENV_DIR/bin/python" ]]; then
      install_dependencies
    fi
  fi

  if [[ "$SERVICE_TOUCHED" -eq 1 ]]; then
    systemctl_cmd restart "$SERVICE"
  fi

  printf 'Деплой отменён; предыдущая версия восстановлена.\n' >&2
  exit "$exit_code"
}

main() {
  require_cmd git
  require_cmd python3
  require_cmd systemctl
  if [[ "$EUID" -ne 0 ]]; then
    require_cmd sudo
  fi

  [[ -d "$APP_DIR/.git" ]] || fail "$APP_DIR не является Git-репозиторием"
  cd "$APP_DIR"

  if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
    git status --short >&2
    fail "на сервере есть локальные изменения; деплой остановлен, чтобы не потерять их"
  fi

  systemctl_cmd cat "$SERVICE" >/dev/null
  BEFORE_HEAD="$(git rev-parse HEAD)"
  log "Текущая версия: ${BEFORE_HEAD:0:12}"

  backup_database

  log "Получение $REMOTE/$BRANCH из GitHub"
  git fetch --prune "$REMOTE" "$BRANCH"
  git checkout "$BRANCH"
  git show-ref --verify --quiet "refs/remotes/$REMOTE/$BRANCH" \
    || fail "ветка $REMOTE/$BRANCH не найдена"
  git merge --ff-only "$REMOTE/$BRANCH"

  if [[ "$(git rev-parse HEAD)" != "$BEFORE_HEAD" ]]; then
    UPDATED=1
  fi

  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    log "Создание виртуального окружения"
    python3 -m venv "$VENV_DIR"
  fi

  log "Обновление зависимостей"
  install_dependencies

  log "Проверка Python-кода"
  "$VENV_DIR/bin/python" -m compileall -q app

  if [[ "$RUN_TESTS" == "1" ]]; then
    log "Запуск тестов"
    "$VENV_DIR/bin/python" -m unittest discover -s tests -q
  fi

  log "Перезапуск $SERVICE"
  SERVICE_TOUCHED=1
  systemctl_cmd restart "$SERVICE"
  systemctl_cmd is-active --quiet "$SERVICE"

  log "Проверка работоспособности"
  wait_for_health

  local after_head
  after_head="$(git rev-parse HEAD)"
  log "Деплой завершён: ${BEFORE_HEAD:0:12} -> ${after_head:0:12}"
}

trap 'rollback_on_error "$?" "$LINENO"' ERR
main "$@"
