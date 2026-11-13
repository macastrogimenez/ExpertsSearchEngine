package com.github.macastrogimenez.embeddingProcessor;
import java.util.List;

public record VectorSearchResult(
        String documentType,
        String documentId,
        List<String> contributors,
        float score
) {}