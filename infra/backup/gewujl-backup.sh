#!/usr/bin/env bash
set -Eeuo pipefail

MODE="${1:-daily}"

APP_NAME="${APP_NAME:-gewujl}"
BACKUP_ROOT="${BACKUP_ROOT:-/root/backups}"
DEPLOY_PATH="${DEPLOY_PATH:-/root/code/kaoyan-miniapp-mvp}"
WEB_ROOT="${WEB_ROOT:-/var/www/html}"
ENV_FILE="${ENV_FILE:-${DEPLOY_PATH}/backend/.env}"
KEEP_DAYS_DAILY="${KEEP_DAYS_DAILY:-14}"
KEEP_DAYS_PREDEPLOY="${KEEP_DAYS_PREDEPLOY:-10}"
RCLONE_REMOTE="${RCLONE_REMOTE:-}"
REMOTE_BACKUP_TARGET="${REMOTE_BACKUP_TARGET:-}"
REMOTE_SSH_PORT="${REMOTE_SSH_PORT:-22}"
REMOTE_SSH_KEY="${REMOTE_SSH_KEY:-}"

if [[ "${MODE}" != "daily" && "${MODE}" != "predeploy" ]]; then
  echo "Usage: $0 [daily|predeploy]"
  exit 2
fi

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

upload_to_ssh_target() {
  local source_dir="$1"
  local target="$2"
  local sub_path="$3"
  local remote_host remote_base remote_dest
  local -a ssh_opts

  if [[ "${target}" != *:* ]]; then
    log "REMOTE_BACKUP_TARGET must be in user@host:/path format"
    return 1
  fi

  remote_host="${target%%:*}"
  remote_base="${target#*:}"
  remote_dest="${remote_base%/}/${APP_NAME}/${MODE}/${sub_path}"
  ssh_opts=(-p "${REMOTE_SSH_PORT}" -o StrictHostKeyChecking=accept-new)

  if [[ -n "${REMOTE_SSH_KEY}" ]]; then
    if [[ ! -f "${REMOTE_SSH_KEY}" ]]; then
      log "REMOTE_SSH_KEY file not found: ${REMOTE_SSH_KEY}"
      return 1
    fi
    ssh_opts+=(-i "${REMOTE_SSH_KEY}")
  fi

  log "uploading backup to ${remote_host}:${remote_dest}"
  ssh "${ssh_opts[@]}" "${remote_host}" "mkdir -p '${remote_dest}'"
  scp "${ssh_opts[@]}" -r "${source_dir}/." "${remote_host}:${remote_dest}/"
}

strip_quotes() {
  local v="$1"
  v="${v%\"}"
  v="${v#\"}"
  v="${v%\'}"
  v="${v#\'}"
  printf '%s' "${v}"
}

load_db_url() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    return 1
  fi
  local line
  line="$(grep -E '^DATABASE_URL=' "${ENV_FILE}" | tail -n 1 || true)"
  if [[ -z "${line}" ]]; then
    return 1
  fi
  strip_quotes "${line#DATABASE_URL=}"
}

parse_mysql_url() {
  local url="$1"
  python3 - "$url" <<'PY'
import sys
from urllib.parse import urlparse

dsn = sys.argv[1]
u = urlparse(dsn)
scheme = (u.scheme or "").split("+")[0]
if scheme != "mysql":
    sys.exit(2)
db_name = (u.path or "/").lstrip("/") or ""
if not (u.hostname and u.username and db_name):
    sys.exit(3)
print(u.hostname)
print(u.port or 3306)
print(u.username)
print(u.password or "")
print(db_name)
PY
}

timestamp="$(date '+%Y%m%d-%H%M%S')"
day="$(date '+%F')"

if [[ "${MODE}" == "daily" ]]; then
  run_dir="${BACKUP_ROOT}/daily/${day}/${timestamp}"
else
  run_dir="${BACKUP_ROOT}/predeploy/${timestamp}"
fi

mkdir -p "${run_dir}"
log "backup mode=${MODE} target=${run_dir}"

if [[ -d "${DEPLOY_PATH}" ]]; then
  tar \
    --exclude='.git' \
    --exclude='backend/.venv' \
    --exclude='**/__pycache__' \
    -czf "${run_dir}/repo.tar.gz" \
    -C "${DEPLOY_PATH}" \
    .
fi

if [[ -d "${WEB_ROOT}" ]]; then
  tar -czf "${run_dir}/web.tar.gz" -C "${WEB_ROOT}" .
fi

if [[ -d "/etc/nginx" ]]; then
  tar -czf "${run_dir}/nginx.tar.gz" -C /etc nginx
fi

if [[ -d "/etc/systemd/system" ]]; then
  tar \
    --ignore-failed-read \
    -czf "${run_dir}/systemd.tar.gz" \
    -C /etc/systemd/system \
    kaoyan-backend.service \
    gewujl-backup.service \
    gewujl-backup.timer
fi

if [[ "${MODE}" == "daily" ]]; then
  db_url="$(load_db_url || true)"
  if [[ -n "${db_url}" ]]; then
    if ! command -v mysqldump >/dev/null 2>&1; then
      log "mysqldump not found, installing mysql client"
      apt-get update -y >/dev/null
      DEBIAN_FRONTEND=noninteractive apt-get install -y default-mysql-client >/dev/null
    fi

    if parsed="$(parse_mysql_url "${db_url}" 2>/dev/null)"; then
      mapfile -t db_fields <<<"${parsed}"
      db_host="${db_fields[0]}"
      db_port="${db_fields[1]}"
      db_user="${db_fields[2]}"
      db_pass="${db_fields[3]}"
      db_name="${db_fields[4]}"

      log "dumping mysql db=${db_name} host=${db_host}:${db_port}"
      MYSQL_PWD="${db_pass}" mysqldump \
        --single-transaction \
        --quick \
        --default-character-set=utf8mb4 \
        -h "${db_host}" \
        -P "${db_port}" \
        -u "${db_user}" \
        "${db_name}" > "${run_dir}/mysql.sql"
      gzip -f "${run_dir}/mysql.sql"
    else
      log "DATABASE_URL is not a supported mysql url, skip db dump"
    fi
  else
    log "DATABASE_URL not found in ${ENV_FILE}, skip db dump"
  fi
fi

(
  cd "${run_dir}"
  sha256sum ./*.gz > SHA256SUMS.txt 2>/dev/null || true
  {
    echo "mode=${MODE}"
    echo "created_at=$(date '+%F %T')"
    echo "hostname=$(hostname)"
    echo "deploy_path=${DEPLOY_PATH}"
    echo "web_root=${WEB_ROOT}"
  } > METADATA.txt
)

if [[ -n "${RCLONE_REMOTE}" ]] && command -v rclone >/dev/null 2>&1; then
  remote_target="${RCLONE_REMOTE%/}/${APP_NAME}/${MODE}/"
  if [[ "${MODE}" == "daily" ]]; then
    remote_target="${remote_target}${day}/${timestamp}/"
  else
    remote_target="${remote_target}${timestamp}/"
  fi
  log "uploading backup to ${remote_target}"
  rclone copy "${run_dir}/" "${remote_target}" --create-empty-src-dirs
fi

if [[ -n "${REMOTE_BACKUP_TARGET}" ]]; then
  if [[ "${MODE}" == "daily" ]]; then
    upload_to_ssh_target "${run_dir}" "${REMOTE_BACKUP_TARGET}" "${day}/${timestamp}"
  else
    upload_to_ssh_target "${run_dir}" "${REMOTE_BACKUP_TARGET}" "${timestamp}"
  fi
fi

if [[ "${MODE}" == "daily" ]]; then
  find "${BACKUP_ROOT}/daily" -mindepth 1 -maxdepth 1 -type d -mtime "+${KEEP_DAYS_DAILY}" -exec rm -rf {} +
else
  find "${BACKUP_ROOT}/predeploy" -mindepth 1 -maxdepth 1 -type d -mtime "+${KEEP_DAYS_PREDEPLOY}" -exec rm -rf {} +
fi

log "backup done"
