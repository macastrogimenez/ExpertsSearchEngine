package com.github.macastrogimenez.embeddingProcessor;

import java.util.List;

public record SearchProject(
        String uuid,
        String title,
        String description,
        List<String> participantIds,
        List<Double> embedding
) {}