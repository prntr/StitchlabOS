# Linux environment for the Klipper drift check (make klipper-drift):
# klippy in batch mode needs Linux (chelper), and the SKR Pico's data
# dictionary needs an rp2040 firmware build. Debian trixie = the image's OS.
FROM debian:trixie-slim
RUN apt-get update -qq \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
      git ca-certificates build-essential libffi-dev python3 python3-dev \
      gcc-arm-none-eabi libnewlib-arm-none-eabi binutils-arm-none-eabi \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /drift
