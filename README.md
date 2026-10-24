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
- **ストリーミング対応**：Qobuz（Hi-Res）、SoundCloud（公式APIで直接取得）、YouTube Music（`yt-dlp` + `ytmusicapi`）
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
- Python ライブラリ（soundfile, scipy, pycamilladsp）と `yt-dlp[default]` の更新（YouTube 再生に必要な部品 `yt-dlp-ejs` を含みます。古い `yt-dlp` が優先されて残っている場合は、自動で検出して `sudo` で更新します）
- CamillaDSP 本体のダウンロード
- `deno`（YouTube の署名解読に使用。**2.3 以上が必要**）のインストール
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
する必要はありません。インストール時に、Qji本体の起動アイコンと同じように
**デスクトップ**へ「QjiDSPアップデート確認」アイコンが自動的に作成されます。

- **デスクトップアイコンから**: 「QjiDSPアップデート確認」アイコンをダブルクリック
- **ターミナルから**: `cd ~/qji && bash update_qjidsp.sh`

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
mkdir -p ~/.config
python3 -c "import os, ytmusicapi; ytmusicapi.setup(filepath=os.path.expanduser('~/.config/qji_ytmusic_auth.json'))"
```

実行すると、ブラウザ（Chrome / Firefox）で music.youtube.com にログインした状態でコピーした「リクエストヘッダー」の貼り付けを求められます。貼り付けたあと `Ctrl-D` で確定してください。

未設定でも `yt-dlp` 検索で再生自体は可能です。

> 🔒 **セキュリティーについて**
> - 認証ファイルにはログイン済みの Cookie が含まれるため、Qji は読み込み時に所有者とパーミッションを確認し、必要なら `600`（自分だけが読める）に自動修正します。
> - YouTube Music のブラウザUI（ポート 8082）は、**このPC自身（127.0.0.1）からのみ**接続できます。同じネットワーク内のスマートフォン等からは開けません。
> - 再生できるのは YouTube / YouTube Music の URL だけです。ジャケット画像も YouTube / Google の画像配信ホストからのみ取得します。
> - `ytmusicapi` などが未インストールの場合、自動インストールの前に実行するコマンドを表示して確認します（既定は「いいえ」）。

### SoundCloud

ログインや認証の設定は不要です。検索・再生に必要な `client_id` は、SoundCloud のウェブサイトから自動で取得・更新されます（`~/.config/qji_soundcloud.json` に保存され、ファイルの権限は `600` です）。

曲もプレイリスト（`/sets/…`）も、SoundCloud の API で直接取得します。`yt-dlp` は、API で取得できなかったときの予備としてだけ使います。

> 🔒 **セキュリティーについて**
> - SoundCloud のブラウザUI（ポート 8081）は、**このPC自身（127.0.0.1）からのみ**接続できます。同じネットワーク内のスマートフォン等からは開けません。あわせて、他のサイトからの操作（CSRF・DNSリバインディング）を拒否する確認を行っています。
> - 再生できるのは SoundCloud（`soundcloud.com`）の URL だけです。ジャケット画像も SoundCloud の画像配信ホストからのみ取得します。
> - SoundCloud が返したストリームURLは、SoundCloud の配信ホストの `https` に限って使います。ffmpeg には `-protocol_whitelist` を付け、`file:` などローカルのものを読ませません。
> - 曲名などの外部文字列から、端末の制御シーケンスを取り除いてから表示します。
> - 再生リクエストの受け渡しファイルやジャケット画像の一時ファイルは、共有の `/tmp` ではなく、自分専用のフォルダー（`$XDG_RUNTIME_DIR/qji`、なければ `/tmp/qji-<UID>`）に権限 `600` で置きます。
> - `yt-dlp` 用の Cookie ファイルを指定している場合は、読み込み時に所有者とパーミッションを確認し、必要なら `600` に自動修正します。
> - `requests` が未インストールの場合、自動インストールの前に実行するコマンドを表示して確認します（既定は「いいえ」）。

> ℹ️ **再生について**
> - DSPモード（出力デバイスで「Loopback」を選んだとき）は、ffmpeg 側で 48000Hz に変換して CamillaDSP へ渡します。直接出力のときは、SoundCloud 本来の 44.1kHz のまま出力します。
> - ピークモニターの表示は、SoundCloud の再生でも使えます。
> - SoundCloud 側で **DRM 保護**されている曲は、ffmpeg では再生できません。その曲は自動でスキップされます（別のアップロード音源が再生できることもあります）。

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

**YouTube Music が再生できない場合**（`403` エラーが出る、すぐに曲が終わってしまう、など）

YouTube 側の仕様変更により、`yt-dlp` が古いままだと再生できなくなります。まず、次のコマンドで `yt-dlp` を更新してください。

```bash
pip install -U "yt-dlp[default]" --break-system-packages
```

`[default]` を付けるのが重要です（YouTube の署名解読に必要な `yt-dlp-ejs` も一緒に入ります）。

更新したのに直らない場合は、**古い `yt-dlp` が優先して呼ばれている**可能性があります（以前に `sudo` で入れた版や、`apt` で入れた版が残っている場合など）。次のコマンドで確認してください。

```bash
which -a yt-dlp      # 見つかった yt-dlp の一覧（先頭のものが使われます）
yt-dlp --version     # 実際に使われる版
```

先頭に出た `yt-dlp` の版が古い場合は、システム全体へ更新します。

```bash
sudo pip3 install --upgrade "yt-dlp[default]" --break-system-packages
```

`apt` で入れた古い版が残っている場合は、`sudo apt remove yt-dlp` で削除してから上のコマンドを実行してください。

あわせて `deno` が **2.3 以上**であることも確認してください。

```bash
deno --version       # 古い場合は: deno upgrade
```

なお、インストーラー（`install_qjidsp.sh`）を再実行すると、上記の更新と確認を自動で行います。

---



**SoundCloud が再生できない場合**

再生を始めると、画面に再生可否の手がかりが出ます。

- `📡 利用可能: …` ── その曲で再生できる配信形式の一覧です。暗号化（DRM）のため除外した形式があれば、その件数も出ます。1つの形式が失敗（`HTTP 404` など）しても、次の形式を自動で試します。
- `🔒 DRM 保護の曲のため再生できません（スキップします）` ── SoundCloud 側で DRM 保護された曲です。ffmpeg では再生できないため、仕様としてスキップされます。`yt-dlp` を更新しても変わりません。
- `許可されていない配信元のため…` ── SoundCloud が新しい配信ホストを使い始めた可能性があります。表示されたホスト名を添えて、Issue でお知らせください。
- `HTTP 401` / `403` が続く ── 取得済みの `client_id` が失効している可能性があります。通常は自動で更新されますが、直らない場合は、次のコマンドで保存済みの `client_id` を消してから、もう一度再生してください。

```bash
python3 - <<'EOF'
import json, pathlib
p = pathlib.Path.home()/'.config'/'qji_soundcloud.json'
c = json.loads(p.read_text()); c.pop('client_id', None); c.pop('client_id_fetched_at', None)
p.write_text(json.dumps(c, ensure_ascii=False, indent=2))
EOF
```

SoundCloud の再生は `yt-dlp` に頼っていないため、`yt-dlp` が古くても、通常は影響しません（予備の経路でだけ使います）。

---



## ディレクトリ構成（インストール後）

```
~/qji/
├── qji.py                      # 本体
├── VERSION                     # インストール済みバージョン(update_qjidsp.shが参照)
├── update_qjidsp.sh            # アップデート確認スクリプト(本体)
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