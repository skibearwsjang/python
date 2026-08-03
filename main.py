from flask import Flask, render_template_string, request, jsonify, send_file
import yt_dlp
import os
import tempfile

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
        .download-btn { background: #28a745; margin-top: 15px; }
        .download-btn:hover { background: #218838; }
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
        <label for="formatSelect">화질/포맷 선택:</label>
        <select id="formatSelect"></select>
        <!-- 다운로드 버튼 추가 -->
        <button class="download-btn" onclick="downloadVideo()">다운로드 시작</button>
        <p id="statusMsg" style="font-size:0.85rem; color:#aaa; margin-top:10px;"></p>
    </div>

    <script>
        async function analyzeUrl() {
            const url = document.getElementById('urlInput').value;
            if(!url) return alert('URL을 입력해주세요.');

            document.getElementById('statusMsg').innerText = "영상을 분석하는 중입니다...";

            const res = await fetch('/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: url})
            });
            const data = await res.json();

            if(data.error) {
                alert('오류 발생: ' + data.error);
                document.getElementById('statusMsg').innerText = "";
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
            document.getElementById('statusMsg').innerText = "";
        }

        function downloadVideo() {
            const url = document.getElementById('urlInput').value;
            const formatId = document.getElementById('formatSelect').value;
            
            if(!url || !formatId) return alert('URL과 화질을 선택해주세요.');

            document.getElementById('statusMsg').innerText = "서버에서 다운로드 준비 중입니다. 잠시만 기다려주세요...";
            
            // 파일 다운로드 링크로 이동
            window.location.href = `/download?url=${encodeURIComponent(url)}&format_id=${encodeURIComponent(formatId)}`;
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
    data = request.get_json(silent=True)
    if not data or 'url' not in data:
        return jsonify({"error": "유효한 URL 데이터가 전달되지 않았습니다."}), 400

    url = data.get('url')
    
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True, 
        'format': 'all',
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None
    }
    
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
                note = f.get('format_note', '')
                options.append({"id": fid, "text": f"[{ext}] {res} {note} (ID: {fid})"})

            return jsonify({"title": title, "formats": options})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/download')
def download():
    url = request.args.get('url')
    format_id = request.args.get('format_id')

    if not url or not format_id:
        return "잘못된 요청입니다.", 400

    temp_dir = tempfile.mkdtemp()
    
    ydl_opts = {
        'format': f'{format_id}+bestaudio/best', # 선택한 영상 + 오디오 병합
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # 다운로드 완료된 파일 브라우저 전송
            return send_file(filename, as_attachment=True)
    except Exception as e:
        return f"다운로드 중 오류 발생: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
