// node_service/src/strategies/model.js

class ModelPromptStrategy {
    system() { return ""; }
    wrapExamples(text) { return text; }
    outputConstraints() { return ""; }
}

class GPTPrompt extends ModelPromptStrategy {
    system() {
        return "You are an expert software engineer generating Git commit messages.";
    }
    wrapExamples(text) {
        return `Here are relevant examples:\n${text}`;
    }
    outputConstraints() {
        return "Output only the final commit message. No explanations.";
    }
}

class QwenPrompt extends ModelPromptStrategy {
    system() {
        return "You are a helpful assistant for code analysis.";
    }
    wrapExamples(text) {
        return `### Examples\n${text}\n### End of examples`;
    }
    outputConstraints() {
        return "Only output the commit message.";
    }
}

const ModelRegistry = {
    "gpt": new GPTPrompt(),
    "qwen": new QwenPrompt(),
    "deepseek": new GPTPrompt() // Re-use GPT strategy for deepseek
};

module.exports = { ModelRegistry };
