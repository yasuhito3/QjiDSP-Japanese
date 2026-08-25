#!/bin/bash
# =============================================================
#  QjiDSP インストーラー v2
#  Qji + CamillaDSP による3D音響空間拡張システム（音場 v1〜v6 対応）
#  ★ ~/qji/ フォルダーへ Qji本体一式 + DSP関連ファイルをまとめて導入します。
# =============================================================

# --- ターミナル未起動の場合、利用可能なターミナルで自分自身を再起動 ---
if [ -z "$TERM" ] || [ "$TERM" = "dumb" ]; then
    INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    for term in xfce4-terminal lxterminal mate-terminal xterm gnome-terminal konsole qterminal; do
        if command -v "$term" &>/dev/null; then
            case "$term" in
                xfce4-terminal) exec "$term" --disable-server -T "QjiDSP インストーラー" -e "bash $0" ;;
                lxterminal)     exec "$term" --title "QjiDSP インストーラー" -e "bash $0" ;;
                mate-terminal)  exec "$term" --title "QjiDSP インストーラー" -e "bash $0" ;;
                gnome-terminal) exec "$term" --title "QjiDSP インストーラー" -- bash "$0" ;;
                konsole)        exec "$term" --title "QjiDSP インストーラー" -e "bash $0" ;;
                qterminal)      exec "$term" -e "bash $0" ;;
                xterm)          exec "$term" -fa "Monospace" -fs 12 -title "QjiDSP インストーラー" -geometry 90x40 -e bash "$0" ;;
            esac
        fi
    done
fi

set -e
trap 'ec=$?; echo ""; echo "----------------------------------------"; echo "エラーが発生しました（終了コード: $ec）。"; echo "上のログを確認してください。"; echo "----------------------------------------"; read -rp "Enterキーで閉じます..." _; exit 1' ERR

# ★ ~/qji/ フォルダーに統一（GitHub配布版の標準レイアウト）
QJI_DIR="$HOME/qji"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$HOME/qjidsp_install_debug.log"
exec > >(tee "$LOG_FILE") 2>&1

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

banner() {
    clear
    echo -e "${CYAN}${BOLD}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║       🎛️  QjiDSP インストーラー           ║"
    echo "  ║   3D空間音響拡張 for Qji 奏在（音場 v1〜v6）║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${RESET}"
}

step() { echo -e "\n${CYAN}▶ $1${RESET}"; }
ok()   { echo -e "  ${GREEN}✓ $1${RESET}"; }
warn() { echo -e "  ${YELLOW}⚠  $1${RESET}"; }
err()  { echo -e "  ${RED}✗ $1${RESET}"; }

banner

# -------------------------------------------------------------
# ステップ0: インストール先の確認
# -------------------------------------------------------------
step "インストール先の確認"
if [ ! -d "$QJI_DIR" ]; then
    warn "$QJI_DIR がまだ存在しません。新規に作成します。"
    mkdir -p "$QJI_DIR"
elif [ -f "$QJI_DIR/qji.py" ]; then
    ok "既存のQjiを検出しました: $QJI_DIR"
else
    ok "$QJI_DIR フォルダーを検出しました（新規導入します）"
fi

echo ""
echo -e "${BOLD}インストール先: ${QJI_DIR}${RESET}"
echo "このスクリプトは以下を行います:"
echo "  1. 必要なシステムパッケージのインストール"
echo "  2. Pythonライブラリ／yt-dlpの更新"
echo "  3. CamillaDSP本体のインストール"
echo "  4. deno（YouTube Music再生の安定化に使用）のインストール"
echo "  5. 仮想サウンドカード(snd-aloop)の設定"
echo "  6. ${QJI_DIR}/ へQji本体一式＋DSP関連ファイル（音場v1〜v6）を配置"
echo "  7. 既存ファイルをDSP対応版に更新（旧版は自動バックアップ）"
echo ""
read -rp "続行しますか？ [Y/n] " answer
case "$answer" in
    [nN]*) echo "インストールを中止しました。"; exit 0 ;;
esac

# -------------------------------------------------------------
# ステップ1: 必要パッケージのインストール
# -------------------------------------------------------------
step "必要パッケージのインストール"

if command -v apt >/dev/null 2>&1; then
    sudo apt update
    sudo apt install -y ffmpeg alsa-utils python3-pip python3-dev wget curl unzip git
elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y ffmpeg alsa-utils python3-pip python3-devel wget curl unzip git
else
    warn "対応していないパッケージマネージャーです。"
    echo "   ffmpeg, alsa-utils, python3-pip, python3-dev, wget, curl, unzip を手動でインストールしてください。"
fi
ok "基本パッケージの確認完了"

# -------------------------------------------------------------
# ステップ2: Pythonライブラリ／yt-dlpのインストール・更新
# -------------------------------------------------------------
step "Pythonライブラリ／yt-dlpのインストール・更新"

# ★ 「--break-system-packages を付けて試し、失敗したらエラーを握りつぶして
#   フラグ無しで再試行」という以前の作りだと、フラグ無し再試行時に出る
#   PEP668(externally-managed-environment)のエラーだけが表示されてしまい、
#   1回目が本当は何で失敗したのか(gitが無い等)が分からなくなる。
#   → pipがこのフラグに対応しているかを最初に一度だけ判定し、以降はエラーを
#   隠さずに1回だけ実行する。
PIP_FLAGS=""
if pip install --help 2>/dev/null | grep -q -- "--break-system-packages"; then
    PIP_FLAGS="--break-system-packages"
fi

pip install $PIP_FLAGS soundfile scipy
pip install $PIP_FLAGS "git+https://github.com/HEnquist/pycamilladsp.git"
ok "soundfile / scipy / pycamilladsp のインストール完了"

pip install -U $PIP_FLAGS yt-dlp
ok "yt-dlp を最新版に更新しました: $(yt-dlp --version 2>/dev/null || echo '（バージョン確認は後段で行います）')"

# -------------------------------------------------------------
# ステップ3: CamillaDSP本体のインストール
# -------------------------------------------------------------
step "CamillaDSPのインストール"

if command -v camilladsp >/dev/null 2>&1; then
    ok "CamillaDSPは既にインストールされています: $(camilladsp --version)"
else
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  CDSP_ASSET="camilladsp-linux-amd64.tar.gz" ;;
        aarch64) CDSP_ASSET="camilladsp-linux-aarch64.tar.gz" ;;
        armv7l)  CDSP_ASSET="camilladsp-linux-armv7.tar.gz" ;;
        *)
            err "未対応のアーキテクチャです: $ARCH"
            echo "   https://github.com/HEnquist/camilladsp/releases から手動でダウンロードしてください。"
            exit 1
            ;;
    esac
    echo "  アーキテクチャ: $ARCH → $CDSP_ASSET"
    TMP_DIR=$(mktemp -d)
    cd "$TMP_DIR"
    wget "https://github.com/HEnquist/camilladsp/releases/latest/download/${CDSP_ASSET}"
    tar xzf "$CDSP_ASSET"
    sudo mv camilladsp /usr/local/bin/
    cd - > /dev/null
    rm -rf "$TMP_DIR"
    ok "CamillaDSPのインストール完了: $(camilladsp --version)"
fi

# -------------------------------------------------------------
# ステップ4: deno のインストール（YouTube Music用yt-dlp補助）
# -------------------------------------------------------------
step "denoのインストール（YouTube Music再生の安定化用）"

if command -v deno >/dev/null 2>&1; then
    ok "denoは既にインストールされています: $(deno --version | head -n1)"
else
    curl -fsSL https://deno.land/install.sh | sh
    ok "denoのインストール完了"
fi

# PATHへの追加（.bashrcに未設定なら追記。既にある場合は何もしない）
DENO_ENV_MARK="# added by QjiDSP installer (deno)"
if ! grep -qs "$DENO_ENV_MARK" "$HOME/.bashrc" 2>/dev/null; then
    {
        echo ""
        echo "$DENO_ENV_MARK"
        echo 'export DENO_INSTALL="$HOME/.deno"'
        echo 'export PATH="$DENO_INSTALL/bin:$PATH"'
    } >> "$HOME/.bashrc"
    ok "~/.bashrc にdenoのPATH設定を追加しました（次回ターミナル起動時から有効）"
else
    ok "~/.bashrc には既にdenoのPATH設定があります"
fi
# 今回のインストール処理内でも使えるようにPATHを通す
export DENO_INSTALL="$HOME/.deno"
export PATH="$DENO_INSTALL/bin:$PATH"

if command -v deno >/dev/null 2>&1; then
    ok "deno 動作確認OK: $(deno --version | head -n1)"
else
    warn "denoコマンドが見つかりません。ターミナルを再起動後に再度お試しください。"
fi

# -------------------------------------------------------------
# ステップ5: 仮想サウンドカード(snd-aloop)の設定
# -------------------------------------------------------------
step "仮想サウンドカード(snd-aloop)の設定"

echo "snd-aloop" | sudo tee /etc/modules-load.d/snd-aloop.conf > /dev/null
sudo modprobe snd-aloop 2>/dev/null || true

if aplay -L 2>/dev/null | grep -qi loopback; then
    ok "Loopbackデバイスを確認しました"
else
    warn "Loopbackデバイスが見つかりません。再起動後に再度確認してください。"
fi

# -------------------------------------------------------------
# ステップ6: ファイルの配置（~/qji/ 配下に統一）
# -------------------------------------------------------------
step "Qji本体＋QjiDSPファイルの配置（${QJI_DIR}/ 配下）"

mkdir -p "$QJI_DIR/camilladsp_test"
for v in 1 2 3 4 5 6; do
    mkdir -p "$QJI_DIR/qjidsp_backup_v${v}"
done

# IRファイル・wobble・watchdog
cp "$SCRIPT_DIR/Musikvereinsaal_48k_tail.wav" "$QJI_DIR/camilladsp_test/"
cp "$SCRIPT_DIR/wobble_v1.py" "$QJI_DIR/camilladsp_test/"
cp "$SCRIPT_DIR/wobble_v2.py" "$QJI_DIR/camilladsp_test/"
cp "$SCRIPT_DIR/wobble_v3_static.py" "$QJI_DIR/camilladsp_test/"
cp "$SCRIPT_DIR/wobble_v4.py" "$QJI_DIR/camilladsp_test/"
cp "$SCRIPT_DIR/wobble_v5.py" "$QJI_DIR/camilladsp_test/"
# ★ qji.py側は「wobble_v5_harmonics_hp.py」というファイル名でv6(ヘッドホン用倍音モード)を
#   参照しているため、配布ファイル名(wobble_v5_harmonics.py)をその名前でも配置する。
cp "$SCRIPT_DIR/wobble_v5_harmonics.py" "$QJI_DIR/camilladsp_test/wobble_v5_harmonics_hp.py"
cp "$SCRIPT_DIR/cdsp_watchdog.py" "$QJI_DIR/camilladsp_test/cdsp_watchdog.py"
ok "IR/wobble/watchdogファイルを配置しました"

# yamlファイル：IR(wav)ファイルのパスをホームディレクトリ非依存の {HOME} プレースホルダーに
# 変換してから配置する（qji.py起動時に {HOME} を実ホームパスへ自動展開する仕様のため）。
# ★ v5/v6のymlはCRLF改行が混入していたため、念のためLFへ統一しておく。
for v in 1 2 3 4 5 6; do
    sed -E 's#/home/[^/"]+/camilladsp_test#{HOME}/camilladsp_test#g' \
        "$SCRIPT_DIR/spatial_final_v${v}.yml" | tr -d '\r' \
        > "$QJI_DIR/qjidsp_backup_v${v}/spatial_final.yml"
done
ok "DSP設定ファイル(v1〜v6)を配置しました"

# --- Qji本体モジュール一式（既存があればタイムスタンプ付きでバックアップしてから上書き） ---
backup_and_install() {
    local fname="$1"
    if [ ! -f "$SCRIPT_DIR/$fname" ]; then
        warn "$fname が同梱パッケージに見つかりません。スキップします。"
        return
    fi
    if [ -f "$QJI_DIR/$fname" ]; then
        local backup_name="${fname}.bak_before_dsp_$(date +%Y%m%d_%H%M%S)"
        cp "$QJI_DIR/$fname" "$QJI_DIR/$backup_name"
        ok "既存の $fname をバックアップしました: $backup_name"
    fi
    cp "$SCRIPT_DIR/$fname" "$QJI_DIR/$fname"
    ok "$fname を更新しました"
}

backup_and_install "qji.py"
backup_and_install "qji_qobuzdsp.py"
backup_and_install "qji_qobuz_browser.py"
backup_and_install "qji_soundcloud.py"
backup_and_install "qji_soundcloud_browser.py"
backup_and_install "qji_ytmusic.py"
backup_and_install "qji_ytmusic_browser.py"

# 古いバイトコードキャッシュが残っていると変更が反映されないことがあるため削除
if [ -d "$QJI_DIR/__pycache__" ]; then
    rm -rf "$QJI_DIR/__pycache__"
    ok "古いPythonキャッシュ(__pycache__)を削除しました"
fi

# import文の安全確認（qji_qobuz→qji_qobuzdspなど、旧名で残っている場合のみ書き換え）
if grep -q "^import qji_qobuz$" "$QJI_DIR/qji.py"; then
    sed -i "s/^import qji_qobuz\$/import qji_qobuzdsp as qji_qobuz/" "$QJI_DIR/qji.py"
    ok "qji.py の import 文を qji_qobuzdsp 対応に更新しました"
fi
if grep -q "modules.get('qji_qobuz')" "$QJI_DIR/qji.py"; then
    sed -i "s/modules.get('qji_qobuz')/modules.get('qji_qobuzdsp')/g" "$QJI_DIR/qji.py"
    ok "qji.py の sys.modules 参照を qji_qobuzdsp 対応に更新しました"
fi

# ★ qji.py内のDSP関連パス（camilladsp_test配下／qjidsp_backup_vN配下）は
#   os.path.expanduser("~") をそのまま使っているため、~/qji/ 配下に統一する場合は
#   qji/ を挟み込むよう書き換える。（音場v1〜v6・wobble・watchdog全パス対応）
python3 - "$QJI_DIR" << 'PYEOF'
import sys
qji_dir = sys.argv[1]
path = f"{qji_dir}/qji.py"
with open(path, "r") as f:
    content = f.read()

before_camilladsp = content.count("{_HOME}/camilladsp_test/")
before_backup = content.count("{_HOME}/qjidsp_backup_v")

content = content.replace("{_HOME}/camilladsp_test/", "{_HOME}/qji/camilladsp_test/")
content = content.replace("{_HOME}/qjidsp_backup_v", "{_HOME}/qji/qjidsp_backup_v")

# ★ yml内部の {HOME} プレースホルダー(IRファイル/wavパス用)を実ホームパスへ
#   展開する箇所は、上とは別方式（.replace('{HOME}', _HOME)）のため
#   個別に qji/ を足す必要がある。ここを見落とすと、Convフィルターの
#   wavファイルが「No such file or directory」で読み込めなくなる。
old_yml_replace = "_yml_content.replace('{HOME}', _HOME)"
new_yml_replace = "_yml_content.replace('{HOME}', _HOME + '/qji')"
yml_replace_count = content.count(old_yml_replace)
content = content.replace(old_yml_replace, new_yml_replace)

with open(path, "w") as f:
    f.write(content)

print(f"  qji.py内のDSPパスを ~/qji/ 配下に統一しました "
      f"(camilladsp_test系: {before_camilladsp}箇所 / qjidsp_backup_v系: {before_backup}箇所 / "
      f"yml内{{HOME}}展開: {yml_replace_count}箇所)")
if yml_replace_count == 0:
    print("  ⚠ yml内の{HOME}展開箇所が見つかりませんでした。qji.pyの実装が変わっている可能性があります。")
PYEOF

# ★ cdsp_watchdog.py も同様に os.path.expanduser("~") を直接使っており、
#   ~/qji/ 配下に統一しないと監視対象のspatial_final.ymlを見失うため書き換える。
python3 - "$QJI_DIR" << 'PYEOF'
import sys
qji_dir = sys.argv[1]
path = f"{qji_dir}/camilladsp_test/cdsp_watchdog.py"
with open(path, "r") as f:
    content = f.read()
old = 'CDSP_YML = f"{HOME}/camilladsp_test/spatial_final.yml"'
new = 'CDSP_YML = f"{HOME}/qji/camilladsp_test/spatial_final.yml"'
if old in content:
    content = content.replace(old, new)
    with open(path, "w") as f:
        f.write(content)
    print("  cdsp_watchdog.py内のパスを ~/qji/ 配下に統一しました")
else:
    print("  cdsp_watchdog.py は既に想定パスのため変更なし")
PYEOF

ok "ファイル配置・パス調整完了"

# -------------------------------------------------------------
# ステップ7: デスクトップアイコンの更新確認
# -------------------------------------------------------------
step "デスクトップアイコンの確認"

DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null)"
[ -z "$DESKTOP_DIR" ] && DESKTOP_DIR="$HOME/Desktop"

if [ -d "$DESKTOP_DIR" ] && ls "$DESKTOP_DIR"/*.desktop >/dev/null 2>&1; then
    ok "既存のQjiデスクトップアイコンをそのまま使用できます（起動先: ${QJI_DIR}/qji.py）"
else
    warn "デスクトップアイコンが見つかりません。Qji本体インストーラーで作成されたアイコンをご利用ください。"
fi

# -------------------------------------------------------------
# ステップ8: 動作確認
# -------------------------------------------------------------
step "動作確認"

for pyfile in qji.py qji_qobuzdsp.py qji_qobuz_browser.py qji_soundcloud.py qji_soundcloud_browser.py qji_ytmusic.py qji_ytmusic_browser.py; do
    if [ -f "$QJI_DIR/$pyfile" ]; then
        python3 -c "import ast; ast.parse(open('$QJI_DIR/$pyfile').read())" \
            && ok "$pyfile 構文チェックOK" \
            || warn "$pyfile の構文チェックでエラーが出ました"
    fi
done

for v in 1 2 3 4 5 6; do
    if camilladsp "$QJI_DIR/qjidsp_backup_v${v}/spatial_final.yml" --check >/dev/null 2>&1; then
        ok "spatial_final_v${v}.yml 構文チェックOK"
    else
        warn "spatial_final_v${v}.yml の構文チェックでエラーが出ました（DAC名の違いによる可能性があります。初回のDAC選択時に自動調整されます）"
    fi
done

python3 -c "import camilladsp; print('  pycamilladsp 動作確認OK')" 2>/dev/null || \
    warn "pycamilladsp のインポートに失敗しました"

command -v yt-dlp >/dev/null 2>&1 && ok "yt-dlp 動作確認OK: $(yt-dlp --version)" || warn "yt-dlpが見つかりません"
command -v deno >/dev/null 2>&1 && ok "deno 動作確認OK: $(deno --version | head -n1)" || warn "denoが見つかりません（ターミナル再起動後に再確認してください）"

# -------------------------------------------------------------
# 完了
# -------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}============================================================${RESET}"
echo -e "${GREEN}${BOLD}  🎉 QjiDSPのインストールが完了しました！${RESET}"
echo -e "${GREEN}${BOLD}============================================================${RESET}"
echo ""
echo "  起動方法:"
echo "    既存のQjiデスクトップアイコンからそのまま起動できます"
echo "    （手動の場合: cd ${QJI_DIR} && python3 qji.py）"
echo ""
echo "  起動後、出力デバイスで「Loopback」を選択すると、"
echo "  6つの3D音響モード（v1〜v6）を選べるようになります。"
echo "    1) 濃厚ホール（静）　2) 濃厚ホール（動）"
echo "    3) 素材の味（静）　　4) 素材の味（動）"
echo "    5) 倍音モード　　　　6) 倍音モード（ヘッドホン用）"
echo ""
echo "  ご使用のDAC（オーディオインターフェース）は、"
echo "  DSPモード選択後に自動検出・選択できます。"
echo ""
echo "  denoのPATHは ~/.bashrc に追加済みです。"
echo "  新しいターミナルを開くか、'source ~/.bashrc' を実行すると反映されます。"
echo -e "${GREEN}${BOLD}============================================================${RESET}"
read -rp "Enterキーで閉じます..." _
