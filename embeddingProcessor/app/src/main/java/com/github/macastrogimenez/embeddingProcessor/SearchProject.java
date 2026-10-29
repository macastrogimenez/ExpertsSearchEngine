package com.github.macastrogimenez.embeddingProcessor;

import java.util.List;

public class SearchProject {
    private String uuid;
    private String title;
    private String description;
    private List<String> participantIds;
    private List<Double> embedding;

    public SearchProject(String uuid, String title, String description, List<String> participantIds) {
        this.uuid = uuid;
        this.title = title;
        this.description = description;
        this.participantIds = participantIds;
    }

    public SearchProject(String uuid, String title, String description, List<String> participantIds, List<Double> embedding) {
        this.uuid = uuid;
        this.title = title;
        this.description = description;
        this.participantIds = participantIds;
        this.embedding = embedding;
    }

    public SearchProject(String uuid, List<Double> embedding) {
        this.uuid = uuid;
        this.embedding = embedding;
    }

    public String getUuid() {
        return uuid;
    }

    public void setUuid(String uuid) {
        this.uuid = uuid;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public List<String> getParticipantIds() {
        return participantIds;
    }

    public void setParticipantIds(List<String> participantIds) {
        this.participantIds = participantIds;
    }

    public List<Double> getEmbedding() {
        return embedding;
    }

    public void setEmbedding(List<Double> embedding) {
        this.embedding = embedding;
    }
}
