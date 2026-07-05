# translator

完全オフラインで動く英→日翻訳常駐ツール(Windows)。
テキストを選択してホットキーを押すと、カーソル脇にポップアップで訳が出る。
翻訳処理での外部通信はゼロ(モデルの初回ダウンロードのみネット使用)。

## 3段構えのエンジン

| 対象 | エンジン | 実行場所 | 実測 (Core Ultra 5 228V) |
|---|---|---|---|
| 英単語 (1〜3語) | EJDict-hand 辞書 (47,307見出し) | SQLite | 数ms |
| 文章 (デフォルト) | FuguMT (staka/fugumt-en-ja) + CTranslate2 int8 | CPU | 0.06〜0.16秒 |
| 高品質枠 その1 | PLaMo翻訳 (pfnet/plamo-2-translate, Q4_K_S) + llama.cpp | CPU (約10 tok/s) | 1文4〜6秒 / 段落13秒 |
| 高品質枠 その2 | Qwen3-4B-Instruct-2507 (int4対称量子化/OpenVINO) | **iGPU** (NPU/CPUフォールバック) | 1文0.5〜0.8秒 / 段落2秒 |

品質の傾向(`bench_results.md` 参照): 訳質は総合で PLaMo > Qwen ≒ FuguMT。
PLaMo はニュアンス(couldn't help but 等)も段落も最も正確。Qwen は段落が得意だが
単文でたまに意味を取り違える。FuguMT は直訳調だが爆速で普段使いに最適。

デバイス別実測 (Qwen3-4B int4): GPU 0.5〜2.0秒 / CPU 1.2〜3.8秒 / NPU 4.1〜9.6秒。
この世代のNPUはiGPUより大幅に遅く、価値は「CPU/GPUを占有しない」ことのみ。
PLaMo は Mamba 系のため NPU 実行経路が存在せず、iGPU も帯域共有のため利点なし。

注: PLaMo は Mamba 系アーキテクチャのため llama.cpp の Vulkan (iGPU) では
動作しない(出力破損+激遅)。CPU 実行が正解。
Qwen は公式の OpenVINO 変換が無いため `translator-setup qwen` が
optimum-intel で自前変換する(NPU 要件の対称量子化、group_size=128)。

単語は辞書に無ければ文章エンジンへ自動フォールバック。
文章エンジンはトレイメニューからいつでも切り替えられる。

## セットアップ

```powershell
uv sync --all-extras          # 依存関係 (convert込み)
uv run translator-setup all   # 辞書+全モデルのダウンロード (合計約9GB)
```

個別に入れる場合: `translator-setup dict | fugumt | plamo | qwen`

## 使い方

```powershell
uv run translator             # 常駐開始
```

- テキストを選択して **`Ctrl+C` を2連打**(config.tomlで通常の組み合わせにも変更可)
- ポップアップは画面のどこかをクリックするか15秒で消える
- トレイアイコン右クリック → エンジン切替 / 一時停止 / 終了

### CLI(動作確認用)

```powershell
uv run translator-cli "serendipity"                 # 自動判定(辞書)
uv run translator-cli -e plamo "Long sentence..."   # エンジン指定
```

### ベンチマーク

```powershell
uv run translator-bench                    # 全エンジン比較
uv run translator-bench --engines fugumt plamo
```

結果は `bench_results.md` に保存される。

## スタートアップ登録(任意)

`shell:startup` フォルダに以下のショートカットを作成:

```
uv --directory C:\Users\kami1\development\translator run translator
```

## 設定

`config.toml`(初回起動時に自動生成)。ホットキー、エンジン、ポップアップ表示時間、
PLaMoのGPUレイヤ数、Qwenのデバイス優先順位などを変更できる。

## ライセンス注意

- EJDict-hand: パブリックドメイン
- FuguMT: CC BY-SA 4.0 ([staka/fugumt-en-ja](https://huggingface.co/staka/fugumt-en-ja))
- PLaMo翻訳: PLaMoコミュニティライセンス(個人利用無料、**法人利用はPFNとの契約が必要**)
- Qwen3: Apache 2.0

## 会社PCで使う場合(PLaMo抜き構成 = カンパニー版)

ライセンスの制約があるのは PLaMo のモデル重みだけ(このアプリのコード自体は無関係)。
会社PCでは PLaMo をダウンロードしない構成にすれば、全コンポーネントが
商用利用可のライセンス(パブリックドメイン / CC BY-SA 4.0 / Apache 2.0)になる。

### パターンA: 会社PCでダウンロードできる場合

```powershell
git clone <このリポジトリ> ; cd translator
uv sync --all-extras
uv run translator-setup company   # 辞書 + FuguMT + Qwen のみ(PLaMoを落とさない)
uv run translator
```

`translator-setup company` は `dict` + `fugumt` + `qwen` と同義。
PLaMo 本体はもちろん、PLaMo 専用の llama.cpp もダウンロードしない。

### パターンB: 社内プロキシで Hugging Face 等が塞がれている場合

セットアップ済みのこのフォルダごと(`.venv` は除く)USB 等でコピーし、
持ち込む前に data/ からライセンス対象物と不要物を削除する:

```powershell
Remove-Item data\models\plamo-2-translate-Q4_K_S.gguf   # PLaMo本体(要削除)
Remove-Item -Recurse data\llama.cpp                     # PLaMo専用の実行系(不要)
```

会社PC側では `uv sync --all-extras` だけ実行すれば動く
(モデル・辞書は data/ に同梱済みなのでダウンロードは発生しない)。

### カンパニー版の動作

- 未インストールのエンジンはトレイメニューに表示されず、誤って選ぶ余地はない
- `config.toml` が PLaMo を指していても起動時に自動で FuguMT へフォールバック
- 翻訳処理は完全ローカル。社内文書がネットに出ることはない

### 導入前の注意

常駐時にグローバルキーボードフック(Ctrl+C の2連打検知)とクリップボード読み取りを
使うため、EDR 等のセキュリティ製品にはキーロガー様の挙動として記録され得る。
隠れて使わず、事前に情シスへ申請するのが安全
(全コードが読める・外部通信ゼロ・モデルもローカル、が説明材料になる)。
許可が下りない場合は、常駐せず `translator-cli` だけ使う運用なら
フックもクリップボード監視も使わない。
