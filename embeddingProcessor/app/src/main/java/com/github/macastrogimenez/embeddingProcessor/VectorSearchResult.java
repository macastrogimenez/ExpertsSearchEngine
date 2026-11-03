package com.github.macastrogimenez.embeddingProcessor;

public record VectorSearchResult(
        String documentType,
        String documentId,
        float score
) {}