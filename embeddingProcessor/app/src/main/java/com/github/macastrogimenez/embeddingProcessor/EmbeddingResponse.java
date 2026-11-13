package com.github.macastrogimenez.embeddingProcessor;

import java.util.List;

public record EmbeddingResponse(
        String model,
        List<List<Double>> embeddings
) {}