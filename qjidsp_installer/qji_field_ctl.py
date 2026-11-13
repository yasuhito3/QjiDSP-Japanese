# -*- coding: utf-8 -*-
"""
qji_field_ctl.py — 音場プリセット制御(qji.py ⇄ wobble 共有モジュール)

  qji.py   : [e] → 次のキー、で音場プリセットを選ぶ(書き込み側)
  wobble_vN: 0.2秒ごとに制御ファイルを読み、揺らぎのパラメーターをその場で更新(読み込み側)

置き場所: ~/camilladsp_test/ (wobbleスクリプトと同じ場所)。
※WOBBLE_LINK=False にすると、wobbleは制御ファイルを読まず、[e]は楽器EQ・記憶のみを扱う(v7/v8は True)。
qji.py側は sys.path に
          このフォルダーを追加して import する。
制御ファイル: /run/user/UID/qji_field_ctl.json  (環境変数 QJI_FIELD_CTL で変更可)
曲/アルバムごとの記憶: ~/qji_field_prefs.json  (環境変数 QJI_FIELD_PREFS で変更可)
  曲の開始時に on_track_start() が呼ばれ、 曲の記憶 > アルバムの記憶 > 曲名などからの自動ルール > 既定
  の順で設定を決めて、フィルターが組み立てられる前にSIのEQへ反映する(再読込[r]は不要)。
"""
import json
import os
import select
import sys
import time

def _default_ctl_path():
    """他のユーザーが書き換えられない場所(/run/user/UID)を優先。環境変数に依らず qji とwobbleで同じ場所になる。"""
    d = f"/run/user/{os.getuid()}"
    if os.path.isdir(d) and os.access(d, os.W_OK):
        return os.path.join(d, 'qji_field_ctl.json')
    return f"/tmp/qji_field_ctl_{os.getuid()}.json"


CTL_PATH = os.environ.get('QJI_FIELD_CTL', _default_ctl_path())
PREFS_PATH = os.environ.get('QJI_FIELD_PREFS', os.path.expanduser('~/qji_field_prefs.json'))

# 既定状態: 揺らぎ・音量連動は ON。OFFにしたい曲は [e]→[f]/[l] で切って [e]→[m] で記憶する。
DEFAULT_FLUTTER = True
DEFAULT_LOUD = True
RULES_ENABLED = True    # 曲名などからの自動選択(記憶が無い曲だけに働く)

# ★ wobble側(余韻・揺らぎ・音量連動)が、この制御ファイルを読む構成かどうか。
#   False: [e] は「楽器EQ・SIのEQ・曲/アルバムの記憶」だけを扱う(静的版wobble用)。
#   (v7/v8は制御ファイルを読むwobbleなので、現在の既定は True)
#          [w][n][f][l] と、余韻/揺らぎ/音量連動の表示は出さない。
#   True : read_ctl() を読む反応型wobbleを組み合わせる構成(v7/v8はこちら)。
WOBBLE_LINK = True

# ── wobble側が受け取る既定値(=リセット状態) ─────────────────────────
DEFAULTS = {
    'seq': 0,
    'label': 'ノーマル',
    'wet_offset_db': 0.0,    # wet_gain への加算(dB)。+で音場が広く、−で近く
    'depth_scale': 1.0,      # 揺らぎ深さの倍率
    'period_scale': 1.0,     # 揺らぎ周期の倍率(<1で速く)
    'loud_link': False,      # 音量連動(大きいほど音場を広げる)
    'loud_boost_db': 1.5,    # 音量連動の最大加算量(dB)
}

# ── シーン(同時に1つだけ有効): 空間軸 + (任意で)ffmpeg側SI-EQデルタ ──────
#  wet_offset_db は「どれだけ広く/近くするか」。まず控えめな値にしてあるので耳で調整のこと。
# 同じシーンキーを続けて押すと 弱→中→強→解除。倍率は wet量とEQデルタの両方にかかる。
LEVELS = (1.0, 1.5, 2.0)          # w / n / o(広く・近く・声を前に)
BEAUTY_LEVELS = (0.8, 1.1, 1.5)   # 「美しく」系(聴き疲れしにくいよう控えめ)
LEVEL_NAMES = ('弱', '中', '強')
BEAUTY_KEYS = ['v', 'u', 'b', 'c', 't', 'h', 'd', 'p', 'q', 'j', 's',
               'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'a8']   # BEAUTY_LEVELS を使うシーン

SCENES = {
    'w': {'label': '音場を広く',         'wet_offset_db': +2.0, 'eq': None},
    'n': {'label': '音場を近く',         'wet_offset_db': -2.0, 'eq': None},
    # ── 「前に出す」型: 声は中域主体なので刺さりにくい(ヴァイオリンの「前に」は廃止) ──
    'o': {'label': 'ヴォーカルを前に',   'wet_offset_db': -1.5,
          'eq': {'mid': +3.0, 'upper_mid': +2.5, 'presence': +1.0}},
    # ── 「美しく響かせる」型: 余韻(wet)を少し足し、2〜5kHzは持ち上げずに、
    #    むしろ少し引いて硬さを抑え、倍音の艶(air系)と胴の豊かさ(mid系)を整える ──
    #    SIのEQは「中心周波数±幅(Hz)」の狭めのベル型なので、隣り合う帯域に配ってある。
    'v': {'label': 'ヴァイオリンを美しく', 'wet_offset_db': +1.5,
          'eq': {'mid': +0.5, 'presence': -0.5, 'air_low': +2.0, 'air': +2.0}},
    # 「しっとり」型: 2kHz付近(存在感)を引いて中域を厚くし、角を丸めたうえで6〜10kHzの艶と低域の土台を少し足す。
    #  ([v]との聴き比べ用。強にすると、SIのEQが積み上がって偶然できていた音に近い: 中域+3.6/存在感-3.6/空気感+3.0)
    'u': {'label': 'ヴァイオリンをしっとり', 'wet_offset_db': +1.5,
          'eq': {'sub_bass': +0.3, 'bass': +0.6, 'low_mid': +0.3, 'mid': +2.4, 'presence': -2.4,
                 'air_low': +2.0, 'air': +2.0}},
    'b': {'label': 'オーボエを美しく',     'wet_offset_db': +1.5,
          'eq': {'low_mid': +1.0, 'mid': +1.5, 'upper_mid': +0.5,
                 'presence': -0.5, 'air_low': +1.5}},
    'c': {'label': 'クラリネットを美しく', 'wet_offset_db': +1.5,
          'eq': {'low_mid': +1.5, 'mid': +1.5, 'presence': -0.5, 'air': +1.5}},
    'p': {'label': 'ピアノを美しく',       'wet_offset_db': +2.0,
          'eq': {'bass': +1.0, 'mid': +0.5, 'high_mid': +0.5,
                 'air_low': +1.5, 'air': +2.0}},
    # ── クラシック追加分 ──
    'd': {'label': 'チェロ・低弦を美しく', 'wet_offset_db': +1.5,
          'eq': {'bass': +1.0, 'low_mid': +0.5, 'mid': +1.0, 'presence': -0.5, 'air_low': +1.0}},
    't': {'label': 'フルートを美しく',     'wet_offset_db': +1.5,
          'eq': {'low_mid': +0.5, 'upper_mid': +0.5, 'presence': -0.5,
                 'air': +2.0, 'air_high': +1.0}},
    'h': {'label': 'ホルン・金管を柔らかく輝かせる', 'wet_offset_db': +1.5,
          'eq': {'low_mid': +1.0, 'mid': +1.5, 'high_mid': -1.0, 'air_low': +1.0}},
    # ── 声楽: [a] を押すと第2メニュー [1]〜[8]。声の高さごとに「胴(基音の厚み)」の帯域が違う。
    #    歌声は 4kHz以上の歯擦音(サ行)が出やすいので、そこは持ち上げず、2kHz付近は少し引く ──
    'a1': {'label': 'ソプラノ(声楽)を美しく', 'wet_offset_db': +1.5,
           'eq': {'mid': +1.0, 'upper_mid': +1.0, 'presence': -0.5, 'air_low': +1.5, 'air': +1.5}},
    'a2': {'label': 'アルト・メゾ(声楽)を美しく', 'wet_offset_db': +1.5,
           'eq': {'low_mid': +1.0, 'mid': +1.5, 'presence': -0.5, 'air_low': +1.0, 'air': +1.0}},
    'a3': {'label': 'テノール(声楽)を美しく', 'wet_offset_db': +1.5,
           'eq': {'low_mid': +0.5, 'mid': +1.0, 'upper_mid': +1.0, 'presence': -0.5,
                  'air_low': +1.0, 'air': +1.0}},
    'a4': {'label': 'バリトン(声楽)を美しく', 'wet_offset_db': +1.5,
           'eq': {'bass': +0.5, 'low_mid': +1.0, 'mid': +1.0, 'upper_mid': +0.5,
                  'presence': -0.5, 'air_low': +1.0}},
    'a5': {'label': 'バス(声楽)を美しく', 'wet_offset_db': +1.5,
           'eq': {'bass': +1.0, 'low_mid': +0.5, 'mid': +1.0, 'upper_mid': +0.5, 'air_low': +1.0}},
    'a6': {'label': '合唱の響きを美しく', 'wet_offset_db': +2.0,
           'eq': {'low_mid': +0.5, 'mid': +0.5, 'upper_mid': +0.5, 'presence': -0.5,
                  'air_low': +1.0, 'air': +1.5}},
    # ── ジャズ・ポップスの歌: 響き(wet)は控えめにして、声の近さと温かみを残す ──
    'a7': {'label': '女声ヴォーカル(ジャズ・ポップス)を美しく', 'wet_offset_db': +0.5,
           'eq': {'low_mid': +0.5, 'mid': +1.0, 'upper_mid': +0.5, 'presence': -0.5,
                  'air_low': +1.0, 'air': +1.0}},
    'a8': {'label': '男声ヴォーカル(ジャズ・ポップス)を美しく', 'wet_offset_db': +0.5,
           'eq': {'bass': +0.5, 'low_mid': +0.5, 'mid': +1.0, 'upper_mid': +0.5,
                  'presence': -0.5, 'air_low': +1.0}},
    'q': {'label': '弦楽四重奏の一体感',   'wet_offset_db': +1.0,
          'eq': {'low_mid': +0.5, 'mid': +1.0, 'presence': -0.5, 'air_low': +1.5, 'air': +1.0}},
    # ── ジャズ: 響き(wet)は控えめ。ベースは胴鳴りを整えて輪郭を少し、サックスは音の厚みと息づかい ──
    'j': {'label': 'ジャズ・ベース(ピチカート)を美しく', 'wet_offset_db': +0.5,
          'eq': {'sub_bass': +0.5, 'bass': +1.5, 'low_mid': -1.0, 'upper_mid': +1.0, 'presence': +0.5}},
    's': {'label': 'サックスを響かせる',   'wet_offset_db': +1.0,
          'eq': {'low_mid': +1.0, 'mid': +1.0, 'presence': -0.5, 'air_low': +1.0}},
}
for _k in BEAUTY_KEYS:
    SCENES[_k]['levels'] = BEAUTY_LEVELS

# ★ 音場(v7 / v8)ごとの「響きの足し方」。EQ(楽器・声楽)はどちらも同じで、響き(wet)・揺らぎ・音量連動の強さだけが違う。
#   inst_wet_scale: 楽器・声楽の「美しく」系プリセットが足す響きの倍率([w]広く/[n]近く/[o]声を前に は対象外)
#   flutter_depth : [f]揺らぎON時の深さ倍率 / loud_boost_db: [l]音量連動の最大加算量(dB)
PROFILES = {
    '7': {'name': '倍音ホールモード', 'inst_wet_scale': 0.0, 'flutter_depth': 2.0,
          'flutter_period': 0.5, 'loud_boost_db': 1.5},   # 籠もらず聴きやすい(EQ中心・響きは控えめ)
    '8': {'name': '実態感ホール',     'inst_wet_scale': 1.0, 'flutter_depth': 4.0,
          'flutter_period': 0.5, 'loud_boost_db': 3.0},   # 響きが濃く、実体感が強い(やや籠もりやすい)
}
_profile_key = '7'


def _prof():
    return PROFILES[_profile_key]


def set_venue(venue):
    """DSP音場が変わったときに呼ぶ(v7/v8以外は、控えめなv7の設定を使う)。変わったら制御ファイルを更新する。"""
    global _profile_key
    key = str(venue) if str(venue) in PROFILES else '7'
    if key != _profile_key:
        _profile_key = key
        try:
            publish()
        except Exception:
            pass

KEY_WAIT_SEC = 20.0     # [e] を押してから次のキーを待つ秒数(超えるとキャンセル)。第2メニュー([a]声楽・[m]記憶)も同じ
EQ_BAND_CAP = 6.0      # 1バンドあたりの上限(dB)。これ以上は刺さりやすいので頭打ち

VOICE_GUIDE = ("🎤 声楽: [1]ソプラノ [2]アルト・メゾ [3]テノール [4]バリトン [5]バス [6]合唱\n"
               "   歌(ジャズ・ポップス): [7]女声 [8]男声")


GUIDE_FULL = ("🎛 音場: [w]広く [n]近く [o]声を前に [f]揺らぎ [l]音量連動 [r]既定に戻す\n"
         "   [z]SIのEQを使わない/使う [m]記憶(曲/アルバム) [?]現在の設定\n"
         "   クラシック: [v]ヴァイオリン [u]ヴァイオリン(しっとり) [b]オーボエ [c]クラリネット [t]フルート [h]ホルン・金管\n"
         "              [d]チェロ・低弦 [p]ピアノ [q]弦楽四重奏 [a]声楽(→1〜8)\n"
         "   ジャズ: [j]ベース(ピチカート) [s]サックス     (同じキー連打: 弱→中→強→解除)")
GUIDE_EQ = GUIDE_FULL.replace("[w]広く [n]近く [o]声を前に [f]揺らぎ [l]音量連動 [r]既定に戻す",
                              "[o]声を前に [r]既定に戻す")
GUIDE = GUIDE_FULL if WOBBLE_LINK else GUIDE_EQ

# ── qji.py 側の状態(プロセス内) ─────────────────────────────────────
_state = {'scene': None, 'level': 1, 'flutter': DEFAULT_FLUTTER, 'loud': DEFAULT_LOUD,
          'source': 'default', 'reason': '', 'si_off': False}
_cur = {'path': None, 'title': '', 'album_key': None, 'album_name': '', 'saved': False}   # 再生中の曲
# xメニュー([x])で確定したSIのEQ。曲が替わるまで有効(その曲の再読込のたびにSIへ入れ直す)。
# xメニューは閉じると自動で曲を頭から再読込するが、そのとき保存済みプロファイルやSIの記憶が読み直されて、
# [EQ全解除]や調整が打ち消されていた。これを防ぐための「この曲のあいだの確定値」。
_si_override = {'path': None, 'eq': None}
SOURCE_LABELS = {'default': '既定', 'rule': '自動(曲名などから)', 'track': 'この曲の記憶',
                 'album': 'このアルバムの記憶', 'preset': '音場別の既定', 'manual': '手動(未保存)'}


def _write_atomic(data):
    tmp = CTL_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, CTL_PATH)


def _levels_for(key):
    sc = SCENES.get(key)
    return sc.get('levels', LEVELS) if sc else LEVELS


def _derive():
    d = dict(DEFAULTS)
    d['seq'] = int(time.time() * 1000) % 2_000_000_000
    labels = []
    sc = SCENES.get(_state['scene'])
    if sc:
        mult = _levels_for(_state['scene'])[_state['level'] - 1]
        if WOBBLE_LINK:
            _wo = sc['wet_offset_db'] * mult
            if _state['scene'] not in ('w', 'n', 'o') and _wo > 0:
                _wo *= _prof()['inst_wet_scale']
            d['wet_offset_db'] = round(_wo, 2)
        labels.append(f"{sc['label']}({LEVEL_NAMES[_state['level'] - 1]})")
    if WOBBLE_LINK and _state['flutter']:
        d.update(depth_scale=_prof()['flutter_depth'], period_scale=_prof()['flutter_period'])
        labels.append('揺らぎ')
    if WOBBLE_LINK and _state['loud']:
        d['loud_link'] = True
        d['loud_boost_db'] = _prof()['loud_boost_db']
        labels.append('音量連動')
    if _state.get('si_off'):
        labels.append('SIのEQなし')
    d['label'] = ' + '.join(labels) if labels else 'ノーマル'
    return d


def publish():
    d = _derive()
    _write_atomic(d)
    return d


def _reset_state(source='default'):
    _state.update({'scene': None, 'level': 1, 'flutter': DEFAULT_FLUTTER,
                   'loud': DEFAULT_LOUD, 'source': source, 'reason': '', 'si_off': False})


def init():
    """qji起動時に呼ぶ: 前回の状態を持ち越さず、既定状態(揺らぎ・音量連動ON)にする"""
    _reset_state()
    _cur.update(path=None, title='', album_key=None, album_name='', saved=False)
    _si_override.update(path=None, eq=None)
    try:
        publish()
    except Exception:
        pass


# ── wobble側: 読み込み ───────────────────────────────────────────────
_cache = {'mtime': None, 'data': dict(DEFAULTS)}


def _num(v, lo, hi, dflt):
    try:
        x = float(v)
    except Exception:
        return dflt
    if x != x:          # NaN
        return dflt
    return max(lo, min(hi, x))


def _sanitize(d):
    d['wet_offset_db'] = _num(d.get('wet_offset_db'), -6.0, 6.0, 0.0)
    d['depth_scale'] = _num(d.get('depth_scale'), 0.0, 8.0, 1.0)
    d['period_scale'] = _num(d.get('period_scale'), 0.25, 4.0, 1.0)
    d['loud_boost_db'] = _num(d.get('loud_boost_db'), 0.0, 6.0, 1.5)
    d['loud_link'] = bool(d.get('loud_link'))
    d['label'] = str(d.get('label', ''))[:80]
    return d


def read_ctl():
    """制御ファイルを読む。無い/壊れている場合は直前の値(最初は既定値)を返す。"""
    try:
        m = os.stat(CTL_PATH).st_mtime_ns
        if m != _cache['mtime']:
            with open(CTL_PATH, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            data = dict(DEFAULTS)
            for k in DEFAULTS:
                if k in raw:
                    data[k] = raw[k]
            data = _sanitize(data)
            _cache['mtime'], _cache['data'] = m, data
    except FileNotFoundError:
        _cache['mtime'], _cache['data'] = None, dict(DEFAULTS)
    except Exception:
        pass   # 書き込み途中などは前回値のまま
    return _cache['data']


# ── SI(ffmpeg側EQ)への反映 ───────────────────────────────────────────
# ── SIのEQには一切手を加えない ────────────────────────────────────────
# (旧方式は SI の current_params.eq を直接書き換えていたため、SI内部でEQ辞書が使い回されていると
#  曲が始まるたびに音場プリセット分が積み上がってしまった。今は、フィルターを組み立てる瞬間にだけ
#  「SIのEQ + 音場プリセットのEQ」の合成ビューを渡す。SI側の値・保存データは変更しない。)
EQ_VIEW_CAP = 8.0      # 最終的な1バンドの上限(dB)。万一おかしな値が来ても、極端な値はffmpegへ渡さない


class _EqView:
    """_si_get_eq_filters() に渡す読み取り専用のEQビュー(.eq だけを持つ)"""
    def __init__(self, eq):
        self.eq = eq


def params_with_scene(p):
    base = {}
    if p is not None and not _state.get('si_off'):
        try:
            base = dict(getattr(p, 'eq', None) or {})
        except Exception:
            base = {}
    delta = _scene_eq_delta()
    if delta:
        for band, d in delta.items():
            base[band] = round(base.get(band, 0.0) + d, 2)
    for band in list(base):
        try:
            base[band] = max(-EQ_VIEW_CAP, min(EQ_VIEW_CAP, float(base[band])))
        except Exception:
            base.pop(band, None)
    return _EqView(base)


def _scene_eq_delta():
    sc = SCENES.get(_state['scene'])
    if not sc or not sc['eq']:
        return None
    mult = _levels_for(_state['scene'])[_state['level'] - 1]
    return {b: round(max(-EQ_BAND_CAP, min(EQ_BAND_CAP, d * mult)), 2)
            for b, d in sc['eq'].items()}


# ── 曲/アルバムごとの記憶(~/qji_field_prefs.json) ─────────────────────
# music_mood_db.json とは別ファイルにしてある: DB側は複数の処理が丸ごと読み書きするため、
# 同じ場所に書くと上書きの取り合いや破損のおそれがある。小さい専用ファイルなら高速で安全。
def _empty_prefs():
    return {'version': 1, 'tracks': {}, 'albums': {}}


def _load_prefs():
    try:
        with open(PREFS_PATH, 'r', encoding='utf-8') as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return _empty_prefs()
        d.setdefault('version', 1)
        if not isinstance(d.get('tracks'), dict):
            d['tracks'] = {}
        if not isinstance(d.get('albums'), dict):
            d['albums'] = {}
        return d
    except FileNotFoundError:
        return _empty_prefs()
    except Exception:
        return None          # 壊れている: 読み取りでは「記憶なし」扱い、書き込み時は退避してから作り直す


def _save_prefs(d):
    try:
        os.makedirs(os.path.dirname(PREFS_PATH) or '.', exist_ok=True)
        tmp = PREFS_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, PREFS_PATH)
        return True
    except Exception:
        return False


def _prefs_for_write():
    d = _load_prefs()
    if d is None:       # 壊れたファイルは消さずに退避
        try:
            os.replace(PREFS_PATH, PREFS_PATH + time.strftime('.broken-%Y%m%d-%H%M%S'))
        except Exception:
            pass
        d = _empty_prefs()
    return d


def _current_record():
    return {'scene': _state['scene'], 'level': _state['level'],
            'flutter': bool(_state['flutter']), 'loud': bool(_state['loud']),
            'si_off': bool(_state.get('si_off')),
            'title': (_cur['title'] or '')[:60], 'saved': time.strftime('%Y-%m-%d')}


# ── 曲名などからの自動ルール(記憶が無い曲だけに働く) ─────────────────────
# 「その曲の主役の楽器が曲名から明らかな場合」だけを対象にした控えめなルール。
# 交響曲など主役が決まらないものは何もしない。追加・変更は自由。 (正規表現, シーンキー, 段階1〜3)
RULES = [
    (r'violin\s+concerto|concerto\s+for\s+violin|violinkonzert|concerto\s+pour\s+violon'
     r'|ヴァイオリン協奏曲|バイオリン協奏曲|ヴァイオリン・協奏曲', 'v', 2),
    (r'violin\s+sonata|sonata\s+for\s+violin|ヴァイオリン・?ソナタ|バイオリン・?ソナタ', 'v', 2),
    (r'piano\s+concerto|concerto\s+for\s+piano|klavierkonzert|ピアノ協奏曲|ピアノ・協奏曲', 'p', 2),
    (r'piano\s+sonata|klaviersonate|ピアノ・?ソナタ', 'p', 2),
    (r'oboe\s+concerto|concerto\s+for\s+oboe|オーボエ協奏曲', 'b', 2),
    (r'clarinet\s+(concerto|quintet)|concerto\s+for\s+clarinet|クラリネット協奏曲|クラリネット五重奏', 'c', 2),
    (r'flute\s+concerto|concerto\s+for\s+flute|フルート協奏曲', 't', 2),
    (r'horn\s+concerto|concerto\s+for\s+horn|ホルン協奏曲', 'h', 2),
    (r'cello\s+(concerto|suite|sonata)|concerto\s+for\s+cello|チェロ協奏曲|チェロ組曲|無伴奏チェロ|チェロ・?ソナタ',
     'd', 2),
    (r'string\s+quartet|streichquartett|弦楽四重奏', 'q', 2),
]


# ── 音場別の既定(記憶も曲名ルールも無い曲にだけ働く) ───────────────────────
# (DSP音場の番号, フィルタープリセット名, シーンキー, 段階1〜3)
#   V7 または V8 で、かつ フィルターが musikverein([c]キーで選択/ジャンル自動判定/保存済みプロファイルのどれでも可)
#   のときだけ「ヴァイオリンを美しく・弱」を既定にする。それ以外の音場では何も付けない。
CONTEXT_DEFAULTS = [
    ('7', 'musikverein', 'v', 1),
    ('8', 'musikverein', 'v', 1),
]


def _context_default(context):
    if not context or not context.get('dsp'):
        return None
    for venue, fp, scene, level in CONTEXT_DEFAULTS:
        if str(context.get('venue')) == venue and context.get('filter_preset') == fp and scene in SCENES:
            return scene, level, f"V{venue}×{fp}"
    return None


def _source_tag():
    src = _state['source']
    tag = SOURCE_LABELS.get(src, src)
    if src == 'rule' and _state['reason']:
        tag += f":「{_state['reason']}」"
    elif src == 'preset' and _state['reason']:
        tag += f"({_state['reason']})"
    return tag


def _match_rule(track):
    import re
    hay = ' '.join(str(track.get(k, '') or '') for k in
                   ('title', 'album', 'composer', 'performer', 'genre', 'filename')).lower()
    for pat, scene, level in RULES:
        m = re.search(pat, hay, re.I)
        if m and scene in SCENES:
            return scene, level, m.group(0)
    return None


def set_si_eq_override(path, eq):
    """xメニューを閉じるときに呼ぶ: 今のSIのEQ(リセット後なら空)を、この曲のあいだの確定値として覚える。"""
    if not path:
        return
    _si_override['path'] = os.path.normpath(path)
    _si_override['eq'] = {b: round(float(v), 2) for b, v in (eq or {}).items()
                          if isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) > 0.001}


def eq_without_scene(eq):
    """互換用: 音場プリセットはSIのEQに加えなくなったので、与えられたEQをそのまま返す([s]保存用)。"""
    return {b: v for b, v in (eq or {}).items() if abs(v) > 0.01}


def on_track_start(track, si=None, say=print, context=None):
    """曲の開始時(フィルターを組み立てる前)に呼ぶ。
    曲の記憶 > アルバムの記憶 > 自動ルール > 既定 の順で設定を決め、SIのEQとwobbleへ反映する。
    同じ曲の再読込([r]・リピート)では、手動の変更を保ったままEQだけ新しいフィルターへ再適用する。"""
    path = (track or {}).get('path') or ''
    if not path:
        return
    if context and context.get('dsp'):
        set_venue(context.get('venue'))
    norm = os.path.normpath(path)
    same = (_cur['path'] == norm)
    album_dir = os.path.dirname(norm)
    if _si_override['path'] is not None:
        if _si_override['path'] == norm:
            _p = getattr(si, 'current_params', None) if si else None
            if _p is not None:
                try:
                    _p.eq = dict(_si_override['eq'] or {})      # 代入のみ(足し込まない): 何度呼んでも同じ結果
                except Exception:
                    pass
        else:
            _si_override.update(path=None, eq=None)         # 別の曲に替わった
    _cur.update(path=norm, title=str(track.get('title', '') or os.path.basename(norm)),
                album_key=album_dir, album_name=os.path.basename(album_dir))
    if same and _state['source'] in ('default', 'preset'):
        # 同じ曲の再読込: [c]キーでフィルターを替えた等で状況が変わっていれば、音場別の既定を判定し直す
        ctxd = _context_default(context)
        if ctxd:
            _state.update(scene=ctxd[0], level=ctxd[1], source='preset', reason=ctxd[2])
        else:
            _state.update(scene=None, level=1, source='default', reason='')
    if not same:
        prefs = _load_prefs() or _empty_prefs()
        rec, src, reason = prefs['tracks'].get(norm), 'track', ''
        if rec is None:
            rec, src = prefs['albums'].get(album_dir), 'album'
        if rec is None and RULES_ENABLED:
            hit = _match_rule(track)
            if hit:
                rec = {'scene': hit[0], 'level': hit[1]}
                src, reason = 'rule', hit[2]
        if rec is None:
            ctxd = _context_default(context)
            if ctxd:
                rec = {'scene': ctxd[0], 'level': ctxd[1]}
                src, reason = 'preset', ctxd[2]
        if rec is None:
            rec, src = {}, 'default'
        scene = rec.get('scene')
        lv = rec.get('level', 1)
        _state.update(
            scene=scene if scene in SCENES else None,
            level=lv if isinstance(lv, int) and 1 <= lv <= 3 else 1,
            flutter=bool(rec.get('flutter', DEFAULT_FLUTTER)),
            loud=bool(rec.get('loud', DEFAULT_LOUD)),
            si_off=bool(rec.get('si_off', False)),
            source=src, reason=reason)
    d = publish()
    say(f"   🎛 音場: {d['label']}  〔{_source_tag()}〕")


def consume_saved():
    """直前の操作で「曲/アルバムに記憶」できたら True を返し、印を消す(qji側がジャケット表示へ戻すのに使う)。"""
    v = bool(_cur.get('saved'))
    _cur['saved'] = False
    return v


MEM_GUIDE = ("💾 今の設定を記憶: [1]この曲  [2]このアルバム全体\n"
             "   記憶を消す:     [3]この曲  [4]このアルバム全体")


def _memory_menu(say, timeout):
    if not _cur['path']:
        say("   ⚠️ 記憶できる曲がありません(ローカルの曲の再生中のみ)")
        return
    say(MEM_GUIDE)
    sub = _read_key(KEY_WAIT_SEC if timeout is None else timeout)
    if sub not in ('1', '2', '3', '4'):
        say("   (キャンセル)" if sub is None else "   (該当なし)")
        return
    d = _prefs_for_write()
    if sub in ('1', '2'):
        table, key = ('tracks', _cur['path']) if sub == '1' else ('albums', _cur['album_key'])
        d[table][key] = _current_record()
        ok = _save_prefs(d)
        if ok:
            _state['source'] = 'track' if sub == '1' else 'album'
            _state['reason'] = ''
            what = 'この曲' if sub == '1' else f"アルバム「{_cur['album_name']}」"
            _cur['saved'] = True
            say(f"   💾 {what}に記憶しました: {_derive()['label']}")
        else:
            say("   ⚠️ 記憶の保存に失敗しました")
    else:
        table, key = ('tracks', _cur['path']) if sub == '3' else ('albums', _cur['album_key'])
        if d[table].pop(key, None) is None:
            say("   (その記憶はありません)")
        elif _save_prefs(d):
            _state['source'] = 'manual'
            say("   🗑 記憶を消しました(次回からは自動ルール/既定に戻ります)")
        else:
            say("   ⚠️ 記憶の更新に失敗しました")


# ── キー操作(2段): [e] → w/n/v/o/f/l/r ───────────────────────────────
BAND_JA = {
    'sub_bass': '超低域', 'bass': '低域', 'low_mid': '低めの中域', 'mid': '中域',
    'upper_mid': '上の中域', 'presence': '存在感', 'high_mid': '高めの中域',
    'air_low': '空気感(下)', 'air': '空気感', 'air_high': '空気感(上)',
}


def status_lines(si=None):
    """現在の設定を表示用の行リストで返す([e]→[?])"""
    d = _derive()
    sc = SCENES.get(_state['scene'])
    L = ["📋 現在の音場設定"]
    if sc:
        lv = _state['level']
        mult = _levels_for(_state['scene'])[lv - 1]
        L.append(f"   楽器・シーン : {sc['label']}  [{LEVEL_NAMES[lv - 1]} ×{mult:g}]")
        if WOBBLE_LINK:
            L.append(f"   余韻(wet)   : {d['wet_offset_db']:+.1f} dB")
        eq = _scene_eq_delta()
        if eq:
            L.append("   楽器EQ      : " + ' / '.join(
                f"{BAND_JA.get(b, b)} {v:+.1f}" for b, v in eq.items()) + " dB")
    else:
        L.append("   楽器・シーン : なし(ノーマル)")
    if WOBBLE_LINK:
        L.append("   揺らぎ      : " + ("ON (深さ×%g / 周期×%g)" % (_prof()['flutter_depth'], _prof()['flutter_period'])
                                    if _state['flutter'] else "OFF"))
        L.append("   音量連動    : " + (f"ON (最大 +{_prof()['loud_boost_db']:g} dB)" if _state['loud'] else "OFF"))
    if _state.get('si_off'):
        L.append("   SIのEQ      : 使わない(楽器EQだけを適用)  ※[e]→[z]で元に戻す")
    if _si_override['path'] is not None and _si_override['path'] == _cur.get('path'):
        L.append("   SIのEQ      : xメニューで調整した値を、この曲のあいだ保持中(残すなら [s] で保存)")
    p = getattr(si, 'current_params', None) if si else None
    eqall = {b: v for b, v in (getattr(p, 'eq', None) or {}).items() if abs(v) > 0.01}
    if eqall:
        L.append("   SIのEQ合計  : " + ' / '.join(
            f"{BAND_JA.get(b, b)} {v:+.1f}" for b, v in eqall.items()) + " dB")
        if any(abs(v) > EQ_VIEW_CAP for v in eqall.values()):
            L.append("   ⚠️ SI側のEQに大きな値があります(異常の可能性)。[x]→EQ全解除 か Qjiの再起動を")
    src = _state['source']
    L.append(f"   設定の出所   : {_source_tag()}")
    prefs = _load_prefs() or _empty_prefs()
    have = []
    if _cur['path'] and _cur['path'] in prefs['tracks']:
        have.append('この曲')
    if _cur['album_key'] and _cur['album_key'] in prefs['albums']:
        have.append('アルバム')
    L.append("   記憶         : " + ('・'.join(have) + 'に記憶あり' if have else 'なし'))
    if src == 'manual':
        L.append("   ※未保存: 次の曲では記憶/自動ルール/既定に戻ります。残すなら [e]→[m]")
    L.append("   ※楽器EQは次の曲か[r]再読込から反映" + (" / 余韻・揺らぎはV7のみ" if WOBBLE_LINK else ""))
    return L


def _read_key(timeout):
    r, _, _ = select.select([sys.stdin], [], [], timeout)
    return sys.stdin.read(1).lower() if r else None


def handle_two_stage_key(si=None, say=print, timeout=None, key=None):
    """[e]が押された後に呼ぶ。次のキーを待って音場プリセットを適用する。
    戻り値: SI-EQを変更したらTrue(次の曲/[r]再読込から反映される)"""
    if key is None:
        say(f"\n📋 現在: {_derive()['label']}\n" + GUIDE)
        key = _read_key(KEY_WAIT_SEC if timeout is None else timeout)
    if key is None:
        say("   (時間切れ: キャンセルしました)")
        return False
    eq_changed = False
    _before = _scene_eq_delta()
    if key == 'a':                      # 声楽: 第2メニュー
        say(VOICE_GUIDE)
        sub = _read_key(KEY_WAIT_SEC if timeout is None else timeout)
        if sub is None:
            say("   (時間切れ: キャンセルしました)")
            return False
        key = 'a' + sub
        if key not in SCENES:
            say("   (該当なし)  " + VOICE_GUIDE)
            return False
    if key in ('?', '/'):
        for line in status_lines(si):
            say(line)
        return False
    if key == 'm':                      # 記憶メニュー(保存/消去)
        _memory_menu(say, timeout)
        return False
    if not WOBBLE_LINK and key in ('w', 'n', 'f', 'l'):   # wobble側を使わない構成では無効
        say("   (該当なし)  " + GUIDE)
        return False
    if key in SCENES:
        # 同じキー連打: 弱→中→強→解除 / 別のシーンは「弱」から
        if _state['scene'] == key:
            if _state['level'] < len(_levels_for(key)):
                _state['level'] += 1
            else:
                _state['scene'], _state['level'] = None, 1
        else:
            _state['scene'], _state['level'] = key, 1
    elif key == 'f':
        _state['flutter'] = not _state['flutter']
    elif key == 'l':
        _state['loud'] = not _state['loud']
    elif key == 'z':                    # SIのEQを使わない/使う の切り替え
        _state['si_off'] = not _state.get('si_off')
    elif key == 'r':
        _reset_state('manual')
    else:
        say("   (該当なし)  " + GUIDE)
        return False
    _state['source'], _state['reason'] = 'manual', ''
    eq_changed = (_scene_eq_delta() != _before) or key == 'z' or key == 'r'
    d = publish()
    if WOBBLE_LINK:
        say(f"   🎛 音場プリセット: {d['label']}"
            f"   [wet {d['wet_offset_db']:+.1f}dB / 揺らぎ×{d['depth_scale']:g}"
            f" / 音量連動 {'ON' if d['loud_link'] else 'OFF'}]")
    else:
        say(f"   🎛 音場プリセット: {d['label']}")
    if eq_changed:
        say("   ℹ️ 楽器のEQ分は次の曲、または [r] 再読込から反映されます")
    return eq_changed
