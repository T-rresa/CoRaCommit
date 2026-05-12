import * as vscode from 'vscode';

export class CommitView {
    static async showSuggestion(suggestion: string, confidence: number): Promise<string | undefined> {
        return vscode.window.showInformationMessage(
            `Suggestion: ${suggestion} (Confidence: ${confidence})`,
            "Copy to Clipboard"
        );
    }
}
