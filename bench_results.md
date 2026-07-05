# 翻訳エンジン比較ベンチマーク

## FuguMT (CPU)

- モデルロード: 4.9s

### 文1 (0.06s)

> The quick brown fox jumps over the lazy dog.

速い茶色のキツネは怠け者の犬を飛び越えます。

### 文2 (0.10s)

> The function returns a promise that resolves when all pending writes have been flushed to disk.

この関数は、保留中のすべての書き込みがディスクにフラッシュされたときに解決するpromiseを返します。

### 文3 (0.10s)

> I couldn't help but notice that the deadline has been quietly pushed back twice already.

締め切りがすでに2回静かに延期されていることに気付かずにはいられない。

### 文4 (0.16s)

> Machine translation has improved dramatically over the past decade. Neural models now capture context across entire sentences, producing output that often reads naturally. However, they still struggle with idioms, cultural references, and highly technical jargon.

機械翻訳は過去10年間で劇的に改善されている。ニューラルモデルは文全体のコンテキストをキャプチャし、しばしば自然に読み込まれる出力を生成する。しかし、彼らはまだイディオム、文化的参照、そして非常に技術的な言葉で苦労しています。

## PLaMo翻訳 (CPU)

- モデルロード: 10.6s

### 文1 (4.35s)

> The quick brown fox jumps over the lazy dog.

すばやく走る茶色いキツネが、怠け者の犬を飛び越える。

### 文2 (5.39s)

> The function returns a promise that resolves when all pending writes have been flushed to disk.

この関数は、すべての保留中の書き込みがディスクにフラッシュされるまで待機するPromiseを返します。

### 文3 (3.65s)

> I couldn't help but notice that the deadline has been quietly pushed back twice already.

締め切りが静かに2回も延期されていることに気づかないわけにはいかなかった。

### 文4 (12.64s)

> Machine translation has improved dramatically over the past decade. Neural models now capture context across entire sentences, producing output that often reads naturally. However, they still struggle with idioms, cultural references, and highly technical jargon.

過去10年間で、機械翻訳は劇的に進化を遂げた。現在のニューラルモデルは文全体の文脈を捉えられるようになり、出力文は自然で流暢なものが多くなっている。ただし、慣用表現や文化的言及、高度に専門的な専門用語などに関しては、まだ課題が残っている。

## Qwen3-4B (NPU)

- モデルロード: 7.5s

### 文1 (4.57s)

> The quick brown fox jumps over the lazy dog.

速いブラウンの狐が、怠惰な犬の上を跳ぶ。

### 文2 (5.11s)

> The function returns a promise that resolves when all pending writes have been flushed to disk.

この関数は、すべてのpending書き込みがディスクにフラッシュされたときに解決するPromiseを返す。

### 文3 (4.50s)

> I couldn't help but notice that the deadline has been quietly pushed back twice already.

期限が二度も無意識に遅らせられていることに、気づけなかった。

### 文4 (9.60s)

> Machine translation has improved dramatically over the past decade. Neural models now capture context across entire sentences, producing output that often reads naturally. However, they still struggle with idioms, cultural references, and highly technical jargon.

マシン翻訳は過去10年間で著しく進化してきた。ニューラルモデルは今や文全体の文脈を捉え、自然な表現を生成できるようになった。しかし、依然として慣用句や文化への関連、そして高度な専門用語には対応できない。


## レイテンシ一覧 (秒)

| エンジン | 文 | 初回 | ベスト |
|---|---|---|---|
| fugumt | 文1 | 0.07 | 0.06 |
| fugumt | 文2 | 0.11 | 0.10 |
| fugumt | 文3 | 0.10 | 0.10 |
| fugumt | 文4 | 0.16 | 0.16 |
| plamo | 文1 | 5.91 | 4.35 |
| plamo | 文2 | 8.28 | 5.39 |
| plamo | 文3 | 6.24 | 3.65 |
| plamo | 文4 | 17.19 | 12.64 |
| qwen_npu | 文1 | 4.66 | 4.57 |
| qwen_npu | 文2 | 5.11 | 5.11 |
| qwen_npu | 文3 | 4.50 | 4.50 |
| qwen_npu | 文4 | 9.60 | 9.60 |