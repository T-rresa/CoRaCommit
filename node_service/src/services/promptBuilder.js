// node_service/src/services/promptBuilder.js

class PromptBuilder {
    constructor(modelStrategy, formatStrategy, styleStrategy, language = 'en') {
        this.model = modelStrategy;
        this.format = formatStrategy;
        this.style = styleStrategy;
        this.language = language;
        this.MAX_EXAMPLES_DIFF_CHARS = 6000;
        this.MAX_SINGLE_EXAMPLE_DIFF_CHARS = 2000;
    }

    build(diff, examples = []) {
        let examplesText = "";
        
        if (Array.isArray(examples) && examples.length > 0) {
            let remaining = this.MAX_EXAMPLES_DIFF_CHARS;
            examples.forEach((ex, i) => {
                if (remaining <= 0) {
                    return;
                }
                const rawDiff = (ex && ex.diff) ? String(ex.diff) : "";
                const limit = Math.min(this.MAX_SINGLE_EXAMPLE_DIFF_CHARS, remaining);
                const trimmedDiff = rawDiff.length > limit ? (rawDiff.slice(0, limit) + "\n\n[...EXAMPLE DIFF TRUNCATED...]") : rawDiff;
                remaining = Math.max(0, remaining - trimmedDiff.length);
                examplesText += `
Example ${i + 1}:
Diff:
${trimmedDiff}

Commit message:
${ex.message}
`;
            });
        }

        const languageInstruction = this.language && this.language !== 'en' 
            ? `Please generate the commit message in ${this._getLanguageName(this.language)}.` 
            : "";

        return `
${this.model.system()}

${this.format.rules()}

${this.style.rules()}

${languageInstruction}

${this.model.wrapExamples(examplesText)}

Now generate a commit message for the following diff:

${diff}

${this.model.outputConstraints()}
`;
    }

    _getLanguageName(code) {
        const { AVAILABLE_LANGUAGES } = require('../config/settings');
        const lang = AVAILABLE_LANGUAGES.find(l => l.code === code.toLowerCase());
        return lang ? lang.name : code;
    }
}

module.exports = PromptBuilder;
