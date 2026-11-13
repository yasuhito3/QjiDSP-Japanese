# -*- coding: utf-8 -*-
"""
wobble_v8.py — v8 実態感ホール用の「音場の揺らぎ・音量連動」

spatial_final.yml の wet 経路(ホールの響き)に置いた Volume フィルター
(wet_fader_L = Aux1 / wet_fader_R = Aux2)のフェーダーを、再生中に少しずつ動かす。

  ・揺らぎ     : 左右の響きの量を、ごくゆっくり(既定60秒周期)位相をずらして上下させる
  ・音量連動   : 再生音量(RMS)が大きいほど、揺らぎを深くし、響きを少し増やす
  ・[e] の設定 : qji_field_ctl.py の制御ファイル(余韻・揺らぎの深さ/周期・音量連動)に従う
  ・v7とv8は同じ仕組み。強さの違い(響きの足し方)は qji_field_ctl.py の PROFILES で決まる

フェーダーは 0 dB が素通し。このスクリプトが止まっても、起動前も、音は変わらない(安全側)。
※ CamillaDSP 側で、Aux フェーダーが効くのは YAML に Volume フィルターがある場合だけ。
"""
import math
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from camilladsp import CamillaClient

try:
    import qji_field_ctl
except Exception:            # qji_field_ctl.py が無くても、既定値で揺らぎだけは動く
    qji_field_ctl = None

HOST = "127.0.0.1"
PORT = int(os.environ.get("QJI_CDSP_PORT", "1234"))
FADER_L, FADER_R = 1, 2          # Aux1 = 左の響き, Aux2 = 右の響き

UPDATE_INTERVAL = 0.20           # 秒
BASE_PERIOD = 60.0               # 揺らぎの基本周期(秒)。[e]の周期倍率で変わる
DEPTH_MIN, DEPTH_MAX = 0.1, 1.0  # 揺らぎの深さ(±dB)。音量に応じてこの間を動く(×深さ倍率)

QUIET_DB, LOUD_DB = -35.0, -15.0 # この範囲の再生音量(RMS)を 0〜1 の強さに換算
SMOOTHING_ALPHA = 0.08

FADER_MIN, FADER_MAX = -12.0, 6.0   # 安全のための絶対的な範囲(YAML側の limit も +6 dB)
MIN_STEP_DB = 0.01                  # これ未満の変化は送らない

DEFAULT_CTL = {"wet_offset_db": 0.0, "depth_scale": 1.0, "period_scale": 1.0,
               "loud_link": False, "loud_boost_db": 1.5}


def _ctl():
    if qji_field_ctl is None:
        return DEFAULT_CTL
    try:
        return qji_field_ctl.read_ctl()
    except Exception:
        return DEFAULT_CTL


def _clamp(v):
    return max(FADER_MIN, min(FADER_MAX, v))


class _Quit(Exception):
    pass


def _on_term(*_a):
    raise _Quit()


def main():
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)
    cdsp = CamillaClient(HOST, PORT)
    print("v8 実態感ホール: 揺らぎ・音量連動 開始", flush=True)

    try:
        while True:
            try:
                cdsp.connect()
                print("接続成功", flush=True)
                phase = 0.0
                intensity = 0.3
                last_l = last_r = None
                t_prev = time.monotonic()

                while True:
                    now = time.monotonic()
                    dt, t_prev = now - t_prev, now
                    ctl = _ctl()

                    # 周期倍率が変わっても位相が飛ばないよう、位相を積算する
                    period = BASE_PERIOD * float(ctl.get("period_scale", 1.0))
                    phase += 2.0 * math.pi * dt / max(period, 1.0)

                    try:
                        rms = cdsp.levels.playback_rms()
                        avg_db = sum(rms) / len(rms) if rms else QUIET_DB
                    except Exception:
                        avg_db = QUIET_DB
                    raw = max(0.0, min(1.0, (avg_db - QUIET_DB) / (LOUD_DB - QUIET_DB)))
                    intensity += SMOOTHING_ALPHA * (raw - intensity)

                    depth = (DEPTH_MIN + intensity * (DEPTH_MAX - DEPTH_MIN)) * float(ctl.get("depth_scale", 1.0))
                    offset = float(ctl.get("wet_offset_db", 0.0))
                    if ctl.get("loud_link"):
                        offset += float(ctl.get("loud_boost_db", 1.5)) * intensity

                    wl = _clamp(offset + depth * math.sin(phase))
                    wr = _clamp(offset + depth * math.sin(phase + math.pi / 2))
                    if last_l is None or abs(wl - last_l) >= MIN_STEP_DB:
                        cdsp.volume.set_volume(FADER_L, wl)
                        last_l = wl
                    if last_r is None or abs(wr - last_r) >= MIN_STEP_DB:
                        cdsp.volume.set_volume(FADER_R, wr)
                        last_r = wr

                    time.sleep(UPDATE_INTERVAL)

            except _Quit:
                raise
            except Exception as e:
                print(f"接続エラー: {e}", flush=True)
                time.sleep(3)
    except _Quit:
        # 終了時はフェーダーを 0 dB(素通し)に戻す。失敗しても構わない
        try:
            cdsp.volume.set_volume(FADER_L, 0.0)
            cdsp.volume.set_volume(FADER_R, 0.0)
        except Exception:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
