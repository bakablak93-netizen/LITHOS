FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System dependencies: FFmpeg, Cairo/Pango (Manim), LaTeX (MathTex), Node.js 20 (Remotion + Web UI), Chromium libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    ffmpeg \
    libcairo2-dev \
    libpango1.0-dev \
    pkg-config \
    python3-dev \
    build-essential \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-lang-cyrillic \
    cm-super \
    dvisvgm \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    fonts-dejavu-core \
    fonts-liberation \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt && rm -f /tmp/requirements.txt

# Remotion dependencies
COPY remotion_studio/package.json ./remotion_studio/package.json
RUN cd remotion_studio && npm install

# Build Web UI
COPY web_ui/package.json ./web_ui/package.json
RUN cd web_ui && npm install
COPY web_ui ./web_ui
RUN cd web_ui && npm run build

# Copy remaining source code
COPY backend ./backend
COPY manim_scenes ./manim_scenes
COPY remotion_studio ./remotion_studio

RUN mkdir -p /app/data/books /app/data/passports /app/outputs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
