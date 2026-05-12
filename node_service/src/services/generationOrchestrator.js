const logger = require('./loggerService');

class GenerationOrchestrator {
    constructor(exampleService, promptService, llmService) {
        this.exampleService = exampleService;
        this.promptService = promptService;
        this.llmService = llmService;
    }

    async generate(options) {
        const {
            diff,
            models,
            template,
            language,
            format,
            templateText,
            manualExamples,
            useCloseAI,
            closeAiKey,
            userId,
            requestId,
            mockLLM,
            mockLatencyMs
        } = options;

        // 1. Get Examples
        const examples = await this.exampleService.getExamples(diff, manualExamples, userId);

        // 2. Prepare Tasks
        // Determine target models list
        let targetModels = [];
        if (Array.isArray(models) && models.length > 0) {
            targetModels = models;
        } else {
            // Default model if none specified
            targetModels = [{ name: 'gpt-4o', apiKey: '' }];
        }

        // Build prompts for each model
        const tasks = await Promise.all(targetModels.map(async model => {
            const { prompt, modelFamily } = await this.promptService.build(diff, examples, {
                modelName: model.name,
                format,
                template,
                templateText,
                language
            });

            let finalApiKey = model.apiKey;
            if (useCloseAI && closeAiKey) {
                finalApiKey = closeAiKey;
            }

            return {
                prompt,
                modelName: model.name,
                apiKey: finalApiKey,
                modelFamily,
                useCloseAI: useCloseAI,
                mockLLM: !!mockLLM,
                mockLatencyMs
            };
        }));

        // 3. Generate
        const results = await this.llmService.generateBatch(tasks);

        // Log Results
        logger.info('Generation Completed', {
            request_id: requestId,
            results: results.map(r => ({
                model: r.model,
                status: r.status,
                duration_ms: r.duration,
                error: r.error // undefined if success
            }))
        });

        // 4. Response Handling
        const suggestions = results.filter(r => r.status === 'success');
        const usedExampleIds = examples.map(ex => ex.commit_id || ex.id).filter(id => id !== null && id !== undefined && id !== "");

        // Error check
        if (suggestions.length === 0 && results.length > 0) {
            const firstError = results[0].error;
            // Check for common auth errors
            if (firstError.includes('Missing API Key') || firstError.includes('401')) {
                const error = new Error(firstError);
                error.name = 'AuthError';
                throw error;
            }
            throw new Error("All models failed to generate.");
        }

        return {
            suggestions,
            usedExampleIds
        };
    }
}

module.exports = GenerationOrchestrator;
