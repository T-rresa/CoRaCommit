import * as vscode from 'vscode';

export class Settings {
    static get config() {
        return vscode.workspace.getConfiguration('auto-gen-message');
    }

    static get model(): string {
        return this.config.get<string>('model') || "deepseek-chat";
    }

    static get template(): string {
        return this.config.get<string>('template') || "conventional";
    }

    static get language(): string {
        return this.config.get<string>('language') || "en";
    }

    static get format(): string {
        return this.config.get<string>('format') || "conventional";
    }

    static get useCustomTemplate(): boolean {
        return this.config.get<boolean>('useCustomTemplate') || false;
    }

    static get customTemplate(): string {
        return this.config.get<string>('customTemplate') || "";
    }

    static get useCloseAI(): boolean {
        return this.config.get<boolean>('useCloseAI') || false;
    }

    static get apiUrl(): string {
        const configured = this.config.get<string>('apiUrl') || 'http://8.160.177.208:3001/api';
        return configured.replace(/\/+$/, '');
    }
}
