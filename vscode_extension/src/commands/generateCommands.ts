import * as vscode from 'vscode';
import * as crypto from 'crypto';
import { GitDiffProvider } from '../git/diffProvider';
import { ApiClient } from '../services/apiClient';
import { Settings } from '../config/settings';
import { SidebarProvider } from '../ui/sidebarProvider';
import { CommitView } from '../ui/commitView';
import { SecretStore } from '../services/secretStore';

export class GenerateCommands {
    private isGenerating: boolean = false;

    constructor(
        private gitProvider: GitDiffProvider,
        private apiClient: ApiClient,
        private sidebarProvider: SidebarProvider,
        private outputChannel: vscode.OutputChannel,
        private secretStore: SecretStore
    ) {}

    public register(context: vscode.ExtensionContext) {
        context.subscriptions.push(
            vscode.commands.registerCommand('auto-gen-message.generateFromUI', this.generateFromUI.bind(this)),
            vscode.commands.registerCommand('auto-gen-message.getCommitSuggestion', this.getCommitSuggestion.bind(this)),
            vscode.commands.registerCommand('auto-gen-message.quickGenerate', this.quickGenerate.bind(this))
        );
    }

    private setGenerating(value: boolean): void {
        this.isGenerating = value;
        this.sidebarProvider.updateGeneratingState(value);
    }

    private async runWithProgress<T>(
        title: string,
        task: (progress: vscode.Progress<{ message?: string; increment?: number }>, token: vscode.CancellationToken) => Promise<T>
    ): Promise<T | undefined> {
        return vscode.window.withProgress<T>(
            {
                location: vscode.ProgressLocation.Notification,
                title,
                cancellable: true
            },
            async (progress, token) => {
                this.setGenerating(true);
                try {
                    const result = await task(progress, token);
                    return result;
                } finally {
                    this.setGenerating(false);
                }
            }
        );
    }

    private async generateFromUI(data: any) {
        if (this.isGenerating) {
            vscode.window.showWarningMessage('A generation is already in progress. Please wait or cancel it first.');
            return;
        }

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

        await this.runWithProgress("Generating commit message...", async (progress, token) => {
            try {
                progress.report({ message: 'Checking API keys...' });
                const modelNames: string[] = Array.isArray(data.models) ? data.models : [];
                const missingFamilies = new Set<string>();
                const modelsWithKeys = await Promise.all(modelNames.map(async (mName: string) => {
                    const family = this.apiClient.getFamilyForModel(mName);
                    const key = await this.secretStore.getApiKeyByFamily(family);
                    if (!key) {
                        missingFamilies.add(family);
                    }
                    return { name: mName, apiKey: key };
                }));

                if (missingFamilies.size > 0) {
                    vscode.window.showErrorMessage(`Missing API Key for: ${Array.from(missingFamilies).join(', ')}.`);
                    return;
                }

                const useCloseAI = data.useCloseAI !== undefined ? data.useCloseAI : Settings.useCloseAI;
                const closeAiKey = await this.secretStore.getCloseAiKey();
                if (useCloseAI && !closeAiKey) {
                    vscode.window.showErrorMessage('Missing CloseAI API Key.');
                    return;
                }

                this.outputChannel.appendLine(`Requesting generation with models: ${modelNames.join(', ')}`);

                progress.report({ message: 'Generating suggestions...', increment: 30 });

                const response = await this.apiClient.getCommitSuggestion({
                    diff: diffContent,
                    models: modelsWithKeys,
                    examples: data.examples,
                    template: Settings.template,
                    language: data.language || Settings.language,
                    format: Settings.format,
                    templateText: Settings.useCustomTemplate ? Settings.customTemplate : undefined,
                    useCloseAI: useCloseAI,
                    closeAiKey: closeAiKey
                });

                progress.report({ message: 'Processing results...', increment: 80 });

                const sessionId = crypto.randomUUID();

                const suggestions = response.suggestions;
                if (!suggestions || suggestions.length === 0) {
                    vscode.window.showWarningMessage("No suggestions returned.");
                    return;
                }

                const suggestionsWithSession = suggestions.map((s: any) => ({
                    ...s,
                    sessionId: sessionId
                }));

                let selectedSuggestion = null;

                if (suggestions.length === 1) {
                    selectedSuggestion = suggestionsWithSession[0];
                } else {
                    const items = suggestionsWithSession.map((s: any) => ({
                        label: s.model,
                        description: s.message,
                        detail: "Click to select this suggestion",
                        suggestion: s
                    }));

                    const selected = await vscode.window.showQuickPick(items, {
                        placeHolder: "Select a generated commit message",
                        matchOnDescription: true
                    });

                    if (selected) {
                        selectedSuggestion = (selected as any).suggestion;
                    }
                }

                if (selectedSuggestion) {
                    this.sidebarProvider.sendSuggestions(suggestionsWithSession, response.used_example_ids);
                    this.sidebarProvider.sendSelectedSuggestion(selectedSuggestion);
                }

            } catch (error: any) {
                if (token.isCancellationRequested) {
                    vscode.window.showInformationMessage('Generation cancelled.');
                } else if (error.response && error.response.status === 401) {
                    vscode.window.showErrorMessage(error.response.data.error || "Authentication failed: Invalid API Key.");
                } else {
                    vscode.window.showErrorMessage(error.message || "Failed to generate. Please try again.");
                }
                const status = error?.response?.status;
                const message = error?.message || String(error);
                this.outputChannel.appendLine(`Error: ${status ? `status=${status} ` : ''}${message}`);

                this.sidebarProvider.sendError(error.message || "Unknown error occurred");
            }
        });
    }

    private async getCommitSuggestion() {
        if (this.isGenerating) {
            vscode.window.showWarningMessage('A generation is already in progress. Please wait or cancel it first.');
            return;
        }

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

        await this.runWithProgress("Generating commit message...", async (progress, token) => {
            try {
                const currentModel = Settings.model;
                const family = this.apiClient.getFamilyForModel(currentModel);
                const apiKey = await this.secretStore.getApiKeyByFamily(family);

                if (!apiKey) {
                    vscode.window.showErrorMessage(`Missing API Key for: ${family}.`);
                    return;
                }

                const closeAiKey = await this.secretStore.getCloseAiKey();
                if (Settings.useCloseAI && !closeAiKey) {
                    vscode.window.showErrorMessage('Missing CloseAI API Key.');
                    return;
                }

                this.outputChannel.appendLine(`Requesting with model=${currentModel}`);

                const response = await this.apiClient.getCommitSuggestion({
                    diff: diffContent,
                    models: [{ name: currentModel, apiKey: apiKey }],
                    template: Settings.template,
                    language: Settings.language,
                    format: Settings.format,
                    templateText: Settings.useCustomTemplate ? Settings.customTemplate : undefined,
                    useCloseAI: Settings.useCloseAI,
                    closeAiKey: closeAiKey
                });

                const suggestions = response.suggestions;
                if (!suggestions || suggestions.length === 0) {
                    vscode.window.showWarningMessage("No suggestions returned.");
                    return;
                }

                const { message } = suggestions[0];

                if (repo.inputBox) {
                    repo.inputBox.value = message;
                }

                const action = await CommitView.showSuggestion(message, 0.9);
                if (action === "Copy to Clipboard") {
                    await vscode.env.clipboard.writeText(message);
                }
            } catch (error: any) {
                if (token.isCancellationRequested) {
                    vscode.window.showInformationMessage('Generation cancelled.');
                } else if (error.response && error.response.status === 401) {
                    vscode.window.showErrorMessage(error.response.data.error || "Authentication failed: Invalid API Key.");
                } else {
                    vscode.window.showErrorMessage(error.message || "Failed to generate. Please try again.");
                }
                const status = error?.response?.status;
                const message = error?.message || String(error);
                this.outputChannel.appendLine(`Error: ${status ? `status=${status} ` : ''}${message}`);
            }
        });
    }

    private async quickGenerate() {
        if (this.isGenerating) {
            vscode.window.showWarningMessage('A generation is already in progress. Please wait or cancel it first.');
            return;
        }

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

        await this.runWithProgress("Generating commit message...", async (progress, token) => {
            try {
                const currentModel = Settings.model;
                const family = this.apiClient.getFamilyForModel(currentModel);
                const apiKey = await this.secretStore.getApiKeyByFamily(family);

                if (!apiKey) {
                    vscode.window.showErrorMessage(`Missing API Key for: ${family}.`);
                    return;
                }

                const closeAiKey = await this.secretStore.getCloseAiKey();
                if (Settings.useCloseAI && !closeAiKey) {
                    vscode.window.showErrorMessage('Missing CloseAI API Key.');
                    return;
                }

                this.outputChannel.appendLine(`Quick Generate requesting with model=${currentModel}`);

                const response = await this.apiClient.getCommitSuggestion({
                    diff: diffContent,
                    models: [{ name: currentModel, apiKey: apiKey }],
                    template: Settings.template,
                    language: Settings.language,
                    format: Settings.format,
                    templateText: Settings.useCustomTemplate ? Settings.customTemplate : undefined,
                    useCloseAI: Settings.useCloseAI,
                    closeAiKey: closeAiKey
                });

                const suggestions = response.suggestions;
                if (!suggestions || suggestions.length === 0) {
                    vscode.window.showWarningMessage("No suggestions returned.");
                    return;
                }

                const { message } = suggestions[0];

                if (repo.inputBox) {
                    repo.inputBox.value = message;
                }

                vscode.window.showInformationMessage("Commit message generated and filled.");

            } catch (error: any) {
                if (token.isCancellationRequested) {
                    vscode.window.showInformationMessage('Generation cancelled.');
                } else if (error.response && error.response.status === 401) {
                    vscode.window.showErrorMessage(error.response.data.error || "Authentication failed: Invalid API Key.");
                } else {
                    vscode.window.showErrorMessage(error.message || "Failed to generate. Please try again.");
                }
                const status = error?.response?.status;
                const message = error?.message || String(error);
                this.outputChannel.appendLine(`Error: ${status ? `status=${status} ` : ''}${message}`);
            }
        });
    }
}
