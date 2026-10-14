package com.github.macastrogimenez.embeddingProcessor;

import java.util.List;

public record SearchPaper(
        String uuid,
        int year,
        String type,
        String title,
        String subtitle,
        String paperAbstract,
        List<String> contributorIds,
        List<Double> embedding
) {}