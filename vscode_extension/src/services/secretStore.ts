import * as vscode from 'vscode';

export class SecretStore {
    private static familyKeySecret(family: string): string {
        return `auto-gen-message.apiKey.${family}`;
    }

    private static closeAiKeySecret(): string {
        return `auto-gen-message.closeAiKey`;
    }

    constructor(private readonly context: vscode.ExtensionContext) {}

    async getApiKeyByFamily(family: string): Promise<string> {
        return (await this.context.secrets.get(SecretStore.familyKeySecret(family))) || "";
    }

    async setApiKeyByFamily(family: string, apiKey: string): Promise<void> {
        if (!apiKey) {
            await this.context.secrets.delete(SecretStore.familyKeySecret(family));
            return;
        }
        await this.context.secrets.store(SecretStore.familyKeySecret(family), apiKey);
    }

    async hasApiKeyByFamily(family: string): Promise<boolean> {
        const v = await this.context.secrets.get(SecretStore.familyKeySecret(family));
        return !!(v && v.trim());
    }

    async getCloseAiKey(): Promise<string> {
        return (await this.context.secrets.get(SecretStore.closeAiKeySecret())) || "";
    }

    async setCloseAiKey(apiKey: string): Promise<void> {
        if (!apiKey) {
            await this.context.secrets.delete(SecretStore.closeAiKeySecret());
            return;
        }
        await this.context.secrets.store(SecretStore.closeAiKeySecret(), apiKey);
    }

    async hasCloseAiKey(): Promise<boolean> {
        const v = await this.context.secrets.get(SecretStore.closeAiKeySecret());
        return !!(v && v.trim());
    }
}

