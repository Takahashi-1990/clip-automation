import yt_dlp
import whisper
import anthropic
import os

def download_audio(url):
    print("動画をダウンロード中...")
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'audio.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info.get('title', '不明')

def transcribe():
    print("文字起こし中（数分かかります）...")
    model = whisper.load_model("base")
    result = model.transcribe("audio.mp3", language="ja")
    return result["segments"]

def build_telop(segments, start_sec, end_sec):
    """指定範囲のセグメントをテロップ形式に変換"""
    telop_lines = []
    offset = start_sec
    for seg in segments:
        if seg["start"] < start_sec or seg["end"] > end_sec:
            continue
        text = seg["text"].strip()
        # フィラー除去
        for filler in ["えー", "あの", "まあ", "えっと", "うーん", "そのー"]:
            text = text.replace(filler, "")
        text = text.strip()
        if not text:
            continue
        t_start = round(seg["start"] - offset, 1)
        t_end = round(seg["end"] - offset, 1)
        telop_lines.append(f"[{t_start}-{t_end}] {text}")
    return "\n".join(telop_lines)

def analyze_with_claude(title, segments):
    print("\nClaudeが切り抜き候補を分析中...")
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    segment_text = "\n".join([
        f"[{int(s['start'])}秒] {s['text'].strip()}"
        for s in segments if s['text'].strip()
    ])

    prompt = f"""あなたはYouTubeショート動画のバズらせる専門家です。
以下の動画から、最もバズる切り抜き候補を3つ選んでください。

【元動画タイトル】
{title}

【全文字起こし（タイムスタンプ付き）】
{segment_text}

## 出力ルール
- 候補3つは全て異なる場面から選ぶ
- 1候補あたり20秒〜50秒の長さ（50秒を超える候補は選ばない）
- 「数字のビフォーアフター」「意外な事実」「感情が動く瞬間」を優先

## 出力形式（厳守）

### 候補1
- タイムスタンプ：〇秒〜〇秒（元動画の秒数）
- バズる理由：（視聴者のどんな感情を刺激するか具体的に）

**タイトル案**
1. （タイトル文）→ バズる理由：
2. （タイトル文）→ バズる理由：
3. （タイトル文）→ バズる理由：

**サムネイル文言**
（10文字以内・数字入り推奨）

**ハッシュタグ**
#〇〇 #〇〇 #〇〇 #〇〇 #〇〇 #〇〇 #〇〇 #〇〇 #〇〇 #〇〇

---

### 候補2
（同じ形式で）

---

### 候補3
（同じ形式で）
"""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

def format_output(analysis, segments):
    """Claudeの分析結果にWhisperのテロップを組み合わせて最終出力を作る"""
    import re
    output = analysis

    # タイムスタンプを抽出してテロップを生成・挿入
    pattern = r"タイムスタンプ：(\d+)秒〜(\d+)秒"
    matches = list(re.finditer(pattern, analysis))

    for match in reversed(matches):
        start_sec = int(match.group(1))
        end_sec = int(match.group(2))
        telop = build_telop(segments, start_sec, end_sec)
        telop_block = f"\n\n**テロップ（Whisper自動生成・実際の発話タイミング）**\n{telop}"
        insert_pos = match.end()
        output = output[:insert_pos] + telop_block + output[insert_pos:]

    return output

if __name__ == "__main__":
    print("=== 切り抜き自動化ツール ===")
    url = input("YouTubeのURLを入力してください: ")
    video_title = download_audio(url)
    segments = transcribe()
    analysis = analyze_with_claude(video_title, segments)
    final_output = format_output(analysis, segments)

    print("\n" + "="*50)
    print(final_output)
    print("="*50)

    with open("result.txt", "w", encoding="utf-8") as f:
        f.write(final_output)
    print("\n結果をresult.txtに保存しました")
