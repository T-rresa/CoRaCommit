// node_service/src/config/settings.js
require('dotenv').config();

const AVAILABLE_MODELS = [
  { name: "gpt-4o", description: "OpenAI GPT-4o", available: true, family: "gpt", base_url: "https://api.openai.com/v1" },
  { name: "gpt-4", description: "OpenAI GPT-4", available: true, family: "gpt", base_url: "https://api.openai.com/v1" },
  { name: "gpt-3.5-turbo", description: "OpenAI GPT-3.5", available: true, family: "gpt", base_url: "https://api.openai.com/v1" },
  { name: "qwen-plus", description: "Qwen Plus (Aliyun)", available: true, family: "qwen", base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1" },
  { name: "qwen-max", description: "Qwen Max (Aliyun)", available: true, family: "qwen", base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1" },
  { name: "deepseek-chat", description: "Deepseek Chat", available: true, family: "deepseek", base_url: "https://api.deepseek.com" }
];

const AVAILABLE_TEMPLATES = [
  { name: "conventional", description: "Conventional Commit message style" },
  { name: "angular", description: "Angular commit style" },
  { name: "emoji", description: "Emoji-based commit style" }
];

const AVAILABLE_LANGUAGES = [
  { code: "en", name: "English" },
  { code: "zh-cn", name: "Chinese (Simplified)" },
  { code: "ja", name: "Japanese" },
  { code: "ru", name: "Russian" },
  { code: "de", name: "German" },
  { code: "fr", name: "French" },
  { code: "es", name: "Spanish" },
  { code: "pt", name: "Portuguese" },
  { code: "it", name: "Italian" },
  { code: "ko", name: "Korean" }
];

const CLOSE_AI_CONFIG = {
  base_urls: {
    gpt: "https://api.openai-proxy.org/v1",
    gemini: "https://api.openai-proxy.org/v1", // Example, adjust as needed
    claude: "https://api.openai-proxy.org/v1", // Example
    deepseek: "https://api.deepseek.com", // Usually direct or specific proxy
    qwen: "https://dashscope.aliyuncs.com/compatible-mode/v1" // Usually direct
  }
};

const RETRIEVAL_BACKEND_URL = process.env.RETRIEVAL_BACKEND_URL || process.env.BACKEND_URL || "http://localhost:8000";
const EVALUATION_BACKEND_URL = process.env.EVALUATION_BACKEND_URL || process.env.BACKEND_URL || "http://localhost:8001";
const EVAL_WORKER_CONCURRENCY = parseInt(process.env.EVAL_WORKER_CONCURRENCY || "1", 10);
const EVAL_JOB_DELAY_MS = parseInt(process.env.EVAL_JOB_DELAY_MS || "300000", 10);
const EVAL_BUSY_CHECK_INTERVAL_MS = parseInt(process.env.EVAL_BUSY_CHECK_INTERVAL_MS || "15000", 10);
const EVAL_CPU_THRESHOLD = parseFloat(process.env.EVAL_CPU_THRESHOLD || "0.75");
const ONLINE_ACTIVE_REQUEST_KEY = process.env.ONLINE_ACTIVE_REQUEST_KEY || "system:active_generation_requests";
const ONLINE_BUSY_FLAG_KEY = process.env.ONLINE_BUSY_FLAG_KEY || "system:busy";
const ONLINE_BUSY_TTL_SECONDS = parseInt(process.env.ONLINE_BUSY_TTL_SECONDS || "30", 10);
const MODEL_SCORE_UPDATE_STRATEGY = process.env.MODEL_SCORE_UPDATE_STRATEGY || "global_ema";
const MODEL_SCORE_EMA_ALPHA = parseFloat(process.env.MODEL_SCORE_EMA_ALPHA || "0.1");
const ALLOW_MOCK_LLM = String(process.env.ALLOW_MOCK_LLM || "false").toLowerCase() === "true";

module.exports = {
  AVAILABLE_MODELS,
  AVAILABLE_TEMPLATES,
  AVAILABLE_LANGUAGES,
  CLOSE_AI_CONFIG,
  RETRIEVAL_BACKEND_URL,
  EVALUATION_BACKEND_URL,
  EVAL_WORKER_CONCURRENCY,
  EVAL_JOB_DELAY_MS,
  EVAL_BUSY_CHECK_INTERVAL_MS,
  EVAL_CPU_THRESHOLD,
  ONLINE_ACTIVE_REQUEST_KEY,
  ONLINE_BUSY_FLAG_KEY,
  ONLINE_BUSY_TTL_SECONDS,
  MODEL_SCORE_UPDATE_STRATEGY,
  MODEL_SCORE_EMA_ALPHA,
  ALLOW_MOCK_LLM
};
