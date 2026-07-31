"""
All 30 free text-generation API provider configurations.
OpenAI-compatible = same /v1/chat/completions endpoint, just swap base_url + api_key.
"""

PROVIDERS = [
    # =========================================================================
    # S-TIER — Massive Throughput
    # =========================================================================
    {
        "name": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "api_key_env": "MISTRAL_API_KEY",
        "model": "mistral-small-latest",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "S",
        "notes": "Free Experiment plan. Phone verification required.",
    },
    {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key_env": "GOOGLE_API_KEY",
        "model": "gemini-2.5-flash",
        "openai_compatible": False,  # Uses Gemini API format
        "auth_required": True,
        "tier": "S",
        "notes": "Not available in EU/UK/CH. Data used for training.",
    },
    {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "model": "llama-3.1-8b-instant",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "S",
        "notes": "Ultra-fast LPU inference. 14,400 RPD on 8B model.",
    },
    {
        "name": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_API_KEY",
        "model": "nvidia/nemotron-3-nano-30b-a3b",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "S",
        "notes": "Free with NVIDIA Developer account. No daily token cap.",
    },
    {
        "name": "AINative Studio",
        "base_url": "https://api.ainative.studio/v1",
        "api_key_env": "AINATIVE_API_KEY",
        "model": "deepseek-chat",  # placeholder — verify actual model ID
        "openai_compatible": True,
        "auth_required": True,
        "tier": "S",
        "notes": "10M tokens/month, 84+ models, 60 RPM.",
    },

    # =========================================================================
    # A-TIER — Strong Throughput
    # =========================================================================
    {
        "name": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "api_key_env": "CEREBRAS_API_KEY",
        "model": "gpt-oss-120b",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "A",
        "notes": "1M tokens/day. Payment method required for free tier.",
    },
    {
        "name": "Cloudflare Workers AI",
        "base_url": "https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run",
        "api_key_env": "CLOUDFLARE_API_TOKEN",
        "account_id_env": "CLOUDFLARE_ACCOUNT_ID",
        "model": "@cf/meta/llama-3.1-8b-instruct",
        "openai_compatible": False,  # Custom Cloudflare endpoint
        "auth_required": True,
        "tier": "A",
        "notes": "10,000 neurons/day. Needs account_id in URL.",
    },
    {
        "name": "GitHub Models",
        "base_url": "https://models.github.ai/inference",
        "api_key_env": "GITHUB_TOKEN",
        "model": "gpt-4o-mini",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "A",
        "notes": "Free for all GitHub users. Per-request: 8K in / 4K out.",
    },
    {
        "name": "Hugging Face",
        "base_url": "https://router.huggingface.co/v1",
        "api_key_env": "HF_TOKEN",
        "model": "meta-llama/Llama-3.1-8B-Instruct",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "A",
        "notes": "~$0.10/month in free credits.",
    },
    {
        "name": "Cohere",
        "base_url": "https://api.cohere.com/v2",
        "api_key_env": "COHERE_API_KEY",
        "model": "command-r7b-12-2024",
        "openai_compatible": False,  # Uses Cohere SDK/REST format
        "auth_required": True,
        "tier": "A",
        "notes": "1,000 req/month free trial. Non-commercial only.",
    },

    # =========================================================================
    # B-TIER — Moderate Throughput
    # =========================================================================
    {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "model": "openai/gpt-oss-20b:free",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "B",
        "notes": "22+ free models. 50 RPD (1,000 with $10 top-up).",
    },
    {
        "name": "SambaNova",
        "base_url": "https://api.sambanova.ai/v1",
        "api_key_env": "SAMBANOVA_API_KEY",
        "model": "Meta-Llama-3.3-70B-Instruct",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "B",
        "notes": "20 RPM, 200K TPD. $5 credits (30 days).",
    },
    {
        "name": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key_env": "SILICONFLOW_API_KEY",
        "model": "Qwen/Qwen3-8B",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "B",
        "notes": "30 RPM, 60K TPM. Permanently free.",
    },
    {
        "name": "LLM7.io",
        "base_url": "https://api.llm7.io/v1",
        "api_key_env": "LLM7_API_KEY",
        "model": "mistral-small-3.1-24b",
        "openai_compatible": True,
        "auth_required": False,  # No registration for basic access
        "tier": "B",
        "notes": "30 RPM anonymous, 120 RPM with token.",
    },
    {
        "name": "Kilo Gateway",
        "base_url": "https://api.kilo.ai/api/gateway",
        "api_key_env": None,
        "model": "kilo-auto/free",
        "openai_compatible": True,
        "auth_required": False,  # No account needed
        "tier": "B",
        "notes": "200 req/hr per IP. Auto-routing to best free model.",
    },
    {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-chat",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "B",
        "notes": "5M tokens one-time for new users.",
    },
    {
        "name": "ModelScope",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "api_key_env": "MODELSCOPE_API_KEY",
        "model": "Qwen/Qwen3.5-35B-A3B",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "B",
        "notes": "2,000 RPD. Requires Alibaba Cloud + real-name verification.",
    },

    # =========================================================================
    # C-TIER — Useful Supplement
    # =========================================================================
    {
        "name": "OVHcloud",
        "base_url": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
        "api_key_env": None,
        "model": "Qwen3.5-9B",
        "openai_compatible": True,
        "auth_required": False,  # NO API key, NO signup
        "tier": "C",
        "notes": "2 RPM per model. EU-hosted, GDPR compliant.",
    },
    {
        "name": "AnyAPI",
        "base_url": "https://api.anyapi.ai/v1",
        "api_key_env": "ANYAPI_API_KEY",
        "model": "gpt-4o-mini",  # placeholder — verify actual model ID
        "openai_compatible": True,
        "auth_required": True,
        "tier": "C",
        "notes": "100K tokens/day, 400+ models.",
    },
    {
        "name": "FreeTheAi",
        "base_url": "https://api.freetheai.com/v1",  # verify actual URL
        "api_key_env": "FREETHEAI_API_KEY",
        "model": "gpt-4o-mini",  # placeholder
        "openai_compatible": True,
        "auth_required": True,
        "tier": "C",
        "notes": "30 RPM, no daily cap. Discord signup.",
    },
    {
        "name": "Requesty",
        "base_url": "https://api.requesty.ai/v1",  # verify actual URL
        "api_key_env": "REQUESTY_API_KEY",
        "model": "gpt-4o-mini",  # placeholder
        "openai_compatible": True,
        "auth_required": True,
        "tier": "C",
        "notes": "200 requests/day. Claude Code compatible.",
    },
    {
        "name": "LongCat AI",
        "base_url": "https://api.longcat.ai/v1",  # verify actual URL
        "api_key_env": "LONGCAT_API_KEY",
        "model": "longcat-chat",  # placeholder
        "openai_compatible": True,
        "auth_required": True,
        "tier": "C",
        "notes": "10M token one-time grant. KYC required.",
    },
    {
        "name": "Chat Oripe",
        "base_url": "https://api.chatoripe.com/v1",  # verify actual URL
        "api_key_env": "CHATORIPE_API_KEY",
        "model": "gpt-4o-mini",  # placeholder
        "openai_compatible": True,
        "auth_required": True,
        "tier": "C",
        "notes": "2M tokens/month. GPT-4 + Claude access.",
    },
    {
        "name": "BazaarLink",
        "base_url": "https://api.bazaarlink.ai/v1",  # verify actual URL
        "api_key_env": "BAZAARLINK_API_KEY",
        "model": "auto:free",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "C",
        "notes": "130 req/day, 10 RPM. Auto-routing.",
    },
    {
        "name": "ZeroLimitAI",
        "base_url": "https://api.zerolimit.ai/v1",  # verify actual URL
        "api_key_env": "ZEROLIMIT_API_KEY",
        "model": "auto",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "C",
        "notes": "Lifetime free. Auto-routing.",
    },
    {
        "name": "Free.ai",
        "base_url": "https://api.free.ai/v1",  # verify actual URL
        "api_key_env": "FREEAI_API_KEY",
        "model": "auto",  # placeholder
        "openai_compatible": True,
        "auth_required": True,
        "tier": "C",
        "notes": "30K tokens/day. 400+ tools.",
    },
    {
        "name": "Ollama Cloud",
        "base_url": "https://api.ollama.com",
        "api_key_env": "OLLAMA_API_KEY",
        "model": "llama3.1:8b",
        "openai_compatible": False,  # Uses Ollama native API
        "auth_required": True,
        "tier": "C",
        "notes": "Not OpenAI-compatible. Session + weekly limits.",
    },
    {
        "name": "Z AI (Zhipu)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_env": "ZHIPU_API_KEY",
        "model": "glm-4-flash",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "C",
        "notes": "Free, no credit card. 1 concurrent request.",
    },
    {
        "name": "Aion Labs",
        "base_url": "https://api.aionlabs.ai/v1",
        "api_key_env": "AION_API_KEY",
        "model": "Aion-3.0",
        "openai_compatible": True,
        "auth_required": True,
        "tier": "C",
        "notes": "15 RPM, 20K tokens/day. Roleplay/storytelling focus.",
    },
    {
        "name": "Chutes.ai",
        "base_url": "https://api.chutes.ai/v1",  # verify actual URL
        "api_key_env": "CHUTES_API_KEY",
        "model": "deepseek-r1",  # placeholder
        "openai_compatible": True,
        "auth_required": True,
        "tier": "C",
        "notes": "Community-powered GPU. Variable limits.",
    },
]


def get_noauth_providers():
    """Providers that can be tested without any API key."""
    return [p for p in PROVIDERS if not p["auth_required"]]


def get_openai_compatible():
    """Providers using standard OpenAI SDK /v1/chat/completions format."""
    return [p for p in PROVIDERS if p["openai_compatible"]]


def get_by_tier(tier: str):
    """Get all providers in a given tier."""
    return [p for p in PROVIDERS if p["tier"] == tier.upper()]


def get_provider(name: str):
    """Get a single provider by name."""
    for p in PROVIDERS:
        if p["name"].lower() == name.lower():
            return p
    return None
