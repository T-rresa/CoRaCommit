FROM python:3.10-slim

ARG VERSION=2.1.0
ARG VCS_REF=unknown
ARG PRELOAD_EMBEDDING_MODEL=microsoft/codebert-base
# Optional mirrors for networks where the default hosts are slow or blocked.
# GitHub Actions and most CI use the defaults.
#   --build-arg APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn
#   --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
#   --build-arg HF_ENDPOINT=https://hf-mirror.com
ARG APT_MIRROR=
ARG PIP_INDEX_URL=
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG HF_ENDPOINT=https://huggingface.co

LABEL org.opencontainers.image.title="CoRaCommit backend" \
      org.opencontainers.image.description="Retrieval and evaluation backends for CoRaCommit (CodeBERT/FAISS, commit-message metrics)" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/T-rresa/CoRaCommit" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RESOURCE_PATH=/app/resource \
    EMBEDDING_MODEL=codebert \
    HF_HOME=/opt/hf-cache \
    HF_ENDPOINT=${HF_ENDPOINT} \
    HF_HUB_DISABLE_TELEMETRY=1 \
    TOKENIZERS_PARALLELISM=false

RUN if [ -n "${APT_MIRROR}" ]; then \
      for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
        [ -f "$f" ] && sed -i "s|http://deb.debian.org|${APT_MIRROR}|g" "$f"; \
      done; \
    fi \
    && apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./

# torch is installed separately from TORCH_INDEX_URL above, so the
# --extra-index-url line in requirements.txt is redundant here and makes pip
# query an unreachable host on restricted networks. Drop it for the image.
RUN grep -v '^--extra-index-url' requirements.txt > requirements.docker.txt

RUN if [ -n "${PIP_INDEX_URL}" ]; then \
      pip install --no-cache-dir --upgrade pip setuptools wheel --index-url "${PIP_INDEX_URL}" \
      && pip install --no-cache-dir torch==2.11.0 --index-url "${TORCH_INDEX_URL}" \
      && pip install --no-cache-dir -r requirements.docker.txt --index-url "${PIP_INDEX_URL}" --timeout 30 --retries 5; \
    else \
      pip install --no-cache-dir --upgrade pip setuptools wheel \
      && pip install --no-cache-dir torch==2.11.0 --index-url "${TORCH_INDEX_URL}" \
      && pip install --no-cache-dir -r requirements.docker.txt --timeout 30 --retries 5; \
    fi

# Bake the embedding model into the image so the first request does not need
# Hugging Face access. Set PRELOAD_EMBEDDING_MODEL= to skip the download when
# building for an air-gapped mirror that mounts the cache separately.
RUN if [ -n "${PRELOAD_EMBEDDING_MODEL}" ]; then \
      python -c "from transformers import AutoTokenizer, AutoModel; m='${PRELOAD_EMBEDDING_MODEL}'; AutoTokenizer.from_pretrained(m); AutoModel.from_pretrained(m)"; \
    fi

COPY . .

RUN groupadd --gid 10001 coracommit \
    && useradd --uid 10001 --gid coracommit --no-create-home --shell /usr/sbin/nologin coracommit \
    && mkdir -p /opt/hf-cache \
    && chown -R coracommit:coracommit /app /opt/hf-cache

USER coracommit

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]