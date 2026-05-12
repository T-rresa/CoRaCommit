// node_service/src/services/promptService.js
const PromptBuilder = require('./promptBuilder');
const { FormatRegistry } = require('../strategies/format');
const { StyleRegistry, UserTemplateStyle } = require('../strategies/style');
const { ModelRegistry } = require('../strategies/model');
const { AVAILABLE_MODELS } = require('../config/settings');
const modelRegistryService = require('./modelRegistryService');
const logger = require('./loggerService');

class PromptService {
    /**
     * Build the prompt for a specific model configuration
     * @param {string} diff 
     * @param {Array} examples 
     * @param {Object} options - { modelName, format, template, templateText }
     */
    async build(diff, examples, options) {
        const { modelName, format, template, templateText, language } = options;

        // 1. Resolve Model Family
        const modelInfo = await modelRegistryService.getModelByName(modelName) || AVAILABLE_MODELS.find(m => m.name === modelName) || AVAILABLE_MODELS[0];
        const modelFamily = modelInfo.family;
        const modelStrategy = ModelRegistry[modelFamily] || ModelRegistry['gpt'];

        // 2. Resolve Format
        const formatStrategy = FormatRegistry[format] || FormatRegistry['conventional'];

        // 3. Resolve Style (Template)
        let styleStrategy;
        if (templateText) {
            styleStrategy = new UserTemplateStyle(templateText);
        } else {
            styleStrategy = StyleRegistry[template] || StyleRegistry['conventional'];
        }

        // 4. Build Prompt
        const builder = new PromptBuilder(modelStrategy, formatStrategy, styleStrategy, language);
        const prompt = builder.build(diff, examples);
        
        logger.info('Prompt', `Built prompt for ${modelName}`, { 
            length: prompt.length, 
            model_family: modelFamily,
            has_custom_template: !!templateText,
            language
        });

        return {
            prompt,
            modelFamily // Return family info as it might be needed for validation
        };
    }
}

module.exports = PromptService;
