export interface BenchmarkConfig {
	prompts: {
		system: string;
		user: string;
	};
	models: {
		label: string;
		id: string;
		params: Record<string, unknown>;
	}[];
	groups: {
		name: string;
		sample_count: number;
	}[];
	sample_count: number;
}

export interface ResultMetrics {
	cer: number;
	wer: number;
	cer_case_insensitive: number;
	wer_case_insensitive: number;
	levenshtein_distance: number;
	normalized_levenshtein_similarity: number;
	char_count_reference: number;
	word_count_reference: number;
}

export interface ResponseMetadata {
	input_tokens: number;
	output_tokens: number;
	cost: number;
	latency_seconds: number;
}

export interface BenchmarkResult {
	group: string;
	label: string;
	image: string;
	ground_truth_file: string;
	ground_truth_text: string;
	model: string;
	model_output: string;
	error: string | null;
	metrics: ResultMetrics | null;
	response_metadata: ResponseMetadata;
}

export interface ModelSummary {
	cer_mean: number;
	cer_median: number;
	cer_min: number;
	cer_max: number;
	wer_mean: number;
	wer_median: number;
	wer_min: number;
	wer_max: number;
	cer_case_insensitive_mean: number;
	cer_case_insensitive_median: number;
	cer_case_insensitive_min: number;
	cer_case_insensitive_max: number;
	wer_case_insensitive_mean: number;
	wer_case_insensitive_median: number;
	wer_case_insensitive_min: number;
	wer_case_insensitive_max: number;
	normalized_levenshtein_similarity_mean: number;
	normalized_levenshtein_similarity_median: number;
	normalized_levenshtein_similarity_min: number;
	normalized_levenshtein_similarity_max: number;
	levenshtein_distance_mean: number;
	levenshtein_distance_median: number;
	levenshtein_distance_min: number;
	levenshtein_distance_max: number;
	samples_evaluated: number;
	samples_failed: number;
	total_input_tokens: number;
	total_output_tokens: number;
	total_tokens: number;
	total_cost: number;
	total_latency_seconds: number;
}

export interface BenchmarkData {
	benchmark: {
		name: string;
		timestamp: string;
		total_duration_seconds: number;
		config: BenchmarkConfig;
	};
	results: BenchmarkResult[];
	model_summaries: Record<string, ModelSummary>;
	group_summaries: Record<string, Record<string, ModelSummary>>;
}
