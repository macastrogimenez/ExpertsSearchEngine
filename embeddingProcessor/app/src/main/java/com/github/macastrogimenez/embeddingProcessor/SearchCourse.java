package com.github.macastrogimenez.embeddingProcessor;

import java.util.List;

public class SearchCourse{
        private int id;
        private String title;
        private String courseAbstract;
        private String description;
        private String programme;
        private String professorId;
        private List<Double> embedding;

        public SearchCourse(
                int id,
                String title,
                String courseAbstract,
                String description,
                String programme,
                String professorId
        ) {
                this.id = id;
                this.title = title;
                this.courseAbstract = courseAbstract;
                this.description = description;
                this.programme = programme;
                this.professorId = professorId;
        }

        public SearchCourse(
                int id,
                List<Double> embedding
        ) {
                this.id = id;
                this.embedding = embedding;
        }

        public int getId() {
                return id;
        }

        public String getTitle() {
                return title;
        }

        public String getCourseAbstract() {
                return courseAbstract;
        }

        public String getDescription() {
                return description;
        }

        public String getProgramme() {
                return programme;
        }

        public String getProfessorId() {
                return professorId;
        }

        public List<Double> getEmbedding() {
                return embedding;
        }

        public void setId(int id) {
                this.id = id;
        }

        public void setTitle(String title) {
                this.title = title;
        }

        public void setCourseAbstract(String courseAbstract) {
                this.courseAbstract = courseAbstract;
        }

        public void setDescription(String description) {
                this.description = description;
        }

        public void setProgramme(String programme) {
                this.programme = programme;
        }

        public void setProfessorId(String professorId) {
                this.professorId = professorId;
        }

        public void setEmbedding(List<Double> embedding) {
                this.embedding = embedding;
        }

        

}
