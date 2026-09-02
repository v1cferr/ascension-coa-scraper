# The Python service: scraper, client extractor, spellbook and the viewer's API.
#
# StormLib is built from source rather than pulled from a distro, because it is the one
# dependency whose absence turns every MPQ read into a confusing failure, and pinning
# the tag here keeps a container and a `nix develop` shell reading the same archives
# the same way.
FROM python:3.13-slim AS stormlib

ARG STORMLIB_TAG=v9.30
RUN apt-get update && apt-get install -y --no-install-recommends \
        git cmake g++ make zlib1g-dev libbz2-dev \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "${STORMLIB_TAG}" \
        https://github.com/ladislav-zezula/StormLib.git /src \
    && cmake -S /src -B /build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON \
    && cmake --build /build --parallel \
    && cmake --install /build --prefix /out


FROM python:3.13-slim

# Pillow's wheels need these at load time; it decodes the client's BLP textures.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo zlib1g libwebp7 libtiff6 libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=stormlib /out/lib/ /usr/local/lib/
RUN ldconfig
ENV ASCENSION_STORMLIB=/usr/local/lib/libstorm.so

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
# Dependencies first, so editing the source does not re-resolve them.
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
RUN uv sync --frozen --extra assets --no-dev

ENV PATH="/app/.venv/bin:${PATH}"
EXPOSE 8000

# --lan binds every interface, which inside a container means the compose network.
# What it exposes to is decided by the port mapping, not here.
CMD ["ascension-coa", "serve", "--lan", "--port", "8000", "--root", "/data"]
