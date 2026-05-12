import * as vscode from 'vscode';
import * as crypto from 'crypto';
import { GitDiffProvider } from '../git/diffProvider';
import { ApiClient } from '../services/apiClient';
import { SidebarProvider } from '../ui/sidebarProvider';

export class CommitCommands {
    constructor(
        private gitProvider: GitDiffProvider,
        private apiClient: ApiClient,
        private sidebarProvider: SidebarProvider,
        private outputChannel: vscode.OutputChannel,
        private context: vscode.ExtensionContext
    ) {}

    public register(context: vscode.ExtensionContext) {
        context.subscriptions.push(
            vscode.commands.registerCommand('auto-gen-message.commitChanges', this.commitChanges.bind(this))
        );
    }

    private async commitChanges(data: any) {
        const repo = await this.gitProvider.getRepository();
        if (!repo) {
            vscode.window.showErrorMessage("No Git repository found.");
            return;
        }

        const message = data.message;
        if (!message) return;

        // Prepare Feedback Data
        const candidates = data.candidates || []; 
        
        // If candidates missing (e.g. quick generate), construct a basic one
        const finalCandidates = candidates.length > 0 ? candidates : [{
            model: data.model,
            generated_message: data.originalMessage,
            message_quality: 0.0 // Placeholder
        }];

        const pluginUserId = this.context.globalState.get<string>('plugin_user_id');

        // Capture diff at commit time for feedback
        let currentDiff = "";
        try {
            currentDiff = await this.gitProvider.getStagedDiff(repo.rootUri.fsPath);
            this.sidebarProvider.sendCurrentDiff(currentDiff);
        } catch (e) {
            this.outputChannel.appendLine("Failed to capture diff for feedback");
        }

        const feedbackData = {
            user_id: pluginUserId,
            models_requested: data.modelsRequested || [data.model], 
            candidates: finalCandidates.map((c: any) => ({
                model: c.model,
                generated_message: c.message || c.generated_message,
                message_quality: 0.0
            })),
            selected_model: data.model,
            final_message: message,
            is_edited: data.isEdited,
            timestamp: new Date().toISOString(),
            example_ids: data.exampleIds || [],
            diff: currentDiff
        };

        this.outputChannel.appendLine(`Sending Feedback: ${JSON.stringify(feedbackData, null, 2)}`);

        // Perform Commit
        try {
            await repo.commit(message);
            vscode.window.showInformationMessage("Commit successful!");
            
            // Clear input if needed
            repo.inputBox.value = "";
            
            // Send Feedback to Backend (Async)
            this.apiClient.sendFeedback(feedbackData).catch(err => {
                 this.outputChannel.appendLine(`Failed to send feedback: ${err.message}`);
            });

            // Notify Sidebar to reset
            if (this.sidebarProvider) {
                 this.sidebarProvider.sendCommitSuccess();
                 this.sidebarProvider.sendCurrentDiff("");
            }

        } catch (e: any) {
            vscode.window.showErrorMessage(`Commit failed: ${e.message}`);
        }
    }
}
