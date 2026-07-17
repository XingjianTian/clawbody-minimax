FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GST_PLUGIN_PATH=/opt/gst-plugins-rs/lib/x86_64-linux-gnu

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ffmpeg \
        git \
        libcairo2-dev \
        libglib2.0-dev \
        libgirepository1.0-dev \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev \
        libgstreamer-plugins-bad1.0-dev \
        libnice10 \
        libssl-dev \
        libportaudio2 \
        pkg-config \
        portaudio19-dev \
        gir1.2-gstreamer-1.0 \
        gir1.2-gst-plugins-base-1.0 \
        gstreamer1.0-alsa \
        gstreamer1.0-nice \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
        gstreamer1.0-tools \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal \
    && . /root/.cargo/env \
    && cargo install cargo-c \
    && git clone --depth 1 --branch 0.14.5 https://github.com/GStreamer/gst-plugins-rs.git /tmp/gst-plugins-rs \
    && cd /tmp/gst-plugins-rs \
    && cargo cinstall -p gst-plugin-webrtc --prefix=/opt/gst-plugins-rs --release \
    && rm -rf /tmp/gst-plugins-rs /root/.cargo /root/.rustup

RUN apt-get update \
    && apt-get install -y --no-install-recommends gstreamer1.0-plugins-bad \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip \
        && pip install . \
    && pip install sounddevice \
    && pip install PyGObject==3.46.0 pycairo pulsectl \
    && pip install reachy_mini==1.8.0 --no-deps \
    && pip install \
        aiohttp \
        asgiref \
        libusb_package \
        log-throttling \
        psutil \
        pyserial \
        pyusb \
        questionary \
        reachy-mini-rust-kinematics \
        reachy_mini_motor_controller \
        rustypot \
        toml \
        tornado \
        zeroconf

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860', timeout=3)"

CMD ["clawbody", "--gradio", "--robot-host", "host.docker.internal", "--robot-port", "8000", "--no-openclaw", "--no-camera", "--no-face-tracking"]
