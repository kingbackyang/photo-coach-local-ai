param(
    [string]$ModelRoot = 'C:\AIModels',
    [string]$CacheRoot = 'E:\Docker\huggingface',
    [string]$Image = 'local/vllm-gguf:qwen38-e2b8ad5',
    [string]$Docker = 'docker'
)
$ErrorActionPreference = 'Stop'
$modelFile = Join-Path $ModelRoot 'Qwen3.8-27B-GGUF\Qwen3.8-27B-UD-Q4_K_M.gguf'
foreach ($path in @($modelFile, (Join-Path $ModelRoot 'Qwen3.8-27B-GGUF\mmproj-BF16.gguf'), (Join-Path $ModelRoot 'Qwen3.8-27B-config\tokenizer.json'))) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required model file missing: $path" }
}
& $Docker container inspect vllm-qwen38-27b *> $null
if ($LASTEXITCODE -eq 0) { throw 'Container already exists. Use docker start vllm-qwen38-27b; this script never replaces an existing container.' }
New-Item -ItemType Directory -Force -Path $CacheRoot | Out-Null
& $Docker run --detach --name vllm-qwen38-27b --restart unless-stopped --gpus all --ipc host `
    --publish '127.0.0.1:8000:8000' `
    --mount "type=bind,source=$ModelRoot,target=/models,readonly" `
    --mount "type=bind,source=$CacheRoot,target=/root/.cache/huggingface" `
    --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 --env VLLM_NO_USAGE_STATS=1 `
    $Image /models/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf `
    --tokenizer /models/Qwen3.8-27B-config --hf-config-path /models/Qwen3.8-27B-config `
    --served-model-name qwen3.8-27b --host 0.0.0.0 --port 8000 `
    --max-model-len 2048 --max-num-seqs 1 --gpu-memory-utilization 0.90 --enforce-eager --language-model-only
if ($LASTEXITCODE -ne 0) { throw 'Model container creation failed' }
