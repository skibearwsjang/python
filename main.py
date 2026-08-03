from flask import Flask, render_template_string, request, jsonify
import yt_dlp

app = Flask(__name__)

# HTML 템플릿
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>YouTube Downloader</title>
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 40px auto; padding: 0 20px; background: #121212; color: #fff; }
        input, button, select { width: 100%; padding: 10px; margin-top: 10px; border-radius: 6px; border: 1px solid #333; box-sizing: border-box; }
        button { background: #ff0000; color: white; font-weight: bold; cursor: pointer; border: none; }
        button:hover { background: #cc0000; }
        select { background: #222; color: white; }
        .result { margin-top: 20px; padding: 15px; background: #1e1e1e; border-radius: 6px; display: none; }
    </style>
</head>
<body>
    <h2>▶ YouTube Downloader</h2>
    <input type="text" id="urlInput" placeholder="유튜브 URL을 입력하세요">
    <button onclick="analyzeUrl()">분석하기</button>

    <div id="resultBox" class="result">
        <h4 id="videoTitle"></h4>
        <select id="formatSelect"></select>
        <p style="font-size:0.85rem; color:#aaa;">* PythonAnywhere 무료 플랜의 네트워크 제한으로 인해 일부 다운로드가 제한될 수 있습니다.</p>
    </div>

    <script>
        async function analyzeUrl() {
            const url = document.getElementById('urlInput').value;
            if(!url) return alert('URL을 입력해주세요.');

            const res = await fetch('/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: url})
            });
            const data = await res.json();

            if(data.error) {
                alert('오류 발생: ' + data.error);
                return;
            }

            document.getElementById('videoTitle').innerText = data.title;
            const select = document.getElementById('formatSelect');
            select.innerHTML = '';
            
            data.formats.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f.id;
                opt.innerText = f.text;
                select.appendChild(opt);
            });

            document.getElementById('resultBox').style.display = 'block';
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/analyze', methods=['POST'])
def analyze():
    url = request.json.get('url')
    ydl_opts = {'quiet': True, 'no_warnings': True, 'format': 'all'}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', '제목 없음')
            formats = info.get('formats', [])
            
            options = []
            for f in formats:
                fid = f.get('format_id')
                ext = f.get('ext', '')
                res = f.get('resolution', 'N/A')
                options.append({"id": fid, "text": f"[{ext}] 화질: {res} (ID: {fid})"})

            return jsonify({"title": title, "formats": options})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
