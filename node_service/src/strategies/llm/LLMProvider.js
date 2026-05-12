class LLMProvider {
    async generate(prompt, modelName, apiKey) {
        throw new Error("Method 'generate' must be implemented.");
    }
}

module.exports = LLMProvider;
