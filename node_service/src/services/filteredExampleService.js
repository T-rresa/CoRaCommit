const ExampleService = require('./exampleService');
const logger = require('./loggerService');

class FilteredExampleService extends ExampleService {
    constructor(retrievalService) {
        super(retrievalService);
    }

    /**
     * Get examples with exclusion logic
     * @param {string} diff 
     * @param {Array} manualExamples 
     * @param {string} excludeId - ID to exclude from results
     * @returns {Promise<Array>}
     */
    async getExamples(diff, manualExamples, excludeId) {
        // Use manual examples if provided
        if (Array.isArray(manualExamples) && manualExamples.length > 0) {
            return super.getExamples(diff, manualExamples);
        }

        logger.info('FilteredExample', `Retrieving examples with exclusion for ID: ${excludeId}`);

        try {
            // Search with higher K to allow for exclusion filtering
            const topK = 5;
            const matches = await this.retrievalService.searchSimilar(diff, topK);

            // Filter out excludeId
            let finalExamples = matches;
            
            if (excludeId) {
                finalExamples = matches.filter(m => {
                    const matchId = m.commit_id || m.id || m._id;
                    return String(matchId) !== String(excludeId);
                });
                
                if (finalExamples.length < matches.length) {
                    logger.info('FilteredExample', `Excluded match with ID ${excludeId}`);
                }
            }

            // Return top 1 example
            const slicedExamples = finalExamples.slice(0, 1);

            logger.info('FilteredExample', `Retrieved ${matches.length} matches, filtered to ${slicedExamples.length} (Excluded: ${excludeId})`);

            return slicedExamples;

        } catch (error) {
            logger.error('FilteredExample', 'Error in filtered retrieval', { error: error.message, excludeId });
            // Fallback to original behavior or empty
            return [];
        }
    }
}

module.exports = FilteredExampleService;
