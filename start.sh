#!/bin/bash
set -e

FFBIN="/tmp/ffmpeg-bin"

if [ ! -f "$FFBIN/ffmpeg" ]; then
    echo "Downloading ffmpeg..."
    mkdir -p "$FFBIN"
    curl -sL "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" -o /tmp/ff.tar.xz
    cd /tmp && tar xf ff.tar.xz
    mv /tmp/ffmpeg-*-static/ffmpeg /tmp/ffmpeg-*-static/ffprobe "$FFBIN/" 2>/dev/null || true
    rm -rf /tmp/ff.tar.xz /tmp/ffmpeg-*-static
    echo "ffmpeg: $FFBIN/ffmpeg"
fi

export PATH="$FFBIN:$PATH"

# Find uvicorn in the virtualenv or system
UVICORN=$(which uvicorn 2>/dev/null || find / -name uvicorn -type f 2>/dev/null | head -1)
echo "Using uvicorn: $UVICORN"
exec $UVICORN backend.main:app --host 0.0.0.0 --port 8000
