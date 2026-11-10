package com.github.macastrogimenez.embeddingProcessor;
import java.util.List;

public class VectorDocument{
        private String documentType;
        private String documentId;
        private List<String> contributors;
        private List<Double> embedding;

        public VectorDocument (String docType, String docID, List<String> contrList ){
                this.contributors = contrList;
                this.documentType = docType;
                this.documentId = docID;
        }

        
        public void setDocumentType(String documentType) {
                this.documentType = documentType;
        }


        public void setDocumentId(String documentId) {
                this.documentId = documentId;
        }

        public void setContributors(List<String> contributors) {
                this.contributors = contributors;
        }


        public void setEmbedding(List<Double> embedding) {
                this.embedding = embedding;
        }


        public String getDocumentType() {
                return documentType;
        }

        public String getDocumentId() {
                return documentId;
        }

        public List<String> getContributors() {
                return contributors;
        }

        public List<Double> getEmbedding() {
                return embedding;
        }

        
}