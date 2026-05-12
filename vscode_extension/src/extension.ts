import * as vscode from 'vscode';
import * as crypto from 'crypto';
import { GitDiffProvider } from './git/diffProvider';
import { ApiClient } from './services/apiClient';
import { SidebarProvider } from './ui/sidebarProvider';
import { GenerateCommands } from './commands/generateCommands';
import { CommitCommands } from './commands/commitCommands';
import { SearchCommands } from './commands/searchCommands';
import { ConfigCommands } from './commands/configCommands';
import { SecretStore } from './services/secretStore';

const outputChannel = vscode.window.createOutputChannel("Auto Gen Message");
const apiClient = new ApiClient();
const gitProvider = new GitDiffProvider(outputChannel);

export async function activate(context: vscode.ExtensionContext) {
    outputChannel.appendLine('Auto Gen Message extension active');

    const secretStore = new SecretStore(context);

    // Register Webview View Provider
    const sidebarProvider = new SidebarProvider(context.extensionUri, apiClient, secretStore);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(SidebarProvider.viewType, sidebarProvider)
    );

    let latestDiffSyncVersion = 0;
    let diffSyncTimer: ReturnType<typeof setTimeout> | undefined;
    const repoStateSubscriptions = new Map<string, vscode.Disposable>();

    const syncCurrentDiff = async (reason: string) => {
        const version = ++latestDiffSyncVersion;
        try {
            const repo = await gitProvider.getRepository();
            if (!repo) {
                sidebarProvider.sendCurrentDiff("");
                outputChannel.appendLine(`Diff sync (${reason}): no repository.`);
                return;
            }

            const diffContent = await gitProvider.getStagedDiff(repo.rootUri.fsPath);
            if (version !== latestDiffSyncVersion) {
                return;
            }

            sidebarProvider.sendCurrentDiff(diffContent);
            outputChannel.appendLine(`Diff sync (${reason}): ${diffContent ? `loaded ${diffContent.length} chars` : 'empty staged diff'}.`);
        } catch (e: any) {
            const message = e?.message || String(e);
            outputChannel.appendLine(`Diff sync (${reason}) failed: ${message}`);
        }
    };

    const scheduleDiffSync = (reason: string, delayMs: number = 120) => {
        if (diffSyncTimer) {
            clearTimeout(diffSyncTimer);
        }
        diffSyncTimer = setTimeout(() => {
            diffSyncTimer = undefined;
            void syncCurrentDiff(reason);
        }, delayMs);
    };

    const attachRepoStateListener = (repo: any) => {
        const repoPath = repo?.rootUri?.fsPath;
        if (!repoPath || repoStateSubscriptions.has(repoPath)) {
            return;
        }
        const disposable = repo.state.onDidChange(() => scheduleDiffSync('git-state-changed'));
        repoStateSubscriptions.set(repoPath, disposable);
        context.subscriptions.push(disposable);
    };

    const detachRepoStateListener = (repo: any) => {
        const repoPath = repo?.rootUri?.fsPath;
        if (!repoPath) {
            return;
        }
        const disposable = repoStateSubscriptions.get(repoPath);
        if (disposable) {
            disposable.dispose();
            repoStateSubscriptions.delete(repoPath);
        }
    };

    const bindGitRepositoryEvents = async () => {
        const gitExtension = vscode.extensions.getExtension('vscode.git');
        if (!gitExtension) {
            return;
        }

        await gitExtension.activate();
        const git = gitExtension.exports.getAPI(1);
        for (const repo of git.repositories) {
            attachRepoStateListener(repo);
        }

        if (typeof git.onDidOpenRepository === 'function') {
            const openSub = git.onDidOpenRepository((repo: any) => {
                attachRepoStateListener(repo);
                scheduleDiffSync('repository-opened');
            });
            context.subscriptions.push(openSub);
        }

        if (typeof git.onDidCloseRepository === 'function') {
            const closeSub = git.onDidCloseRepository((repo: any) => {
                detachRepoStateListener(repo);
                scheduleDiffSync('repository-closed');
            });
            context.subscriptions.push(closeSub);
        }
    };

    // 1. Initial Config Sync (Fire and Forget to avoid blocking activation)
    apiClient.getModels().then(data => {
        const models = data.models.map((m: any) => m.name);
        outputChannel.appendLine(`Synced available models: ${models.join(', ')}`);
        // In future: we could cache these to local storage or validate current setting
    }).catch(e => {
        outputChannel.appendLine(`Failed to sync models on startup: ${e.message}`);
    });
    
    // 2. Generate and persist unique Plugin User ID
    const USER_ID_KEY = 'plugin_user_id';
    let pluginUserId = context.globalState.get<string>(USER_ID_KEY);

    if (!pluginUserId) {
        pluginUserId = crypto.randomUUID();
        await context.globalState.update(USER_ID_KEY, pluginUserId);
        outputChannel.appendLine(`Generated new Plugin User ID: ${pluginUserId}`);
    } else {
        outputChannel.appendLine(`Loaded existing Plugin User ID: ${pluginUserId}`);
    }

    const config = vscode.workspace.getConfiguration('auto-gen-message');
    const legacyApiKeys = config.get<Record<string, string>>('apiKeys');
    if (legacyApiKeys && typeof legacyApiKeys === 'object') {
        const entries = Object.entries(legacyApiKeys).filter(([_, v]) => typeof v === 'string' && v.trim() && v !== 'sample');
        if (entries.length > 0) {
            for (const [family, apiKey] of entries) {
                await secretStore.setApiKeyByFamily(family, apiKey);
            }
            await config.update('apiKeys', undefined, vscode.ConfigurationTarget.Global);
        }
    }

    const legacyCloseAiKey = config.get<string>('closeAiKey');
    if (legacyCloseAiKey && legacyCloseAiKey.trim()) {
        await secretStore.setCloseAiKey(legacyCloseAiKey);
        await config.update('closeAiKey', undefined, vscode.ConfigurationTarget.Global);
    }

    // 3. Register Commands
    const generateCommands = new GenerateCommands(gitProvider, apiClient, sidebarProvider, outputChannel, secretStore);
    generateCommands.register(context);

    const commitCommands = new CommitCommands(gitProvider, apiClient, sidebarProvider, outputChannel, context);
    commitCommands.register(context);

    const searchCommands = new SearchCommands(gitProvider, apiClient, sidebarProvider);
    searchCommands.register(context);

    const configCommands = new ConfigCommands(apiClient);
    configCommands.register(context);

    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(() => scheduleDiffSync('active-editor-changed')),
        new vscode.Disposable(() => {
            if (diffSyncTimer) {
                clearTimeout(diffSyncTimer);
                diffSyncTimer = undefined;
            }
            for (const disposable of repoStateSubscriptions.values()) {
                disposable.dispose();
            }
            repoStateSubscriptions.clear();
        })
    );

    await bindGitRepositoryEvents();
    scheduleDiffSync('extension-activated', 0);
}

export function deactivate() {}
