// node_service/src/services/retrievalService.js
const axios = require('axios');
const logger = require('./loggerService');

class RetrievalService {
    constructor(backendUrl) {
        this.backendUrl = backendUrl;
    }

    async searchSimilar(diff, topK = 5) {
        try {
            const start = Date.now();
            const response = await axios.post(`${this.backendUrl}/api/retrieval/search-by-text`, {
                text: diff,
                top_k: topK,
                model: "codebert"
            });
            const duration = Date.now() - start;
            const matches = response.data.matches || [];

            logger.info('Retrieval', `Search completed in ${duration}ms`, {
                matches_count: matches.length,
                top_score: matches.length > 0 ? matches[0].similarity_score : 0
            });
            
            return matches;
        } catch (error) {
            logger.error('Retrieval', "RetrievalService Error", { error: error.message });
            return []; // Fallback to empty examples on error
        }
    }
}

module.exports = RetrievalService;
