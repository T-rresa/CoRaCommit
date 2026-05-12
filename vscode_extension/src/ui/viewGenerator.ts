import * as vscode from 'vscode';

export class ViewGenerator {
    constructor(private readonly _extensionUri: vscode.Uri) {}

    public getHtmlForWebview(webview: vscode.Webview): string {
        const styleResetUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'reset.css'));
        const styleVSCodeUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'vscode.css'));
        const styleMainUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'sidebar.css'));
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'sidebar.js'));
        
        // Simple CSS-based bar chart styles
        const chartCss = `
            .bar-chart-container {
                display: flex;
                align-items: flex-end;
                height: 100px;
                gap: 5px;
                padding-top: 10px;
                border-bottom: 1px solid var(--vscode-widget-border);
                overflow-x: auto;
            }
            .bar-group {
                display: flex;
                flex-direction: column;
                align-items: center;
                flex: 1;
                min-width: 30px;
            }
            .bar {
                width: 100%;
                background-color: var(--vscode-charts-blue);
                transition: height 0.3s ease;
                min-height: 1px;
                border-radius: 2px 2px 0 0;
            }
            .bar-label {
                font-size: 0.7em;
                margin-top: 4px;
                text-align: center;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                width: 100%;
            }
            .diff-preview-container {
                margin-bottom: 15px;
                border: 1px solid var(--vscode-widget-border);
                padding: 10px;
                background: var(--vscode-editor-inactiveSelectionBackground);
            }
            .diff-preview-content {
                max-height: 180px;
                overflow: auto;
                white-space: pre-wrap;
                word-break: break-word;
                font-family: var(--vscode-editor-font-family, Consolas, "Courier New", monospace);
                font-size: 12px;
                line-height: 1.4;
                border: 1px solid var(--vscode-input-border);
                background: var(--vscode-input-background);
                color: var(--vscode-input-foreground);
                padding: 8px;
            }
        `;

        return `<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src ${webview.cspSource} 'unsafe-inline';">
                <link href="${styleResetUri}" rel="stylesheet">
                <link href="${styleVSCodeUri}" rel="stylesheet">
                <link href="${styleMainUri}" rel="stylesheet">
                <style>${chartCss}</style>
            </head>
            <body>
                <h3>Configuration <span class="refresh-link" id="btn-refresh">Refresh</span></h3>
                
                <!-- 0. Model Rankings & Stats -->
                <div id="rankingsSection" style="display:none; margin-bottom: 15px; border: 1px solid var(--vscode-widget-border); padding: 10px; background: var(--vscode-editor-inactiveSelectionBackground);">
                    <div style="font-weight:bold; margin-bottom:5px;">🏆 Model Leaderboard</div>
                    <div id="rankingsList" style="font-size: 0.85em; margin-bottom: 10px;">
                        <!-- Injected via JS -->
                    </div>
                    
                    <div style="border-top: 1px dashed var(--vscode-widget-border); padding-top: 8px; margin-top: 8px;">
                        <div style="font-weight:bold; margin-bottom:5px; font-size: 0.9em;">📈 Usage Trend (7 Days)</div>
                        <div id="usageChartContainer" class="bar-chart-container">
                            <!-- Injected via JS -->
                            <div style="width:100%; text-align:center; color:gray; font-size:0.8em; align-self:center;">No Data</div>
                        </div>
                    </div>
                </div>

                <!-- 0.1 Current Diff Preview -->
                <div id="currentDiffSection" class="diff-preview-container" style="display:none;">
                    <div style="font-weight:bold; margin-bottom:6px;">Current Staged Diff</div>
                    <div id="currentDiffContent" class="diff-preview-content">No staged diff loaded.</div>
                </div>

                <!-- 1. Example Selection (Top Priority) -->
                <div class="form-group checkbox-group" style="margin-bottom: 5px;">
                    <input type="checkbox" id="useCloseAI">
                    <label for="useCloseAI" style="margin-bottom:0">Use CloseAI Proxy</label>
                </div>

                <div style="margin-bottom: 15px; border: 1px solid var(--vscode-widget-border); padding: 10px;">
                    <div style="font-weight:bold; margin-bottom:6px;">🔐 API Keys</div>
                    <div style="display:flex; gap:6px; flex-wrap: wrap; margin-bottom: 8px;">
                        <button id="btnSetKeyGpt" class="vscode-button" type="button">Set GPT Key</button>
                        <button id="btnSetKeyQwen" class="vscode-button" type="button">Set Qwen Key</button>
                        <button id="btnSetKeyDeepseek" class="vscode-button" type="button">Set Deepseek Key</button>
                        <button id="btnSetKeyCloseAi" class="vscode-button" type="button">Set CloseAI Key</button>
                    </div>
                    <div style="font-size: 0.85em; opacity: 0.9;">
                        <div>GPT: <span id="keyStatusGpt">Unknown</span></div>
                        <div>Qwen: <span id="keyStatusQwen">Unknown</span></div>
                        <div>Deepseek: <span id="keyStatusDeepseek">Unknown</span></div>
                        <div>CloseAI: <span id="keyStatusCloseAi">Unknown</span></div>
                    </div>
                </div>

                <div class="form-group checkbox-group" style="margin-bottom: 5px;">
                    <input type="checkbox" id="manualExamples">
                    <label for="manualExamples" style="margin-bottom:0">Select Examples Manually</label>
                </div>

                <div id="examplesSection" style="display:none; margin-bottom: 20px; border: 1px solid var(--vscode-widget-border); padding: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <label>Available Examples:</label>
                        <span class="refresh-link" id="btn-re-search" style="font-size: 0.9em;">Refresh</span>
                    </div>
                    <div id="examplesList" style="max-height: 200px; overflow-y: auto;">
                        <div style="font-style:italic; color:gray;">Click "Search Examples" to load...</div>
                    </div>
                </div>

                <hr style="margin: 15px 0; border: 0; border-top: 1px solid var(--vscode-widget-border);">

                <!-- 2. Model & Template Configuration -->
                <div class="form-group">
                    <label for="primaryModel">Default Model</label>
                    <div id="recommendationSection" style="display:none; margin-bottom: 10px; padding: 8px; background-color: var(--vscode-editor-inactiveSelectionBackground); border-left: 3px solid var(--vscode-textLink-foreground);">
                        <strong>Recommended:</strong> <span id="recommendedModelName"></span>
                    </div>
                    <div id="recommendationWarning" style="display:none; margin-bottom: 10px; padding: 8px; background-color: var(--vscode-editor-warningBackground); border-left: 3px solid var(--vscode-textLink-foreground); color: var(--vscode-editorWarning-foreground);">
                        <strong>Insufficient Feedback Data</strong>
                        <div id="recommendationWarningText" style="font-size: 0.85em; margin-top: 4px;"></div>
                    </div>
                    <select id="primaryModel"></select>
                </div>

                <div class="form-group checkbox-group" style="margin-bottom: 8px;">
                    <input type="checkbox" id="enableMultiModel">
                    <label for="enableMultiModel" style="margin-bottom:0">Enable Multi-Model Compare</label>
                </div>

                <div class="form-group" id="additionalModelsSection" style="display:none;">
                    <label>Additional Models</label>
                    <div id="additionalModelsCheckboxes"></div>
                </div>

                <div class="form-group radio-group">
                    <label>Template Source:</label>
                    <div>
                        <input type="radio" id="sourceSystem" name="templateSource" value="system" checked>
                        <label for="sourceSystem" style="display:inline; font-weight:normal">System Template</label>
                    </div>
                    <div>
                        <input type="radio" id="sourceCustom" name="templateSource" value="custom">
                        <label for="sourceCustom" style="display:inline; font-weight:normal">Custom Template</label>
                    </div>
                </div>

                <div class="form-group" id="systemTemplateGroup">
                    <label for="template">Select Template</label>
                    <select id="template"></select>
                </div>

                <div class="form-group">
                    <label for="language">Select Language</label>
                    <select id="language">
                        <!-- Populated dynamically -->
                    </select>
                </div>

                <div class="form-group" id="customTemplateGroup" style="display:none;">
                    <label for="customTemplate">Custom Template Content</label>
                    <div class="template-hint">
                        Example: "Generate a commit message for the following diff. Use conventional commits format."
                    </div>
                    <textarea id="customTemplate" rows="5" placeholder="Enter your custom prompt template here..."></textarea>
                </div>

                <hr style="margin: 20px 0; border: 0; border-top: 1px solid var(--vscode-widget-border);">
                
                <!-- 3. Action -->
                <div id="loadingIndicator" style="display:none; text-align:center; padding:10px; color:var(--vscode-textLink-foreground);">
                    <span>Generating... (Click Cancel on progress notification to abort)</span>
                </div>
                <div class="template-hint" style="margin-bottom: 10px;">
                    Ensure your changes are staged in Git before generating.
                </div>
                <button id="btn-generate" style="background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground);">Generate Commit Message</button>

                <!-- 4. Result & Edit Area -->
                <div id="resultSection" style="display:none; margin-top: 20px; border-top: 1px solid var(--vscode-widget-border); padding-top: 15px;">
                    <label style="margin-bottom: 5px;">Generated Suggestions:</label>
                    <div id="suggestionsList" style="margin-bottom: 10px; max-height: 150px; overflow-y: auto; border: 1px solid var(--vscode-input-border); background: var(--vscode-input-background);">
                        <!-- Suggestions items will be injected here -->
                    </div>

                    <label for="finalMessage" style="margin-top: 10px;">Edit Final Message:</label>
                    <textarea id="finalMessage" rows="5" style="width: 100%; margin-bottom: 10px;"></textarea>
                    
                    <button id="btn-commit" style="background: var(--vscode-button-primaryBackground); color: var(--vscode-button-primaryForeground);">Commit Changes</button>
                </div>

                <script src="${scriptUri}"></script>
            </body>
            </html>`;
    }
}
