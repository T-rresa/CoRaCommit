// node_service/src/strategies/format.js

class FormatStrategy {
    rules() { return ""; }
}

class ConventionalCommit extends FormatStrategy {
    rules() {
        return `Use Conventional Commits format:
type(scope): subject
Examples of types: feat, fix, docs, refactor, test, chore`;
    }
}

class KarmaCommit extends FormatStrategy {
    rules() {
        return "Use imperative, present tense in the subject line.";
    }
}

const FormatRegistry = {
    "conventional": new ConventionalCommit(),
    "karma": new KarmaCommit()
};

module.exports = { FormatRegistry };
