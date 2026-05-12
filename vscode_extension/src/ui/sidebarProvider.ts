import * as vscode from 'vscode';
import { ApiClient } from '../services/apiClient';
import { Settings } from '../config/settings';
import { ViewGenerator } from './viewGenerator';
import { SidebarMessageHandler } from './sidebarMessageHandler';
import { SecretStore } from '../services/secretStore';

export class SidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'autoGenMessage.configView';
    private _view?: vscode.WebviewView;
    private _lastCurrentDiff: string = '';
    private _isGenerating: boolean = false;
    private readonly _viewGenerator: ViewGenerator;
    private readonly _messageHandler: SidebarMessageHandler;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly _apiClient: ApiClient,
        private readonly _secretStore: SecretStore
    ) { 
        this._viewGenerator = new ViewGenerator(_extensionUri);
        this._messageHandler = new SidebarMessageHandler((force?: boolean) => this.refreshOptions(force), _secretStore);
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this._viewGenerator.getHtmlForWebview(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(async (data) => {
            await this._messageHandler.handleMessage(data);
        });

        // Initial load
        this.refreshOptions(true);
        this.sendCurrentDiff(this._lastCurrentDiff);
    }

    public sendExamples(examples: any[], recommendedModel: string | null = null, exampleModelScores: any[] = []) {
        if (this._view) {
            this._view.webview.postMessage({
                type: 'showExamples',
                examples: examples,
                recommendedModel: recommendedModel,
                exampleModelScores: exampleModelScores
            });
        }
    }

    public sendSuggestions(suggestions: any[], usedExampleIds: string[] = []) {
        if (this._view) {
            this._view.webview.postMessage({
                type: 'showSuggestions',
                suggestions: suggestions,
                usedExampleIds: usedExampleIds
            });
        }
    }

    public sendSelectedSuggestion(suggestion: any) {
        if (this._view) {
            this._view.webview.postMessage({
                type: 'suggestionSelected',
                suggestion: suggestion
            });
        }
    }

    public sendError(message: string) {
        if (this._view) {
            this._view.webview.postMessage({
                type: 'error',
                value: message
            });
        }
    }

    public sendCommitSuccess() {
        if (this._view) {
            this._view.webview.postMessage({
                type: 'commitSuccess'
            });
        }
    }

    public sendCurrentDiff(diff: string) {
        this._lastCurrentDiff = diff;
        if (this._view) {
            this._view.webview.postMessage({
                type: 'showCurrentDiff',
                diff
            });
        }
    }

    public updateGeneratingState(isGenerating: boolean) {
        this._isGenerating = isGenerating;
        if (this._view) {
            this._view.webview.postMessage({
                type: 'setGeneratingState',
                isGenerating
            });
        }
    }

    private async refreshOptions(forceSync: boolean = false) {
        if (!this._view) { return; }
        
        try {
            const [modelsData, templatesData, languagesData, rankingsData, usageStats] = await Promise.all([
                this._apiClient.getModels(),
                this._apiClient.getTemplates(),
                this._apiClient.getLanguages(),
                this._apiClient.getModelRankings().catch(err => {
                    console.error('Failed to fetch rankings:', err);
                    return { rankings: [] }; // Fallback
                }),
                this._apiClient.getModelUsageStats().catch(err => {
                     console.error('Failed to fetch stats:', err);
                     return { stats: [] };
                })
            ]);

            this._view.webview.postMessage({
                type: 'updateOptions',
                forceSync,
                models: modelsData.models,
                templates: templatesData.templates,
                languages: languagesData.languages,
                rankings: rankingsData.rankings, 
                usageStats: usageStats.stats, // Pass stats
                keyStatus: {
                    gpt: await this._secretStore.hasApiKeyByFamily('gpt'),
                    qwen: await this._secretStore.hasApiKeyByFamily('qwen'),
                    deepseek: await this._secretStore.hasApiKeyByFamily('deepseek'),
                    closeAi: await this._secretStore.hasCloseAiKey()
                },
                currentSettings: {
                    model: Settings.model,
                    template: Settings.template,
                    language: Settings.language, 
                    useCustomTemplate: Settings.useCustomTemplate,
                    customTemplate: Settings.customTemplate,
                    useCloseAI: Settings.useCloseAI // Pass CloseAI setting
                }
            });
        } catch (error: any) {
            this._view.webview.postMessage({
                type: 'error',
                value: `Failed to fetch options: ${error.message}`
            });
        }
    }
}
