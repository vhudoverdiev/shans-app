#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/var/www/shans-app}"
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
SERVICE="${SERVICE:-shans.service}"
CLEAN_MODE="${CLEAN_MODE:-safe}" # safe|aggressive
VERIFY_CLEAN="${VERIFY_CLEAN:-true}" # true|false

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

usage() {
  cat <<'USAGE'
Использование:
  ./deploy.sh

Опциональные переменные окружения:
  APP_DIR=/var/www/shans-app   # путь к репозиторию
  BRANCH=main                  # ветка для деплоя
  REMOTE=origin                # удалённый репозиторий
  SERVICE=shans.service        # systemd unit
  CLEAN_MODE=safe              # safe | aggressive
  VERIFY_CLEAN=true            # true | false (проверка, что нет изменённых tracked-файлов)

Пример:
  APP_DIR=/var/www/shans-app BRANCH=main SERVICE=shans.service ./deploy.sh
USAGE
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Ошибка: не найдена команда '$1'" >&2
    exit 1
  }
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
  fi

  require_cmd git
  require_cmd systemctl

  log "Старт деплоя"
  log "APP_DIR=$APP_DIR, REMOTE=$REMOTE, BRANCH=$BRANCH, SERVICE=$SERVICE, CLEAN_MODE=$CLEAN_MODE, VERIFY_CLEAN=$VERIFY_CLEAN"

  if [[ ! -d "$APP_DIR/.git" ]]; then
    echo "Ошибка: $APP_DIR не является git-репозиторием" >&2
    exit 1
  fi

  cd "$APP_DIR"

  local before_head after_head remote_head
  before_head="$(git rev-parse --short HEAD)"

  log "Текущий branch до деплоя: $(git branch --show-current)"
  log "Текущий HEAD до деплоя: $before_head"

  log "git fetch $REMOTE"
  git fetch --prune "$REMOTE"

  log "checkout branch '$BRANCH'"
  git checkout "$BRANCH"

  remote_head="$(git rev-parse --short "$REMOTE/$BRANCH")"
  log "Удалённый HEAD $REMOTE/$BRANCH: $remote_head"

  log "reset --hard $REMOTE/$BRANCH"
  git reset --hard "$REMOTE/$BRANCH"

  if [[ "$CLEAN_MODE" == "aggressive" ]]; then
    log "clean -fdx (агрессивно: удаляет игнорируемые файлы, включая .env)"
    git clean -fdx
  else
    log "clean -fd (без удаления .env и других игнорируемых файлов)"
    git clean -fd
  fi

  after_head="$(git rev-parse --short HEAD)"
  log "HEAD после деплоя: $after_head"

  log "restart service: $SERVICE"
  systemctl restart "$SERVICE"

  log "service status"
  systemctl status "$SERVICE" --no-pager -l

  if [[ "$VERIFY_CLEAN" == "true" ]]; then
    log "Проверка tracked-изменений после деплоя"
    if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
      echo "Ошибка: после деплоя есть изменённые tracked-файлы. Проверьте git status." >&2
      git status --short
      exit 1
    fi
    log "tracked-файлы чистые"
  fi

  log "Деплой завершён: $before_head -> $after_head (remote: $remote_head)"
}

main "$@"
