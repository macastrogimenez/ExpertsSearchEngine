package com.github.macastrogimenez.embeddingProcessor;

import java.util.List;

public class SearchPaper {
    private String uuid;
    private int year;
    private String type;
    private String title;
    private String subtitle;
    private String paperAbstract;
    private List<String> contributorIds;
    private List<Double> embedding;

    public SearchPaper(String uuid, int year, String type, String title, String subtitle, String paperAbstract, List<String> contributorIds) {
        this.uuid = uuid;
        this.year = year;
        this.type = type;
        this.title = title;
        this.subtitle = subtitle;
        this.paperAbstract = paperAbstract;
        this.contributorIds = contributorIds;
    }

    public SearchPaper(String uuid, int year, String type, String title, String subtitle, String paperAbstract, List<String> contributorIds, List<Double> embedding) {
        this.uuid = uuid;
        this.year = year;
        this.type = type;
        this.title = title;
        this.subtitle = subtitle;
        this.paperAbstract = paperAbstract;
        this.contributorIds = contributorIds;
        this.embedding = embedding;
    }

    public SearchPaper(String uuid, List<Double> embedding) {
        this.uuid = uuid;
        this.embedding = embedding;
    }

    public String getUuid() {
        return uuid;
    }

    public void setUuid(String uuid) {
        this.uuid = uuid;
    }

    public int getYear() {
        return year;
    }

    public void setYear(int year) {
        this.year = year;
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getSubtitle() {
        return subtitle;
    }

    public void setSubtitle(String subtitle) {
        this.subtitle = subtitle;
    }

    public String getPaperAbstract() {
        return paperAbstract;
    }

    public void setPaperAbstract(String paperAbstract) {
        this.paperAbstract = paperAbstract;
    }

    public List<String> getContributorIds() {
        return contributorIds;
    }

    public void setContributorIds(List<String> contributorIds) {
        this.contributorIds = contributorIds;
    }

    public List<Double> getEmbedding() {
        return embedding;
    }

    public void setEmbedding(List<Double> embedding) {
        this.embedding = embedding;
    }
}
