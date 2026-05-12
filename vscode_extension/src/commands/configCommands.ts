import * as vscode from 'vscode';
import { ApiClient } from '../services/apiClient';

export class ConfigCommands {
    constructor(
        private apiClient: ApiClient
    ) {}

    public register(context: vscode.ExtensionContext) {
        context.subscriptions.push(
            vscode.commands.registerCommand('auto-gen-message.checkHealth', this.checkHealth.bind(this)),
            vscode.commands.registerCommand('auto-gen-message.selectModel', this.selectModel.bind(this)),
            vscode.commands.registerCommand('auto-gen-message.selectTemplate', this.selectTemplate.bind(this))
        );
    }

    private async checkHealth() {
        try {
            const data = await this.apiClient.checkHealth();
            vscode.window.showInformationMessage(`Service Status: ${data.status} (Version: ${data.version})`);
        } catch (error: any) {
            vscode.window.showErrorMessage(`Failed to connect to backend: ${error.message}`);
        }
    }

    private async selectModel() {
        try {
            const data = await this.apiClient.getModels();

            const models: vscode.QuickPickItem[] = data.models.map((m: any) => ({
                label: m.name,              // 使用 name 作为真实值
                description: m.description, // UI 显示
                detail: m.family
            }));

            const selected = await vscode.window.showQuickPick<vscode.QuickPickItem>(
                models,
                { placeHolder: "Select AI Model" }
            );

            if (selected) {
                await vscode.workspace
                    .getConfiguration("auto-gen-message")
                    .update("model", selected.label, vscode.ConfigurationTarget.Global);

                vscode.window.showInformationMessage(`Model switched to: ${selected.label}`);
            }
        } catch (e: any) {
            vscode.window.showErrorMessage(`Failed to fetch models: ${e.message}`);
        }
    }

    private async selectTemplate() {
        try {
            const data = await this.apiClient.getTemplates();

            const templates: vscode.QuickPickItem[] = data.templates.map((t: any) => ({
                label: t.name,
                description: t.description
            }));

            const selected = await vscode.window.showQuickPick<vscode.QuickPickItem>(
                templates,
                { placeHolder: "Select Commit Template" }
            );

            if (selected) {
                await vscode.workspace
                    .getConfiguration("auto-gen-message")
                    .update("template", selected.label, vscode.ConfigurationTarget.Global);

                vscode.window.showInformationMessage(`Template switched to: ${selected.label}`);
            }
        } catch (e: any) {
            vscode.window.showErrorMessage(`Failed to fetch templates: ${e.message}`);
        }
    }
}
