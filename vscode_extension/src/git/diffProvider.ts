import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as util from 'util';

const exec = util.promisify(cp.exec);

export class GitDiffProvider {
    private outputChannel: vscode.OutputChannel;
    private readonly MAX_DIFF_CHARS = 12000;
    private readonly MAX_LINE_CHARS = 2000;

    constructor(outputChannel: vscode.OutputChannel) {
        this.outputChannel = outputChannel;
    }

    async getRepository(): Promise<any> {
        const gitExtension = vscode.extensions.getExtension('vscode.git');
        if (!gitExtension) {
            return null;
        }
        const git = gitExtension.exports.getAPI(1);
        
        if (git.repositories.length === 0) {
            return null;
        }
        
        const editor = vscode.window.activeTextEditor;
        if (editor && editor.document.uri) {
            const repo = git.getRepository(editor.document.uri);
            if (repo) return repo;
        }
        
        return git.repositories[0];
    }

    async getStagedDiff(repoRoot: string): Promise<string> {
        try {
            const { stdout: staged } = await exec('git diff --cached', { cwd: repoRoot });
            const diff = staged.trim() ? staged : "";
            return diff ? this.preprocessDiff(diff) : "";
        } catch (e) {
            this.outputChannel.appendLine(`Error reading diff: ${e}`);
            return "";
        }
    }

    private preprocessDiff(diff: string): string {
        let text = diff.replace(/\r\n/g, '\n');
        text = this.stripBinaryDiffs(text);
        text = this.maskSecrets(text);
        text = this.limitLineLength(text);
        text = this.truncate(text, this.MAX_DIFF_CHARS);
        return text.trim();
    }

    private stripBinaryDiffs(diff: string): string {
        const sections = diff.split(/\n(?=diff --git )/g);
        const kept: string[] = [];
        for (const section of sections) {
            const headerLine = section.split('\n', 1)[0] || '';
            const isBinary = /(^|\n)GIT binary patch(\n|$)/.test(section) || /(^|\n)Binary files .+ differ(\n|$)/.test(section);
            if (!isBinary) {
                kept.push(section);
                continue;
            }
            const m = /^diff --git a\/(.+?) b\/(.+)$/.exec(headerLine);
            const fileLabel = m ? `${m[1]} -> ${m[2]}` : 'unknown file';
            kept.push(`${headerLine}\n(Binary diff omitted: ${fileLabel})`);
        }
        return kept.join('\n');
    }

    private limitLineLength(diff: string): string {
        const lines = diff.split('\n');
        const limited = lines.map(l => (l.length > this.MAX_LINE_CHARS ? (l.slice(0, this.MAX_LINE_CHARS) + '…') : l));
        return limited.join('\n');
    }

    private truncate(text: string, maxChars: number): string {
        if (text.length <= maxChars) {
            return text;
        }
        const headSize = Math.floor(maxChars * 0.85);
        const tailSize = maxChars - headSize;
        const head = text.slice(0, headSize);
        const tail = text.slice(text.length - tailSize);
        return `${head}\n\n[...DIFF TRUNCATED...]\n\n${tail}`;
    }

    private maskSecrets(diff: string): string {
        let text = diff;

        text = text.replace(/-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/g, '[REDACTED:PRIVATE_KEY]');

        const tokenPatterns: Array<[RegExp, string]> = [
            [/\bsk-(?:proj-)?[A-Za-z0-9_-]{10,}\b/g, '[REDACTED:OPENAI_KEY]'],
            [/\bghp_[A-Za-z0-9]{20,}\b/g, '[REDACTED:GITHUB_TOKEN]'],
            [/\bgithub_pat_[A-Za-z0-9_]{20,}\b/g, '[REDACTED:GITHUB_TOKEN]'],
            [/\bAKIA[0-9A-Z]{16}\b/g, '[REDACTED:AWS_ACCESS_KEY_ID]'],
            [/\bASIA[0-9A-Z]{16}\b/g, '[REDACTED:AWS_TEMP_ACCESS_KEY_ID]'],
            [/\bAIza[0-9A-Za-z_-]{20,}\b/g, '[REDACTED:GOOGLE_API_KEY]'],
            [/\bxox[baprs]-[0-9A-Za-z-]{10,}\b/g, '[REDACTED:SLACK_TOKEN]'],
            [/\bBearer\s+[A-Za-z0-9._~-]{10,}\b/gi, 'Bearer [REDACTED:TOKEN]'],
        ];
        for (const [re, replacement] of tokenPatterns) {
            text = text.replace(re, replacement);
        }

        const kvPatterns: Array<RegExp> = [
            /(\b(api[_-]?key|access[_-]?token|secret|password|passwd|pwd)\b\s*[:=]\s*)(['"]?)[^'"\s]{6,}\3/gi,
            /("?(api[_-]?key|access[_-]?token|secret|password|passwd|pwd)"?\s*:\s*)"(?:\\.|[^"\\]){6,}"/gi,
        ];
        for (const re of kvPatterns) {
            text = text.replace(re, (m, p1) => `${p1}[REDACTED]`);
        }

        return text;
    }
}
