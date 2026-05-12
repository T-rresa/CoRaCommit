// node_service/src/services/llmService.js
const { AVAILABLE_MODELS, CLOSE_AI_CONFIG } = require('../config/settings');
const modelRegistryService = require('./modelRegistryService');
const logger = require('./loggerService');
const OpenAIProvider = require('../strategies/llm/OpenAIProvider');
const CloseAIProvider = require('../strategies/llm/CloseAIProvider');

class LLMService {
    constructor() {
        this.closeAIProvider = new CloseAIProvider(CLOSE_AI_CONFIG);
    }

    buildMockMessage(task) {
        const prompt = typeof task.prompt === 'string' ? task.prompt : '';
        const normalized = prompt.replace(/\s+/g, ' ').trim();
        const preview = normalized.slice(0, 80) || 'mock commit message';
        return `[MOCK:${task.modelName}] ${preview}`;
    }

    async generateMock(task) {
        const latencyMs = Number.isFinite(task.mockLatencyMs) ? Math.max(0, task.mockLatencyMs) : 0;
        if (latencyMs > 0) {
            await new Promise(resolve => setTimeout(resolve, latencyMs));
        }
        return this.buildMockMessage(task);
    }

    async generate(prompt, modelName, apiKey, useCloseAI = false) {
        if (!apiKey) {
            throw new Error("API Key is missing.");
        }

        const modelInfo = await modelRegistryService.getModelByName(modelName) || AVAILABLE_MODELS.find(m => m.name === modelName);
        if (!modelInfo) {
            throw new Error(`Unknown model: ${modelName}`);
        }

        if (useCloseAI) {
            const family = modelInfo.family || 'gpt';
            return this.closeAIProvider.generate(prompt, modelName, apiKey, family);
        } else {
            // For standard usage, we create a provider with the model's specific base_url
            const provider = new OpenAIProvider(modelInfo.base_url);
            return provider.generate(prompt, modelName, apiKey);
        }
    }

    /**
     * Batch generate suggestions using multiple models/prompts
     * @param {Array} tasks - Array of { prompt, modelName, apiKey, useCloseAI? }
     * @returns {Promise<Array>} Array of { model, message, status, error? }
     */
    async generateBatch(tasks) {
        return await Promise.all(tasks.map(async (task) => {
            const startTime = Date.now();
            try {
                const message = task.mockLLM
                    ? await this.generateMock(task)
                    : await this.generate(task.prompt, task.modelName, task.apiKey, task.useCloseAI);
                const duration = Date.now() - startTime;
                return { model: task.modelName, message, status: 'success', duration };
            } catch (err) {
                const duration = Date.now() - startTime;
                return { model: task.modelName, error: err.message, status: 'error', duration };
            }
        }));
    }
}

module.exports = LLMService;
