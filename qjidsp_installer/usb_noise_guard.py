# -*- coding: utf-8 -*-
"""
usb_noise_guard.py - USB出力系デジタルノイズ対策モジュール

【目的】
USB接続DAC/オーディオインターフェースで発生する「デジタルノイズ」
（プチプチ音、ジッターによる音質劣化、まれなドロップアウト）の
主な原因のうち、ソフトウェア側から緩和できるものに対処する。

対応する原因（互いに独立、個別にON/OFF可能）:
  1. USBオートサスペンド（アイドル時にUSBデバイスの電源を落とす省電力機能）
     → 復帰時のレイテンシでプチノイズ/瞬断が起きる。無効化すると
       無音部のノイズフロアが下がる方向に効く傾向がある。
  2. 再生プロセス(camilladsp/wobble等)のスケジューリング優先度が低い
     → 他プロセスにCPUを奪われてバッファアンダーランが起き、
       サンプルタイミングの微小な揺らぎ(ジッター)が生じる。
       付与すると音像がより正確になる一方、ジッターが与えていた
       にじみ由来の「厚み」「押し出し感」が減る場合がある。

対応できない（ハードウェア/物理層の）原因の参考:
  - USBケーブル/ハブの品質、電源ノイズ、グラウンドループ
  - USB3.0コントローラーの電磁干渉(EMI)がUSB2.0オーディオに漏れる
  → これらはソフトでは直せないため、診断メッセージで注意喚起のみ行う。

【使い方】
  from usb_noise_guard import optimize_usb_audio_output
  optimize_usb_audio_output(card_num, extra_pids=[cdsp_proc.pid])

  その場A/B比較用（原因の切り分け）:
    toggle_autosuspend_guard()  # オートサスペンド対策だけON/OFF
    toggle_rtprio_guard()       # リアルタイム優先度だけON/OFF
    toggle_usb_audio_output()   # 両方まとめてON/OFF

事前準備（1回だけ、root権限が必要）:
  install_usb_audio_optimize.sh を実行しておくこと。
  （USBオートサスペンド無効化のudevルールと、rtprio権限の付与を行う。
   このシェルスクリプト自体はQji専用ではなく、Linux上のUSBオーディオ
   全般に効くOSレベルの設定なので、他のプレーヤーにも効果がある）
  未実行でも本モジュールは例外を出さず、警告を表示するだけで再生は継続する。
"""

import os
import re
import subprocess


def card_num_from_alsa_device(device_str):
    """'hw:2,0' や 'plughw:2,0' のようなALSAデバイス文字列からカード番号を取り出す。
    BlueALSA等（"hw:"形式でない）の場合はNoneを返す。"""
    if not device_str:
        return None
    m = re.search(r'hw:(\d+)', device_str)
    return m.group(1) if m else None


def _find_usb_device_syspath(card_num):
    """ALSAカード番号から、対応するUSBデバイスのsysfsパスを特定する。
    /sys/class/sound/cardN/device はUSBの「インターフェース」ディレクトリを
    指していることが多いため、idVendorファイルが見つかるまで親を辿る。
    USB接続でない（オンボード/HDMI等の）カードの場合はNoneを返す。
    """
    try:
        link_path = f'/sys/class/sound/card{card_num}/device'
        real_path = os.path.realpath(link_path)
        cur = real_path
        for _ in range(6):  # インターフェース→デバイス本体まで数階層のはずなので上限を設ける
            if os.path.exists(os.path.join(cur, 'idVendor')):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    except Exception:
        pass
    return None


def _read_sysfs(path):
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except Exception:
        return None


def _write_sysfs(path, value):
    try:
        with open(path, 'w') as f:
            f.write(value)
        return True
    except PermissionError:
        return False
    except Exception:
        return False


def check_autosuspend(dev_syspath):
    """USBデバイスのオートサスペンド設定状態を確認する。
    戻り値: (is_disabled: bool, control_value: str or None)
    """
    control = _read_sysfs(os.path.join(dev_syspath, 'power', 'control'))
    return (control == 'on'), control


def fix_autosuspend(dev_syspath):
    """オートサスペンドを無効化する（書き込み権限が無い場合は失敗しFalseを返す）。
    udevルールが既に適用済みなら通常は既に'on'になっており、ここでの
    書き込みは不要（無害な二重処理）になる。
    """
    ok_control = _write_sysfs(os.path.join(dev_syspath, 'power', 'control'), 'on')
    # autosuspendの遅延値。存在しないカーネルもあるため失敗は無視してよい。
    _write_sysfs(os.path.join(dev_syspath, 'power', 'autosuspend'), '-1')
    return ok_control


def get_rtprio_limit():
    """現在のプロセスに許可されているリアルタイム優先度の上限を返す。
    0の場合、audioグループへのrtprio権限(limits.d)が未設定の可能性が高い。
    """
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_RTPRIO)
        return soft, hard
    except Exception:
        return 0, 0


def apply_realtime_priority(pid, priority=40):
    """指定PIDにFIFOリアルタイムスケジューリング優先度を付与する。
    権限不足の場合は静かに失敗し、通常優先度のまま再生を継続させる
    （音は出るが、CPU競合時にジッター/プチノイズのリスクが残る状態）。
    """
    if not pid:
        return False
    try:
        result = subprocess.run(
            ['chrt', '-f', '-p', str(priority), str(pid)],
            capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0
    except Exception:
        return False


def clear_realtime_priority(pid):
    """指定PIDのスケジューリングを通常優先度(SCHED_OTHER)に戻す。"""
    if not pid:
        return False
    try:
        result = subprocess.run(
            ['chrt', '-o', '-p', '0', str(pid)],
            capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0
    except Exception:
        return False


# ★ 最後に適用した内容を記憶しておくための状態。
#   toggle系の関数がこれを見てON/OFFを切り替える（呼び出し側はカード番号や
#   PIDを毎回渡す必要がない）。オートサスペンド対策とRT優先度対策は
#   互いに独立してON/OFFできるよう、別々のenabledフラグを持つ。
_LAST_STATE = {
    'card_num': None, 'dev_syspath': None, 'extra_pids': [], 'priority': 40,
    'autosuspend_enabled': False, 'rtprio_enabled': False,
}


def optimize_usb_audio_output(card_num, extra_pids=None, priority=40, verbose=True):
    """USB出力経路のデジタルノイズ対策を一括で適用し、結果を診断表示する。

    引数:
      card_num  : DSP出力先のALSAカード番号（文字列 "2" や 数値 2）
      extra_pids: リアルタイム優先度を付与したいプロセスIDのリスト
                  （camilladsp, aplay, wobbleスクリプト等）
      priority  : chrt -f に渡す優先度 (1-99)。40は音声再生用途として一般的な値
      verbose   : Trueなら診断結果を標準出力に表示する

    この関数自体は例外を投げない（再生を止めないことを最優先する）。
    """
    global _LAST_STATE
    report = {'usb_device_found': False, 'autosuspend_disabled': False,
              'rtprio_available': False, 'rtprio_applied': []}
    dev_syspath = None
    try:
        card_num_str = str(card_num)
        dev_syspath = _find_usb_device_syspath(card_num_str)

        if verbose:
            print('\n' + '=' * 60)
            print('🔌 USB出力デジタルノイズ対策チェック')
            print('=' * 60)

        if dev_syspath:
            report['usb_device_found'] = True
            is_disabled, control_value = check_autosuspend(dev_syspath)
            if not is_disabled:
                fix_autosuspend(dev_syspath)
                is_disabled, control_value = check_autosuspend(dev_syspath)
            report['autosuspend_disabled'] = is_disabled
            report['runtime_toggle_writable'] = os.access(
                os.path.join(dev_syspath, 'power', 'control'), os.W_OK)
            if verbose:
                if is_disabled:
                    print('✅ USBオートサスペンド: 無効化済み（電源プチ切れによるノイズを防止）')
                else:
                    print(f'⚠️ USBオートサスペンド: 有効のまま (power/control="{control_value}")')
                    print('   → install_usb_audio_optimize.sh を一度sudoで実行してください')
                if report['runtime_toggle_writable']:
                    print('✅ 実行時のON/OFF切替(k): 可能')
                else:
                    print('⚠️ 実行時のON/OFF切替(k): 不可（書き込み権限が未委譲）')
                    print('   → 最新版の install_usb_audio_optimize.sh をsudoで再実行してください')
        else:
            if verbose:
                print('ℹ️ このカードはUSBデバイスとして検出されませんでした（オンボード等の可能性）')

        soft_rt, _hard_rt = get_rtprio_limit()
        report['rtprio_available'] = soft_rt > 0
        if verbose:
            if soft_rt > 0:
                print(f'✅ リアルタイム優先度: 利用可能 (上限 {soft_rt})')
            else:
                print('⚠️ リアルタイム優先度: 未許可（バッファアンダーラン耐性が下がります）')
                print('   → install_usb_audio_optimize.sh を一度sudoで実行し、再ログインしてください')

        if extra_pids:
            for pid in extra_pids:
                if apply_realtime_priority(pid, priority=priority):
                    report['rtprio_applied'].append(pid)
            if verbose:
                if report['rtprio_applied']:
                    print(f'✅ リアルタイム優先度を付与: PID {report["rtprio_applied"]} (優先度{priority})')
                elif soft_rt > 0:
                    print('⚠️ リアルタイム優先度の付与に失敗しました（chrt未インストール等）')

        if verbose:
            print('=' * 60 + '\n')

        # ★ toggle系の関数でのその場A/B比較用に、適用内容を記憶しておく
        _LAST_STATE = {
            'card_num': card_num_str,
            'dev_syspath': dev_syspath,
            'extra_pids': list(extra_pids) if extra_pids else [],
            'priority': priority,
            'autosuspend_enabled': report['autosuspend_disabled'],
            'rtprio_enabled': bool(report['rtprio_applied']),
        }
    except Exception as _e:
        if verbose:
            print(f'⚠️ USBノイズ対策チェック中にエラー（再生は継続します）: {_e}')
    return report


def list_usb_audio_cards():
    """接続中のALSAカードのうち、USBオーディオデバイスのものを一覧化する。
    各要素: {'card_num': str, 'name': str, 'vendor': str, 'product': str,
             'dev_syspath': str, 'autosuspend_disabled': bool}
    """
    results = []
    try:
        base = '/sys/class/sound'
        if not os.path.isdir(base):
            return results
        for entry in sorted(os.listdir(base)):
            m = re.match(r'^card(\d+)$', entry)
            if not m:
                continue
            card_num = m.group(1)
            dev_syspath = _find_usb_device_syspath(card_num)
            if not dev_syspath:
                continue
            name = _read_sysfs(os.path.join(dev_syspath, 'product')) or 'Unknown'
            vendor = _read_sysfs(os.path.join(dev_syspath, 'idVendor')) or '????'
            product = _read_sysfs(os.path.join(dev_syspath, 'idProduct')) or '????'
            is_disabled, _control = check_autosuspend(dev_syspath)
            results.append({
                'card_num': card_num, 'name': name, 'vendor': vendor,
                'product': product, 'dev_syspath': dev_syspath,
                'autosuspend_disabled': is_disabled,
            })
    except Exception:
        pass
    return results


def card_num_from_arg(arg):
    """CLI引数として渡された 'hw:2,0' / 'plughw:2,0' / '2' のいずれの形式も
    カード番号の文字列に正規化する。"""
    if arg is None:
        return None
    arg = str(arg).strip()
    if arg.isdigit():
        return arg
    return card_num_from_alsa_device(arg)


def _pid_is_realtime(pid):
    """指定PIDが現在リアルタイムスケジューリング(FIFO/RR)かどうかを実際に調べる。
    プロセスが既に存在しない場合はNoneを返す。"""
    try:
        policy = os.sched_getscheduler(pid)
        return policy in (os.SCHED_FIFO, os.SCHED_RR)
    except (ProcessLookupError, OSError, AttributeError):
        return None


def get_guard_status():
    """現在の対策状態を、内部フラグではなく「実際のシステムの状態」から取得する。

    戻り値: {'autosuspend': True/False/None, 'rtprio': True/False/None}
      autosuspend: power/control が "on"(=オートサスペンド無効化=対策ON) ならTrue。
                   USBデバイス未検出ならNone。
      rtprio     : 登録済みの生存プロセスが全てリアルタイム優先度ならTrue、
                   1つでも通常優先度ならFalse。生存プロセスが無ければNone。
    """
    st = _LAST_STATE
    result = {'autosuspend': None, 'rtprio': None}
    dev_syspath = st.get('dev_syspath')
    if dev_syspath:
        is_disabled, control = check_autosuspend(dev_syspath)
        result['autosuspend'] = is_disabled if control is not None else None
    flags = [_pid_is_realtime(pid) for pid in (st.get('extra_pids') or [])]
    alive = [f for f in flags if f is not None]
    if alive:
        result['rtprio'] = all(alive)
    return result


def _sync_state():
    """内部フラグを実際の状態に合わせる（フラグのずれを防ぐ）。"""
    status = get_guard_status()
    if status['autosuspend'] is not None:
        _LAST_STATE['autosuspend_enabled'] = status['autosuspend']
    if status['rtprio'] is not None:
        _LAST_STATE['rtprio_enabled'] = status['rtprio']
    return status


def format_guard_status():
    """現在の状態を1行の文字列で返す（Qjiの画面表示などに使う）。
    例: 🔌 現在: [k]オートサスペンド対策=ON 🟢 | [j]RT優先度=OFF ⚪"""
    status = _sync_state()

    def _mark(v):
        if v is True:
            return 'ON 🟢'
        if v is False:
            return 'OFF ⚪'
        return '不明 ➖'

    return (f"🔌 現在: [k]オートサスペンド対策={_mark(status['autosuspend'])} | "
            f"[j]RT優先度={_mark(status['rtprio'])}")


_PERM_HINT = ('   → 書き込み権限が未委譲です。最新版の install_usb_audio_optimize.sh を\n'
              '     sudoで再実行してください（再ログインは不要。反映されない場合はDACを抜き挿し）')


def toggle_autosuspend_guard(verbose=True):
    """USBオートサスペンド対策だけをON/OFF切り替える（RT優先度側には触れない）。

    内部フラグではなく、sysfsの実際の値(power/control)を見て切り替える。
    書き込みに失敗した場合は状態を変えず、Noneを返す（呼び出し側が誤って
    「切り替わった」と表示しないようにするため）。

    戻り値: 切り替え後の状態 (True=ON / False=OFF)。
            対象デバイス未検出、または書き込み失敗時はNone。
    """
    global _LAST_STATE
    _sync_state()
    st = _LAST_STATE
    dev_syspath = st.get('dev_syspath')
    if not dev_syspath:
        if verbose:
            print('⚠️ USBデバイスが未検出のため、オートサスペンド対策を切り替えられません')
        return None
    control_path = os.path.join(dev_syspath, 'power', 'control')
    is_disabled, _control = check_autosuspend(dev_syspath)
    if is_disabled:
        ok = _write_sysfs(control_path, 'auto')
        if ok:
            st['autosuspend_enabled'] = False
            if verbose:
                print('🔙 USBオートサスペンド対策: OFF（power/control="auto" に戻しました）')
            return False
        if verbose:
            print('⚠️ OFFにできませんでした（書き込み権限なし）。対策はONのままです')
            print(_PERM_HINT)
        st['autosuspend_enabled'] = True
        return None
    else:
        ok = fix_autosuspend(dev_syspath)
        if ok:
            st['autosuspend_enabled'] = True
            if verbose:
                print('✅ USBオートサスペンド対策: ON（電源プチ切れによるノイズを防止）')
            return True
        if verbose:
            print('⚠️ ONにできませんでした（書き込み権限なし）。対策はOFFのままです')
            print(_PERM_HINT)
        st['autosuspend_enabled'] = False
        return None


def toggle_rtprio_guard(verbose=True):
    """リアルタイム優先度対策だけをON/OFF切り替える（オートサスペンド側には触れない）。

    内部フラグではなく、各プロセスの実際のスケジューリング状態を見て切り替える。
    戻り値: 切り替え後の状態 (True=ON / False=OFF)。
            対象プロセスが無い、または切り替えに失敗した場合はNone。
    """
    global _LAST_STATE
    status = _sync_state()
    st = _LAST_STATE
    pids = [pid for pid in (st.get('extra_pids') or []) if _pid_is_realtime(pid) is not None]
    if not pids:
        if verbose:
            print('⚠️ 対象プロセスが見つからないため、リアルタイム優先度を切り替えられません')
        return None
    if status['rtprio']:
        for pid in pids:
            clear_realtime_priority(pid)
        after = _sync_state()['rtprio']
        if after is False:
            if verbose:
                print(f'🔙 リアルタイム優先度対策: OFF（通常優先度に戻しました PID {pids}）')
            return False
        if verbose:
            print('⚠️ OFFにできませんでした。対策はONのままです')
        return None
    else:
        for pid in pids:
            apply_realtime_priority(pid, priority=st.get('priority', 40))
        after = _sync_state()['rtprio']
        if after is True:
            if verbose:
                print(f'✅ リアルタイム優先度対策: ON（PID {pids} に優先度{st.get("priority", 40)}を付与）')
            return True
        if verbose:
            print('⚠️ ONにできませんでした（chrt未インストール、または権限不足）。対策はOFFのままです')
        return None


def toggle_usb_audio_output(verbose=True):
    """USB出力デジタルノイズ対策を2つまとめてON/OFF切り替える
    （プラシーボ排除のための全体A/B比較用。個別の切り分けは
     toggle_autosuspend_guard()/toggle_rtprio_guard()を使う）。
    直前にoptimize_usb_audio_output()が一度も呼ばれていない場合は何もしない。
    戻り値: 切り替え後の状態 (True=ON / False=OFF)。
            対象が無い、または切り替えに失敗した場合はNone。
    """
    global _LAST_STATE
    if _LAST_STATE.get('card_num') is None:
        if verbose:
            print('⚠️ まだUSBノイズ対策が一度も適用されていません（DAC未選択の可能性）')
        return None
    _sync_state()
    any_on = bool(_LAST_STATE.get('autosuspend_enabled') or _LAST_STATE.get('rtprio_enabled'))
    if verbose:
        print('\n' + '=' * 60)
        print(f'🔌 USB出力デジタルノイズ対策 — {"OFF" if any_on else "ON"}（一括切り替え）')
        print('=' * 60)
    if any_on:
        if _LAST_STATE.get('autosuspend_enabled'):
            toggle_autosuspend_guard(verbose=verbose)
        if _LAST_STATE.get('rtprio_enabled'):
            toggle_rtprio_guard(verbose=verbose)
        still_on = bool(_LAST_STATE.get('autosuspend_enabled') or _LAST_STATE.get('rtprio_enabled'))
        result = None if still_on else False
    else:
        toggle_autosuspend_guard(verbose=verbose)
        toggle_rtprio_guard(verbose=verbose)
        now_on = bool(_LAST_STATE.get('autosuspend_enabled') or _LAST_STATE.get('rtprio_enabled'))
        result = True if now_on else None
    if verbose:
        print('=' * 60 + '\n')
    return result
