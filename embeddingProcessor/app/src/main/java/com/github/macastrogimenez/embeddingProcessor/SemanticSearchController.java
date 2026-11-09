package com.github.macastrogimenez.embeddingProcessor;

import org.springframework.web.bind.annotation.RestController;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.server.ResponseStatusException;

@RestController 
public class SemanticSearchController {
    
    private final EmbeddingService embeddingService;
    private final MilvusRepository milvusRepository;

    public SemanticSearchController(
        EmbeddingService embeddingService,
        MilvusRepository milvusRepository
    ) {
        this.embeddingService = embeddingService;
        this.milvusRepository = milvusRepository;
    }

    @GetMapping("/semanticSearch")
    public List<VectorSearchResult> semanticSearch(
        @RequestParam("query") String query,
        @RequestParam ("K") int k) throws Exception {
            if (query.isBlank()){
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Query cannot be blank");
            }
            if (k<1 || k>100){
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"K needs to be between 1 and 100");
            }
            else try {
                List<Double> embedding = embeddingService.embed(query, false);
                List<VectorSearchResult> searchResults = milvusRepository.searchKNN(embedding, k);
                return searchResults;
            } catch (Exception e) {
                throw new Exception(e);
            }
    }
    
}
