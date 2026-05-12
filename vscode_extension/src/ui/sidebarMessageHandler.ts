import * as vscode from 'vscode';
import { SecretStore } from '../services/secretStore';

export class SidebarMessageHandler {
    constructor(
        private readonly _refreshCallback: (force?: boolean) => Promise<void>,
        private readonly _secretStore: SecretStore
    ) {}

    public async handleMessage(data: any) {
        switch (data.type) {
            case 'onInfo': {
                if (!data.value) { return; }
                vscode.window.showInformationMessage(data.value);
                break;
            }
            case 'onError': {
                if (!data.value) { return; }
                vscode.window.showErrorMessage(data.value);
                break;
            }
            case 'saveSettings': {
                await this.saveSettings(data);
                break;
            }
            case 'refreshOptions':
            case 'requestRankings': {
                await this._refreshCallback(!!data.force);
                break;
            }
            case 'generate': {
                vscode.commands.executeCommand('auto-gen-message.generateFromUI', data);
                break;
            }
            case 'commit': {
                vscode.commands.executeCommand('auto-gen-message.commitChanges', data.data);
                break;
            }
            case 'searchExamples': {
                vscode.commands.executeCommand('auto-gen-message.searchExamples');
                break;
            }
            case 'setApiKey': {
                await this.setApiKey(data.family);
                await this._refreshCallback(true);
                break;
            }
            case 'setCloseAiKey': {
                await this.setCloseAiKey();
                await this._refreshCallback(true);
                break;
            }
        }
    }

    private async saveSettings(data: any) {
        const config = vscode.workspace.getConfiguration('auto-gen-message');
        await Promise.all([
            config.update('model', data.model, vscode.ConfigurationTarget.Global),
            config.update('template', data.template, vscode.ConfigurationTarget.Global),
            config.update('useCustomTemplate', data.useCustomTemplate, vscode.ConfigurationTarget.Global),
            config.update('customTemplate', data.customTemplate, vscode.ConfigurationTarget.Global),
            config.update('useCloseAI', data.useCloseAI, vscode.ConfigurationTarget.Global),
            config.update('language', data.language, vscode.ConfigurationTarget.Global)
        ]);
        vscode.window.showInformationMessage('Settings saved successfully!');
    }

    private async setApiKey(family: string) {
        if (!family || typeof family !== 'string') {
            vscode.window.showErrorMessage('Missing model family.');
            return;
        }
        const apiKey = await vscode.window.showInputBox({
            title: `Set API Key (${family})`,
            prompt: 'Paste your API key. Leave empty to clear.',
            password: true,
            ignoreFocusOut: true
        });
        if (apiKey === undefined) {
            return;
        }
        await this._secretStore.setApiKeyByFamily(family, apiKey.trim());
        vscode.window.showInformationMessage(`API Key saved (${family}).`);
    }

    private async setCloseAiKey() {
        const apiKey = await vscode.window.showInputBox({
            title: 'Set CloseAI API Key',
            prompt: 'Paste your CloseAI API key. Leave empty to clear.',
            password: true,
            ignoreFocusOut: true
        });
        if (apiKey === undefined) {
            return;
        }
        await this._secretStore.setCloseAiKey(apiKey.trim());
        vscode.window.showInformationMessage('CloseAI API Key saved.');
    }
}
