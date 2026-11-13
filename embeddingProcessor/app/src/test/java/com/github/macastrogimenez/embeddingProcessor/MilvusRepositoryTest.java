package com.github.macastrogimenez.embeddingProcessor;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;

public class MilvusRepositoryTest {
    private EmbeddingService s;
    private MilvusRepository mr;
    private List<List<Double>> vectorsList;
    private List<VectorDocument> vectorsDocs;


    
    @BeforeEach
    void setUp (){
        s = new EmbeddingService();
        // Create 2 search doc text
        String paperText1 = 
            """
                title: machine learning in agriculture
                abstract: this is a paper about how can we apply machine learning methods in agriculture
                description: quantitative methods for data aggregation and harvest prediction models
            """;
        String paperText2 =  
            """
                title: spanish football
                abstract: study of spanish first division and the ranking of its teams according to their income and debt levels
                description: in this study we look into how being more or less leveraged can cause teams to be better competitors or not
            """;
        //create vect list
        vectorsList = new ArrayList<>();
        
        //create vect docs to send to milvus
        vectorsDocs = new ArrayList<>();
        mr = new MilvusRepository(true);
        mr.initializeCollection();
        //mr.clearCollection();
        try{
            // Create 2 Embeddings for them 
            List<Double> vectorP1 = s.embed(paperText1, false);
            List<Double> vectorP2 = s.embed(paperText2, false);
            // add vectors to a list of vectors
            vectorsList.add(0,vectorP1);
            vectorsList.add(1,vectorP2);

            List<String> contributors = new ArrayList<>();
            contributors.add("miguel");    
            contributors.add("peter");    
            
            for (int i = 0; i < 2; i++) {
                VectorDocument vd = new VectorDocument("paper", Integer.toString(i),contributors);
                vd.setEmbedding(vectorsList.get(i));
                vectorsDocs.add(i,vd);
            }
            
            // save vector docs to milvus
            mr.saveBatch(vectorsDocs);
        }
        catch (Exception e) {
            System.out.println(e);
        }
    }
    

    
    @Test
    void savingDocIsSuccessfulAndSearchWorksCorrectly (){
        try {
            // Create query for one of them
            String query = "artificial intelligence";
            // create embedding for query
            List<Double> queryEmbeddings = s.embed(query, true);
            // search milvus for query, k = 1
            List<VectorSearchResult> results = mr.searchKNN(queryEmbeddings, 1);
            
            String resultId = results.get(0).documentId();
            int expectedRes = 0;

            System.out.printf("\nThe expected doc id was %s and the actual doc was %s", expectedRes, resultId);
            // check that the result includes only the relevant doc
            assertEquals(Integer.toString(expectedRes),resultId );
        } catch (Exception e) {
            System.out.println(e);
        }
    }

    @Test
    void testingSecondQueryForSemanticSearch (){
        try {
            // Create query for one of them
            String query = "soccer";
            // create embedding for query
            List<Double> queryEmbeddings = s.embed(query, true);
            // search milvus for query, k = 1
            List<VectorSearchResult> results = mr.searchKNN(queryEmbeddings, 1);
            
            String resultId = results.get(0).documentId();
            int expectedRes = 1;

            System.out.printf("\nThe expected doc id was %s and the actual doc was %s", expectedRes, resultId);
            // check that the result includes only the relevant doc
            assertEquals(Integer.toString(expectedRes),resultId );
        } catch (Exception e) {
            System.out.println(e);
        }
    }
    
}
