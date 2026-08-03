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
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YouTube Downloader</title>
<style>
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        max-width: 640px;
        margin: 40px auto;
        padding: 0 20px;
        background: #121212;
        color: #fff;
    }
    
    h2 {
        text-align: center;
        margin-bottom: 25px;
        color: #ff4757;
    }

    /* 입력 및 버튼 레이아웃 */
    .input-group {
        display: flex;
        gap: 8px;
        margin-bottom: 20px;
    }

    .input-group input {
        flex: 1;
        padding: 12px;
        border: 1px solid #333;
        border-radius: 6px;
        background: #1e1e1e;
        color: #fff;
        font-size: 0.95rem;
        outline: none;
    }

    .input-group input:focus {
        border-color: #007bff;
    }

    .btn {
        padding: 10px 16px;
        border: none;
        border-radius: 6px;
        font-weight: bold;
        cursor: pointer;
        white-space: nowrap;
        transition: opacity 0.2s;
    }

    .btn:hover {
        opacity: 0.85;
    }

    .btn-preview { background: #28a745; color: white; }
    .btn-analyze { background: #007bff; color: white; }
    .btn-download { background: #ff4757; color: white; width: 100%; margin-top: 15px; padding: 12px; font-size: 1rem; }

    /* 미리보기 컨테이너 */
    .preview-container {
        display: none;
        margin-bottom: 25px;
        text-align: center;
        background: #000;
        border-radius: 8px;
        overflow: hidden;
    }

    .preview-container iframe {
        width: 100%;
        max-width: 100%;
        height: 315px;
        border: none;
    }

    /* 진행바 스타일 */
    .progress-container {
        width: 100%;
        background-color: #222;
        border-radius: 6px;
        margin-bottom: 15px;
        overflow: hidden;
        display: none;
    }

    .progress-bar {
        width: 0%;
        height: 22px;
        background-color: #007bff;
        text-align: center;
        line-height: 22px;
        color: white;
        font-size: 0.8rem;
        font-weight: bold;
        transition: width 0.2s;
    }

    .progress-bar.downloading {
        background-color: #28a745;
    }

    /* 결과 선택 박스 */
    .result-box {
        display: none;
        padding: 20px;
        background: #1e1e1e;
        border-radius: 8px;
        border: 1px solid #2a2a2a;
    }

    .result-box h4 {
        margin-top: 0;
        margin-bottom: 15px;
        font-size: 1.1rem;
        color: #f1f1f1;
        word-break: break-all;
    }

    .result-box label {
        font-size: 0.9rem;
        color: #aaa;
        display: block;
        margin-bottom: 8px;
    }

    select {
        width: 100%;
        padding: 10px;
        border-radius: 6px;
        border: 1px solid #333;
        background: #2b2b2b;
        color: #fff;
        font-size: 0.95rem;
        outline: none;
    }
</style>
</head>
<body>

    <h2>▶ YouTube Downloader</h2>

    <!-- 1. 입력 영역 -->
    <div class="input-group">
        <input type="text" id="urlInput" placeholder="유튜브 URL을 입력하세요">
        <button onclick="previewUrl()" class="btn btn-preview">미리보기</button>
        <button id="downloadBtn" class="btn btn-download" onclick="downloadVideo()">다운로드 시작</button>
    </div>

    <!-- 2. 미리보기 컨테이너 -->
       <div id="previewContainer" class="preview-container">
       <iframe id="previewPlayer" src="" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
    </div>

    <!-- 진행바 -->
    <div id="progressContainer" class="progress-container">
        <div id="progressBar" class="progress-bar">0%</div>
    </div>
    <p id="statusMsg" style="font-size:0.85rem; color:#aaa; margin-top:8px;"></p>

    <!--
    <div id="resultBox" class="result">
        <h4 id="videoTitle"></h4>
        <label for="formatSelect">화질/포맷 선택:</label>
        <select id="formatSelect"></select>
        <button id="downloadBtn" class="download-btn" onclick="downloadVideo()">다운로드 시작</button>
    </div>
    -->

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

        function extractVideoId(url) {
            if (!url) return null;
            // 일반 URL(watch?v=), 단축 URL(youtu.be/), embed URL 등을 모두 지원하는 정규식
            const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
            const match = url.match(regExp);
            return (match && match[2].length === 11) ? match[2] : null;
        }

        function previewUrl() {
            const url = document.getElementById('urlInput').value.trim();
            const videoId = extractVideoId(url);
    
            if (!videoId) {
                alert('올바른 유튜브 URL을 입력해 주세요.');
                return;
            }
    
            const previewContainer = document.getElementById('previewContainer');
            const previewPlayer = document.getElementById('previewPlayer');
    
            // 유튜브 embed URL 설정
            previewPlayer.src = `https://www.youtube.com/embed/${videoId}`;
            previewContainer.style.display = 'block';
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
            if(!url) return alert('URL을 입력해주세요.');
            // const formatId = document.getElementById('formatSelect').value;
            // if(!url || !formatId) return alert('URL과 화질을 선택해주세요.');

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
        'format': 'all',  # [핵심 추가] 특정 포맷을 강제하지 않고 전체 포맷 메타데이터를 추출하도록 설정
        'quiet': True, 
        'no_warnings': True, 
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', '제목 없음')
            formats = info.get('formats', [])
            
            options = []
            for f in formats:
                ext = f.get('ext', '')
                # 스토리보드(sb)나 자막 등 무의미한 포맷 제외
                if ext in ['mhtml', 'vtt'] or f.get('format_note') == 'storyboard':
                    continue

                fid = f.get('format_id')
                
                # resolution 안전 처리
                res = f.get('resolution')
                if not res or res == 'N/A':
                    height = f.get('height')
                    res = f"{height}p" if height else 'N/A'

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

            # 만약 거르고 난 옵션이 없으면 기본 메시지
            if not options:
                options.append({"id": "best", "text": "기본 최적 화질 (best)"})

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
    ffmpeg_bin = os.path.join(os.getcwd(), 'ffmpeg')

    # [수정 부분] 
    # 선택된 format_id가 있는 경우: 해당 format_id에 bestaudio를 병합하거나, 안 될 경우 format_id 단일 다운로드 시도
    # 오디오 전용/단일 통합 스트림(예: 18번) 선택 시에도 안전하게 작동하도록 fallback(/)을 단순하게 작성합니다.
    if format_id:
        selected_format = f"{format_id}+bestaudio/{format_id}/best"
    else:
        selected_format = "bestvideo+bestaudio/best"

    ydl_opts = {
        'format': 'all',
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'ffmpeg_location': ffmpeg_bin if os.path.exists(ffmpeg_bin) else None,
        'progress_hooks': [progress_hook],
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
    }

    try:
        download_progress[task_id] = {'status': 'starting', 'percent': 0}
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
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
