import * as vscode from 'vscode';

export class SecretStore {
    private static familyKeySecret(family: string): string {
        return `auto-gen-message.apiKey.${family}`;
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
}

