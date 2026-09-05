#!/usr/bin/env bash
#
# QjiDSP — アップデート確認
#
# GitHub上の VERSION ファイルと、~/qji/ にインストール済みのバージョンを
# 比較し、新しいバージョンがあれば確認のうえダウンロード →
# install_qjidsp.sh を再実行します。
#
# Qji Peak Monitor の update.sh と同じ方式(VERSIONファイル比較 → zip取得
# → インストーラー再実行)を採用しています。
#
set -euo pipefail

QJI_DIR="${HOME}/qji"

# ── アップデート元リポジトリ ─────────────────────────────
REPO_OWNER="yasuhito3"
REPO_NAME="QjiDSP-Japanese"
REPO_BRANCH="main"
RAW_VERSION_URL="https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${REPO_BRANCH}/VERSION"
ZIP_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/refs/heads/${REPO_BRANCH}.zip"

TMP_DIR=""
_cleanup() {
    if [ -n "${TMP_DIR}" ] && [ -d "${TMP_DIR}" ]; then
        rm -rf "${TMP_DIR}"
    fi
}
trap _cleanup EXIT

_pause() {
    read -r -p "Enterキーを押すとこのウィンドウを閉じます… " _dummy || true
}

echo "=============================================="
echo " QjiDSP アップデート確認"
echo "=============================================="
echo

# ── 1. ローカルのバージョンを確認 ────────────────────────
LOCAL_VERSION="unknown"
if [ -f "${QJI_DIR}/VERSION" ]; then
    LOCAL_VERSION="$(tr -d '[:space:]' < "${QJI_DIR}/VERSION")"
fi
echo "現在のバージョン: ${LOCAL_VERSION}"

# ── 2. curl / wget の確認 ────────────────────────────────
if command -v curl >/dev/null 2>&1; then
    _fetch() { curl -fsSL "$1"; }
elif command -v wget >/dev/null 2>&1; then
    _fetch() { wget -qO- "$1"; }
else
    echo "✗ curl または wget が見つかりません。"
    echo "  以下でインストールしてから再試行してください: sudo apt install curl"
    _pause
    exit 1
fi

# ── 3. GitHub上の最新バージョンを取得 ────────────────────
echo "GitHubで最新バージョンを確認しています…"
REMOTE_VERSION="$(_fetch "${RAW_VERSION_URL}" 2>/dev/null | tr -d '[:space:]' || true)"
if [ -z "${REMOTE_VERSION}" ]; then
    echo "✗ 最新バージョン情報の取得に失敗しました。インターネット接続を確認してください。"
    _pause
    exit 1
fi
echo "GitHub上の最新バージョン: ${REMOTE_VERSION}"
echo

# ── 4. バージョン比較(簡易セマンティックバージョニング) ──
# 戻り値 0 : 第1引数 > 第2引数 / 戻り値 1 : それ以外
_version_gt() {
    [ "$1" = "$2" ] && return 1
    local IFS=.
    local -a ver1 ver2
    read -r -a ver1 <<< "$1"
    read -r -a ver2 <<< "$2"
    local len=${#ver1[@]}
    [ "${#ver2[@]}" -gt "${len}" ] && len=${#ver2[@]}
    local i a b
    for ((i = 0; i < len; i++)); do
        a="${ver1[i]:-0}"
        b="${ver2[i]:-0}"
        if ((10#${a} > 10#${b})); then return 0; fi
        if ((10#${a} < 10#${b})); then return 1; fi
    done
    return 1
}

if [ "${LOCAL_VERSION}" != "unknown" ] && ! _version_gt "${REMOTE_VERSION}" "${LOCAL_VERSION}"; then
    echo "✓ すでに最新バージョンです。アップデートの必要はありません。"
    _pause
    exit 0
fi

if [ "${LOCAL_VERSION}" = "unknown" ]; then
    echo "現在のバージョンが確認できませんでした(初回導入、または旧バージョンの可能性があります)。"
    read -r -p "最新版(${REMOTE_VERSION})を取得してインストーラーを実行しますか？ [y/N]: " ANSWER
else
    echo "🆕 新しいバージョンがあります(現在: ${LOCAL_VERSION} → 最新: ${REMOTE_VERSION})。"
    read -r -p "アップデートしますか？ [y/N]: " ANSWER
fi
case "${ANSWER}" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "中止しました。"; _pause; exit 0 ;;
esac
echo

# ── 5. unzip の確認 ──────────────────────────────────────
if ! command -v unzip >/dev/null 2>&1; then
    echo "✗ unzip が見つかりません。"
    echo "  以下でインストールしてから再試行してください: sudo apt install unzip"
    _pause
    exit 1
fi

# ── 6. 最新版をダウンロード・展開 ────────────────────────
echo "最新版をダウンロードしています…"
TMP_DIR="$(mktemp -d)"
if ! _fetch "${ZIP_URL}" > "${TMP_DIR}/update.zip"; then
    echo "✗ ダウンロードに失敗しました。インターネット接続を確認してください。"
    _pause
    exit 1
fi

echo "展開しています…"
unzip -q "${TMP_DIR}/update.zip" -d "${TMP_DIR}"

EXTRACTED_DIR="$(find "${TMP_DIR}" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
# ★ install.sh がリポジトリ直下にある Qji Peak Monitor と違い、QjiDSPの
#   インストーラー本体は "qjidsp_installer/" サブフォルダの中にある点に注意。
INSTALLER_PATH="${EXTRACTED_DIR}/qjidsp_installer/install_qjidsp.sh"
if [ -z "${EXTRACTED_DIR}" ] || [ ! -f "${INSTALLER_PATH}" ]; then
    echo "✗ 展開したファイルの中に install_qjidsp.sh が見つかりませんでした。"
    _pause
    exit 1
fi
echo "  ✓ 展開完了"
echo

# ── 7. install_qjidsp.sh を再実行 ────────────────────────
# install_qjidsp.sh は正常終了時に自分自身でEnterキー待ちの一時停止を
# 行うため(既存の仕様)、ここでは重ねて一時停止しない。
echo "インストーラーを実行しています…"
echo "----------------------------------------------"
bash "${INSTALLER_PATH}"
echo "----------------------------------------------"
echo

echo "=============================================="
echo " アップデート完了！(${LOCAL_VERSION} → ${REMOTE_VERSION})"
echo "=============================================="
