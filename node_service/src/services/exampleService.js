// node_service/src/services/exampleService.js
const logger = require('./loggerService');

class ExampleService {
    constructor(retrievalService) {
        this.retrievalService = retrievalService;
    }

    /**
     * Get examples either from user input or by searching similar commits
     * @param {string} diff - The git diff content
     * @param {Array} manualExamples - Optional manually selected examples
     * @returns {Promise<Array>} List of examples
     */
    async getExamples(diff, manualExamples) {
        if (Array.isArray(manualExamples) && manualExamples.length > 0) {
            logger.info('Example', `Using ${manualExamples.length} manually selected examples.`);
            return manualExamples;
        }

        logger.info('Example', `Retrieving examples automatically...`);
        const examples = await this.retrievalService.searchSimilar(diff);
        logger.info('Example', `Retrieved ${examples.length} examples via RAG.`);
        return examples;
    }
}

module.exports = ExampleService;
