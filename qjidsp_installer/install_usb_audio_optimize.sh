#!/bin/bash
# install_usb_audio_optimize.sh
#
# Qji用: USB出力デジタルノイズ対策の初期設定（1回だけ、sudoで実行）
#
# 行うこと:
#   1) 現在接続中のUSBオーディオデバイスを検出し、それぞれについて
#      「USBオートサスペンド無効化」のudevルールを idVendor/idProduct 指定で作成
#      （USBの省電力機能による電源の抜き挿しでプチノイズ/瞬断が起きるのを防ぐ）
#   2) audioグループにリアルタイムスケジューリング優先度(rtprio)と
#      メモリロック(memlock)の権限を付与
#      （再生プロセスが他プロセスにCPUを奪われてバッファアンダーラン→
#        プチノイズが出るのを防ぐ）
#   3) 実行ユーザーをaudioグループに追加（未所属の場合）
#
# 使い方:
#   sudo bash install_usb_audio_optimize.sh
#   実行後、一度ログアウト/ログインし直してください（グループ変更の反映のため）。

set -e

if [ "$EUID" -ne 0 ]; then
    echo "❌ このスクリプトはroot権限が必要です。sudo を付けて実行してください:"
    echo "   sudo bash $0"
    exit 1
fi

TARGET_USER="${SUDO_USER:-$(whoami)}"
echo "============================================================"
echo "🔌 Qji USBオーディオ ノイズ対策セットアップ"
echo "============================================================"

# ---------------------------------------------------------------
# 1) 接続中のUSBオーディオデバイスを検出してudevルールを生成
# ---------------------------------------------------------------
RULE_FILE="/etc/udev/rules.d/99-qji-usb-audio-noautosuspend.rules"
echo "# Qji: USBオーディオ出力デバイスのオートサスペンドを無効化" > "$RULE_FILE"
echo "# (このファイルは install_usb_audio_optimize.sh により自動生成されました)" >> "$RULE_FILE"

FOUND=0
for cardpath in /sys/class/sound/card*/device; do
    [ -e "$cardpath" ] || continue
    devpath=$(readlink -f "$cardpath")
    # idVendor/idProductが見つかるまで親ディレクトリを辿る（USB本体のディレクトリを探す）
    d="$devpath"
    for _i in 1 2 3 4 5 6; do
        if [ -f "$d/idVendor" ] && [ -f "$d/idProduct" ]; then
            VID=$(cat "$d/idVendor")
            PID=$(cat "$d/idProduct")
            NAME=$(cat "$d/product" 2>/dev/null || echo "Unknown USB Audio Device")
            echo "  検出: $NAME (idVendor=$VID idProduct=$PID)"
            {
                echo "ACTION==\"add\", SUBSYSTEM==\"usb\", ATTR{idVendor}==\"$VID\", ATTR{idProduct}==\"$PID\", TEST==\"power/control\", ATTR{power/control}=\"on\""
                echo "ACTION==\"add\", SUBSYSTEM==\"usb\", ATTR{idVendor}==\"$VID\", ATTR{idProduct}==\"$PID\", TEST==\"power/autosuspend\", ATTR{power/autosuspend}=\"-1\""
                echo "ACTION==\"add\", SUBSYSTEM==\"usb\", ATTR{idVendor}==\"$VID\", ATTR{idProduct}==\"$PID\", RUN+=\"/bin/sh -c 'chgrp audio /sys\$devpath/power/control 2>/dev/null; chmod g+w /sys\$devpath/power/control 2>/dev/null; chgrp audio /sys\$devpath/power/autosuspend 2>/dev/null; chmod g+w /sys\$devpath/power/autosuspend 2>/dev/null'\""
            } >> "$RULE_FILE"
            FOUND=$((FOUND+1))
            break
        fi
        d=$(dirname "$d")
    done
done

if [ "$FOUND" -eq 0 ]; then
    echo "⚠️ USBオーディオデバイスが見つかりませんでした（DACを接続してから再実行してください）"
else
    echo "✅ ${FOUND}台のUSBオーディオデバイスにルールを作成しました: $RULE_FILE"
    udevadm control --reload-rules
    udevadm trigger --action=add --subsystem-match=usb
    echo "✅ udevルールを反映しました"
fi

# ---------------------------------------------------------------
# 2) audioグループへrtprio/memlock権限を付与
# ---------------------------------------------------------------
LIMITS_FILE="/etc/security/limits.d/99-qji-audio-rt.conf"
cat > "$LIMITS_FILE" << 'EOF'
# Qji: オーディオ再生の安定性向上のためのリアルタイム優先度設定
# (このファイルは install_usb_audio_optimize.sh により自動生成されました)
@audio   -  rtprio     95
@audio   -  memlock    unlimited
@audio   -  nice       -19
EOF
echo "✅ リアルタイム優先度の権限設定を作成しました: $LIMITS_FILE"

# ---------------------------------------------------------------
# 3) 実行ユーザーをaudioグループに追加
# ---------------------------------------------------------------
if id -nG "$TARGET_USER" | grep -qw audio; then
    echo "✅ ユーザー '$TARGET_USER' は既にaudioグループに所属しています"
else
    usermod -aG audio "$TARGET_USER"
    echo "✅ ユーザー '$TARGET_USER' をaudioグループに追加しました"
fi

echo "============================================================"
echo "🎉 セットアップ完了"
echo "============================================================"
echo "⚠️ 重要: グループ変更を反映するため、一度ログアウト→ログインし直してください"
echo "   （反映後、qji.py起動時に「✅ リアルタイム優先度: 利用可能」と表示されます）"
echo ""
echo "補足（任意・上級者向け）:"
echo "  高解像度音源(DSD/PCM768kHz等)で音切れが出る場合、カーネルパラメータ"
echo "  usbcore.usbfs_memory_mb を増やすと改善することがあります。"
echo "  例: GRUB_CMDLINE_LINUX_DEFAULT に usbcore.usbfs_memory_mb=1000 を追加し"
echo "  update-grub && 再起動（これは自動化していません。必要な場合のみ手動で）"
