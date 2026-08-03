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
    .btn-more { 
        background: #333; 
        color: #fff; 
        border: 1px solid #555; 
        width: 100%; 
        padding: 14px; 
        font-size: 1rem; 
        margin-top: 10px; 
        margin-bottom: 30px;
        display: none; 
    }
    .btn-download { background: #28a745; color: white; width: 100%; margin-top: 10px; padding: 12px; font-size: 0.95rem; }

    /* 검색된 영상 카드 목록 */
    .results-container {
        display: flex;
        flex-direction: column;
        gap: 20px;
        margin-bottom: 20px;
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
        background-color: #28a745;
        text-align: center;
        line-height: 22px;
        color: white;
        font-size: 0.8rem;
        font-weight: bold;
        transition: width 0.2s;
    }
</style>
</head>
<body>

    <h2>▶ YouTube Downloader</h2>

    <!-- 1. 키워드 검색 입력 영역 -->
    <div class="search-group">
        <input type="text" id="searchInput" placeholder="검색할 키워드(예: 아이유 노래) 또는 유튜브 URL을 입력하세요" onkeypress="if(event.key==='Enter') searchVideos(true)">
        <button onclick="searchVideos(true)" class="btn btn-search">검색하기</button>
    </div>

    <!-- 2. 진행 상태 및 진행바 -->
    <div id="progressContainer" class="progress-container">
        <div id="progressBar" class="progress-bar">0%</div>
    </div>
    <p id="statusMsg" style="font-size:0.85rem; color:#aaa; margin-top:-5px; margin-bottom:15px; text-align:center;"></p>

    <!-- 3. 검색 결과 영상 카드가 출력될 컨테이너 -->
    <div id="searchResultsContainer" class="results-container"></div>

    <!-- 4. 추가 5개 계속 검색(더보기) 버튼 -->
    <button id="moreBtn" onclick="searchVideos(false)" class="btn btn-more">▼ 계속 검색 (5개 더보기)</button>

<script>
    let currentQuery = '';
    let fetchedCount = 0; // 이미 가져온 영상 수

    // 진행률 표시 업데이트
    function updateProgress(percent, text) {
        const container = document.getElementById('progressContainer');
        const bar = document.getElementById('progressBar');
        const status = document.getElementById('statusMsg');
        
        const roundedPercent = Math.floor(percent / 10) * 10;
        container.style.display = 'block';
        bar.style.width = roundedPercent + '%';
        bar.innerText = roundedPercent + '%';
        status.innerText = text;
    }

    // 유튜브 URL에서 11자리 Video ID 추출
    function extractVideoId(url) {
        if (!url) return null;
        const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
        const match = url.match(regExp);
        return (match && match[2].length === 11) ? match[2] : null;
    }

    // 유튜브 검색 실행 (isNewSearch가 true면 처음부터, false면 더보기)
    async function searchVideos(isNewSearch = true) {
        const queryInput = document.getElementById('searchInput').value.trim();
        if (!queryInput) return alert('검색어를 입력해 주세요.');

        const container = document.getElementById('searchResultsContainer');
        const moreBtn = document.getElementById('moreBtn');

        if (isNewSearch) {
            currentQuery = queryInput;
            fetchedCount = 0;
            container.innerHTML = '<p id="loadingMsg" style="text-align:center; color:#aaa;">관련 영상을 검색 중입니다...</p>';
            moreBtn.style.display = 'none';

            // 단일 URL을 직접 입력한 경우
            const singleVideoId = extractVideoId(currentQuery);
            if (singleVideoId) {
                renderVideoCards([{ id: singleVideoId, title: "입력한 유튜브 영상", url: currentQuery }], true);
                return;
            }
        } else {
            moreBtn.innerText = '검색 중...';
            moreBtn.disabled = true;
        }

        try {
            const res = await fetch('/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    query: currentQuery,
                    offset: fetchedCount,
                    count: 5 
                })
            });
            const data = await res.json();

            // 로딩 메시지 제거
            const loadingMsg = document.getElementById('loadingMsg');
            if (loadingMsg) loadingMsg.remove();

            moreBtn.disabled = false;
            moreBtn.innerText = '▼ 계속 검색 (5개 더보기)';

            if (data.error) {
                alert('검색 중 오류 발생: ' + data.error);
                return;
            }

            if (data.results.length === 0) {
                if (isNewSearch) {
                    container.innerHTML = '<p style="text-align:center; color:#aaa;">검색 결과가 없습니다.</p>';
                } else {
                    alert('더 이상 검색된 결과가 없습니다.');
                    moreBtn.style.display = 'none';
                }
                return;
            }

            fetchedCount += data.results.length;
            renderVideoCards(data.results, isNewSearch);

            // 단일 URL이 아닌 일반 키워드 검색 시에만 계속 검색 버튼 표시
            moreBtn.style.display = 'block';

        } catch (err) {
            alert('검색 요청 실패: ' + err);
            const loadingMsg = document.getElementById('loadingMsg');
            if (loadingMsg) loadingMsg.remove();
        }
    }

    // 영상 카드를 생성해 목록에 누적 추가
    function renderVideoCards(videos, isNewSearch) {
        const container = document.getElementById('searchResultsContainer');
        if (isNewSearch) {
            container.innerHTML = '';
        }

        videos.forEach(video => {
            const card = document.createElement('div');
            card.className = 'video-card';

            card.innerHTML = `
                <h4>${video.title}</h4>
                <div class="player-wrapper">
                    <iframe src="https://www.youtube.com/embed/${video.id}" allowfullscreen></iframe>
                </div>
                <button onclick="downloadStandardVideo('${video.url}')" class="btn btn-download">표준 화질로 바로 다운로드</button>
            `;

            container.appendChild(card);
        });
    }

    // 표준 화질 다운로드 실행
    function downloadStandardVideo(url) {
        if (!url) return alert('유효한 영상 URL이 아닙니다.');

        const downloadId = 'dl_' + Date.now();
        updateProgress(0, "서버에서 다운로드를 준비 중입니다...");

        // SSE를 통한 실시간 진행률 수신
        const eventSource = new EventSource(`/progress/${downloadId}`);

        eventSource.onmessage = function(e) {
            const data = JSON.parse(e.data);
            
            if (data.percent !== undefined) {
                updateProgress(data.percent, `서버에서 영상 다운로드 중...`);
            }

            if (data.status === 'finished') {
                updateProgress(100, "다운로드 완료! 브라우저로 전송 중...");
                eventSource.close();
                window.location.href = `/get_file?task_id=${downloadId}`;
            }

            if (data.error) {
                alert("다운로드 실패: " + data.error);
                eventSource.close();
                document.getElementById('progressContainer').style.display = 'none';
            }
        };

        fetch(`/start_download?task_id=${downloadId}&url=${encodeURIComponent(url)}`);
    }
</script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

# 1. 키워드 페이징 검색 엔드포인트 (offset과 count 사용)
@app.route('/search', methods=['POST'])
def search_youtube():
    data = request.get_json(silent=True) or {}
    query = data.get('query')
    offset = data.get('offset', 0)
    count = data.get('count', 5)

    if not query:
        return jsonify({"error": "검색어를 입력해 주세요."}), 400

    # 요청된 offset + count 만큼 검색하도록 ytsearch 설정
    search_limit = offset + count

    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'web']}}
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{search_limit}:{query}", download=False)
            entries = info.get('entries', [])

            # 전체 결과 중 offset 이후의 항목만 슬라이싱하여 5개 가져오기
            paged_entries = entries[offset:offset + count]

            results = []
            for entry in paged_entries:
                if entry:
                    results.append({
                        "id": entry.get('id'),
                        "title": entry.get('title', '제목 없음'),
                        "url": f"https://www.youtube.com/watch?v={entry.get('id')}"
                    })

            return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# 2. 비동기 표준 화질 다운로드 실행
@app.route('/start_download')
def start_download():
    task_id = request.args.get('task_id')
    url = request.args.get('url')

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

    # 표준 화질(720p 이하 최적 영상+음성) 포맷 설정
    selected_format = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"

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

# 3. SSE (Server-Sent Events) 다운로드 진행률 스트리밍
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

# 4. 완성된 파일 브라우저 전송
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
