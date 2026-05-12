// node_service/src/controllers/commitController.js
const RetrievalService = require('../services/retrievalService');
const LLMService = require('../services/llmService');
const ExampleService = require('../services/exampleService');
const PromptService = require('../services/promptService');
const GenerationOrchestrator = require('../services/generationOrchestrator');
const logger = require('../services/loggerService');
const priorityService = require('../services/priorityService');
const { ALLOW_MOCK_LLM } = require('../config/settings');
const { v4: uuidv4 } = require('uuid');

const backendUrl = process.env.RETRIEVAL_BACKEND_URL || process.env.BACKEND_URL || "http://127.0.0.1:8000";
const retrievalService = new RetrievalService(backendUrl);
const llmService = new LLMService();
const exampleService = new ExampleService(retrievalService);
const promptService = new PromptService();
const generationOrchestrator = new GenerationOrchestrator(exampleService, promptService, llmService);

exports.suggestCommit = async (req, res) => {
    const requestId = uuidv4();
    try {
        await priorityService.markGenerationStarted();
        const { 
            diff, models, template, language, format, templateText, examples: manualExamples,
            useCloseAI, closeAiKey, userId, mockLLM, mockLatencyMs
        } = req.body;
        const effectiveMockLLM = ALLOW_MOCK_LLM && !!mockLLM;
        
        logger.info('Received Generate Request', {
            request_id: requestId,
            input: {
                diff_length: diff ? diff.length : 0,
                manual_examples_count: manualExamples ? manualExamples.length : 0
            },
            config: {
                models: Array.isArray(models) ? models.map(m => m.name) : [],
                template,
                language,
                format,
                use_custom_template: !!templateText,
                use_close_ai: !!useCloseAI,
                mock_llm_requested: !!mockLLM,
                mock_llm_enabled: effectiveMockLLM
            }
        });

        const result = await generationOrchestrator.generate({
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
            mockLLM: effectiveMockLLM,
            mockLatencyMs,
            requestId
        });

        res.json({ 
            suggestions: result.suggestions,
            used_example_ids: result.usedExampleIds
        });

    } catch (error) {
        if (error.name === 'AuthError') {
            logger.warn('Request Failed: Auth Error', { request_id: requestId, error: error.message });
            return res.status(401).json({ error: error.message });
        }
        logger.error('Unhandled Controller Error', { request_id: requestId, error: error.message, stack: error.stack });
        res.status(500).json({ error: error.message });
    } finally {
        await priorityService.markGenerationFinished();
    }
};

const dbService = require('../services/dbService');

exports.similaritySearch = async (req, res) => {
    try {
        const { diff } = req.body;
        
        logger.info('SimilaritySearch', 'Received request', { diffLength: diff ? diff.length : 0 });

        if (!diff) {
            logger.warn('SimilaritySearch', 'Missing diff');
            return res.status(400).json({ error: "Diff is required" });
        }

        const examples = await retrievalService.searchSimilar(diff); // Get top 10
         
        let recommendedModel = null;
        if (examples && examples.length > 0) {
            const exampleScores = examples.map(m => ({
                id: m.commit_id || m.id, 
                similarity: m.similarity_score || m.score
            }));
            
            try {
                recommendedModel = await dbService.getRecommendedModel(exampleScores);
            } catch (recError) {
                logger.warn('SimilaritySearch', 'Recommendation failed', { error: recError.message });
            }
        }

        logger.info('SimilaritySearch', 'Search completed', { 
            count: examples.length, 
            topMatch: examples.length > 0 ? { id: examples[0].commit_id, score: examples[0].similarity_score } : null,
            recommendedModel
        });

        res.json({ matches: examples, recommended_model: recommendedModel });
        
    } catch (error) {
        logger.error('SimilaritySearch', 'Search failed', { error: error.message, stack: error.stack });
        res.status(500).json({ error: error.message });
    }
};

exports.getExampleModelScores = async (req, res) => {
    try {
        const { example_ids } = req.body;
        
        if (!example_ids || !Array.isArray(example_ids) || example_ids.length === 0) {
            return res.status(400).json({ error: "example_ids array is required" });
        }

        const scores = await dbService.getExampleModelScores(example_ids);

        res.json({ scores });
    } catch (error) {
        logger.error('GetExampleModelScores', 'Failed', { error: error.message });
        res.status(500).json({ error: error.message });
    }
};
