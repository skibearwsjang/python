from flask import Flask, render_template_string, request, jsonify, send_file, Response
import yt_dlp
import os
import tempfile
import json
import time

app = Flask(__name__)

# 각 다운로드 작업의 진행 상황을 저장할 딕셔너리
download_progress = {}

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
        
        /* 진행바 스타일 */
        .progress-container { width: 100%; background-color: #333; border-radius: 6px; margin-top: 15px; overflow: hidden; display: none; }
        .progress-bar { width: 0%; height: 22px; background-color: #ff0000; text-align: center; line-height: 22px; color: white; font-size: 0.8rem; font-weight: bold; transition: width 0.2s; }
        .progress-bar.downloading { background-color: #28a745; }
    </style>
</head>
<body>
    <h2>▶ YouTube Downloader</h2>
    <input type="text" id="urlInput" placeholder="유튜브 URL을 입력하세요">
    <button id="analyzeBtn" onclick="analyzeUrl()">분석하기</button>

    <!-- 진행바 -->
    <div id="progressContainer" class="progress-container">
        <div id="progressBar" class="progress-bar">0%</div>
    </div>
    <p id="statusMsg" style="font-size:0.85rem; color:#aaa; margin-top:8px;"></p>

    <div id="resultBox" class="result">
        <h4 id="videoTitle"></h4>
        <label for="formatSelect">화질/포맷 선택:</label>
        <select id="formatSelect"></select>
        <button id="downloadBtn" class="download-btn" onclick="downloadVideo()">다운로드 시작</button>
    </div>

    <script>
        function updateProgress(percent, text, isDownload = false) {
            const container = document.getElementById('progressContainer');
            const bar = document.getElementById('progressBar');
            const status = document.getElementById('statusMsg');
            
            // 10% 단위로 버림 처리
            const roundedPercent = Math.floor(percent / 10) * 10;
            
            container.style.display = 'block';
            bar.style.width = roundedPercent + '%';
            bar.innerText = roundedPercent + '%';
            status.innerText = text;

            if (isDownload) {
                bar.classList.add('downloading');
            } else {
                bar.classList.remove('downloading');
            }
        }

        async function analyzeUrl() {
            const url = document.getElementById('urlInput').value;
            if(!url) return alert('URL을 입력해주세요.');

            updateProgress(10, "영상을 분석하는 중입니다..."); // 10% 시작

            try {
                const res = await fetch('/analyze', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url})
                });
                const data = await res.json();

                if(data.error) {
                    alert('오류 발생: ' + data.error);
                    updateProgress(0, "");
                    document.getElementById('progressContainer').style.display = 'none';
                    return;
                }

                updateProgress(100, "분석 완료!");
                
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
                setTimeout(() => {
                    document.getElementById('progressContainer').style.display = 'none';
                    document.getElementById('statusMsg').innerText = "";
                }, 1500);

            } catch (err) {
                alert('분석 중 오류가 발생했습니다.');
                document.getElementById('progressContainer').style.display = 'none';
            }
        }

        function downloadVideo() {
            const url = document.getElementById('urlInput').value;
            const formatId = document.getElementById('formatSelect').value;
            if(!url || !formatId) return alert('URL과 화질을 선택해주세요.');

            const downloadId = 'dl_' + Date.now();
            updateProgress(0, "서버에서 다운로드를 준비 중입니다...", true);

            // Server-Sent Events (SSE)로 서버 다운로드 진행률 실시간 수신
            const eventSource = new EventSource(`/progress/${downloadId}`);

            eventSource.onmessage = function(e) {
                const data = JSON.parse(e.data);
                if (data.percent) {
                    // 서버에서 받은 퍼센트를 updateProgress 함수에 그대로 전달 (내부에서 10% 단위 처리)
                    updateProgress(data.percent, `서버 다운로드 중...`, true);
                }
                if (data.status === 'finished') {
                    updateProgress(100, "파일을 브라우저로 전송합니다...", true);
                    eventSource.close();
                    
                    // 파일 실제 다운로드 링크 이동
                    window.location.href = `/get_file?task_id=${downloadId}`;
                }
                if (data.error) {
                    alert("다운로드 오류: " + data.error);
                    eventSource.close();
                    document.getElementById('progressContainer').style.display = 'none';
                }
            };

            // 서버 다운로드 요청 시작
            fetch(`/start_download?task_id=${downloadId}&url=${encodeURIComponent(url)}&format_id=${encodeURIComponent(formatId)}`);
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
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', '제목 없음')
            formats = info.get('formats', [])
            
            options = []
            for f in formats:
                ext = f.get('ext', '')
                if ext in ['mhtml', 'sb', 'vtt']:
                    continue

                fid = f.get('format_id')
                res = f.get('resolution', 'N/A')
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                note = f.get('format_note', '')

                if vcodec != 'none' and acodec != 'none':
                    type_str = "영상+음성"
                elif vcodec != 'none':
                    type_str = "비디오전용"
                elif acodec != 'none':
                    type_str = "오디오전용"
                else:
                    type_str = "기타"

                options.append({
                    "id": fid, 
                    "text": f"[{ext.upper()}] {res} ({type_str}) {note} - ID: {fid}"
                })

            return jsonify({"title": title, "formats": options})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/progress/<task_id>')
def progress(task_id):
    def generate():
        while True:
            prog = download_progress.get(task_id, {})
            yield f"data: {json.dumps(prog)}\n\n"
            if prog.get('status') == 'finished' or 'error' in prog:
                break
            time.sleep(0.5)
    return Response(generate(), mimetype='text/event-stream')

@app.route('/start_download')
def start_download():
    task_id = request.args.get('task_id')
    url = request.args.get('url')
    format_id = request.args.get('format_id')

    def progress_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            percent = (downloaded / total * 100) if total > 0 else 0
            download_progress[task_id] = {'status': 'downloading', 'percent': percent}
        elif d['status'] == 'finished':
            download_progress[task_id]['status'] = 'finished'
            download_progress[task_id]['filename'] = d['filename']

    temp_dir = tempfile.mkdtemp()
    ydl_opts = {
        'format': f'{format_id}+bestaudio/bestvideo+bestaudio/best', # ffmpeg를 통한 고화질+음성 자동 병합
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'progress_hooks': [progress_hook]
    }

    try:
        download_progress[task_id] = {'status': 'starting', 'percent': 0}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            download_progress[task_id]['filepath'] = file_path
            download_progress[task_id]['status'] = 'finished'
    except Exception as e:
        download_progress[task_id] = {'error': str(e)}

    return jsonify({"status": "ok"})

@app.route('/get_file')
def get_file():
    task_id = request.args.get('task_id')
    prog = download_progress.get(task_id, {})
    filepath = prog.get('filepath')

    if filepath and os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return "파일을 찾을 수 없습니다.", 404

if __name__ == '__main__':
    app.run(debug=True)
