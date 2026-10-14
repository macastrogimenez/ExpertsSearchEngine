package com.github.macastrogimenez.embeddingProcessor;

public record SearchDocument(
        String id,
        long academicId,
        String type,
        String title,
        String content
        //List<Double> embedding
) {}