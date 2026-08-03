#!/usr/bin/env bash
# exit on error
set -o errexit

# 파이썬 패키지 설치
pip install -r requirements.txt

# ffmpeg 바이너리 다운로드 및 압축 해제
mkdir -p ffmpeg
cd ffmpeg
curl -L -O https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar -xf ffmpeg-release-amd64-static.tar.xz --strip-components=1
cd ..

# 환경 변수 PATH에 ffmpeg 경로 추가
export PATH=$PATH:$(pwd)/ffmpeg