import * as vscode from 'vscode';
import { GitDiffProvider } from '../git/diffProvider';
import { ApiClient } from '../services/apiClient';
import { SidebarProvider } from '../ui/sidebarProvider';

export class SearchCommands {
    constructor(
        private gitProvider: GitDiffProvider,
        private apiClient: ApiClient,
        private sidebarProvider: SidebarProvider
    ) {}

    public register(context: vscode.ExtensionContext) {
        context.subscriptions.push(
            vscode.commands.registerCommand('auto-gen-message.searchExamples', this.searchExamples.bind(this)),
            vscode.commands.registerCommand('auto-gen-message.searchSimilar', this.searchSimilar.bind(this))
        );
    }

    private async searchExamples() {
        const repo = await this.gitProvider.getRepository();
        if (!repo) {
            vscode.window.showErrorMessage("No Git repository found.");
            return;
        }

        const diffContent = await this.gitProvider.getStagedDiff(repo.rootUri.fsPath);
        if (!diffContent) {
            this.sidebarProvider.sendCurrentDiff("");
            vscode.window.showWarningMessage("No staged changes found. Please stage your changes first.");
            return;
        }
        this.sidebarProvider.sendCurrentDiff(diffContent);

        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "Searching for similar examples...",
            cancellable: false
        }, async () => {
            try {
                const response = await this.apiClient.searchSimilar(diffContent);
                const matches = response.matches || [];

                // Fetch example model scores for client-side recommendation calculation
                let exampleModelScores: any[] = [];
                if (matches.length > 0) {
                    const exampleIds = matches
                        .map((m: any) => m.commit_id || m.id)
                        .filter((id: any) => id);
                    try {
                        const scoresResponse = await this.apiClient.getExampleModelScores(exampleIds);
                        exampleModelScores = scoresResponse.scores || [];
                    } catch (scoresError) {
                        console.warn('Failed to fetch example model scores:', scoresError);
                    }
                }

                // Send matches back to Webview
                // response structure: { matches: [...], recommended_model: "model_name" }
                this.sidebarProvider.sendExamples(matches, response.recommended_model, exampleModelScores);

            } catch (e: any) {
                vscode.window.showErrorMessage(`Search failed: ${e.message}`);
                // Notify UI to reset button state
                this.sidebarProvider.sendError(e.message);
            }
        });
    }

    private async searchSimilar() {
        const repo = await this.gitProvider.getRepository();
        let diffContent = "";
        
        if (repo) {
             diffContent = await this.gitProvider.getStagedDiff(repo.rootUri.fsPath);
        }
        
        if (!diffContent) {
             this.sidebarProvider.sendCurrentDiff("");
             const editor = vscode.window.activeTextEditor;
             if (editor && !editor.selection.isEmpty) {
                 diffContent = editor.document.getText(editor.selection);
             }
        }
        if (diffContent) {
            this.sidebarProvider.sendCurrentDiff(diffContent);
        }
        
        if (!diffContent) {
             vscode.window.showWarningMessage("No diff found (staged changes or selection).");
             return;
        }

        try {
            const response = await this.apiClient.searchSimilar(diffContent);
            const matches = response.matches;
            if (matches && matches.length > 0) {
                const items = matches.map((m: any) => `${m.message} (Score: ${m.similarity_score.toFixed(2)})`);
                vscode.window.showQuickPick(items, { placeHolder: "Similar commits found" });
            } else {
                vscode.window.showInformationMessage("No similar commits found.");
            }
        } catch (e: any) {
            vscode.window.showErrorMessage(`Search failed: ${e.message}`);
        }
    }
}
