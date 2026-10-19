package com.github.macastrogimenez.embeddingProcessor;

import java.util.List;

public record SearchCourse(
        int id,
        String title,
        String courseAbstract,
        String description,
        String programme,
        String professorId,
        List<Double> embedding
) {}