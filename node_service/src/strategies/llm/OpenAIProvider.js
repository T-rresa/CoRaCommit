const OpenAI = require('openai');
const LLMProvider = require('./LLMProvider');
const logger = require('../../services/loggerService');

class OpenAIProvider extends LLMProvider {
    constructor(baseURL) {
        super();
        this.baseURL = baseURL;
    }

    async generate(prompt, modelName, apiKey) {
        if (!apiKey) {
            throw new Error("API Key is missing.");
        }

        const clientConfig = {
            apiKey: apiKey,
            baseURL: this.baseURL,
            timeout: 60000,
            maxRetries: 0
        };

        const client = new OpenAI(clientConfig);

        try {
            logger.info('LLM', `Sending request to OpenAI model: ${modelName}`);
            const temperature = modelName.startsWith('kimi') ? 1 : 0.2;
            const completion = await client.chat.completions.create({
                messages: [{ role: "user", content: prompt }],
                model: modelName,
                temperature
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

module.exports = OpenAIProvider;
