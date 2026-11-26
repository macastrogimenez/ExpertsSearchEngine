package com.github.macastrogimenez.embeddingProcessor;
import java.util.List;

public record VectorSearchResult(
        String documentType,
        String documentId,
        String title,
        String snippet,
        List<String> contributors,
        float score
) {}