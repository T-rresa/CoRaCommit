import axios, { AxiosError, AxiosRequestConfig } from 'axios';
import * as vscode from 'vscode';
import { Settings } from '../config/settings';

const DEFAULT_TIMEOUT = 60000; // 60 seconds

export interface CommitSuggestionRequest {
    diff: string;
    model?: string;
    mode?: 'single' | 'multi';
    models?: Array<{name: string, apiKey: string}>;
    examples?: any[];
    template?: string;
    language?: string;
    format?: string;
    apiKey?: string;
    templateText?: string;
    useCloseAI?: boolean;
    closeAiKey?: string;
}

export class ApiClient {
    private modelsCache: any[] = [];

    private getBaseUrl(): string {
        return Settings.apiUrl;
    }

    private getTimeoutConfig(): AxiosRequestConfig {
        return { timeout: DEFAULT_TIMEOUT };
    }

    private enrichError(action: string, error: any): never {
        if ((error as AxiosError).isAxiosError) {
            const axiosError = error as AxiosError<any>;
            const status = axiosError.response?.status;
            const details = axiosError.response?.data?.error || axiosError.response?.data?.message || axiosError.message;
            throw new Error(`${action} failed (${this.getBaseUrl()})${status ? ` [${status}]` : ''}: ${details}`);
        }
        throw error;
    }

    private isTimeoutError(error: any): boolean {
        if ((error as AxiosError).isAxiosError) {
            const axiosError = error as AxiosError<any>;
            return axiosError.code === 'ECONNABORTED' || axiosError.message?.includes('timeout');
        }
        return error.message?.includes('timeout') || false;
    }

    async checkHealth(): Promise<any> {
        try {
            const response = await axios.get(`${this.getBaseUrl()}/health`, { timeout: 5000 });
            return response.data;
        } catch (error) {
            this.enrichError('Health check', error);
        }
    }

    async getCommitSuggestion(req: CommitSuggestionRequest): Promise<any> {
        try {
            const response = await axios.post(`${this.getBaseUrl()}/commit-suggestion`, req, this.getTimeoutConfig());
            return response.data;
        } catch (error) {
            if (this.isTimeoutError(error)) {
                throw new Error('Request timeout. The server took too long to respond. Please try again.');
            }
            this.enrichError('Commit suggestion', error);
        }
    }

    async searchSimilar(diff: string): Promise<any> {
        try {
            const response = await axios.post(`${this.getBaseUrl()}/similarity-search`, { diff }, this.getTimeoutConfig());
            return response.data;
        } catch (error) {
            if (this.isTimeoutError(error)) {
                throw new Error('Search timeout. Please try again.');
            }
            this.enrichError('Similarity search', error);
        }
    }

    async getModels(): Promise<any> {
        try {
            const response = await axios.get(`${this.getBaseUrl()}/config/models`, { timeout: 10000 });
            if (response.data && response.data.models) {
                this.modelsCache = response.data.models;
            }
            return response.data;
        } catch (error) {
            this.enrichError('Fetch models', error);
        }
    }

    getFamilyForModel(modelName: string): string {
        const model = this.modelsCache.find((m: any) => m.name === modelName);
        return model ? model.family : 'gpt';
    }

    async getTemplates(): Promise<any> {
        try {
            const response = await axios.get(`${this.getBaseUrl()}/config/templates`, { timeout: 10000 });
            return response.data;
        } catch (error) {
            this.enrichError('Fetch templates', error);
        }
    }

    async getLanguages(): Promise<any> {
        try {
            const response = await axios.get(`${this.getBaseUrl()}/config/languages`, { timeout: 10000 });
            return response.data;
        } catch (error) {
            this.enrichError('Fetch languages', error);
        }
    }

    async getModelRankings(): Promise<any> {
        try {
            const response = await axios.get(`${this.getBaseUrl()}/models/ranking`, { timeout: 15000 });
            return response.data;
        } catch (error) {
            this.enrichError('Fetch rankings', error);
        }
    }

    async getModelUsageStats(days: number = 7): Promise<any> {
        try {
            const response = await axios.get(`${this.getBaseUrl()}/stats/model-usage`, { params: { days }, timeout: 15000 });
            return response.data;
        } catch (error) {
            this.enrichError('Fetch usage stats', error);
        }
    }

    async sendFeedback(data: any): Promise<any> {
        try {
            const response = await axios.post(`${this.getBaseUrl()}/feedback/commit`, data, { timeout: 30000 });
            return response.data;
        } catch (error) {
            this.enrichError('Send feedback', error);
        }
    }

    async getExampleModelScores(exampleIds: string[]): Promise<any> {
        try {
            const response = await axios.post(`${this.getBaseUrl()}/examples/model-scores`, { example_ids: exampleIds }, { timeout: 10000 });
            return response.data;
        } catch (error) {
            this.enrichError('Fetch example model scores', error);
        }
    }
}

export interface ModelRecommendation {
    model: string;
    score: number;
}

export function calculateModelRecommendations(
    selectedExamples: any[],
    exampleModelScores: any[]
): ModelRecommendation[] {
    if (!selectedExamples || selectedExamples.length === 0 || !exampleModelScores || exampleModelScores.length === 0) {
        return [];
    }

    const exampleIds = new Set(selectedExamples.map((ex: any) => ex.commit_id || ex.id));
    const filteredScores = exampleModelScores.filter((s: any) => exampleIds.has(s.exampleId));

    if (filteredScores.length === 0) {
        return [];
    }

    const modelScores: { [model: string]: { weightedSum: number; totalSim: number } } = {};

    filteredScores.forEach((score: any) => {
        const example = selectedExamples.find((ex: any) => (ex.commit_id || ex.id) === score.exampleId);
        if (!example) return;

        const similarity = example.similarity_score || 0.5;

        if (!modelScores[score.model]) {
            modelScores[score.model] = { weightedSum: 0, totalSim: 0 };
        }
        modelScores[score.model].weightedSum += score.score * similarity;
        modelScores[score.model].totalSim += similarity;
    });

    const recommendations: ModelRecommendation[] = Object.entries(modelScores)
        .map(([model, data]) => ({
            model,
            score: data.totalSim > 0 ? data.weightedSum / data.totalSim : 0
        }))
        .sort((a, b) => b.score - a.score);

    return recommendations;
}
