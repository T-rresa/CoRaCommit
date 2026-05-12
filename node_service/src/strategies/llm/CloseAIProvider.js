const OpenAI = require('openai');
const LLMProvider = require('./LLMProvider');
const logger = require('../../services/loggerService');

class CloseAIProvider extends LLMProvider {
    constructor(config) {
        super();
        this.config = config;
    }

    async generate(prompt, modelName, apiKey, modelFamily = 'gpt') {
        if (!apiKey) {
            throw new Error("API Key is missing.");
        }

        let baseURL = this.config.base_urls[modelFamily];
        
        if (baseURL) {
            logger.info('LLM', `Using CloseAI Proxy for ${modelName} (Family: ${modelFamily})`, { baseURL });
        } else {
            logger.warn('LLM', `CloseAI Proxy enabled but no mapping for family: ${modelFamily}. Using default.`);
            // Fallback to a default if necessary or throw error
        }

        const clientConfig = {
            apiKey: apiKey,
            baseURL: baseURL,
            timeout: 60000,
            maxRetries: 0
        };

        const client = new OpenAI(clientConfig);

        try {
            logger.info('LLM', `Sending request to CloseAI model: ${modelName}`);
            const completion = await client.chat.completions.create({
                messages: [{ role: "user", content: prompt }],
                model: modelName,
                temperature: 0.2
            });
            
            if (completion.usage) {
                 logger.info('LLM', `Token Usage for ${modelName}`, completion.usage);
            }

            return completion.choices[0].message.content.trim();
        } catch (error) {
            logger.error('LLM', `Error generating with ${modelName}`, { error: error.message });
            throw error;
        }
    }
}

module.exports = CloseAIProvider;
