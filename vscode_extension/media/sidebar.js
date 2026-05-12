// vscode_extension/media/sidebar.js
(function() {
    const vscode = acquireVsCodeApi();

    // DOM Elements
    let primaryModelSelect;
    let enableMultiModelCheck;
    let additionalModelsSection;
    let additionalModelsCheckboxes;
    let templateSelect;
    let languageSelect;
    let useCloseAICheck;
    let btnSetKeyGpt;
    let btnSetKeyQwen;
    let btnSetKeyDeepseek;
    let btnSetKeyCloseAi;
    let keyStatusGpt;
    let keyStatusQwen;
    let keyStatusDeepseek;
    let keyStatusCloseAi;
    let sourceSystemRadio;
    let sourceCustomRadio;
    let systemTemplateGroup;
    let customTemplateGroup;
    let customTemplateArea;
    let manualExamplesCheck;
    let examplesSection;
    let examplesList;
    let btnGenerate;
    let btnRefresh;
    let resultSection;
    let suggestionsList;
    let finalMessageArea;
    let btnCommit;
    let btnReSearch;
    let recommendationSection;
    let recommendedModelName;
    let rankingsSection; 
    let rankingsList; 
    let usageChartContainer; 
    let currentDiffSection;
    let currentDiffContent;
    let loadingIndicator;

    let fetchedExamples = [];
    let currentSuggestions = []; // Store generated suggestions
    let selectedSuggestion = null;
    let backendUsedExampleIds = []; // New: Store IDs used by backend in auto mode
    let isGenerating = false;
    let exampleModelScores = []; // Store model scores for each example for client-side recommendation

    document.addEventListener('DOMContentLoaded', () => {
        console.log('Sidebar JS: DOMContentLoaded');
        
        primaryModelSelect = document.getElementById('primaryModel');
        enableMultiModelCheck = document.getElementById('enableMultiModel');
        additionalModelsSection = document.getElementById('additionalModelsSection');
        additionalModelsCheckboxes = document.getElementById('additionalModelsCheckboxes');
        templateSelect = document.getElementById('template');
        languageSelect = document.getElementById('language'); // New
        useCloseAICheck = document.getElementById('useCloseAI'); // New
        btnSetKeyGpt = document.getElementById('btnSetKeyGpt');
        btnSetKeyQwen = document.getElementById('btnSetKeyQwen');
        btnSetKeyDeepseek = document.getElementById('btnSetKeyDeepseek');
        btnSetKeyCloseAi = document.getElementById('btnSetKeyCloseAi');
        keyStatusGpt = document.getElementById('keyStatusGpt');
        keyStatusQwen = document.getElementById('keyStatusQwen');
        keyStatusDeepseek = document.getElementById('keyStatusDeepseek');
        keyStatusCloseAi = document.getElementById('keyStatusCloseAi');
        sourceSystemRadio = document.getElementById('sourceSystem');
        sourceCustomRadio = document.getElementById('sourceCustom');
        systemTemplateGroup = document.getElementById('systemTemplateGroup');
        customTemplateGroup = document.getElementById('customTemplateGroup');
        customTemplateArea = document.getElementById('customTemplate');
        manualExamplesCheck = document.getElementById('manualExamples');
        examplesSection = document.getElementById('examplesSection');
        examplesList = document.getElementById('examplesList');
        btnGenerate = document.getElementById('btn-generate');
        btnRefresh = document.getElementById('btn-refresh');
        
        resultSection = document.getElementById('resultSection');
        suggestionsList = document.getElementById('suggestionsList');
        finalMessageArea = document.getElementById('finalMessage');
        btnCommit = document.getElementById('btn-commit');
        btnReSearch = document.getElementById('btn-re-search'); // New
        recommendationSection = document.getElementById('recommendationSection');
        recommendedModelName = document.getElementById('recommendedModelName');
        rankingsSection = document.getElementById('rankingsSection');
        rankingsList = document.getElementById('rankingsList');
        usageChartContainer = document.getElementById('usageChartContainer');
        currentDiffSection = document.getElementById('currentDiffSection');
        currentDiffContent = document.getElementById('currentDiffContent');

        // Create loading indicator
        loadingIndicator = document.createElement('div');
        loadingIndicator.id = 'loadingIndicator';
        loadingIndicator.style.cssText = 'display:none; text-align:center; padding:10px; color:var(--vscode-textLink-foreground);';
        loadingIndicator.innerHTML = '<span>Generating...</span>';

        initListeners();
        restoreState(); 
    });

    // --- State Management ---
    function saveState() {
        const state = {
            manualExamplesChecked: manualExamplesCheck ? manualExamplesCheck.checked : false,
            fetchedExamples: fetchedExamples,
            sourceCustomChecked: sourceCustomRadio ? sourceCustomRadio.checked : false,
            templateValue: templateSelect ? templateSelect.value : '',
            languageValue: languageSelect ? languageSelect.value : '', // New
            useCloseAIChecked: useCloseAICheck ? useCloseAICheck.checked : false, // New
            customTemplateValue: customTemplateArea ? customTemplateArea.value : '',
            primaryModelValue: primaryModelSelect ? primaryModelSelect.value : '',
            enableMultiModelChecked: enableMultiModelCheck ? enableMultiModelCheck.checked : false,
            additionalModels: [],
            cachedPrimaryModelsHTML: primaryModelSelect ? primaryModelSelect.innerHTML : '',
            cachedAdditionalModelsHTML: additionalModelsCheckboxes ? additionalModelsCheckboxes.innerHTML : '',
            cachedTemplatesHTML: templateSelect ? templateSelect.innerHTML : '',
            
            // New State
            currentSuggestions: currentSuggestions,
            finalMessageValue: finalMessageArea ? finalMessageArea.value : '',
            selectedSuggestion: selectedSuggestion,
            backendUsedExampleIds: backendUsedExampleIds, // Persist this
            
            // Recommendation State
            recommendedModel: recommendedModelName ? recommendedModelName.innerText : '',
            isRecommendationVisible: recommendationSection ? recommendationSection.style.display : 'none',
            currentDiffText: currentDiffContent ? currentDiffContent.innerText : '',
            isCurrentDiffVisible: currentDiffSection ? currentDiffSection.style.display : 'none',
            exampleModelScores: exampleModelScores
        };

        if (additionalModelsCheckboxes) {
            const checkboxes = additionalModelsCheckboxes.querySelectorAll('input[type="checkbox"]:checked');
            checkboxes.forEach(cb => state.additionalModels.push(cb.value));
        }

        vscode.setState(state);
    }

    function restoreState() {
        const state = vscode.getState();
        if (!state) return;

        // Restore Options
        if (state.cachedPrimaryModelsHTML && primaryModelSelect) {
            primaryModelSelect.innerHTML = state.cachedPrimaryModelsHTML;
            if (state.primaryModelValue) primaryModelSelect.value = state.primaryModelValue;
        }

        if (state.cachedAdditionalModelsHTML && additionalModelsCheckboxes) {
            additionalModelsCheckboxes.innerHTML = state.cachedAdditionalModelsHTML;
            if (state.additionalModels) {
                const inputs = additionalModelsCheckboxes.querySelectorAll('input[type="checkbox"]');
                inputs.forEach(input => {
                    input.checked = state.additionalModels.includes(input.value);
                });
            }
        }

        if (state.cachedTemplatesHTML && templateSelect) {
            templateSelect.innerHTML = state.cachedTemplatesHTML;
            if (state.templateValue) templateSelect.value = state.templateValue;
        }

        if (state.languageValue && languageSelect) {
            languageSelect.value = state.languageValue;
        }

        if (useCloseAICheck) {
            useCloseAICheck.checked = state.useCloseAIChecked;
        }

        if (enableMultiModelCheck) {
            enableMultiModelCheck.checked = !!state.enableMultiModelChecked;
        }

        // Restore Recommendation
        if (state.isRecommendationVisible === 'block' && recommendationSection && recommendedModelName) {
            recommendationSection.style.display = 'block';
            recommendedModelName.innerText = state.recommendedModel;
        }

        if (currentDiffSection && currentDiffContent) {
            if (state.isCurrentDiffVisible === 'block' && state.currentDiffText) {
                currentDiffSection.style.display = 'block';
                currentDiffContent.innerText = state.currentDiffText;
            } else {
                currentDiffSection.style.display = 'none';
            }
        }

        // Restore UI States
        if (manualExamplesCheck) manualExamplesCheck.checked = state.manualExamplesChecked;

        if (sourceCustomRadio && sourceSystemRadio) {
            if (state.sourceCustomChecked) sourceCustomRadio.checked = true;
            else sourceSystemRadio.checked = true;
        }

        if (customTemplateArea) customTemplateArea.value = state.customTemplateValue;

        // Restore Examples
        if (state.fetchedExamples && state.fetchedExamples.length > 0) {
            fetchedExamples = state.fetchedExamples;
            renderExamples(fetchedExamples);
        }

        // Restore Example Model Scores
        if (state.exampleModelScores && state.exampleModelScores.length > 0) {
            exampleModelScores = state.exampleModelScores;
        }

        // Restore Results
        if (state.currentSuggestions && state.currentSuggestions.length > 0) {
            currentSuggestions = state.currentSuggestions;
            selectedSuggestion = state.selectedSuggestion;
            backendUsedExampleIds = state.backendUsedExampleIds || []; // Restore
            renderSuggestions(currentSuggestions);
            
            if (resultSection) resultSection.style.display = 'block';
            if (finalMessageArea) finalMessageArea.value = state.finalMessageValue;
        }

        updateVisibility();
        updateMultiModelVisibility();
        syncAdditionalModelAvailability();
        updateGenerateButton();

        // Request fresh rankings data after state restoration
        vscode.postMessage({ type: 'requestRankings' });
    }

    function renderUsageChart(stats) {
        if (!usageChartContainer) return;
        usageChartContainer.innerHTML = '';

        if (!stats || stats.length === 0) {
            usageChartContainer.innerHTML = '<div style="width:100%; text-align:center; color:gray; font-size:0.8em; align-self:center;">No Usage Data</div>';
            return;
        }

        // Group by Date
        const grouped = {};
        let maxCount = 0;
        
        // Ensure we have entries for the last 7 days even if empty
        const today = new Date();
        for (let i = 6; i >= 0; i--) {
            const d = new Date(today);
            d.setDate(today.getDate() - i);
            const dateStr = d.toISOString().split('T')[0]; // YYYY-MM-DD
            grouped[dateStr] = 0;
        }

        stats.forEach(s => {
            if (grouped[s.date] !== undefined) {
                grouped[s.date] += s.count;
            }
        });

        // Find max for scaling
        Object.values(grouped).forEach(c => {
            if (c > maxCount) maxCount = c;
        });

        // Render Bars
        Object.keys(grouped).sort().forEach(date => {
            const count = grouped[date];
            const height = maxCount > 0 ? (count / maxCount) * 80 : 1; // Max 80px height
            
            const groupDiv = document.createElement('div');
            groupDiv.className = 'bar-group';
            groupDiv.title = `${date}: ${count} calls`; // Tooltip

            const barDiv = document.createElement('div');
            barDiv.className = 'bar';
            barDiv.style.height = `${height}px`;
            // Color code based on activity? Or simple blue.
            if (count === 0) {
                barDiv.style.backgroundColor = 'var(--vscode-widget-border)';
                barDiv.style.height = '1px';
            }

            const labelDiv = document.createElement('div');
            labelDiv.className = 'bar-label';
            // Show MM-DD
            labelDiv.innerText = date.substring(5); 

            groupDiv.appendChild(barDiv);
            groupDiv.appendChild(labelDiv);
            usageChartContainer.appendChild(groupDiv);
        });
    }

    function renderCurrentDiff(diffText) {
        if (!currentDiffSection || !currentDiffContent) return;

        const hasDiff = !!(diffText && diffText.trim().length > 0);
        if (!hasDiff) {
            currentDiffSection.style.display = 'none';
            currentDiffContent.innerText = 'No staged diff loaded.';
            return;
        }

        currentDiffSection.style.display = 'block';
        currentDiffContent.innerText = diffText;
    }

    function resetSessionState() {
        fetchedExamples = [];
        currentSuggestions = [];
        selectedSuggestion = null;
        backendUsedExampleIds = [];
        exampleModelScores = [];

        if (manualExamplesCheck) {
            manualExamplesCheck.checked = false;
        }

        if (examplesSection) {
            examplesSection.style.display = 'none';
        }

        if (examplesList) {
            examplesList.innerHTML = '<div style="font-style:italic; color:gray;">Click "Search Examples" to load...</div>';
        }

        if (recommendationSection) {
            recommendationSection.style.display = 'none';
        }

        if (recommendedModelName) {
            recommendedModelName.innerText = '';
        }

        hideRecommendationWarning();

        if (resultSection) {
            resultSection.style.display = 'none';
        }

        if (suggestionsList) {
            suggestionsList.innerHTML = '';
            suggestionsList.style.display = '';
        }

        if (finalMessageArea) {
            finalMessageArea.value = '';
        }

        if (btnGenerate) {
            btnGenerate.disabled = false;
        }

        if (enableMultiModelCheck) {
            enableMultiModelCheck.checked = false;
        }

        if (additionalModelsCheckboxes) {
            const inputs = additionalModelsCheckboxes.querySelectorAll('input[type="checkbox"]');
            inputs.forEach(input => {
                input.checked = false;
            });
        }

        updateGenerateButton();
        updateMultiModelVisibility();
    }

    // --- UI Logic ---
    function initListeners() {
        if (sourceSystemRadio && sourceCustomRadio) {
            sourceSystemRadio.addEventListener('change', () => { updateVisibility(); saveState(); });
            sourceCustomRadio.addEventListener('change', () => { updateVisibility(); saveState(); });
        }

        if (manualExamplesCheck) {
            manualExamplesCheck.addEventListener('change', () => {
                const isManual = manualExamplesCheck.checked;
                if (examplesSection) examplesSection.style.display = isManual ? 'block' : 'none';
                updateGenerateButton();
                saveState();
            });
        }

        if (templateSelect) templateSelect.addEventListener('change', saveState);
        if (primaryModelSelect) primaryModelSelect.addEventListener('change', () => {
            syncAdditionalModelAvailability();
            saveState();
        });
        if (enableMultiModelCheck) enableMultiModelCheck.addEventListener('change', () => {
            updateMultiModelVisibility();
            saveState();
        });
        if (languageSelect) languageSelect.addEventListener('change', saveState); // New
        if (useCloseAICheck) useCloseAICheck.addEventListener('change', saveState); // New
        if (btnSetKeyGpt) btnSetKeyGpt.addEventListener('click', () => vscode.postMessage({ type: 'setApiKey', family: 'gpt' }));
        if (btnSetKeyQwen) btnSetKeyQwen.addEventListener('click', () => vscode.postMessage({ type: 'setApiKey', family: 'qwen' }));
        if (btnSetKeyDeepseek) btnSetKeyDeepseek.addEventListener('click', () => vscode.postMessage({ type: 'setApiKey', family: 'deepseek' }));
        if (btnSetKeyCloseAi) btnSetKeyCloseAi.addEventListener('click', () => vscode.postMessage({ type: 'setCloseAiKey' }));
        if (customTemplateArea) customTemplateArea.addEventListener('input', saveState);
        if (additionalModelsCheckboxes) additionalModelsCheckboxes.addEventListener('change', saveState);
        if (finalMessageArea) finalMessageArea.addEventListener('input', saveState);

        if (btnRefresh) {
            btnRefresh.addEventListener('click', () => {
                btnRefresh.textContent = 'Refreshing...';
                btnRefresh.style.pointerEvents = 'none';
                vscode.postMessage({ type: 'refreshOptions', force: true });
            });
        }

        if (btnGenerate) {
            btnGenerate.addEventListener('click', handleGenerateClick);
        }
        
        if (btnCommit) {
            btnCommit.addEventListener('click', handleCommitClick);
        }

        if (btnReSearch) {
            btnReSearch.addEventListener('click', () => {
                // Clear existing examples
                fetchedExamples = [];
                renderExamples([]);
                if (recommendationSection) recommendationSection.style.display = 'none';
                
                // Trigger search
                vscode.postMessage({ type: 'searchExamples' });
                // Update UI state
                if (btnGenerate) {
                    btnGenerate.disabled = true;
                    btnGenerate.innerText = "Searching...";
                }
                saveState();
            });
        }
    }

    function updateVisibility() {
        if (!sourceCustomRadio || !systemTemplateGroup || !customTemplateGroup) return;
        const isCustom = sourceCustomRadio.checked;
        systemTemplateGroup.style.display = isCustom ? 'none' : 'block';
        customTemplateGroup.style.display = isCustom ? 'block' : 'none';
    }

    function updateMultiModelVisibility() {
        if (!enableMultiModelCheck || !additionalModelsSection) return;
        additionalModelsSection.style.display = enableMultiModelCheck.checked ? 'block' : 'none';
    }

    function syncAdditionalModelAvailability() {
        if (!primaryModelSelect || !additionalModelsCheckboxes) return;
        const selectedPrimary = primaryModelSelect.value;
        const inputs = additionalModelsCheckboxes.querySelectorAll('input[type="checkbox"]');
        inputs.forEach(input => {
            input.disabled = input.value === selectedPrimary;
            if (input.disabled) {
                input.checked = false;
            }
        });
    }

    function showRecommendationWarning(message) {
        const warningSection = document.getElementById('recommendationWarning');
        const warningText = document.getElementById('recommendationWarningText');
        if (warningSection) {
            warningSection.style.display = 'block';
            if (warningText) {
                warningText.textContent = message;
            }
        }
    }

    function hideRecommendationWarning() {
        const warningSection = document.getElementById('recommendationWarning');
        if (warningSection) {
            warningSection.style.display = 'none';
        }
    }

    function updateGenerateButton() {
        if (!manualExamplesCheck || !btnGenerate) return;
        const isManual = manualExamplesCheck.checked;
        const hasExamples = fetchedExamples.length > 0;

        if (isManual && !hasExamples) {
            btnGenerate.innerText = "Search Examples";
        } else {
            btnGenerate.innerText = "Generate Commit Message";
        }
        if (examplesSection) {
            examplesSection.style.display = isManual ? 'block' : 'none';
        }
    }

    function getSelectedExamples() {
        const selected = [];
        const exCheckboxes = examplesList.querySelectorAll('input[type="checkbox"]:checked');
        exCheckboxes.forEach(cb => {
            const idx = parseInt(cb.value);
            if (fetchedExamples[idx]) {
                selected.push(fetchedExamples[idx]);
            }
        });
        return selected;
    }

    function calculateModelRecommendationsClient(selectedExamples, allScores) {
        if (!selectedExamples || selectedExamples.length === 0 || !allScores || allScores.length === 0) {
            return [];
        }

        const selectedIds = new Set(selectedExamples.map(ex => ex.commit_id || ex.id));
        const filteredScores = allScores.filter(s => selectedIds.has(s.exampleId));

        if (filteredScores.length === 0) {
            return [];
        }

        const modelScores = {};

        filteredScores.forEach(score => {
            const example = selectedExamples.find(ex => (ex.commit_id || ex.id) === score.exampleId);
            if (!example) return;

            const similarity = example.similarity_score || 0.5;

            if (!modelScores[score.model]) {
                modelScores[score.model] = { weightedSum: 0, totalSim: 0 };
            }
            modelScores[score.model].weightedSum += score.score * similarity;
            modelScores[score.model].totalSim += similarity;
        });

        const recommendations = Object.entries(modelScores)
            .map(([model, data]) => ({
                model,
                score: data.totalSim > 0 ? data.weightedSum / data.totalSim : 0
            }))
            .sort((a, b) => b.score - a.score);

        return recommendations;
    }

    function updateRecommendationOnExampleChange() {
        const selectedExamples = getSelectedExamples();
        const recommendations = calculateModelRecommendationsClient(selectedExamples, exampleModelScores);

        if (recommendations.length > 0) {
            const topModel = recommendations[0].model;
            if (recommendationSection && recommendedModelName) {
                recommendationSection.style.display = 'block';
                recommendedModelName.innerText = topModel;
            }
            hideRecommendationWarning();
            // Auto-select the recommended model
            if (primaryModelSelect && Array.from(primaryModelSelect.options).some(o => o.value === topModel)) {
                primaryModelSelect.value = topModel;
                syncAdditionalModelAvailability();
            }
        } else {
            if (recommendationSection) {
                recommendationSection.style.display = 'none';
            }
            // Show warning if examples are loaded but no feedback data
            if (selectedExamples.length > 0) {
                showRecommendationWarning('Insufficient feedback data, using default settings.');
            } else {
                hideRecommendationWarning();
            }
        }
        saveState();
    }

    function renderExamples(examples) {
        if (!examplesList) return;
        examplesList.innerHTML = '';
        if (examples.length === 0) {
            examplesList.innerHTML = '<div style="color:gray;">No similar examples found.</div>';
            return;
        }

        examples.forEach((ex, index) => {
            const div = document.createElement('div');
            div.style.marginBottom = '10px';
            div.style.borderBottom = '1px solid var(--vscode-widget-border)';
            div.style.paddingBottom = '5px';

            const headDiv = document.createElement('div');
            headDiv.className = 'checkbox-group';

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.id = 'ex_' + index;
            cb.value = index;
            cb.checked = true;
            // Add event listener for checkbox changes
            cb.addEventListener('change', () => {
                updateRecommendationOnExampleChange();
                saveState();
            });

            const lbl = document.createElement('label');
            lbl.htmlFor = 'ex_' + index;
            lbl.style.fontWeight = 'bold';
            lbl.innerHTML = `Example ${index + 1} (Similarity Score: ${ex.similarity_score.toFixed(2)} <span class="info-icon" title="Cosine similarity between the current diff and the retrieved example (0-1).">!</span>)`;

            headDiv.appendChild(cb);
            headDiv.appendChild(lbl);

            const contentDiv = document.createElement('div');
            contentDiv.style.fontSize = '0.85em';
            contentDiv.style.marginLeft = '20px';

            let diffPreview = ex.diff || "";
            if (diffPreview.length > 150) {
                diffPreview = diffPreview.substring(0, 150) + '...';
            }

            const msgDiv = document.createElement('div');
            const msgStrong = document.createElement('strong');
            msgStrong.innerText = 'Msg:';
            const msgText = document.createElement('span');
            msgText.innerText = ` ${ex.message || ''}`;
            msgDiv.appendChild(msgStrong);
            msgDiv.appendChild(msgText);

            const diffDiv = document.createElement('div');
            diffDiv.style.color = 'gray';
            diffDiv.style.marginTop = '2px';
            const diffStrong = document.createElement('strong');
            diffStrong.innerText = 'Diff:';
            const diffText = document.createElement('span');
            diffText.innerText = ` ${diffPreview}`;
            diffDiv.appendChild(diffStrong);
            diffDiv.appendChild(diffText);

            contentDiv.appendChild(msgDiv);
            contentDiv.appendChild(diffDiv);

            div.appendChild(headDiv);
            div.appendChild(contentDiv);
            examplesList.appendChild(div);
        });
    }

    function renderSuggestions(suggestions) {
        if (!suggestionsList) return;
        suggestionsList.innerHTML = '';

        suggestions.forEach((s, index) => {
            const div = document.createElement('div');
            div.style.padding = '8px';
            div.style.borderBottom = '1px solid var(--vscode-widget-border)';
            div.style.cursor = 'pointer';
            div.style.background = (selectedSuggestion && selectedSuggestion.model === s.model) ? 'var(--vscode-list-activeSelectionBackground)' : 'transparent';
            div.style.color = (selectedSuggestion && selectedSuggestion.model === s.model) ? 'var(--vscode-list-activeSelectionForeground)' : 'var(--vscode-foreground)';

            div.innerHTML = `<div><strong>${s.model}</strong></div><div style="font-size:0.9em; margin-top:3px;">${s.message}</div>`;
            
            div.addEventListener('click', () => {
                selectedSuggestion = s;
                finalMessageArea.value = s.message;
                renderSuggestions(suggestions); // Re-render to update selection style
                saveState();
            });

            suggestionsList.appendChild(div);
        });
        
        // Auto-select first if none selected
        if (!selectedSuggestion && suggestions.length > 0) {
            selectedSuggestion = suggestions[0];
            finalMessageArea.value = selectedSuggestion.message;
            // Update UI selection immediately without full re-render loop
            const firstChild = suggestionsList.firstChild;
            if (firstChild) {
                firstChild.style.background = 'var(--vscode-list-activeSelectionBackground)';
                firstChild.style.color = 'var(--vscode-list-activeSelectionForeground)';
            }
        }
    }

    function handleGenerateClick() {
        if (isGenerating) {
            vscode.postMessage({ type: 'onInfo', value: 'Generation in progress. Please wait.' });
            return;
        }

        const isManual = manualExamplesCheck.checked;
        const hasExamples = fetchedExamples.length > 0;

        // 1. Search Examples
        if (isManual && !hasExamples) {
            vscode.postMessage({ type: 'searchExamples' });
            btnGenerate.disabled = true;
            btnGenerate.innerText = "Searching...";
            return;
        }

        // 2. Generate
        let selectedModels = [];
        if (primaryModelSelect && primaryModelSelect.value) {
            selectedModels.push(primaryModelSelect.value);
        }
        if (enableMultiModelCheck && enableMultiModelCheck.checked && additionalModelsCheckboxes) {
            const checkboxes = additionalModelsCheckboxes.querySelectorAll('input[type="checkbox"]:checked');
            checkboxes.forEach(cb => {
                if (!selectedModels.includes(cb.value)) {
                    selectedModels.push(cb.value);
                }
            });
        }
        
        if (selectedModels.length === 0) {
            vscode.postMessage({ type: 'onError', value: 'Please select at least one model.' });
            return;
        }

        let selectedExamples = [];
        if (isManual && hasExamples) {
            const exCheckboxes = examplesList.querySelectorAll('input[type="checkbox"]:checked');
            exCheckboxes.forEach(cb => {
                const idx = parseInt(cb.value);
                selectedExamples.push(fetchedExamples[idx]);
            });
        }

        // Reset Results
        if (resultSection) resultSection.style.display = 'none';
        currentSuggestions = [];
        selectedSuggestion = null;
        backendUsedExampleIds = []; // Clear previous backend examples

        saveState();

        vscode.postMessage({
            type: 'generate',
            models: selectedModels,
            examples: isManual ? selectedExamples : null,
            language: languageSelect ? languageSelect.value : 'en', // Pass language
            useCloseAI: useCloseAICheck ? useCloseAICheck.checked : false // Pass CloseAI
        });
        
        btnGenerate.disabled = true;
        btnGenerate.innerText = "Generating...";
    }

    function handleCommitClick() {
        const finalMsg = finalMessageArea.value;
        if (!finalMsg || !finalMsg.trim()) {
            vscode.postMessage({ type: 'onError', value: 'Commit message cannot be empty.' });
            return;
        }

        // Prepare data payload
        const payload = {
            message: finalMsg,
            model: selectedSuggestion ? selectedSuggestion.model : 'unknown',
            originalMessage: selectedSuggestion ? selectedSuggestion.message : '',
            isEdited: selectedSuggestion ? (finalMsg !== selectedSuggestion.message) : true,
            usedExamplesCount: fetchedExamples.length,
            // Pass candidates and session info back
            candidates: currentSuggestions,
            modelsRequested: currentSuggestions.map(s => s.model),
            // Pass example IDs if manual mode used and examples selected
            exampleIds: []
        };

        const isManual = manualExamplesCheck ? manualExamplesCheck.checked : false;
        if (isManual && fetchedExamples.length > 0) {
            const exCheckboxes = examplesList.querySelectorAll('input[type="checkbox"]:checked');
            exCheckboxes.forEach(cb => {
                const idx = parseInt(cb.value);
                const ex = fetchedExamples[idx];
                if (ex && ex.commit_id) {
                    payload.exampleIds.push(ex.commit_id);
                }
            });
        } else if (!isManual && backendUsedExampleIds.length > 0) {
            // Use backend auto-selected examples
            payload.exampleIds = backendUsedExampleIds;
        }

        vscode.postMessage({
            type: 'commit',
            data: payload
        });
    }

    // Handle Incoming Messages
    window.addEventListener('message', event => {
        const message = event.data;
        switch (message.type) {
            case 'showCurrentDiff':
                renderCurrentDiff(message.diff || '');
                saveState();
                break;
            case 'updateOptions':
                if (btnRefresh) {
                    btnRefresh.textContent = 'Refresh';
                    btnRefresh.style.pointerEvents = '';
                }
                if (message.forceSync) {
                    resetSessionState();
                }
                // ... (Existing options logic) ...
                if (primaryModelSelect) {
                    const currentPrimary = message.forceSync ? message.currentSettings.model : primaryModelSelect.value;
                    primaryModelSelect.innerHTML = '';
                    message.models.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m.name;
                        opt.text = m.name;
                        primaryModelSelect.appendChild(opt);
                    });
                    if (currentPrimary && Array.from(primaryModelSelect.options).some(o => o.value === currentPrimary)) {
                        primaryModelSelect.value = currentPrimary;
                    } else if (message.models.length > 0) {
                        primaryModelSelect.value = message.models[0].name;
                    }
                }

                if (additionalModelsCheckboxes) {
                    const currentAdditional = message.forceSync ? [] : Array.from(additionalModelsCheckboxes.querySelectorAll('input:checked')).map(cb => cb.value);
                    additionalModelsCheckboxes.innerHTML = '';
                    message.models.forEach(m => {
                        const div = document.createElement('div');
                        div.className = 'checkbox-group';
                        div.style.marginBottom = '5px';
                        const cb = document.createElement('input');
                        cb.type = 'checkbox';
                        cb.id = 'additional_cb_' + m.name;
                        cb.value = m.name;
                        if (currentAdditional.includes(m.name)) cb.checked = true;
                        const lbl = document.createElement('label');
                        lbl.htmlFor = 'additional_cb_' + m.name;
                        lbl.style.fontWeight = 'normal';
                        lbl.style.marginBottom = '0';
                        lbl.innerText = m.name;
                        div.appendChild(cb);
                        div.appendChild(lbl);
                        additionalModelsCheckboxes.appendChild(div);
                    });
                    syncAdditionalModelAvailability();
                }
                if (templateSelect) {
                    const currentVal = message.forceSync ? message.currentSettings.template : templateSelect.value;
                    templateSelect.innerHTML = '';
                    message.templates.forEach(t => {
                        const opt = document.createElement('option');
                        opt.value = t.name;
                        opt.text = t.name;
                        templateSelect.appendChild(opt);
                    });
                    if (currentVal && Array.from(templateSelect.options).some(o => o.value === currentVal)) {
                        templateSelect.value = currentVal;
                    } else {
                        templateSelect.value = message.currentSettings.template;
                    }
                }

                if (languageSelect) {
                    const currentVal = message.forceSync ? (message.currentSettings.language || 'en') : languageSelect.value;
                    languageSelect.innerHTML = '';
                    if (message.languages) {
                        message.languages.forEach(l => {
                            const opt = document.createElement('option');
                            opt.value = l.code;
                            opt.text = l.name;
                            languageSelect.appendChild(opt);
                        });
                    }
                    
                    if (currentVal && Array.from(languageSelect.options).some(o => o.value === currentVal)) {
                        languageSelect.value = currentVal;
                    } else {
                         languageSelect.value = message.currentSettings.language || 'en';
                    }
                }

                if (useCloseAICheck) {
                    if (message.forceSync || useCloseAICheck.checked === undefined) {
                        useCloseAICheck.checked = message.currentSettings.useCloseAI;
                    }
                }

                if (message.keyStatus) {
                    const statusText = (v) => v ? 'Configured' : 'Not set';
                    if (keyStatusGpt) keyStatusGpt.innerText = statusText(!!message.keyStatus.gpt);
                    if (keyStatusQwen) keyStatusQwen.innerText = statusText(!!message.keyStatus.qwen);
                    if (keyStatusDeepseek) keyStatusDeepseek.innerText = statusText(!!message.keyStatus.deepseek);
                    if (keyStatusCloseAi) keyStatusCloseAi.innerText = statusText(!!message.keyStatus.closeAi);
                }

                // Render Rankings
                if (rankingsList && message.rankings && message.rankings.length > 0) {
                    rankingsSection.style.display = 'block';
                    rankingsList.innerHTML = '';
                    
                    message.rankings.slice(0, 5).forEach((r, idx) => {
                        const div = document.createElement('div');
                        div.style.display = 'grid';
                        div.style.gridTemplateColumns = '25px 1fr auto';
                        div.style.alignItems = 'center';
                        div.style.marginBottom = '4px';
                        
                        const medalSpan = document.createElement('span');
                        medalSpan.style.textAlign = 'center';
                        const medal = idx === 0 ? '🥇' : (idx === 1 ? '🥈' : (idx === 2 ? '🥉' : `${idx + 1}.`));
                        medalSpan.innerText = medal;
                        
                        const nameSpan = document.createElement('span');
                        nameSpan.innerText = r.model;
                        
                        const scoreContainer = document.createElement('div');
                        scoreContainer.style.display = 'flex';
                        scoreContainer.style.alignItems = 'center';
                        scoreContainer.style.justifyContent = 'flex-end'; // Right align

                        const scoreSpan = document.createElement('span');
                        scoreSpan.innerText = r.score.toFixed(3);
                        scoreSpan.style.fontFamily = 'monospace';

                        const infoSpan = document.createElement('span');
                        infoSpan.className = 'info-icon';
                        infoSpan.innerText = '!';
                        infoSpan.title = 'Model performance score based on user feedback (EMA). Higher is better(default value:0.60).';

                        scoreContainer.appendChild(scoreSpan);
                        scoreContainer.appendChild(infoSpan);
                        
                        div.appendChild(medalSpan);
                        div.appendChild(nameSpan);
                        div.appendChild(scoreContainer);
                        rankingsList.appendChild(div);
                    });

                    // Render Usage Chart
                    if (usageChartContainer && message.usageStats) {
                        renderUsageChart(message.usageStats);
                    }

                } else {
                    if (rankingsSection) rankingsSection.style.display = 'none';
                }

                updateVisibility();
                updateMultiModelVisibility();
                saveState();
                break;
            
            case 'showExamples':
                fetchedExamples = message.examples;
                exampleModelScores = message.exampleModelScores || [];

                // Calculate initial recommendation based on all examples
                {
                    const recommendations = calculateModelRecommendationsClient(fetchedExamples, exampleModelScores);

                    if (recommendations.length > 0) {
                        const topModel = recommendations[0].model;
                        if (recommendationSection && recommendedModelName) {
                            recommendationSection.style.display = 'block';
                            recommendedModelName.innerText = topModel;
                        }
                        hideRecommendationWarning();

                        // Auto-select the recommended model
                        if (primaryModelSelect && Array.from(primaryModelSelect.options).some(o => o.value === topModel)) {
                            primaryModelSelect.value = topModel;
                            syncAdditionalModelAvailability();
                        }
                    } else if (message.recommendedModel) {
                        // Fallback to server-side recommendation if no example scores
                        if (recommendationSection && recommendedModelName) {
                            recommendationSection.style.display = 'block';
                            recommendedModelName.innerText = message.recommendedModel;
                        }

                        if (primaryModelSelect && Array.from(primaryModelSelect.options).some(o => o.value === message.recommendedModel)) {
                            primaryModelSelect.value = message.recommendedModel;
                            syncAdditionalModelAvailability();
                        }
                        hideRecommendationWarning();
                    } else {
                        if (recommendationSection) {
                            recommendationSection.style.display = 'none';
                        }
                        // Show warning when examples are loaded but no feedback data available
                        if (fetchedExamples.length > 0) {
                            showRecommendationWarning('Insufficient feedback data, using default settings.');
                        } else {
                            hideRecommendationWarning();
                        }
                    }
                }

                renderExamples(fetchedExamples);
                if (btnGenerate) {
                    btnGenerate.disabled = false;
                    updateGenerateButton();
                }
                saveState();
                break;

            case 'showSuggestions':
                currentSuggestions = message.suggestions;
                backendUsedExampleIds = message.usedExampleIds || []; // Capture IDs
                if (resultSection) resultSection.style.display = 'block';
                renderSuggestions(currentSuggestions);
                
                if (btnGenerate) {
                    btnGenerate.disabled = false;
                    updateGenerateButton(); // Reset text
                }
                saveState();
                break;

            case 'suggestionSelected':
                selectedSuggestion = message.suggestion;
                if (resultSection) resultSection.style.display = 'block';
                if (finalMessageArea) finalMessageArea.value = selectedSuggestion.message;
                
                // Hide suggestions list since we already selected via QuickPick
                if (suggestionsList) suggestionsList.style.display = 'none';
                
                if (btnGenerate) {
                    btnGenerate.disabled = false;
                    updateGenerateButton(); 
                }
                saveState();
                break;

            case 'commitSuccess':
                // Reset everything after successful commit
                fetchedExamples = [];
                currentSuggestions = [];
                selectedSuggestion = null;
                backendUsedExampleIds = []; // Clear
                exampleModelScores = []; // Clear
                
                if (resultSection) resultSection.style.display = 'none';
                if (examplesSection) examplesSection.style.display = 'none'; // Will be re-shown if manual check is still true
                if (recommendationSection) recommendationSection.style.display = 'none';
                if (examplesList) examplesList.innerHTML = '<div style="font-style:italic; color:gray;">Click "Search Examples" to load...</div>';
                
                // If Manual Mode is still checked, user sees "Search Examples" button again
                updateGenerateButton();
                saveState();
                break;

            case 'setGeneratingState':
                isGenerating = message.isGenerating;
                if (btnGenerate) {
                    btnGenerate.disabled = isGenerating;
                    btnGenerate.innerText = isGenerating ? "Generating..." : (updateGenerateButton() || "Generate Commit Message");
                }
                if (loadingIndicator) {
                    loadingIndicator.style.display = isGenerating ? 'block' : 'none';
                }
                break;

            case 'requestRankings':
                vscode.postMessage({ type: 'refreshOptions', force: false });
                break;

            case 'error':
                if (btnRefresh) {
                    btnRefresh.textContent = 'Refresh';
                    btnRefresh.style.pointerEvents = '';
                }
                vscode.postMessage({ type: 'onError', value: message.value });
                if (btnGenerate) {
                    btnGenerate.disabled = false;
                    updateGenerateButton();
                }
                isGenerating = false;
                break;
        }
    });

})();
