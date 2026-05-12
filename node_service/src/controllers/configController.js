// node_service/src/controllers/configController.js
const { AVAILABLE_TEMPLATES, AVAILABLE_LANGUAGES } = require('../config/settings');
const modelRegistryService = require('../services/modelRegistryService');
const scoreInitializationService = require('../services/scoreInitializationService');
const logger = require('../services/loggerService');

exports.getModels = async (req, res) => {
    try {
        const models = await modelRegistryService.getAvailableModels();
        res.json({ models });
    } catch (error) {
        logger.error('API', 'Get models error', { error: error.message });
        res.status(500).json({ error: 'Internal Server Error' });
    }
};

exports.getTemplates = (req, res) => {
    res.json({ templates: AVAILABLE_TEMPLATES });
};

exports.getLanguages = (req, res) => {
    res.json({ languages: AVAILABLE_LANGUAGES });
};

exports.addNewModel = async (req, res) => {
    try {
        const { model_name, description, family, base_url, available, initial_score } = req.body;

        if (!model_name) {
            return res.status(400).json({ error: "model_name is required" });
        }
        if (!family) {
            return res.status(400).json({ error: "family is required" });
        }
        if (!base_url) {
            return res.status(400).json({ error: "base_url is required" });
        }

        const score = initial_score !== undefined ? parseFloat(initial_score) : 0.6;

        await modelRegistryService.registerModel({
            model_name,
            description: description || '',
            family,
            base_url,
            available: available !== false,
            initial_score: score
        });

        res.json({ status: "success", message: `Model ${model_name} registered with score ${score}` });
        
    } catch (error) {
        logger.error('API', 'Add new model error', { error: error.message });
        res.status(500).json({ error: "Internal Server Error" });
    }
};

exports.initModelScores = async (req, res) => {
    try {
        const { model_name, initial_score } = req.body;
        
        // Validation: model_name is required
        if (!model_name) {
            return res.status(400).json({ error: "model_name is required" });
        }
        const score = initial_score !== undefined ? parseFloat(initial_score) : 0.6;
        
        const result = await scoreInitializationService.initializeScores(model_name, score);
        res.json(result);
    } catch (error) {
        logger.error('API', 'Init scores error', { error: error.message });
        res.status(500).json({ error: "Internal Server Error" });
    }
};
