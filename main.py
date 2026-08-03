from flask import Flask, render_template_string, request, jsonify, send_file, Response
import yt_dlp
import os
import tempfile
import json
import time

app = Flask(__name__)

# 각 다운로드 작업의 진행 상황을 저장할 딕셔너리
download_progress = {}

# HTML / CSS / JS 템플릿
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
        max-width: 680px;
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

    /* 검색 입력창 영역 */
    .search-group {
        display: flex;
        gap: 8px;
        margin-bottom: 25px;
    }

    .search-group input {
        flex: 1;
        padding: 12px;
        border: 1px solid #333;
        border-radius: 6px;
        background: #1e1e1e;
        color: #fff;
        font-size: 0.95rem;
        outline: none;
    }

    .search-group input:focus {
        border-color: #ff4757;
    }

    .btn {
        padding: 10px 18px;
        border: none;
        border-radius: 6px;
        font-weight: bold;
        cursor: pointer;
        white-space: nowrap;
        transition: opacity 0.2s;
    }

    .btn:hover { opacity: 0.85; }
    .btn-search { background: #ff4757; color: white; }
    .btn-analyze { background: #007bff; color: white; width: 100%; margin-top: 10px; padding: 10px; }
    .btn-download { background: #28a745; color: white; width: 100%; margin-top: 15px; padding: 12px; font-size: 1rem; }

    /* 검색된 영상 카드 목록 */
    .results-container {
        display: flex;
        flex-direction: column;
        gap: 20px;
        margin-bottom: 25px;
    }

    .video-card {
        background: #1e1e1e;
        border-radius: 8px;
        padding: 15px;
        border: 1px solid #2a2a2a;
    }

    .video-card h4 {
        margin-top: 0;
        margin-bottom: 12px;
        color: #fff;
        font-size: 1rem;
        word-break: break-all;
    }

    .video-card .player-wrapper {
        background: #000;
        border-radius: 6px;
        overflow: hidden;
        margin-bottom: 12px;
    }

    .video-card iframe {
        width: 100%;
        height: 300px;
        border: none;
        display: block;
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

    /* 화질 분석 및 다운로드 상자 */
    .analysis-box {
        display: none;
        padding: 20px;
        background: #1e1e1e;
        border-radius: 8px;
        border: 1px solid #007bff;
        margin-top: 20px;
        margin-bottom: 25px;
    }

    .analysis-box h4 {
        margin-top: 0;
        margin-bottom: 15px;
        font-size: 1.1rem;
        color: #f1f1f1;
        word-break: break-all;
    }

    .analysis-box label {
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

    <!-- 1. 키워드 검색 입력 영역 -->
    <div class="search-group">
        <input type="text" id="searchInput" placeholder="검색할 키워드(예: 아이유 노래) 또는 유튜브 URL을 입력하세요" onkeypress="if(event.key==='Enter') searchVideos()">
        <button onclick="searchVideos()" class="btn btn-search">검색하기</button>
    </div>

    <!-- 2. 진행 상태 및 진행바 -->
    <div id="progressContainer" class="progress-container">
        <div id="progressBar" class="progress-bar">0%</div>
    </div>
    <p id="statusMsg" style="font-size:0.85rem; color:#aaa; margin-top:-5px; margin-bottom:15px; text-align:center;"></p>

    <!-- 3. 선택한 영상 분석 및 화질 선택 상자 -->
    <div id="analysisBox" class="analysis-box">
        <h4 id="targetTitle"></h4>
        <input type="hidden" id="targetUrl">
        <label for="formatSelect">화질/포맷 선택</label>
        <select id="formatSelect"></select>
        <button id="downloadBtn" class="btn btn-download" onclick="downloadVideo()">다운로드 시작</button>
    </div>

    <!-- 4. 검색 결과 영상 카드가 출력될 컨테이너 -->
    <div id="searchResultsContainer" class="results-container"></div>

<script>
    // 진행률 표시 업데이트
    function updateProgress(percent, text, isDownload = false) {
        const container = document.getElementById('progressContainer');
        const bar = document.getElementById('progressBar');
        const status = document.getElementById('statusMsg');
        
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

    // 유튜브 URL에서 11자리 Video ID 추출
    function extractVideoId(url) {
        if (!url) return null;
        const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
        const match = url.match(regExp);
        return (match && match[2].length === 11) ? match[2] : null;
    }

    // 유튜브 검색 실행
    async function searchVideos() {
        const query = document.getElementById('searchInput').value.trim();
        if (!query) return alert('검색어를 입력해 주세요.');

        const container = document.getElementById('searchResultsContainer');
        document.getElementById('analysisBox').style.display = 'none'; // 이전 분석 상자 숨김
        container.innerHTML = '<p style="text-align:center; color:#aaa;">관련 영상을 검색 중입니다...</p>';

        // 단일 URL을 직접 입력한 경우
        const singleVideoId = extractVideoId(query);
        if (singleVideoId) {
            renderVideoCards([{ id: singleVideoId, title: "입력한 유튜브 영상", url: query }]);
            return;
        }

        try {
            const res = await fetch('/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query })
            });
            const data = await res.json();

            if (data.error) {
                alert('검색 중 오류 발생: ' + data.error);
                container.innerHTML = '';
                return;
            }

            renderVideoCards(data.results);
        } catch (err) {
            alert('검색 요청 실패: ' + err);
            container.innerHTML = '';
        }
    }

    // 검색된 상위 5개 영상 미리보기 카드 생성
    function renderVideoCards(videos) {
        const container = document.getElementById('searchResultsContainer');
        container.innerHTML = '';

        if (!videos || videos.length === 0) {
            container.innerHTML = '<p style="text-align:center; color:#aaa;">검색 결과가 없습니다.</p>';
            return;
        }

        videos.forEach(video => {
            const card = document.createElement('div');
            card.className = 'video-card';

            card.innerHTML = `
                <h4>${video.title}</h4>
                <div class="player-wrapper">
                    <iframe src="https://www.youtube.com/embed/${video.id}" allowfullscreen></iframe>
                </div>
                <button onclick="analyzeSelectedVideo('${video.url}')" class="btn btn-analyze">이 영상 분석 및 다운로드</button>
            `;

            container.appendChild(card);
        });
    }

    // [이 영상 분석 및 다운로드] 버튼 클릭 시 동작
    async function analyzeSelectedVideo(url) {
        document.getElementById('targetUrl').value = url;
        updateProgress(10, "선택한 영상의 화질 정보를 분석 중입니다...");

        try {
            const res = await fetch('/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                cache: 'no-cache',
                body: JSON.stringify({url: url})
            });

            const data = await res.json();

            if(data.error) {
                alert('분석 오류: ' + data.error);
                document.getElementById('progressContainer').style.display = 'none';
                return;
            }

            updateProgress(100, "분석 완료!");
            document.getElementById('targetTitle').innerText = data.title;

            const select = document.getElementById('formatSelect');
            select.innerHTML = '';

            data.formats.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f.id;
                opt.innerText = f.text;
                select.appendChild(opt);
            });

            const analysisBox = document.getElementById('analysisBox');
            analysisBox.style.display = 'block';
            analysisBox.scrollIntoView({ behavior: 'smooth' });

            setTimeout(() => {
                document.getElementById('progressContainer').style.display = 'none';
                document.getElementById('statusMsg').innerText = "";
            }, 1500);

        } catch (err) {
            alert('분석 요청에 실패했습니다: ' + err);
            document.getElementById('progressContainer').style.display = 'none';
        }
    }

    // 다운로드 실행
    function downloadVideo() {
        const url = document.getElementById('targetUrl').value;
        const formatId = document.getElementById('formatSelect').value;

        if (!url || !formatId) return alert('유효한 영상 정보를 먼저 분석해 주세요.');

        const downloadId = 'dl_' + Date.now();
        updateProgress(0, "서버에서 다운로드를 준비 중입니다...", true);

        // SSE를 통한 실시간 진행률 수신
        const eventSource = new EventSource(`/progress/${downloadId}`);

        eventSource.onmessage = function(e) {
            const data = JSON.parse(e.data);
            
            if (data.percent !== undefined) {
                updateProgress(data.percent, `서버에서 영상 다운로드 중...`, true);
            }

            if (data.status === 'finished') {
                updateProgress(100, "다운로드 완료! 브라우저로 전송 중...", true);
                eventSource.close();
                window.location.href = `/get_file?task_id=${downloadId}`;
            }

            if (data.error) {
                alert("다운로드 실패: " + data.error);
                eventSource.close();
                document.getElementById('progressContainer').style.display = 'none';
            }
        };

        fetch(`/start_download?task_id=${downloadId}&url=${encodeURIComponent(url)}&format_id=${encodeURIComponent(formatId)}`);
    }
</script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

# 1. 키워드 검색 엔드포인트 (상위 5개 추출)
@app.route('/search', methods=['POST'])
def search_youtube():
    data = request.get_json(silent=True)
    query = data.get('query') if data else None

    if not query:
        return jsonify({"error": "검색어를 입력해 주세요."}), 400

    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'web']}}
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            entries = info.get('entries', [])

            results = []
            for entry in entries:
                if entry:
                    results.append({
                        "id": entry.get('id'),
                        "title": entry.get('title', '제목 없음'),
                        "url": f"https://www.youtube.com/watch?v={entry.get('id')}"
                    })

            return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# 2. 선택한 영상의 화질/포맷 분석 엔드포인트
@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json(silent=True)
    if not data or 'url' not in data:
        return jsonify({"error": "유효한 URL 데이터가 전달되지 않았습니다."}), 400

    url = data.get('url')

    ydl_opts = {
        'format': 'all',
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'web']}}
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', '제목 없음')
            formats = info.get('formats', [])

            options = []
            for f in formats:
                ext = f.get('ext', '')
                if ext in ['mhtml', 'vtt'] or f.get('format_note') == 'storyboard':
                    continue

                fid = f.get('format_id')
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

            if not options:
                options.append({"id": "best", "text": "기본 최적 화질 (best)"})

            return jsonify({"title": title, "formats": options})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# 3. 비동기 다운로드 실행
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

    if format_id:
        selected_format = f"{format_id}+bestaudio/{format_id}/best"
    else:
        selected_format = "bestvideo+bestaudio/best"

    ydl_opts = {
        'format': selected_format,
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'ffmpeg_location': ffmpeg_bin if os.path.exists(ffmpeg_bin) else None,
        'progress_hooks': [progress_hook],
        'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'web']}}
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

# 4. SSE (Server-Sent Events) 다운로드 진행률 스트리밍
@app.route('/progress/<task_id>')
def progress(task_id):
    def generate():
        while True:
            if task_id in download_progress:
                data = download_progress[task_id]
                yield f"data: {json.dumps(data)}\n\n"
                if data.get('status') == 'finished' or 'error' in data:
                    break
            time.sleep(0.5)
    return Response(generate(), mimetype='text/event-stream')

# 5. 완성된 파일 브라우저 전송
@app.route('/get_file')
def get_file():
    task_id = request.args.get('task_id')
    if task_id in download_progress and 'filepath' in download_progress[task_id]:
        file_path = download_progress[task_id]['filepath']
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
    return "파일을 찾을 수 없습니다.", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
