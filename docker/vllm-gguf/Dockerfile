ARG BASE_IMAGE=vllm/vllm-openai:v0.31.0
FROM ${BASE_IMAGE}
ARG CUDA_ARCH=8.6
ENV TORCH_CUDA_ARCH_LIST=${CUDA_ARCH} MAX_JOBS=2
# The helper downloads official source and verifies the wheel's PyPI SHA256.
# Copying them first allows the build itself to run without network access.
COPY vendor/ /tmp/inference-build/
RUN uv pip install --system --no-deps /tmp/inference-build/gguf-0.19.0-py3-none-any.whl && \
    mkdir -p /tmp/gguf-plugin && \
    tar -xzf /tmp/inference-build/plugin.tar.gz -C /tmp/gguf-plugin --strip-components=1 && \
    uv pip install --system --no-build-isolation --no-deps /tmp/gguf-plugin && \
    python3 -c "import vllm_gguf_plugin; from vllm_gguf_plugin import _C_gguf; import importlib.metadata as m; assert m.version('vllm') == '0.31.0'; print('GGUF extension import verified')" && \
    rm -rf /tmp/inference-build /tmp/gguf-plugin
LABEL org.opencontainers.image.source="https://github.com/kingbackyang/photo-coach-local-ai" \
      inference.gguf-plugin.commit="e2b8ad532b8b5ea175100202c30430c1d2b5e6a8"
