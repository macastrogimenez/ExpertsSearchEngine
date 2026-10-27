package com.github.macastrogimenez.embeddingProcessor;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

public class EmbeddingServiceTest {
    private ArrayList<String> l = new ArrayList<>();
    private EmbeddingService s = new EmbeddingService();
 
    
    @BeforeEach
    void setUp() {
        // creating an array with three elements which will be vectorised
        l = new ArrayList<>();
        l.add("cheese");
        l.add("what");
        l.add("tired");
    }

    @Test 
    void embeddingsHasLength3 () throws Exception{
        List<List<Double>> r = s.batchEmbed(l);
        // List<Double> tiredVector = r.get(2);
        // for (Double double1 : tiredVector) {
        //     System.out.printf("%f, ",double1);
        // }
        assertTrue(r.size() == 3);
        
    }
}
