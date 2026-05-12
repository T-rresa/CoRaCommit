// node_service/src/strategies/style.js

class StyleStrategy {
    rules() { return ""; }
}

class AngularStyle extends StyleStrategy {
    rules() {
        return "Use Angular commit style with concise subject and optional body.";
    }
}

class EmojiStyle extends StyleStrategy {
    rules() {
        return "Use Gitmoji style with appropriate emoji prefix (e.g., ✨ for feat, 🐛 for fix).";
    }
}

class UserTemplateStyle extends StyleStrategy {
    constructor(template) {
        super();
        this.template = template;
    }
    rules() {
        return `The commit message must follow this template:\n\n${this.template}`;
    }
}

const StyleRegistry = {
    "angular": new AngularStyle(),
    "emoji": new EmojiStyle(),
    "conventional": new AngularStyle() // Default mapping
};

module.exports = { StyleRegistry, UserTemplateStyle };
