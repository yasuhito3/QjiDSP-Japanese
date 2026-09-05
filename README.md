**🟢 初めてQjiDSPをお使いになる方へ**  
[まずはこちらをご覧ください →](https://github.com/yasuhito3/QjiDSP-Japanese/blob/main/QjiDSP_Quick_Start_Japanese.md) `QjiDSP Quick Start Guide`

# Qji（奏在）

Linux 向けのハイファイ音楽再生システムです。ローカルファイル再生に加え、Qobuz・SoundCloud・YouTube Music のストリーミング再生、CamillaDSP による3D空間音響拡張（音場 v1〜v6）、ジャンル適応型EQ（Sonia Intelligence）、自動歪み軽減（Auto De-Clip）などを統合しています。

> 個人のオーディオ環境（Mark Levinson アンプ、Amanero Combo384 USB DAC 等）で日常的に使うために開発・改良を重ねているプロジェクトです。

> ⚠️ **前提条件**：本リポジトリ（QjiDSP拡張）は、**先に[Qji本体](https://github.com/yasuhito3/Qji-Network-Audio-Player)をインストール済みであること**を前提としています。
> Qji本体がまだの場合は、先にそちらのインストール手順に従ってセットアップしてから、本リポジトリのインストーラーを実行してください。

---

## 特徴

- **ローカル音楽再生**：ジャケット画像選曲、フォルダー再生、作曲家／演奏者／指揮者／ジャンル／ムード等の条件検索
- **ストリーミング対応**：Qobuz（Hi-Res）、SoundCloud、YouTube Music（`yt-dlp` + `ytmusicapi`）
- **3D空間音響拡張（QjiDSP）**：CamillaDSP を用いた仮想サウンドカード（ALSA Loopback）経由のDSPパイプライン。6種類の音場プリセットを収録
  1. 濃厚ホール（静）— フル装備EQ・落ち着いた響き
  2. 濃厚ホール（動）— フル装備EQ・空気の流れ
  3. 素材の味（静）— シンプル・実在感重視
  4. 素材の味（動）— シンプル・和食系パンニング
  5. 倍音モード — ヴァイオリン共鳴・尺八系倍音強調
  6. 倍音モード（ヘッドホン用）— クロスフィード処理でヘッドホン再生に最適化
- **Sonia Intelligence（SI）**：再生中のジャンルに応じてEQを自動調整
- **Auto De-Clip**：ffmpeg の astats/ametadata フィルターでリアルタイムに歪みを検出し、ゲインを自動調整
- **音声操作（任意）**：Vosk による日本語音声認識（オフライン）
- **AirPlay / UPnP 受信**：shairport-sync / gmediarender 経由
- **プリセット保存**：音量・音響プリセット・ゲインプリセット等を名前付きで保存／呼び出し

---



## 動作環境

- Linux（Ubuntu / Linux Mint 系で動作確認）
- Python 3.10 以上
- ALSA（`snd-aloop` カーネルモジュールを使用）
- ffmpeg
- （推奨）USB DAC 等のオーディオインターフェース。QjiDSP利用時は48kHz対応のDACを推奨

---



## インストール



### 0. 前提：Qji本体のインストール（未導入の場合）

本リポジトリ単体では動作しません。まだの場合は、先にQji本体をインストールしてください。

```bash
git clone https://github.com/yasuhito3/Qji-Network-Audio-Player.git
cd Qji-Network-Audio-Player
# Qji本体側のインストール手順に従ってください
```



### 1. 本リポジトリ（QjiDSP拡張）を取得

```bash
git clone https://github.com/yasuhito3/QjiDSP-Japanese.git
cd QjiDSP-Japanese/qjidsp_installer
```

> 📦 インストーラー本体・DSP設定ファイル・IRファイル等は、すべて `qjidsp_installer/` **フォルダの中** にまとめてあります。
> GitHubの「Download ZIP」で取得した場合は、展開後にできる `QjiDSP-Japanese-main/` のようなフォルダの中の、
> さらに `qjidsp_installer/` フォルダまで進んでから、次のステップを実行してください。



### 2. インストーラーを実行

`qjidsp_installer/` フォルダの中で、次のいずれかを実行します。

```bash
bash install_qjidsp.sh
```

またはデスクトップ環境から `QjiDSPインストール.desktop` をダブルクリックしてください。

インストーラーは以下を行います。

- 必要パッケージ（ffmpeg, alsa-utils, git 等）のインストール
- Python ライブラリ（soundfile, scipy, pycamilladsp）と `yt-dlp` の更新
- CamillaDSP 本体のダウンロード
- `deno`（YouTube Music 再生の安定化に使用）のインストール
- 仮想サウンドカード（`snd-aloop`）の有効化
- `~/qji/` へ本体一式・DSP設定ファイル（音場 v1〜v6）・IR（残響）ファイルを配置

既存の `~/qji/` にインストール済みの場合、上書きされるファイルは自動的にタイムスタンプ付きでバックアップされます。

### 3. 起動

デスクトップにあるQjiアイコンをダブルクリックすると起動します。

手動で起動する場合：

```bash
cd ~/qji && python3 qji.py
```

出力デバイスで「Loopback」を選択すると、6つの音場（v1〜v6）から選べます。それ以外のデバイスを選ぶと、DSPを介さない直接出力になります。

---



## アップデート

一度インストールすれば、以後は毎回ZIPを再ダウンロードしたり`git clone`し直したり
する必要はありません。インストール時に、`~/qji/`へ`update_qjidsp.sh`（と
アップデート確認用のデスクトップアイコン）が一緒に配置されます。

- **ターミナルから**: `cd ~/qji && bash update_qjidsp.sh`
- **デスクトップアイコンから**: `~/qji/QjiDSPアップデート確認.desktop` をダブルクリック

このリポジトリの`VERSION`ファイルを確認し、新しいバージョンがあれば確認のうえ
自動的にダウンロードし、最新のファイルで`install_qjidsp.sh`を実行し直します
（上書きされる既存ファイルはインストーラーの仕様により自動的にタイムスタンプ付き
でバックアップされます）。すでに最新版の場合は、その旨を表示して終了します。

Qji Peak Monitorのアップデート確認と同じ方式です。

---



## 任意設定



### YouTube Music（ライブラリ連携）

「いいね」した曲やライブラリへアクセスする場合のみ、ブラウザ認証を設定してください。

```bash
python3 -c "from ytmusicapi import YTMusic; YTMusic.setup(filepath='~/.config/qji_ytmusic_auth.json')"
```

未設定でも `yt-dlp` 検索で再生自体は可能です。

### 音声操作（Vosk）

日本語音声認識モデルを以下に配置すると有効になります（未配置の場合は自動的に無効化されます）。

```
~/vosk-model-ja-0.22
```

モデルは [alphacep/vosk-api](https://alphacephei.com/vosk/models) 等から取得してください。

### Qji Peak Monitor（ステレオVUメーター）

⚠️ **本インストーラー（**`install_qjidsp.sh`**）には含まれていません。** 独立したオプションのリポジトリとして公開しています：
👉 **[Qji Peak Monitor](https://github.com/yasuhito3/Qji-peak-monitor)**

Qjiの最終出力段をリアルタイムに可視化する、スタンドアロンのステレオピーク（VU）メーターです。
QjiDSP経由で聴く際に生じる下流バッファ分のズレを補正する「ディスプレイディレイ」機能も備えています。
インストール方法・使い方は、そちらのリポジトリのREADMEを参照してください。

---



## コマンドラインオプション

```
python3 qji.py --tempo 120 --tempo-tol 10       # テンポ指定再生
python3 qji.py --composer "モーツァルト"          # 作曲家指定再生
python3 qji.py --genre クラシック --mood 安らぎ     # 条件複合検索
python3 qji.py --device hw:2,0                  # 出力デバイス指定
python3 qji.py --no-voice                       # 音声認識を無効化して起動
```

---



## トラブルシューティング

**DSPモードで音が出ない場合**、以下を確認してください。

```bash
cat /tmp/camilladsp.log /tmp/wobble.log /tmp/cdsp_watchdog.log
```

`Invalid filter ... No such file or directory` のようなエラーが出ている場合、IR（残響）ファイルのパスが正しく展開されていません。`~/qji/camilladsp_test/` 以下にファイルが存在するか確認してください。

Loopback → DAC の経路だけを単体で確認したい場合：

```bash
speaker-test -D hw:CARD=Loopback,DEV=0 -c 2 -r 48000 -F S32_LE
```

---



## ディレクトリ構成（インストール後）

```
~/qji/
├── qji.py                      # 本体
├── VERSION                     # インストール済みバージョン(update_qjidsp.shが参照)
├── update_qjidsp.sh            # アップデート確認スクリプト
├── QjiDSPアップデート確認.desktop  # 上記のデスクトップアイコン版
├── qji_qobuzdsp.py             # Qobuz モジュール
├── qji_qobuz_browser.py        # Qobuz ブラウザUI
├── qji_soundcloud.py           # SoundCloud モジュール
├── qji_soundcloud_browser.py   # SoundCloud ブラウザUI
├── qji_ytmusic.py              # YouTube Music モジュール
├── qji_ytmusic_browser.py      # YouTube Music ブラウザUI
├── camilladsp_test/
│   ├── spatial_final.yml       # 現在有効なDSP設定（起動時に生成）
│   ├── wobble_v1〜v5.py        # 揺らぎLFOスクリプト
│   ├── wobble_v5_harmonics_hp.py
│   ├── cdsp_watchdog.py        # CamillaDSP死活監視
│   └── Musikvereinsaal_48k_tail.wav  # 残響IRファイル
└── qjidsp_backup_v1〜v6/
    └── spatial_final.yml       # 音場プリセット v1〜v6（テンプレート）
```

---



## 謝辞・使用ライブラリ

- [CamillaDSP](https://github.com/HEnquist/camilladsp) / [pycamilladsp](https://github.com/HEnquist/pycamilladsp)
- [ffmpeg](https://ffmpeg.org/)
- [mutagen](https://github.com/quodlibet/mutagen)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) / [ytmusicapi](https://github.com/sigma67/ytmusicapi)
- [Vosk](https://alphacephei.com/vosk/)
- [deno](https://deno.com/)
- [shairport-sync](https://github.com/mikebrady/shairport-sync)

残響IR（`Musikvereinsaal_48k_tail.wav`）の出典・利用条件、および依存ライブラリのライセンス（`mutagen`はGPLv2+など、
ソースコードは同梱せずpip経由で別インストールする形を取っています）については [NOTICE.md](./NOTICE.md) を参照してください。

## ライセンス

[LICENSE](./LICENSE) を参照してください。