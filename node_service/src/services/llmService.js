// node_service/src/services/llmService.js
const { AVAILABLE_MODELS } = require('../config/settings');
const modelRegistryService = require('./modelRegistryService');
const logger = require('./loggerService');
const OpenAIProvider = require('../strategies/llm/OpenAIProvider');

class LLMService {
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

    async generate(prompt, modelName, apiKey) {
        if (!apiKey) {
            throw new Error("API Key is missing.");
        }

        const modelInfo = await modelRegistryService.getModelByName(modelName) || AVAILABLE_MODELS.find(m => m.name === modelName);
        if (!modelInfo) {
            throw new Error(`Unknown model: ${modelName}`);
        }

        // Each model talks to its own provider endpoint directly.
        const provider = new OpenAIProvider(modelInfo.base_url);
        return provider.generate(prompt, modelName, apiKey);
    }

    /**
     * Batch generate suggestions using multiple models/prompts
     * @param {Array} tasks - Array of { prompt, modelName, apiKey }
     * @returns {Promise<Array>} Array of { model, message, status, error? }
     */
    async generateBatch(tasks) {
        return await Promise.all(tasks.map(async (task) => {
            const startTime = Date.now();
            try {
                const message = task.mockLLM
                    ? await this.generateMock(task)
                    : await this.generate(task.prompt, task.modelName, task.apiKey);
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
